"""
BOT App - Celery Tasks for Courier Notifications

Asynchronous task processing for:
- Sending WhatsApp notifications
- Daily summaries
- Broadcast to nearby couriers
- Reminder notifications
"""

import logging
from celery import shared_task
from decimal import Decimal

logger = logging.getLogger(__name__)


# ===========================================
# NOTIFICATION TASKS
# ===========================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def send_new_delivery_notification(
    self,
    courier_phone: str,
    delivery_id: str,
    pickup_address: str,
    dropoff_address: str,
    distance_km: float,
    earning: str
):
    """
    Send notification about new available delivery (async).
    
    Args:
        courier_phone: Courier's phone number
        delivery_id: Delivery UUID string
        pickup_address: Pickup location
        dropoff_address: Dropoff location
        distance_km: Total distance
        earning: Courier earning as string (to avoid Decimal serialization issues)
    """
    from bot.courier_notifications import CourierNotificationService
    
    try:
        result = CourierNotificationService.notify_new_delivery_available(
            courier_phone=courier_phone,
            delivery_id=delivery_id,
            pickup_address=pickup_address,
            dropoff_address=dropoff_address,
            distance_km=distance_km,
            earning=Decimal(earning)
        )
        
        if not result:
            logger.warning(f"[TASK] Failed to send notification to {courier_phone[:8]}...")
            
        return result
        
    except Exception as e:
        logger.error(f"[TASK] Error sending notification: {e}")
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30
)
def send_delivery_assigned_notification(
    self,
    courier_phone: str,
    delivery_id: str,
    pickup_address: str,
    dropoff_address: str,
    sender_phone: str
):
    """
    Send notification when delivery is assigned to courier (async).
    """
    from bot.courier_notifications import CourierNotificationService
    
    try:
        result = CourierNotificationService.notify_delivery_assigned(
            courier_phone=courier_phone,
            delivery_id=delivery_id,
            pickup_address=pickup_address,
            dropoff_address=dropoff_address,
            sender_phone=sender_phone
        )
        return result
        
    except Exception as e:
        logger.error(f"[TASK] Error sending assigned notification: {e}")
        raise self.retry(exc=e)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30
)
def send_urgent_delivery_notification(
    self,
    courier_phone: str,
    delivery_id: str,
    distance_meters: int,
    distance_km: float,
    earning: str
):
    """
    Send urgent notification about nearby delivery (async).
    """
    from bot.courier_notifications import CourierNotificationService
    
    try:
        result = CourierNotificationService.notify_urgent_delivery(
            courier_phone=courier_phone,
            delivery_id=delivery_id,
            distance_meters=distance_meters,
            distance_km=distance_km,
            earning=Decimal(earning)
        )
        return result
        
    except Exception as e:
        logger.error(f"[TASK] Error sending urgent notification: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True)
def send_delivery_reminder(
    self,
    courier_phone: str,
    delivery_id: str,
    minutes_waiting: int
):
    """
    Send reminder about pending pickup (async).
    """
    from bot.courier_notifications import CourierNotificationService
    
    try:
        return CourierNotificationService.notify_delivery_reminder(
            courier_phone=courier_phone,
            delivery_id=delivery_id,
            minutes_waiting=minutes_waiting
        )
    except Exception as e:
        logger.error(f"[TASK] Error sending reminder: {e}")
        return False


@shared_task(bind=True)
def send_low_balance_warning(
    self,
    courier_phone: str,
    balance: str,
    ceiling: str
):
    """
    Send low balance warning to courier (async).
    """
    from bot.courier_notifications import CourierNotificationService
    
    try:
        return CourierNotificationService.notify_low_balance(
            courier_phone=courier_phone,
            balance=Decimal(balance),
            ceiling=Decimal(ceiling)
        )
    except Exception as e:
        logger.error(f"[TASK] Error sending low balance warning: {e}")
        return False


# ===========================================
# BROADCAST TASKS
# ===========================================

@shared_task
def broadcast_new_delivery(delivery_id: str, radius_km: float = 5.0, max_couriers: int = 5):
    """
    Broadcast new delivery to nearby couriers.
    
    Args:
        delivery_id: UUID of the delivery
        radius_km: Search radius for couriers
        max_couriers: Maximum couriers to notify
    """
    from logistics.models import Delivery
    from bot.courier_notifications import CourierBroadcastService
    
    try:
        delivery = Delivery.objects.get(id=delivery_id)
        
        notified = CourierBroadcastService.broadcast_new_delivery(
            delivery=delivery,
            radius_km=radius_km,
            max_couriers=max_couriers
        )
        
        logger.info(f"[TASK] Broadcast delivery {delivery_id[:8]} to {notified} couriers")
        return notified
        
    except Delivery.DoesNotExist:
        logger.error(f"[TASK] Delivery {delivery_id} not found for broadcast")
        return 0
    except Exception as e:
        logger.error(f"[TASK] Error broadcasting delivery: {e}")
        return 0


# ===========================================
# SCHEDULED TASKS (for Celery Beat)
# ===========================================

@shared_task
def send_all_daily_summaries():
    """
    Send daily summary to all couriers who worked today.
    
    Schedule: Every day at 21:00 local time.
    """
    from bot.courier_notifications import CourierBroadcastService
    
    try:
        sent = CourierBroadcastService.send_daily_summaries()
        logger.info(f"[TASK] Sent {sent} daily summaries")
        return sent
        
    except Exception as e:
        logger.error(f"[TASK] Error sending daily summaries: {e}")
        return 0


@shared_task
def check_pending_reminders():
    """
    Check for deliveries waiting too long and send reminders.
    
    Schedule: Every 15 minutes.
    """
    from logistics.models import Delivery, DeliveryStatus
    from django.utils import timezone
    from datetime import timedelta
    
    # Find deliveries assigned > 20 minutes ago but not picked up
    threshold = timezone.now() - timedelta(minutes=20)
    
    pending = Delivery.objects.filter(
        status=DeliveryStatus.ASSIGNED,
        assigned_at__lte=threshold,
        picked_up_at__isnull=True,
        courier__isnull=False
    ).select_related('courier')
    
    reminders_sent = 0
    for delivery in pending:
        if delivery.courier and delivery.courier.phone_number:
            minutes = int((timezone.now() - delivery.assigned_at).total_seconds() / 60)
            
            send_delivery_reminder.delay(
                courier_phone=delivery.courier.phone_number,
                delivery_id=str(delivery.id),
                minutes_waiting=minutes
            )
            reminders_sent += 1
    
    logger.info(f"[TASK] Sent {reminders_sent} pending reminders")
    return reminders_sent


@shared_task
def check_debt_warnings():
    """
    Check for couriers with high debt and send warnings.
    
    Schedule: Every hour.
    """
    from core.models import User, UserRole
    from django.db.models import F
    
    # Find couriers at > 80% of debt ceiling
    high_debt_couriers = User.objects.filter(
        role=UserRole.COURIER,
        is_verified=True,
        wallet_balance__lt=0
    ).annotate(
        debt_ratio=F('wallet_balance') / F('debt_ceiling') * -1
    ).filter(
        debt_ratio__gte=0.8
    )
    
    warnings_sent = 0
    for courier in high_debt_couriers:
        send_low_balance_warning.delay(
            courier_phone=courier.phone_number,
            balance=str(courier.wallet_balance),
            ceiling=str(courier.debt_ceiling)
        )
        warnings_sent += 1
    
    logger.info(f"[TASK] Sent {warnings_sent} debt warnings")
    return warnings_sent
