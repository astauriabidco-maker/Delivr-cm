"""
LOGISTICS App - Dispatch Service for DELIVR-CM

Handles courier dispatch and order assignment logic.
"""

import logging
from typing import List, Optional
from decimal import Decimal
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db import transaction
from django.utils import timezone

from logistics.models import Delivery, DeliveryStatus
from core.models import User, UserRole

logger = logging.getLogger(__name__)


# ============================================
# DISPATCH CONFIGURATION
# ============================================

DISPATCH_RADIUS_KM = 5.0  # Search radius for nearby couriers
MAX_COURIERS_TO_NOTIFY = 10  # Maximum number of couriers to notify


def find_nearby_couriers(
    pickup_point: Point,
    radius_km: float = DISPATCH_RADIUS_KM,
    max_results: int = MAX_COURIERS_TO_NOTIFY
) -> List[User]:
    """
    Find available couriers within a radius of the pickup point.
    
    Filters:
    - Role = COURIER
    - is_active = True
    - has a location (last_location is not None)
    - wallet_balance > -debt_ceiling (not blocked)
    - within radius_km of pickup_point
    
    Args:
        pickup_point: PostGIS Point of the pickup location
        radius_km: Search radius in kilometers
        max_results: Maximum number of couriers to return
    
    Returns:
        List of User instances (couriers), sorted by distance
    """
    couriers = User.objects.filter(
        role=UserRole.COURIER,
        is_active=True,
        last_location__isnull=False
    ).annotate(
        distance=Distance('last_location', pickup_point)
    ).filter(
        distance__lte=D(km=radius_km)
    ).order_by('distance')[:max_results]
    
    # Additional filter: check if not blocked (wallet > -debt_ceiling)
    available_couriers = []
    for courier in couriers:
        if courier.wallet_balance > -courier.debt_ceiling:
            available_couriers.append(courier)
            logger.debug(
                f"[DISPATCH] Courier {courier.phone_number} available | "
                f"Distance: {courier.distance.km:.2f}km | Balance: {courier.wallet_balance}"
            )
        else:
            logger.debug(
                f"[DISPATCH] Courier {courier.phone_number} BLOCKED | "
                f"Balance: {courier.wallet_balance} < -{courier.debt_ceiling}"
            )
    
    return available_couriers


def dispatch_order(order_id: str) -> int:
    """
    Dispatch a delivery order to nearby couriers.
    
    This function finds couriers near the pickup point and sends
    notifications to them. In production, this would send WhatsApp
    messages via the Meta Business API.
    
    Args:
        order_id: UUID of the delivery order
    
    Returns:
        Number of couriers notified
    
    Raises:
        ValueError: If order not found or not in PENDING status
    """
    try:
        delivery = Delivery.objects.get(pk=order_id)
    except Delivery.DoesNotExist:
        logger.error(f"[DISPATCH] Order {order_id} not found")
        raise ValueError(f"Commande {order_id} introuvable")
    
    if delivery.status != DeliveryStatus.PENDING:
        logger.warning(
            f"[DISPATCH] Order {order_id} is not PENDING (status: {delivery.status})"
        )
        return 0
    
    if not delivery.pickup_geo:
        logger.error(f"[DISPATCH] Order {order_id} has no pickup location")
        raise ValueError("La commande n'a pas de point de ramassage")
    
    # Find nearby couriers
    couriers = find_nearby_couriers(delivery.pickup_geo)
    
    if not couriers:
        logger.warning(
            f"[DISPATCH] No couriers available near pickup for order {order_id}"
        )
        print(f"\n⚠️  Aucun coursier disponible à proximité pour la commande #{str(order_id)[:8]}")
        return 0
    
    # Notify each courier (simulated)
    notified_count = 0
    for courier in couriers:
        notify_courier_of_order(courier, delivery)
        notified_count += 1
    
    logger.info(
        f"[DISPATCH] Order {str(order_id)[:8]} dispatched to {notified_count} couriers"
    )
    
    return notified_count


def notify_courier_of_order(courier: User, delivery: Delivery) -> None:
    """
    Send notification to a courier about an available order.
    
    In production, this would use:
    - WhatsApp Business API
    - Push notifications
    - SMS
    
    For now, we simulate with a print statement.
    
    Args:
        courier: User instance (courier to notify)
        delivery: Delivery instance
    """
    # Calculate distance from courier to pickup
    if courier.last_location and delivery.pickup_geo:
        distance_m = courier.last_location.distance(delivery.pickup_geo)
        # Convert degrees to approximate km (at equator, 1 degree ≈ 111km)
        distance_km = distance_m * 111  # Rough approximation
    else:
        distance_km = 0
    
    # Simulated notification
    print(
        f"\n📲 NOTIFICATION COURSIER\n"
        f"   Téléphone: {courier.phone_number}\n"
        f"   Commande: #{str(delivery.id)[:8]}\n"
        f"   Distance pickup: ~{distance_km:.1f} km\n"
        f"   Prix course: {delivery.total_price} XAF\n"
        f"   Gain coursier: {delivery.courier_earning} XAF\n"
    )
    
    # TODO: In production, send actual WhatsApp message
    # Example:
    # whatsapp_client.send_template_message(
    #     to=courier.phone_number,
    #     template="new_delivery_available",
    #     parameters={
    #         "delivery_id": str(delivery.id)[:8],
    #         "price": str(delivery.total_price),
    #         "distance": f"{distance_km:.1f}km"
    #     }
    # )


@transaction.atomic
def accept_order(order_id: str, courier: User) -> Delivery:
    """
    Accept an order as a courier (race condition safe).
    
    Uses SELECT FOR UPDATE to prevent multiple couriers from
    accepting the same order simultaneously.
    
    Args:
        order_id: UUID of the delivery order
        courier: User instance (the accepting courier)
    
    Returns:
        Updated Delivery instance
    
    Raises:
        ValueError: If order not found, already taken, or courier issues
    """
    # Validate courier
    if courier.role != UserRole.COURIER:
        raise ValueError("Seuls les coursiers peuvent accepter des commandes")
    
    if not courier.is_active:
        raise ValueError("Votre compte est désactivé")
    
    if courier.wallet_balance < -courier.debt_ceiling:
        raise ValueError("Votre compte est bloqué pour dette excessive")
    
    # Lock the order row
    try:
        delivery = Delivery.objects.select_for_update().get(pk=order_id)
    except Delivery.DoesNotExist:
        raise ValueError(f"Commande {order_id} introuvable")
    
    # Check if still pending
    if delivery.status != DeliveryStatus.PENDING:
        raise ValueError("Cette commande a déjà été prise par un autre coursier")
    
    # Assign the courier
    delivery.courier = courier
    delivery.status = DeliveryStatus.ASSIGNED
    delivery.assigned_at = timezone.now()
    delivery.save(update_fields=['courier', 'status', 'assigned_at'])
    
    logger.info(
        f"[DISPATCH] Order {str(order_id)[:8]} accepted by courier {courier.phone_number}"
    )
    
    print(
        f"\n✅ COMMANDE ACCEPTÉE\n"
        f"   Commande: #{str(delivery.id)[:8]}\n"
        f"   Coursier: {courier.phone_number}\n"
        f"   Statut: {delivery.status}\n"
    )
    
    return delivery
