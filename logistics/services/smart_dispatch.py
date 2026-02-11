"""
LOGISTICS App - Smart Dispatch Service for DELIVR-CM

Intelligent courier dispatch with multi-factor scoring algorithm.
Uses PostGIS for efficient geo-queries and Redis for caching.

SCORING FACTORS (all configurable by admin via DispatchConfiguration):
  1. Distance      — Proximity to pickup point
  2. Rating        — Average customer rating (/5)
  3. History       — Delivery success rate (30 days)
  4. Availability  — Time since last delivery (avoid overloading)
  5. Financial     — Wallet health (debt ratio)
  6. Response time — Average acceptance speed
  7. Level         — Courier gamification level (Bronze→Platinum)
  8. Acceptance    — Order acceptance rate
  
BONUSES:
  + Streak bonus   — Active consecutive success streak
  - Probation      — Penalty for couriers still in probation

All weights and thresholds are stored in the database and can be
adjusted by admins in real-time via Django Admin.
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
from django.db.models import F, Count, Q, Avg
from django.utils import timezone
from django.core.cache import cache

from logistics.models import Delivery, DeliveryStatus, DispatchConfiguration
from core.models import User, UserRole

logger = logging.getLogger(__name__)


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
    bonuses: Dict[str, float]
    
    @property
    def total_with_bonuses(self) -> float:
        """Final score including bonuses and penalties."""
        return self.score + sum(self.bonuses.values())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'courier_id': str(self.courier.id),
            'phone': self.courier.phone_number,
            'name': self.courier.full_name,
            'level': self.courier.courier_level,
            'rating': float(self.courier.average_rating),
            'distance_km': round(self.distance_km, 2),
            'score': round(self.score, 1),
            'total_score': round(self.total_with_bonuses, 1),
            'breakdown': self.score_breakdown,
            'bonuses': self.bonuses,
        }


# ============================================
# SMART DISPATCH SERVICE
# ============================================

class SmartDispatchService:
    """
    Intelligent dispatch service with admin-configurable multi-factor scoring.
    
    The scoring algorithm considers 8 weighted factors + bonuses/penalties,
    all configurable by admins via Django Admin (DispatchConfiguration model).
    
    Usage:
        service = SmartDispatchService()
        scored_couriers = service.find_optimal_couriers(pickup_point)
    """
    
    def __init__(self, config: DispatchConfiguration = None):
        self.config = config or DispatchConfiguration.get_config()
    
    def find_optimal_couriers(
        self,
        pickup_point: Point,
        max_results: int = None
    ) -> List[CourierScore]:
        """
        Find and score couriers for a delivery.
        
        Uses an expanding radius search: starts small and expands
        if not enough couriers are found.
        
        Args:
            pickup_point: PostGIS Point of the pickup location
            max_results: Maximum number of scored couriers to return
                         (defaults to config.max_couriers_to_notify)
        
        Returns:
            List of CourierScore objects, sorted by total score (highest first)
        """
        if max_results is None:
            max_results = self.config.max_couriers_to_notify
        
        current_radius = self.config.initial_radius_km
        candidates = []
        
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
            if score.total_with_bonuses >= self.config.min_score_threshold:
                scored_couriers.append(score)
        
        # Sort by total score (highest first)
        scored_couriers.sort(key=lambda x: x.total_with_bonuses, reverse=True)
        
        logger.info(
            f"[SMART_DISPATCH] Found {len(scored_couriers)} qualified couriers "
            f"(radius: {current_radius}km, threshold: {self.config.min_score_threshold})"
        )
        
        return scored_couriers[:max_results]
    
    def _query_nearby_couriers(
        self,
        pickup_point: Point,
        radius_km: float
    ) -> List[Tuple[User, float]]:
        """
        Query couriers within radius using PostGIS.
        
        Filters:
        - Role = COURIER
        - Active account
        - Online (is_online = True)
        - Has GPS location
        - Not blocked by debt
        - Onboarding approved or in probation
        
        Returns:
            List of (courier, distance_km) tuples
        """
        couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_active=True,
            is_online=True,
            last_location__isnull=False,
            onboarding_status__in=['APPROVED', 'PROBATION'],
        ).annotate(
            raw_distance=Distance('last_location', pickup_point)
        ).filter(
            raw_distance__lte=D(km=radius_km)
        ).order_by('raw_distance')
        
        result = []
        for courier in couriers:
            # Check if not blocked by debt
            if courier.wallet_balance <= -courier.debt_ceiling:
                logger.debug(
                    f"[SMART_DISPATCH] Skipping {courier.phone_number} — "
                    f"debt blocked (wallet: {courier.wallet_balance})"
                )
                continue
            
            # Convert distance to km
            distance_km = courier.raw_distance.km if courier.raw_distance else 999
            result.append((courier, distance_km))
        
        return result
    
    def _calculate_courier_score(
        self,
        courier: User,
        distance_km: float
    ) -> CourierScore:
        """
        Calculate composite score for a courier using 8 weighted factors.
        
        Each factor produces a sub-score from 0 to 100.
        The total is the weighted sum of all sub-scores + bonuses - penalties.
        """
        config = self.config
        breakdown = {}
        bonuses = {}
        
        # ====== 1. DISTANCE SCORE (0-100) ======
        # Closer is better: 100 within perfect range, linear decay to 0
        if distance_km <= config.distance_perfect_km:
            distance_score = 100
        elif distance_km >= config.distance_zero_km:
            distance_score = 0
        else:
            # Linear interpolation between perfect and zero
            range_km = config.distance_zero_km - config.distance_perfect_km
            distance_score = max(0, 100 * (1 - (distance_km - config.distance_perfect_km) / range_km))
        breakdown['distance'] = round(distance_score, 1)
        
        # ====== 2. RATING SCORE (0-100) ======
        # Based on average_rating (/5) from the User model
        rating = float(courier.average_rating)
        rating_count = courier.total_ratings_count
        
        if rating_count < config.min_ratings_for_full_score:
            # Not enough ratings — use a blended neutral score
            # Blend between neutral (60) and actual rating as more reviews come in
            confidence = rating_count / config.min_ratings_for_full_score
            base_rating_score = (rating / 5) * 100 if rating > 0 else 60
            rating_score = (base_rating_score * confidence) + (60 * (1 - confidence))
        else:
            # Full confidence in the rating
            rating_score = (rating / 5) * 100
        breakdown['rating'] = round(rating_score, 1)
        
        # ====== 3. HISTORY SCORE (0-100) ======
        # Based on delivery success rate (last 30 days)
        history = self._get_courier_history(courier)
        if history['total_deliveries'] == 0:
            history_score = 50  # Neutral for new couriers
        else:
            success_rate = history['completed'] / history['total_deliveries']
            history_score = success_rate * 100
        breakdown['history'] = round(history_score, 1)
        
        # ====== 4. AVAILABILITY SCORE (0-100) ======
        # Time since last delivery completion
        # High score = available and not overworked
        # Low score = just finished a delivery (might be busy)
        last_completed = self._get_last_completion_time(courier)
        if last_completed is None:
            availability_score = 70  # Good default for idle couriers
        else:
            minutes_since = (timezone.now() - last_completed).total_seconds() / 60
            if minutes_since > 120:
                availability_score = 100  # Very available
            elif minutes_since > 30:
                availability_score = 70 + (minutes_since - 30) * 0.33
            elif minutes_since > 10:
                availability_score = 30 + (minutes_since - 10) * 2
            else:
                availability_score = 20  # Just finished, likely still busy
        breakdown['availability'] = round(min(100, availability_score), 1)
        
        # ====== 5. FINANCIAL HEALTH SCORE (0-100) ======
        # Based on wallet balance relative to debt ceiling
        wallet = float(courier.wallet_balance)
        ceiling = float(courier.debt_ceiling)
        
        if wallet >= 0:
            financial_score = 100  # No debt = perfect
        else:
            # Negative wallet: score decreases as debt ratio increases
            debt_ratio = abs(wallet) / ceiling if ceiling > 0 else 1
            financial_score = max(0, 100 - (debt_ratio * 100))
        breakdown['financial'] = round(financial_score, 1)
        
        # ====== 6. RESPONSE TIME SCORE (0-100) ======
        # Average time to accept orders
        avg_response = float(courier.average_response_seconds)
        if avg_response <= 0:
            response_score = 70  # No data, neutral
        elif avg_response <= 30:
            response_score = 100  # Lightning fast
        elif avg_response <= 60:
            response_score = 80 + (60 - avg_response) * 0.67  # Good
        elif avg_response <= 120:
            response_score = 50 + (120 - avg_response) * 0.5  # OK
        elif avg_response <= 300:
            response_score = 20 + (300 - avg_response) * 0.17  # Slow
        else:
            response_score = 10  # Very slow
        breakdown['response'] = round(response_score, 1)
        
        # ====== 7. LEVEL SCORE (0-100) ======
        # Based on courier gamification level
        level_score = config.get_level_score(courier.courier_level)
        breakdown['level'] = round(level_score, 1)
        
        # ====== 8. ACCEPTANCE RATE SCORE (0-100) ======
        # Based on acceptance_rate field
        acceptance = float(courier.acceptance_rate)
        if acceptance <= 0:
            acceptance_score = 50  # No data
        else:
            # Direct mapping: 100% acceptance = 100 score
            acceptance_score = acceptance
        breakdown['acceptance'] = round(min(100, acceptance_score), 1)
        
        # ====== WEIGHTED TOTAL ======
        total_score = (
            breakdown['distance'] * config.weight_distance +
            breakdown['rating'] * config.weight_rating +
            breakdown['history'] * config.weight_history +
            breakdown['availability'] * config.weight_availability +
            breakdown['financial'] * config.weight_financial +
            breakdown['response'] * config.weight_response +
            breakdown['level'] * config.weight_level +
            breakdown['acceptance'] * config.weight_acceptance
        )
        
        # ====== BONUSES & PENALTIES ======
        
        # Streak bonus
        if config.streak_bonus_enabled and courier.consecutive_success_streak > 0:
            streak_bonus = min(
                courier.consecutive_success_streak * config.streak_bonus_per_delivery,
                config.streak_bonus_max
            )
            bonuses['streak'] = round(streak_bonus, 1)
        
        # Probation penalty
        if courier.onboarding_status == 'PROBATION':
            bonuses['probation'] = -config.probation_penalty
        
        return CourierScore(
            courier=courier,
            distance_km=distance_km,
            score=round(total_score, 1),
            score_breakdown=breakdown,
            bonuses=bonuses
        )
    
    def _get_courier_history(self, courier: User) -> Dict[str, int]:
        """Get delivery history stats for a courier (cached)."""
        cache_key = f"courier_history_{courier.id}"
        cached = cache.get(cache_key)
        
        if cached:
            return cached
        
        # Query delivery history for last 30 days
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
        cache_key = f"courier_last_completed_{courier.id}"
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached if cached != 'NONE' else None
        
        try:
            last_delivery = Delivery.objects.filter(
                courier=courier,
                status=DeliveryStatus.COMPLETED,
                completed_at__isnull=False
            ).order_by('-completed_at').values_list('completed_at', flat=True).first()
            
            cache.set(
                cache_key,
                last_delivery if last_delivery else 'NONE',
                120  # Cache 2 min
            )
            return last_delivery
        except Exception:
            return None


# ============================================
# DISPATCH FUNCTIONS
# ============================================

def smart_dispatch_order(order_id: str, auto_assign: bool = False) -> Dict[str, Any]:
    """
    Dispatch an order using the smart scoring algorithm.
    
    Reads scoring weights and thresholds from the database
    (DispatchConfiguration), so admins can adjust behavior
    without code changes.
    
    Args:
        order_id: UUID of the delivery order
        auto_assign: If True, automatically assign to best courier
    
    Returns:
        Dict with dispatch results including scored courier list
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
    
    # Load config from database (cached)
    config = DispatchConfiguration.get_config()
    
    # Find and score couriers
    service = SmartDispatchService(config)
    scored_couriers = service.find_optimal_couriers(delivery.pickup_geo)
    
    if not scored_couriers:
        logger.warning(f"[SMART_DISPATCH] No qualified couriers for {order_id}")
        return {
            'success': False,
            'message': "Aucun coursier qualifié disponible",
            'couriers': [],
            'config': {
                'radius_searched': config.max_radius_km,
                'min_threshold': config.min_score_threshold,
            }
        }
    
    # Auto-assign if requested and top courier scores high enough
    if auto_assign and scored_couriers[0].total_with_bonuses >= config.auto_assign_threshold:
        best_courier = scored_couriers[0]
        
        try:
            from logistics.services.dispatch import accept_order
            accept_order(str(order_id), best_courier.courier)
            
            logger.info(
                f"[SMART_DISPATCH] Auto-assigned {str(order_id)[:8]} to "
                f"{best_courier.courier.phone_number} "
                f"(score: {best_courier.total_with_bonuses:.1f}, "
                f"level: {best_courier.courier.courier_level})"
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
    notified = _notify_scored_couriers(scored_couriers, delivery, config)
    
    return {
        'success': True,
        'message': f"Notifié {notified} coursiers",
        'auto_assigned': False,
        'couriers': [c.to_dict() for c in scored_couriers]
    }


def _notify_scored_couriers(
    scored_couriers: List[CourierScore],
    delivery: Delivery,
    config: DispatchConfiguration
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
    max_notify = config.max_couriers_to_notify
    
    for score in scored_couriers[:max_notify]:
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
                f"(score: {score.total_with_bonuses:.1f}, "
                f"level: {courier.courier_level}, "
                f"rating: {courier.average_rating}⭐)"
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
    
    # Also send directly to scored couriers with their personalized score
    for score in scored_couriers:
        personalized_event = {
            **event,
            'your_score': round(score.total_with_bonuses, 1),
            'distance_to_pickup': round(score.distance_km, 2),
        }
        async_to_sync(channel_layer.group_send)(
            f'courier_{score.courier.id}',
            personalized_event
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
    cache.delete(f"courier_last_completed_{courier_id}")


def get_dispatch_config_summary() -> Dict[str, Any]:
    """
    Get a human-readable summary of the current dispatch configuration.
    Useful for debugging or displaying in the admin panel.
    """
    config = DispatchConfiguration.get_config()
    
    weights = {
        'Distance': f"{config.weight_distance * 100:.0f}%",
        'Note moyenne': f"{config.weight_rating * 100:.0f}%",
        'Historique succès': f"{config.weight_history * 100:.0f}%",
        'Disponibilité': f"{config.weight_availability * 100:.0f}%",
        'Santé financière': f"{config.weight_financial * 100:.0f}%",
        'Temps de réponse': f"{config.weight_response * 100:.0f}%",
        'Niveau coursier': f"{config.weight_level * 100:.0f}%",
        "Taux d'acceptation": f"{config.weight_acceptance * 100:.0f}%",
    }
    
    return {
        'weights': weights,
        'total_weight': f"{config.total_weight * 100:.0f}%",
        'weights_valid': config.weights_valid,
        'search_radius': f"{config.initial_radius_km} → {config.max_radius_km} km",
        'score_threshold': config.min_score_threshold,
        'auto_assign_threshold': config.auto_assign_threshold,
        'streak_bonus': config.streak_bonus_enabled,
        'probation_penalty': config.probation_penalty,
        'last_updated': config.updated_at,
    }
