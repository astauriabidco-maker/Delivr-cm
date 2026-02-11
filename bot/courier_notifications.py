"""
BOT App - Courier Push Notifications Service

Handles WhatsApp notifications to couriers for:
- New deliveries available nearby
- Delivery assigned to courier
- Urgent deliveries (high priority)
- Status updates and reminders
"""

import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance

logger = logging.getLogger(__name__)


# ===========================================
# NOTIFICATION TEMPLATES
# ===========================================

class CourierNotificationTemplates:
    """WhatsApp message templates for courier notifications."""
    
    NEW_DELIVERY_AVAILABLE = """
✅ *Nouvelle Course Disponible!*

📍 *Ramassage:* {pickup_address}
🏁 *Livraison:* {dropoff_address}
📏 *Distance:* {distance_km} km
💰 *Gain:* {earning} XAF

⏰ Répondez *ACCEPTER {delivery_id}* pour prendre cette course!
"""

    DELIVERY_ASSIGNED = """
✅ *Course Assignée!*

📦 Course #{delivery_id}
📍 *Ramassage:* {pickup_address}
🏁 *Livraison:* {dropoff_address}
📱 *Contact expéditeur:* {sender_phone}

🔐 *Code OTP Retrait:* Sera envoyé à l'expéditeur

Rendez-vous au point de ramassage!
"""

    URGENT_DELIVERY = """
⚡ *COURSE URGENTE - Proche de vous!*

📍 À seulement {distance_m}m de votre position!
💰 *Gain:* {earning} XAF
📏 *Distance totale:* {distance_km} km

⚡ Répondez *ACCEPTER {delivery_id}* maintenant!
"""

    DELIVERY_REMINDER = """
⏰ *Rappel Course en Attente*

📦 Course #{delivery_id}
📍 En attente de ramassage depuis {minutes} minutes

Rendez-vous au point de ramassage ou répondez *ANNULER {delivery_id}*
"""

    DAILY_SUMMARY = """
📊 *Résumé de la Journée - DELIVR-CM*

📦 Courses complétées: {deliveries_count}
💰 Gains du jour: {total_earnings} XAF
📏 Distance parcourue: {total_distance} km
⭐ Note moyenne: {average_rating}

✅ _Travail accompli avec succès !_
"""

    WEEKLY_BONUS = """
🎉 *Bonus Hebdomadaire Débloqué!*

Vous avez complété {deliveries_count} courses cette semaine!
💰 Bonus: +{bonus_amount} XAF

Continuez sur cette lancée! 💪
"""

    LOW_BALANCE_WARNING = """
⚠️ *Attention - Solde Faible*

Votre solde actuel: {balance} XAF
Plafond dette: {ceiling} XAF

Pensez à rembourser pour continuer à recevoir des courses.
"""


# ===========================================
# NOTIFICATION SERVICE
# ===========================================

class CourierNotificationService:
    """
    Service for sending push notifications to couriers via WhatsApp.
    
    Uses Celery for async sending to avoid blocking the main thread.
    Supports both Twilio and Meta WhatsApp Cloud API.
    """
    
    @staticmethod
    def _get_provider():
        """Get the active WhatsApp provider."""
        provider = getattr(settings, 'ACTIVE_WHATSAPP_PROVIDER', 'META')
        if provider == 'TWILIO':
            from bot.services import TwilioService
            return TwilioService
        else:
            from bot.services import MetaWhatsAppService
            return MetaWhatsAppService
    
    @staticmethod
    def _send_message(phone_number: str, message: str) -> bool:
        """
        Send a WhatsApp message to a courier.
        
        Args:
            phone_number: Courier's phone number
            message: Message text
            
        Returns:
            True if sent successfully
        """
        try:
            provider = CourierNotificationService._get_provider()
            result = provider.send_message(phone_number, message)
            if result:
                logger.info(f"[NOTIFICATION] Sent to {phone_number[:8]}...")
                return True
            return False
        except Exception as e:
            logger.error(f"[NOTIFICATION] Failed to send to {phone_number}: {e}")
            return False
    
    @classmethod
    def notify_new_delivery_available(
        cls,
        courier_phone: str,
        delivery_id: str,
        pickup_address: str,
        dropoff_address: str,
        distance_km: float,
        earning: Decimal
    ) -> bool:
        """
        Notify a courier about a new available delivery.
        
        Args:
            courier_phone: Courier's phone number
            delivery_id: Short delivery ID (first 8 chars)
            pickup_address: Pickup location description
            dropoff_address: Dropoff location description
            distance_km: Total delivery distance
            earning: Courier's earning for this delivery
            
        Returns:
            True if notification sent successfully
        """
        message = CourierNotificationTemplates.NEW_DELIVERY_AVAILABLE.format(
            delivery_id=delivery_id[:8],
            pickup_address=pickup_address or "À déterminer",
            dropoff_address=dropoff_address or "À déterminer",
            distance_km=f"{distance_km:.1f}",
            earning=f"{earning:,.0f}".replace(",", " ")
        )
        return cls._send_message(courier_phone, message.strip())
    
    @classmethod
    def notify_delivery_assigned(
        cls,
        courier_phone: str,
        delivery_id: str,
        pickup_address: str,
        dropoff_address: str,
        sender_phone: str
    ) -> bool:
        """
        Notify a courier that a delivery has been assigned to them.
        
        Args:
            courier_phone: Courier's phone number
            delivery_id: Short delivery ID
            pickup_address: Pickup location
            dropoff_address: Dropoff location
            sender_phone: Sender's phone for contact
            
        Returns:
            True if notification sent successfully
        """
        message = CourierNotificationTemplates.DELIVERY_ASSIGNED.format(
            delivery_id=delivery_id[:8],
            pickup_address=pickup_address or "À déterminer",
            dropoff_address=dropoff_address or "À déterminer",
            sender_phone=sender_phone
        )
        return cls._send_message(courier_phone, message.strip())
    
    @classmethod
    def notify_urgent_delivery(
        cls,
        courier_phone: str,
        delivery_id: str,
        distance_meters: int,
        distance_km: float,
        earning: Decimal
    ) -> bool:
        """
        Notify a courier about an urgent nearby delivery.
        
        Args:
            courier_phone: Courier's phone number
            delivery_id: Short delivery ID
            distance_meters: Distance to pickup in meters
            distance_km: Total delivery distance
            earning: Courier's earning
            
        Returns:
            True if notification sent successfully
        """
        message = CourierNotificationTemplates.URGENT_DELIVERY.format(
            delivery_id=delivery_id[:8],
            distance_m=distance_meters,
            distance_km=f"{distance_km:.1f}",
            earning=f"{earning:,.0f}".replace(",", " ")
        )
        return cls._send_message(courier_phone, message.strip())
    
    @classmethod
    def notify_delivery_reminder(
        cls,
        courier_phone: str,
        delivery_id: str,
        minutes_waiting: int
    ) -> bool:
        """
        Send a reminder about a pending pickup.
        
        Args:
            courier_phone: Courier's phone number
            delivery_id: Delivery ID
            minutes_waiting: Minutes since assignment
            
        Returns:
            True if notification sent successfully
        """
        message = CourierNotificationTemplates.DELIVERY_REMINDER.format(
            delivery_id=delivery_id[:8],
            minutes=minutes_waiting
        )
        return cls._send_message(courier_phone, message.strip())
    
    @classmethod
    def notify_daily_summary(
        cls,
        courier_phone: str,
        deliveries_count: int,
        total_earnings: Decimal,
        total_distance: float,
        average_rating: float
    ) -> bool:
        """
        Send end-of-day summary to courier.
        
        Args:
            courier_phone: Courier's phone number
            deliveries_count: Number of deliveries completed today
            total_earnings: Total earnings today
            total_distance: Total distance traveled
            average_rating: Average rating received
            
        Returns:
            True if notification sent successfully
        """
        message = CourierNotificationTemplates.DAILY_SUMMARY.format(
            deliveries_count=deliveries_count,
            total_earnings=f"{total_earnings:,.0f}".replace(",", " "),
            total_distance=f"{total_distance:.1f}",
            average_rating=f"{average_rating:.1f}" if average_rating else "N/A"
        )
        return cls._send_message(courier_phone, message.strip())
    
    @classmethod
    def notify_weekly_bonus(
        cls,
        courier_phone: str,
        deliveries_count: int,
        bonus_amount: Decimal
    ) -> bool:
        """
        Notify courier about a weekly bonus.
        
        Args:
            courier_phone: Courier's phone number
            deliveries_count: Deliveries completed this week
            bonus_amount: Bonus amount earned
            
        Returns:
            True if notification sent successfully
        """
        message = CourierNotificationTemplates.WEEKLY_BONUS.format(
            deliveries_count=deliveries_count,
            bonus_amount=f"{bonus_amount:,.0f}".replace(",", " ")
        )
        return cls._send_message(courier_phone, message.strip())
    
    @classmethod
    def notify_low_balance(
        cls,
        courier_phone: str,
        balance: Decimal,
        ceiling: Decimal
    ) -> bool:
        """
        Warn courier about low/negative balance.
        
        Args:
            courier_phone: Courier's phone number
            balance: Current wallet balance
            ceiling: Debt ceiling
            
        Returns:
            True if notification sent successfully
        """
        message = CourierNotificationTemplates.LOW_BALANCE_WARNING.format(
            balance=f"{balance:,.0f}".replace(",", " "),
            ceiling=f"{ceiling:,.0f}".replace(",", " ")
        )
        return cls._send_message(courier_phone, message.strip())


# ===========================================
# BROADCAST SERVICE
# ===========================================

class CourierBroadcastService:
    """
    Service for broadcasting notifications to multiple couriers.
    
    Used for:
    - Notifying nearby couriers about new deliveries
    - Sending daily summaries to all active couriers
    - Alerting about system updates
    """
    
    @staticmethod
    def find_nearby_couriers(
        pickup_point: Point,
        radius_km: float = 5.0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find online couriers near a pickup point.
        
        Args:
            pickup_point: PostGIS Point of pickup location
            radius_km: Search radius in kilometers
            limit: Maximum number of couriers to return
            
        Returns:
            List of courier dicts with phone and distance
        """
        from core.models import User, UserRole
        
        # Convert km to meters for distance query
        radius_m = radius_km * 1000
        
        couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=True,
            is_online=True,
            is_active=True,
            last_location__isnull=False
        ).annotate(
            distance=Distance('last_location', pickup_point)
        ).filter(
            distance__lte=radius_m
        ).order_by('distance')[:limit]
        
        return [
            {
                'id': str(c.id),
                'phone': c.phone_number,
                'name': c.first_name or f"Coursier {c.phone_number[-4:]}",
                'distance_m': c.distance.m if c.distance else 0,
                'level': c.courier_level,
                'rating': c.average_rating,
            }
            for c in couriers
        ]
    
    @classmethod
    def broadcast_new_delivery(
        cls,
        delivery,
        radius_km: float = 5.0,
        max_couriers: int = 5
    ) -> int:
        """
        Broadcast a new delivery to nearby couriers.
        
        Args:
            delivery: Delivery model instance
            radius_km: Search radius
            max_couriers: Max couriers to notify
            
        Returns:
            Number of couriers notified
        """
        if not delivery.pickup_geo:
            logger.warning(f"[BROADCAST] Delivery {delivery.id} has no pickup_geo")
            return 0
        
        # Find nearby couriers
        nearby = cls.find_nearby_couriers(
            pickup_point=delivery.pickup_geo,
            radius_km=radius_km,
            limit=max_couriers
        )
        
        if not nearby:
            logger.info(f"[BROADCAST] No couriers nearby for delivery {delivery.id}")
            return 0
        
        # Notify each courier
        notified = 0
        for courier in nearby:
            # Check if very close (< 500m) for urgent notification
            if courier['distance_m'] < 500:
                success = CourierNotificationService.notify_urgent_delivery(
                    courier_phone=courier['phone'],
                    delivery_id=str(delivery.id),
                    distance_meters=int(courier['distance_m']),
                    distance_km=delivery.distance_km,
                    earning=delivery.courier_earning
                )
            else:
                success = CourierNotificationService.notify_new_delivery_available(
                    courier_phone=courier['phone'],
                    delivery_id=str(delivery.id),
                    pickup_address=delivery.pickup_address,
                    dropoff_address=delivery.dropoff_address,
                    distance_km=delivery.distance_km,
                    earning=delivery.courier_earning
                )
            
            if success:
                notified += 1
                logger.info(
                    f"[BROADCAST] Notified {courier['name']} for delivery {str(delivery.id)[:8]}"
                )
        
        return notified
    
    @classmethod
    def send_daily_summaries(cls) -> int:
        """
        Send daily summary to all couriers who worked today.
        
        Should be called via Celery at end of day (e.g., 21:00).
        
        Returns:
            Number of summaries sent
        """
        from core.models import User, UserRole
        from logistics.models import Delivery, DeliveryStatus
        from django.db.models import Sum, Avg, Count
        from datetime import timedelta
        
        today = timezone.now().date()
        today_start = timezone.make_aware(
            timezone.datetime.combine(today, timezone.datetime.min.time())
        )
        
        # Find couriers with completed deliveries today
        couriers_with_deliveries = Delivery.objects.filter(
            status=DeliveryStatus.COMPLETED,
            completed_at__gte=today_start
        ).values('courier').annotate(
            count=Count('id'),
            earnings=Sum('courier_earning'),
            distance=Sum('distance_km')
        ).filter(courier__isnull=False)
        
        sent = 0
        for stats in couriers_with_deliveries:
            try:
                courier = User.objects.get(id=stats['courier'])
                
                success = CourierNotificationService.notify_daily_summary(
                    courier_phone=courier.phone_number,
                    deliveries_count=stats['count'],
                    total_earnings=stats['earnings'] or Decimal('0'),
                    total_distance=stats['distance'] or 0,
                    average_rating=courier.average_rating or 0
                )
                
                if success:
                    sent += 1
                    
            except User.DoesNotExist:
                continue
        
        logger.info(f"[BROADCAST] Sent {sent} daily summaries")
        return sent
