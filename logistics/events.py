"""
LOGISTICS App - Real-time Event Broadcasting

Utility functions to broadcast events via Django Channels.
Used by signals, views, and services to push real-time updates.
"""

import logging
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_channel_layer():
    """Get the Django Channels layer (lazy import)."""
    try:
        from channels.layers import get_channel_layer as _get_channel_layer
        return _get_channel_layer()
    except ImportError:
        logger.warning("[EVENTS] Django Channels not installed")
        return None


def _send_group_event(group_name: str, event: dict):
    """Send event to a channel group."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return False
    
    try:
        from asgiref.sync import async_to_sync
        async_to_sync(channel_layer.group_send)(group_name, event)
        return True
    except Exception as e:
        logger.error(f"[EVENTS] Failed to send to group {group_name}: {e}")
        return False


# ============================================
# DELIVERY EVENTS
# ============================================

def broadcast_delivery_status(
    delivery_id: str,
    new_status: str,
    message: str = ""
):
    """
    Broadcast delivery status change to all interested parties.
    
    Notifies:
    - Clients tracking the specific delivery
    - Dispatch zone monitors
    - The assigned courier (if any)
    """
    timestamp = timezone.now().isoformat()
    
    # Notify clients tracking this delivery
    _send_group_event(
        f'delivery_{delivery_id}',
        {
            'type': 'delivery_status_update',
            'status': new_status,
            'timestamp': timestamp,
            'message': message,
        }
    )
    
    # Notify dispatch zone
    _send_group_event(
        'dispatch_DOUALA',  # TODO: Get city from delivery
        {
            'type': 'delivery_status_change',
            'delivery_id': str(delivery_id),
            'new_status': new_status,
        }
    )
    
    logger.debug(
        f"[EVENTS] Broadcasted status change: {delivery_id[:8]} -> {new_status}"
    )


def broadcast_courier_location(
    courier_id: str,
    latitude: float,
    longitude: float,
    active_delivery_id: Optional[str] = None
):
    """
    Broadcast courier location update.
    
    Notifies:
    - Clients tracking the courier's active delivery
    - Dispatch zone monitors
    """
    timestamp = timezone.now().isoformat()
    
    location_event = {
        'type': 'courier_location_update',
        'courier_id': str(courier_id),
        'latitude': latitude,
        'longitude': longitude,
        'timestamp': timestamp,
    }
    
    # If courier has an active delivery, notify those tracking it
    if active_delivery_id:
        _send_group_event(f'delivery_{active_delivery_id}', location_event)
    
    # Notify dispatch zone
    _send_group_event('dispatch_DOUALA', location_event)
    
    logger.debug(
        f"[EVENTS] Broadcasted courier location: {courier_id[:8]} "
        f"({latitude:.5f}, {longitude:.5f})"
    )


def broadcast_new_delivery(delivery_data: dict, city: str = 'DOUALA'):
    """
    Broadcast new delivery available for dispatch.
    
    Notifies:
    - Dispatch zone monitors
    - All connected couriers in the city
    """
    _send_group_event(
        f'dispatch_{city.upper()}',
        {
            'type': 'new_delivery',
            'delivery': delivery_data,
        }
    )
    
    logger.info(f"[EVENTS] Broadcasted new delivery in {city}")


def broadcast_delivery_eta(
    delivery_id: str,
    eta_minutes: int,
    distance_km: float
):
    """
    Broadcast updated ETA for a delivery.
    
    Called when:
    - Courier picks up the package
    - Courier location updates significantly
    - Traffic/routing changes
    """
    _send_group_event(
        f'delivery_{delivery_id}',
        {
            'type': 'delivery_eta_update',
            'eta_minutes': eta_minutes,
            'distance_km': distance_km,
        }
    )


# ============================================
# COURIER EVENTS
# ============================================

def broadcast_order_assigned(
    courier_id: str,
    delivery_id: str,
    delivery_details: dict
):
    """
    Notify a specific courier they were assigned an order.
    """
    _send_group_event(
        f'courier_{courier_id}',
        {
            'type': 'order_assigned',
            'order_id': str(delivery_id),
            'details': delivery_details,
        }
    )
    
    logger.info(f"[EVENTS] Notified courier {courier_id[:8]} of assignment")


def broadcast_order_cancelled(
    courier_id: str,
    delivery_id: str,
    reason: str = ""
):
    """
    Notify a courier their assigned order was cancelled.
    """
    _send_group_event(
        f'courier_{courier_id}',
        {
            'type': 'order_cancelled',
            'order_id': str(delivery_id),
            'reason': reason,
        }
    )


# ============================================
# TRACKING PAGE HELPER
# ============================================

def get_tracking_url(delivery_id: str) -> str:
    """
    Generate a public tracking URL for a delivery.
    
    This URL can be shared with customers to track their package.
    """
    # In production, use your domain
    base_url = "https://delivr.cm"
    return f"{base_url}/track/{delivery_id}"
