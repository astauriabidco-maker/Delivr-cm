"""
BOT App - WhatsApp Notification Service for Delivery Events

Sends WhatsApp notifications to clients (sender/recipient) when
delivery lifecycle events occur:
- Order created (OTP codes sent to sender & recipient)
- Pickup confirmed
- Delivery completed
- Tracking link shared

Uses the unified send_whatsapp_notification utility from bot.services.
"""

import logging
from django.conf import settings
from .services import send_notification_with_fallback

logger = logging.getLogger(__name__)


def send_order_confirmation_to_sender(delivery):
    """
    Send order confirmation to the SENDER via WhatsApp.
    
    Includes:
    - Order reference number
    - Pickup OTP (sender gives this to courier at pickup)
    - Delivery OTP (recipient gives this to courier at dropoff)
    - Tracking link
    - Price summary
    
    Called when a delivery is created via ANY channel (API, admin, partner portal).
    The bot flow already sends this inline, so this is for non-bot channels.
    
    Args:
        delivery: Delivery model instance (must have otp_code and pickup_otp set)
    """
    if not delivery.sender or not delivery.sender.phone_number:
        logger.warning(f"No sender phone for delivery {delivery.id}, skipping confirmation")
        return
    
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"🎉 *Commande Créée - DELIVR-CM*\n\n"
        f"📦 Référence : *#{str(delivery.id)[:8].upper()}*\n"
        f"💰 Prix : *{delivery.total_price:,.0f} XAF*\n"
        f"📏 Distance : *{delivery.distance_km or 0:.1f} km*\n\n"
        f"🔐 *Codes de sécurité :*\n"
        f"   📤 Code Ramassage : *{delivery.pickup_otp}*\n"
        f"   _→ Donnez ce code au coursier lors du retrait_\n\n"
        f"   📥 Code Livraison : *{delivery.otp_code}*\n"
        f"   _→ Transmettez ce code au destinataire_\n\n"
        f"📍 Suivi en direct :\n{tracking_url}\n\n"
        f"🔍 _Recherche d'un coursier en cours..._\n\n"
        f"💬 _DELIVR-CM - Livraison urbaine intelligente_"
    )
    
    try:
        msg_id, channel = send_notification_with_fallback(
            delivery.sender.phone_number,
            message
        )
        logger.info(
            f"Order confirmation sent for delivery {delivery.id} "
            f"to sender {delivery.sender.phone_number} via {channel}"
        )
        return msg_id
    except Exception as e:
        logger.error(f"Failed to send order confirmation for delivery {delivery.id}: {e}")
        return None


def send_otp_to_recipient(delivery):
    """
    Send the delivery OTP code to the RECIPIENT via WhatsApp.
    
    The recipient needs this code to confirm delivery when the courier arrives.
    
    Args:
        delivery: Delivery model instance (must have otp_code and recipient_phone set)
    """
    if not delivery.recipient_phone:
        logger.warning(f"No recipient phone for delivery {delivery.id}, skipping OTP send")
        return
    
    sender_name = delivery.sender.full_name if delivery.sender else "Un expéditeur"
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"📦 *Colis en route vers vous !*\n\n"
        f"👤 Expéditeur : *{sender_name}*\n"
        f"📦 Commande : *#{str(delivery.id)[:8].upper()}*\n\n"
        f"🔐 *Votre code de livraison : {delivery.otp_code}*\n"
        f"⚠️ _Donnez ce code au coursier à la réception du colis._\n\n"
        f"📍 Suivez le coursier en temps réel :\n{tracking_url}\n\n"
        f"💬 _DELIVR-CM - Livraison urbaine intelligente_"
    )
    
    try:
        msg_id, channel = send_notification_with_fallback(
            delivery.recipient_phone,
            message
        )
        logger.info(
            f"OTP sent to recipient {delivery.recipient_phone} "
            f"for delivery {delivery.id} via {channel}"
        )
        return msg_id
    except Exception as e:
        logger.error(f"Failed to send OTP to recipient for delivery {delivery.id}: {e}")
        return None


def _build_tracking_url(delivery):
    """Build the public tracking URL for a delivery."""
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    return f"{base_url}/track/{delivery.id}/"


def send_pickup_confirmed_notification(delivery):
    """
    Notify the sender that their package has been picked up.
    
    Sent when a courier confirms pickup with OTP.
    
    Args:
        delivery: Delivery model instance
    """
    if not delivery.sender or not delivery.sender.phone_number:
        logger.warning(f"No sender phone for delivery {delivery.id}, skipping notification")
        return
    
    tracking_url = _build_tracking_url(delivery)
    courier_name = delivery.courier.full_name if delivery.courier else "Le coursier"
    
    message = (
        f"📤 *Colis Récupéré !*\n\n"
        f"🏍️ {courier_name} a récupéré votre colis.\n"
        f"📦 Commande #{str(delivery.id)[:8]}\n\n"
        f"🚀 Votre livraison est en route vers *{delivery.recipient_name or 'le destinataire'}*.\n\n"
        f"📍 Suivez en temps réel :\n{tracking_url}\n\n"
        f"💬 _DELIVR-CM - Livraison urbaine intelligente_"
    )
    
    try:
        msg_id, channel = send_notification_with_fallback(
            delivery.sender.phone_number, 
            message
        )
        logger.info(
            f"Pickup notification sent for delivery {delivery.id} "
            f"to {delivery.sender.phone_number} via {channel}"
        )
    except Exception as e:
        logger.error(f"Failed to send pickup notification for delivery {delivery.id}: {e}")


def send_delivery_completed_notification(delivery):
    """
    Notify the sender that the delivery has been completed.
    
    Sent when a courier confirms dropoff with OTP.
    
    Args:
        delivery: Delivery model instance
    """
    if not delivery.sender or not delivery.sender.phone_number:
        logger.warning(f"No sender phone for delivery {delivery.id}, skipping notification")
        return
    
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"✅ *Livraison Terminée !*\n\n"
        f"📦 Commande #{str(delivery.id)[:8]}\n"
        f"🏁 Le colis a été remis à *{delivery.recipient_name or 'le destinataire'}*.\n\n"
        f"💰 Montant : {delivery.total_price:,.0f} XAF\n"
        f"📏 Distance : {delivery.distance_km or 0:.1f} km\n\n"
        f"📋 Détails complets :\n{tracking_url}\n\n"
        f"⭐ Merci de votre confiance !\n"
        f"💬 _DELIVR-CM - Livraison urbaine intelligente_"
    )
    
    try:
        msg_id, channel = send_notification_with_fallback(
            delivery.sender.phone_number, 
            message
        )
        logger.info(
            f"Completion notification sent for delivery {delivery.id} "
            f"to {delivery.sender.phone_number} via {channel}"
        )
    except Exception as e:
        logger.error(f"Failed to send completion notification for delivery {delivery.id}: {e}")


def send_delivery_status_notification(delivery, new_status):
    """
    Send a generic status update notification to the sender.
    
    Args:
        delivery: Delivery model instance
        new_status: New status string
    """
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    status_messages = {
        'ASSIGNED': '🏍️ Un coursier a accepté votre commande !',
        'EN_ROUTE_PICKUP': '🚗 Le coursier est en route vers le point de ramassage.',
        'ARRIVED_PICKUP': '📍 Le coursier est arrivé au point de ramassage.',
        'IN_TRANSIT': '🚀 Votre colis est en route vers la destination.',
        'ARRIVED_DROPOFF': '📍 Le coursier est arrivé à destination.',
    }
    
    status_msg = status_messages.get(new_status)
    if not status_msg:
        return
    
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"📦 *Mise à jour - Commande #{str(delivery.id)[:8]}*\n\n"
        f"{status_msg}\n\n"
        f"📍 Suivi en direct :\n{tracking_url}"
    )
    
    try:
        send_notification_with_fallback(delivery.sender.phone_number, message)
    except Exception as e:
        logger.error(f"Failed to send status notification for delivery {delivery.id}: {e}")
