"""
LOGISTICS App - Smart Dispatch Service for DELIVR-CM

Intelligent courier dispatch with multi-factor scoring algorithm.
Uses PostGIS for efficient geo-queries and Redis for caching.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import F, Count, Q, Avg, ExpressionWrapper, DecimalField
from django.utils import timezone
from django.core.cache import cache

from logistics.models import Delivery, DeliveryStatus
from core.models import User, UserRole

logger = logging.getLogger(__name__)


# ============================================
# SCORING CONFIGURATION
# ============================================

@dataclass
class DispatchConfig:
    """Configuration for smart dispatch algorithm."""
    
    # Search parameters
    initial_radius_km: float = 3.0      # Start with small radius
    max_radius_km: float = 10.0         # Expand up to this radius
    radius_increment_km: float = 2.0    # Step size for expansion
    max_couriers_to_score: int = 20     # Max couriers to evaluate
    
    # Scoring weights (must sum to 1.0)
    weight_distance: float = 0.35       # Proximity to pickup
    weight_history: float = 0.25        # Delivery success rate
    weight_availability: float = 0.20   # Time since last delivery
    weight_financial: float = 0.15      # Wallet health
    weight_response: float = 0.05       # Response time history
    
    # Thresholds
    min_score_threshold: float = 40.0   # Minimum score to be considered
    auto_assign_threshold: float = 80.0 # Score above which to auto-assign
    
    # Cache TTL
    courier_stats_cache_ttl: int = 300  # 5 minutes


DEFAULT_CONFIG = DispatchConfig()


# ============================================
# COURIER SCORING DATA CLASS
# ============================================

@dataclass
class CourierScore:
    """Represents a scored courier for dispatch."""
    courier: User
    distance_km: float
    score: float
    score_breakdown: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'courier_id': str(self.courier.id),
            'phone': self.courier.phone_number,
            'name': self.courier.full_name,
            'distance_km': round(self.distance_km, 2),
            'score': round(self.score, 1),
            'breakdown': self.score_breakdown,
        }


# ============================================
# SMART DISPATCH SERVICE
# ============================================

class SmartDispatchService:
    """
    Intelligent dispatch service with multi-factor courier scoring.
    
    The scoring algorithm considers:
    1. Distance: How close is the courier to the pickup point?
    2. History: What's their delivery success rate?
    3. Availability: How long since their last delivery?
    4. Financial health: Is their wallet in good standing?
    5. Response time: How quickly do they typically accept orders?
    """
    
    def __init__(self, config: DispatchConfig = None):
        self.config = config or DEFAULT_CONFIG
    
    def find_optimal_couriers(
        self,
        pickup_point: Point,
        max_results: int = 5
    ) -> List[CourierScore]:
        """
        Find and score couriers for a delivery.
        
        Uses an expanding radius search: starts small and expands
        if not enough couriers are found.
        
        Args:
            pickup_point: PostGIS Point of the pickup location
            max_results: Maximum number of scored couriers to return
        
        Returns:
            List of CourierScore objects, sorted by score (highest first)
        """
        current_radius = self.config.initial_radius_km
        scored_couriers: List[CourierScore] = []
        
        while current_radius <= self.config.max_radius_km:
            # Query couriers within current radius
            candidates = self._query_nearby_couriers(pickup_point, current_radius)
            
            if len(candidates) >= max_results:
                break
            
            # Expand radius
            current_radius += self.config.radius_increment_km
            logger.debug(f"[SMART_DISPATCH] Expanding radius to {current_radius}km")
        
        # Score all candidates
        scored_couriers = []
        for courier, distance_km in candidates[:self.config.max_couriers_to_score]:
            score = self._calculate_courier_score(courier, distance_km)
            
            # Only include couriers above minimum threshold
            if score.score >= self.config.min_score_threshold:
                scored_couriers.append(score)
        
        # Sort by score (highest first)
        scored_couriers.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(
            f"[SMART_DISPATCH] Found {len(scored_couriers)} qualified couriers "
            f"(radius: {current_radius}km)"
        )
        
        return scored_couriers[:max_results]
    
    def _query_nearby_couriers(
        self,
        pickup_point: Point,
        radius_km: float
    ) -> List[Tuple[User, float]]:
        """
        Query couriers within radius using PostGIS.
        
        Returns:
            List of (courier, distance_km) tuples
        """
        couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_active=True,
            last_location__isnull=False
        ).annotate(
            raw_distance=Distance('last_location', pickup_point)
        ).filter(
            raw_distance__lte=D(km=radius_km)
        ).order_by('raw_distance')
        
        result = []
        for courier in couriers:
            # Check if not blocked by debt
            if courier.wallet_balance <= -courier.debt_ceiling:
                continue
            
            # Convert distance to km (raw_distance is in meters)
            distance_km = courier.raw_distance.km if courier.raw_distance else 999
            result.append((courier, distance_km))
        
        return result
    
    def _calculate_courier_score(
        self,
        courier: User,
        distance_km: float
    ) -> CourierScore:
        """
        Calculate composite score for a courier.
        
        Score is 0-100 based on weighted factors.
        """
        breakdown = {}
        
        # ====== 1. DISTANCE SCORE (0-100) ======
        # Closer is better: 100 at 0km, 50 at 3km, 0 at 6km+
        if distance_km <= 0.5:
            distance_score = 100
        elif distance_km <= 6:
            distance_score = max(0, 100 - (distance_km * 16.67))
        else:
            distance_score = 0
        breakdown['distance'] = round(distance_score, 1)
        
        # ====== 2. HISTORY SCORE (0-100) ======
        # Based on delivery success rate
        history = self._get_courier_history(courier)
        if history['total_deliveries'] == 0:
            history_score = 50  # Neutral for new couriers
        else:
            success_rate = history['completed'] / history['total_deliveries']
            history_score = success_rate * 100
        breakdown['history'] = round(history_score, 1)
        
        # ====== 3. AVAILABILITY SCORE (0-100) ======
        # Time since last delivery completion
        # 100 if > 2 hours, 50 if 30 min, 20 if < 10 min (too recent = busy)
        last_completed = self._get_last_completion_time(courier)
        if last_completed is None:
            availability_score = 70  # Good default
        else:
            minutes_since = (timezone.now() - last_completed).total_seconds() / 60
            if minutes_since > 120:
                availability_score = 100
            elif minutes_since > 30:
                availability_score = 70 + (minutes_since - 30) * 0.33
            elif minutes_since > 10:
                availability_score = 30 + (minutes_since - 10) * 2
            else:
                availability_score = 20  # Too recent, might be busy
        breakdown['availability'] = round(availability_score, 1)
        
        # ====== 4. FINANCIAL HEALTH SCORE (0-100) ======
        # Based on wallet balance relative to debt ceiling
        wallet = float(courier.wallet_balance)
        ceiling = float(courier.debt_ceiling)
        
        if wallet >= 0:
            financial_score = 100  # No debt = perfect
        else:
            # Negative wallet: score decreases as debt increases
            debt_ratio = abs(wallet) / ceiling
            financial_score = max(0, 100 - (debt_ratio * 100))
        breakdown['financial'] = round(financial_score, 1)
        
        # ====== 5. RESPONSE TIME SCORE (0-100) ======
        # Average time to accept orders (placeholder for now)
        response_score = 75  # Default until we have data
        breakdown['response'] = round(response_score, 1)
        
        # ====== WEIGHTED TOTAL ======
        total_score = (
            breakdown['distance'] * self.config.weight_distance +
            breakdown['history'] * self.config.weight_history +
            breakdown['availability'] * self.config.weight_availability +
            breakdown['financial'] * self.config.weight_financial +
            breakdown['response'] * self.config.weight_response
        )
        
        return CourierScore(
            courier=courier,
            distance_km=distance_km,
            score=total_score,
            score_breakdown=breakdown
        )
    
    def _get_courier_history(self, courier: User) -> Dict[str, int]:
        """Get delivery history stats for a courier (cached)."""
        cache_key = f"courier_history_{courier.id}"
        cached = cache.get(cache_key)
        
        if cached:
            return cached
        
        # Query delivery history
        stats = Delivery.objects.filter(
            courier=courier,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(status=DeliveryStatus.COMPLETED)),
            cancelled=Count('id', filter=Q(status=DeliveryStatus.CANCELLED)),
            failed=Count('id', filter=Q(status=DeliveryStatus.FAILED)),
        )
        
        result = {
            'total_deliveries': stats['total'] or 0,
            'completed': stats['completed'] or 0,
            'cancelled': stats['cancelled'] or 0,
            'failed': stats['failed'] or 0,
        }
        
        cache.set(cache_key, result, self.config.courier_stats_cache_ttl)
        return result
    
    def _get_last_completion_time(self, courier: User):
        """Get timestamp of last completed delivery."""
        try:
            last_delivery = Delivery.objects.filter(
                courier=courier,
                status=DeliveryStatus.COMPLETED,
                completed_at__isnull=False
            ).order_by('-completed_at').first()
            
            return last_delivery.completed_at if last_delivery else None
        except Exception:
            return None


# ============================================
# DISPATCH FUNCTIONS
# ============================================

def smart_dispatch_order(order_id: str, auto_assign: bool = False) -> Dict[str, Any]:
    """
    Dispatch an order using the smart scoring algorithm.
    
    Args:
        order_id: UUID of the delivery order
        auto_assign: If True, automatically assign to best courier
    
    Returns:
        Dict with dispatch results
    """
    try:
        delivery = Delivery.objects.get(pk=order_id)
    except Delivery.DoesNotExist:
        logger.error(f"[SMART_DISPATCH] Order {order_id} not found")
        raise ValueError(f"Commande {order_id} introuvable")
    
    if delivery.status != DeliveryStatus.PENDING:
        return {
            'success': False,
            'message': f"Commande n'est pas en attente (status: {delivery.status})",
            'couriers': []
        }
    
    if not delivery.pickup_geo:
        raise ValueError("La commande n'a pas de point de ramassage")
    
    # Find and score couriers
    service = SmartDispatchService()
    scored_couriers = service.find_optimal_couriers(delivery.pickup_geo)
    
    if not scored_couriers:
        logger.warning(f"[SMART_DISPATCH] No qualified couriers for {order_id}")
        return {
            'success': False,
            'message': "Aucun coursier qualifié disponible",
            'couriers': []
        }
    
    # Auto-assign if requested and top courier scores high enough
    if auto_assign and scored_couriers[0].score >= DEFAULT_CONFIG.auto_assign_threshold:
        best_courier = scored_couriers[0]
        
        try:
            from logistics.services.dispatch import accept_order
            accept_order(str(order_id), best_courier.courier)
            
            logger.info(
                f"[SMART_DISPATCH] Auto-assigned {order_id[:8]} to "
                f"{best_courier.courier.phone_number} (score: {best_courier.score:.1f})"
            )
            
            return {
                'success': True,
                'message': f"Assigné automatiquement à {best_courier.courier.full_name}",
                'auto_assigned': True,
                'assigned_courier': best_courier.to_dict(),
                'couriers': [c.to_dict() for c in scored_couriers]
            }
        except ValueError as e:
            logger.warning(f"[SMART_DISPATCH] Auto-assign failed: {e}")
    
    # Notify top couriers
    notified = _notify_scored_couriers(scored_couriers, delivery)
    
    return {
        'success': True,
        'message': f"Notifié {notified} coursiers",
        'auto_assigned': False,
        'couriers': [c.to_dict() for c in scored_couriers]
    }


def _notify_scored_couriers(
    scored_couriers: List[CourierScore],
    delivery: Delivery
) -> int:
    """
    Notify scored couriers of the available delivery.
    
    Uses Celery tasks for async WhatsApp notifications.
    
    Returns:
        Number of couriers notified
    """
    from bot.tasks import (
        send_new_delivery_notification,
        send_urgent_delivery_notification
    )
    
    notified = 0
    
    for score in scored_couriers[:5]:  # Notify top 5 only
        courier = score.courier
        
        try:
            # Use urgent notification if very close (< 500m)
            if score.distance_km < 0.5:
                send_urgent_delivery_notification.delay(
                    courier_phone=courier.phone_number,
                    delivery_id=str(delivery.id),
                    distance_meters=int(score.distance_km * 1000),
                    distance_km=delivery.distance_km,
                    earning=str(delivery.courier_earning)
                )
            else:
                send_new_delivery_notification.delay(
                    courier_phone=courier.phone_number,
                    delivery_id=str(delivery.id),
                    pickup_address=delivery.pickup_address or "À déterminer",
                    dropoff_address=delivery.dropoff_address or "À déterminer",
                    distance_km=delivery.distance_km,
                    earning=str(delivery.courier_earning)
                )
            
            notified += 1
            logger.info(
                f"[SMART_DISPATCH] Queued notification for {courier.phone_number} "
                f"(score: {score.score:.1f})"
            )
        except Exception as e:
            logger.error(
                f"[SMART_DISPATCH] Failed to queue notification for {courier.phone_number}: {e}"
            )
    
    # Also broadcast via WebSocket to connected couriers
    try:
        _broadcast_to_couriers(scored_couriers, delivery)
    except Exception as e:
        logger.warning(f"[SMART_DISPATCH] WebSocket broadcast failed: {e}")
    
    return notified


def _broadcast_to_couriers(
    scored_couriers: List[CourierScore],
    delivery: Delivery
):
    """Broadcast new order to connected couriers via WebSocket."""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    
    # Broadcast to all couriers in the dispatch zone
    city = 'DOUALA'  # TODO: Determine from delivery location
    
    event = {
        'type': 'new_order_available',
        'order_id': str(delivery.id),
        'pickup_address': delivery.pickup_address or '',
        'dropoff_address': delivery.dropoff_address or '',
        'distance_km': delivery.distance_km,
        'total_price': str(delivery.total_price),
        'courier_earning': str(delivery.courier_earning),
    }
    
    async_to_sync(channel_layer.group_send)(f'dispatch_{city}', event)
    
    # Also send directly to scored couriers
    for score in scored_couriers:
        event['distance_to_pickup'] = score.distance_km
        async_to_sync(channel_layer.group_send)(
            f'courier_{score.courier.id}',
            event
        )


# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_courier_score(courier_id: str, pickup_point: Point) -> Optional[CourierScore]:
    """Get score for a specific courier at a pickup point."""
    try:
        courier = User.objects.annotate(
            raw_distance=Distance('last_location', pickup_point)
        ).get(pk=courier_id, role=UserRole.COURIER)
        
        distance_km = courier.raw_distance.km if courier.raw_distance else 999
        
        service = SmartDispatchService()
        return service._calculate_courier_score(courier, distance_km)
    
    except User.DoesNotExist:
        return None


def invalidate_courier_cache(courier_id: str):
    """Invalidate cached stats for a courier."""
    cache.delete(f"courier_history_{courier_id}")
