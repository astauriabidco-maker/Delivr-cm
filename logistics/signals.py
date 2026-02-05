"""
LOGISTICS App - Django Signals

Auto-dispatch orders and broadcast real-time events.
"""

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from logistics.models import Delivery, DeliveryStatus

logger = logging.getLogger(__name__)


# Store previous status for change detection
_previous_status = {}


@receiver(pre_save, sender=Delivery)
def capture_previous_status(sender, instance, **kwargs):
    """Capture the previous status before save for change detection."""
    if instance.pk:
        try:
            old_instance = Delivery.objects.get(pk=instance.pk)
            _previous_status[instance.pk] = old_instance.status
        except Delivery.DoesNotExist:
            pass


@receiver(post_save, sender=Delivery)
def on_delivery_saved(sender, instance, created, **kwargs):
    """
    Handle delivery creation and updates.
    
    On creation:
    - Dispatch to nearby couriers using smart algorithm
    - Broadcast new delivery event
    
    On status change:
    - Broadcast status update to tracking clients
    - Trigger financial transactions on completion
    """
    if created:
        _handle_new_delivery(instance)
    else:
        _handle_delivery_update(instance)


def _handle_new_delivery(delivery: Delivery):
    """Handle a newly created delivery."""
    if delivery.status != DeliveryStatus.PENDING:
        return
    
    logger.info(f"[SIGNAL] New delivery created: {delivery.id}")
    
    # Broadcast new delivery event
    try:
        from logistics.events import broadcast_new_delivery
        
        delivery_data = {
            'id': str(delivery.id),
            'pickup_address': delivery.pickup_address or '',
            'dropoff_address': delivery.dropoff_address or '',
            'total_price': str(delivery.total_price),
            'courier_earning': str(delivery.courier_earning),
            'distance_km': delivery.distance_km,
        }
        
        broadcast_new_delivery(delivery_data)
    except Exception as e:
        logger.warning(f"[SIGNAL] Broadcast new delivery failed: {e}")
    
    # Smart dispatch to couriers
    try:
        from logistics.services.smart_dispatch import smart_dispatch_order
        
        # Use smart dispatch with scoring algorithm
        result = smart_dispatch_order(str(delivery.id), auto_assign=False)
        
        logger.info(
            f"[SIGNAL] Smart dispatch for {str(delivery.id)[:8]}: "
            f"{result.get('message', 'unknown')}"
        )
        
        if result.get('couriers'):
            top_courier = result['couriers'][0]
            logger.info(
                f"[SIGNAL] Top courier: {top_courier['name']} "
                f"(score: {top_courier['score']})"
            )
    
    except ImportError:
        # Fallback to basic dispatch if smart dispatch unavailable
        logger.warning("[SIGNAL] Smart dispatch unavailable, using basic dispatch")
        from logistics.services.dispatch import dispatch_order
        
        try:
            notified_count = dispatch_order(str(delivery.id))
            logger.info(
                f"[SIGNAL] Basic dispatch for {str(delivery.id)[:8]}: "
                f"{notified_count} couriers notified"
            )
        except Exception as e:
            logger.error(f"[SIGNAL] Basic dispatch failed: {e}")
    
    except Exception as e:
        logger.error(f"[SIGNAL] Smart dispatch failed for {delivery.id}: {e}")


def _handle_delivery_update(delivery: Delivery):
    """Handle delivery status changes."""
    previous = _previous_status.pop(delivery.pk, None)
    
    if previous is None or previous == delivery.status:
        return  # No status change
    
    logger.info(
        f"[SIGNAL] Delivery {str(delivery.id)[:8]} status: "
        f"{previous} -> {delivery.status}"
    )
    
    # Broadcast status change
    try:
        from logistics.events import broadcast_delivery_status
        
        status_messages = {
            DeliveryStatus.ASSIGNED: "Un coursier a accepté votre commande",
            DeliveryStatus.PICKED_UP: "Le coursier a récupéré votre colis",
            DeliveryStatus.IN_TRANSIT: "Votre colis est en route",
            DeliveryStatus.COMPLETED: "Livraison effectuée avec succès!",
            DeliveryStatus.CANCELLED: "La commande a été annulée",
            DeliveryStatus.FAILED: "La livraison a échoué",
        }
        
        message = status_messages.get(delivery.status, "")
        
        broadcast_delivery_status(
            str(delivery.id),
            delivery.status,
            message
        )
    except Exception as e:
        logger.warning(f"[SIGNAL] Status broadcast failed: {e}")
    
    # Handle completion - trigger financial transactions
    if delivery.status == DeliveryStatus.COMPLETED:
        _handle_delivery_completed(delivery)
    
    # Handle assignment - notify courier
    if delivery.status == DeliveryStatus.ASSIGNED and delivery.courier:
        _handle_delivery_assigned(delivery)


def _handle_delivery_completed(delivery: Delivery):
    """Process financial transactions when delivery is completed."""
    logger.info(f"[SIGNAL] Processing completion for {str(delivery.id)[:8]}")
    
    try:
        from finance.models import WalletService
        from logistics.models import PaymentMethod
        
        if delivery.payment_method == PaymentMethod.CASH_P2P:
            WalletService.process_cash_delivery(delivery)
            logger.info(f"[SIGNAL] CASH payment processed for {str(delivery.id)[:8]}")
        
        elif delivery.payment_method == PaymentMethod.PREPAID_WALLET:
            WalletService.process_prepaid_delivery(delivery)
            logger.info(f"[SIGNAL] PREPAID payment processed for {str(delivery.id)[:8]}")
    
    except Exception as e:
        logger.error(f"[SIGNAL] Financial processing failed for {delivery.id}: {e}")
    
    # Invalidate courier cache for updated stats
    if delivery.courier:
        try:
            from logistics.services.smart_dispatch import invalidate_courier_cache
            invalidate_courier_cache(str(delivery.courier.id))
        except Exception:
            pass


def _handle_delivery_assigned(delivery: Delivery):
    """Notify courier when they are assigned to a delivery."""
    try:
        from logistics.events import broadcast_order_assigned
        
        details = {
            'pickup_address': delivery.pickup_address or 'GPS fourni',
            'dropoff_address': delivery.dropoff_address or 'GPS fourni',
            'recipient_phone': delivery.recipient_phone,
            'total_price': str(delivery.total_price),
            'courier_earning': str(delivery.courier_earning),
            'otp_code': delivery.otp_code,  # For delivery confirmation
            'pickup_otp': delivery.pickup_otp,  # For pickup confirmation (courier needs to verify)
        }
        
        broadcast_order_assigned(
            str(delivery.courier.id),
            str(delivery.id),
            details
        )
    except Exception as e:
        logger.warning(f"[SIGNAL] Assignment notification failed: {e}")

