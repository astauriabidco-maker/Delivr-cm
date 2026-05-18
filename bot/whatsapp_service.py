"""
BOT App - WhatsApp Notification Service for Delivery Events

Sends WhatsApp notifications to clients (sender/recipient) at EVERY
stage of the delivery lifecycle. Each notification can be independently
toggled ON/OFF by the super-admin via NotificationConfiguration.

Supported events:
  📦 PENDING         → Order created (OTPs to sender & recipient)
  🏍️ ASSIGNED        → Courier accepted
  🚗 EN_ROUTE_PICKUP → Courier heading to pickup
  📍 ARRIVED_PICKUP  → Courier at pickup point
  📤 PICKED_UP       → Package collected
  🚀 IN_TRANSIT      → Package on the way
  📍 ARRIVED_DROPOFF → Courier at destination
  ✅ COMPLETED       → Delivered!
  ❌ CANCELLED       → Order cancelled
  ❌ FAILED          → Delivery failed
"""

import logging
from django.conf import settings
from .services import send_notification_with_fallback

logger = logging.getLogger(__name__)


def _get_config():
    """Get the notification configuration (cached singleton)."""
    from .models import NotificationConfiguration
    return NotificationConfiguration.get_config()


def _build_tracking_url(delivery):
    """Build the public tracking URL for a delivery."""
    base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
    return f"{base_url}/track/{delivery.id}/"


def _ref(delivery):
    """Short reference for display."""
    return str(delivery.id)[:8].upper()


def _safe_send(phone, message, context=""):
    """Send with error handling."""
    try:
        msg_id, channel = send_notification_with_fallback(phone, message)
        logger.info(f"[NOTIF] {context} sent to {phone} via {channel}")
        return msg_id
    except Exception as e:
        logger.error(f"[NOTIF] Failed to send {context} to {phone}: {e}")
        return None


# ============================================================
# 📦 1. COMMANDE CRÉÉE (PENDING)
# ============================================================

def send_order_confirmation_to_sender(delivery):
    """
    Notify SENDER: order created with OTP codes + tracking link.
    """
    config = _get_config()
    if not config.is_enabled('PENDING', 'sender'):
        logger.debug(f"[NOTIF] sender/PENDING disabled, skipping")
        return
    
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    tracking_url = _build_tracking_url(delivery)
    
    # Check for custom message
    custom = config.get_custom_message('PENDING', 'sender')
    if custom:
        message = custom.format(
            ref=_ref(delivery),
            price=f"{delivery.total_price:,.0f}",
            distance=f"{delivery.distance_km or 0:.1f}",
            pickup_otp=delivery.pickup_otp,
            delivery_otp=delivery.otp_code,
            tracking_url=tracking_url,
            recipient_name=delivery.recipient_name or "le destinataire",
        )
    else:
        message = (
            f"✅ *Commande Créée - RELAY237*\n\n"
            f"📦 Référence : *#{_ref(delivery)}*\n"
            f"💰 Prix : *{delivery.total_price:,.0f} XAF*\n"
            f"📏 Distance : *{delivery.distance_km or 0:.1f} km*\n\n"
            f"🔐 *Codes de sécurité :*\n"
            f"   📤 Code Ramassage : *{delivery.pickup_otp}*\n"
            f"   _→ Donnez ce code au coursier lors du retrait_\n\n"
            f"   📥 Code Livraison : *{delivery.otp_code}*\n"
            f"   _→ Transmettez ce code au destinataire_\n\n"
            f"📍 Suivi en direct :\n{tracking_url}\n\n"
            f"🔍 _Recherche d'un coursier en cours..._\n\n"
            f"✅ _RELAY237 - Livré avec confiance_"
        )
    
    return _safe_send(
        delivery.sender.phone_number, message,
        f"order_created/sender for {_ref(delivery)}"
    )


def send_otp_to_recipient(delivery):
    """
    Notify RECIPIENT: order created, here's your OTP + tracking link.
    """
    config = _get_config()
    if not config.is_enabled('PENDING', 'recipient'):
        logger.debug(f"[NOTIF] recipient/PENDING disabled, skipping")
        return
    
    if not delivery.recipient_phone:
        return
    
    sender_name = delivery.sender.full_name if delivery.sender else "Un expéditeur"
    tracking_url = _build_tracking_url(delivery)
    
    custom = config.get_custom_message('PENDING', 'recipient')
    if custom:
        message = custom.format(
            ref=_ref(delivery),
            sender_name=sender_name,
            otp=delivery.otp_code,
            tracking_url=tracking_url,
        )
    else:
        message = (
            f"📦 *Colis en route vers vous !*\n\n"
            f"👤 Expéditeur : *{sender_name}*\n"
            f"📦 Commande : *#{_ref(delivery)}*\n\n"
            f"🔐 *Votre code de livraison : {delivery.otp_code}*\n"
            f"⚠️ _Donnez ce code au coursier à la réception du colis._\n\n"
            f"📍 Suivez le coursier en temps réel :\n{tracking_url}\n\n"
            f"✅ _RELAY237 - Livré avec confiance_"
        )
    
    return _safe_send(
        delivery.recipient_phone, message,
        f"otp/recipient for {_ref(delivery)}"
    )


# ============================================================
# 🏍️ 2. COURSIER ASSIGNÉ (ASSIGNED)
# ============================================================

def send_assigned_notification_sender(delivery):
    """Notify SENDER: a courier accepted the order."""
    config = _get_config()
    if not config.is_enabled('ASSIGNED', 'sender'):
        return
    
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    courier_name = delivery.courier.full_name if delivery.courier else "Un coursier"
    courier_phone = delivery.courier.phone_number if delivery.courier else ""
    tracking_url = _build_tracking_url(delivery)
    
    custom = config.get_custom_message('ASSIGNED', 'sender')
    if custom:
        message = custom.format(
            ref=_ref(delivery), courier_name=courier_name,
            courier_phone=courier_phone, tracking_url=tracking_url,
        )
    else:
        message = (
            f"🏍️ *Coursier Assigné !*\n\n"
            f"📦 Commande #{_ref(delivery)}\n"
            f"👤 Coursier : *{courier_name}*\n"
            f"📱 Tél : {courier_phone}\n\n"
            f"Le coursier se dirige vers le point de ramassage.\n"
            f"📍 Suivre en direct :\n{tracking_url}"
        )
    
    _safe_send(
        delivery.sender.phone_number, message,
        f"assigned/sender for {_ref(delivery)}"
    )


def send_assigned_notification_recipient(delivery):
    """Notify RECIPIENT: a courier is coming with your package."""
    config = _get_config()
    if not config.is_enabled('ASSIGNED', 'recipient'):
        return
    
    if not delivery.recipient_phone:
        return
    
    courier_name = delivery.courier.full_name if delivery.courier else "Un coursier"
    tracking_url = _build_tracking_url(delivery)
    
    custom = config.get_custom_message('ASSIGNED', 'recipient')
    if custom:
        message = custom.format(
            ref=_ref(delivery), courier_name=courier_name,
            tracking_url=tracking_url,
        )
    else:
        message = (
            f"📦 *Coursier en chemin !*\n\n"
            f"Commande #{_ref(delivery)}\n"
            f"🏍️ *{courier_name}* va récupérer votre colis.\n\n"
            f"📍 Suivre en direct :\n{tracking_url}"
        )
    
    _safe_send(
        delivery.recipient_phone, message,
        f"assigned/recipient for {_ref(delivery)}"
    )


# ============================================================
# 🚗 3. EN ROUTE VERS LE PICKUP (EN_ROUTE_PICKUP)
# ============================================================

def send_en_route_pickup_sender(delivery):
    """Notify SENDER: courier is on the way to pick up."""
    config = _get_config()
    if not config.is_enabled('EN_ROUTE_PICKUP', 'sender'):
        return
    
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    courier_name = delivery.courier.full_name if delivery.courier else "Le coursier"
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"🚗 *En route vers vous !*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"🏍️ {courier_name} est en route pour récupérer le colis.\n\n"
        f"🔐 Préparez votre code de ramassage : *{delivery.pickup_otp}*\n\n"
        f"📍 Suivre en direct :\n{tracking_url}"
    )
    
    _safe_send(
        delivery.sender.phone_number, message,
        f"en_route_pickup/sender for {_ref(delivery)}"
    )


def send_en_route_pickup_recipient(delivery):
    """Notify RECIPIENT (optional): courier is heading to pickup."""
    config = _get_config()
    if not config.is_enabled('EN_ROUTE_PICKUP', 'recipient'):
        return
    
    if not delivery.recipient_phone:
        return
    
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"📦 *Votre colis se prépare*\n\n"
        f"Commande #{_ref(delivery)}\n"
        f"Le coursier est en route pour récupérer votre colis.\n\n"
        f"📍 Suivre :\n{tracking_url}"
    )
    
    _safe_send(
        delivery.recipient_phone, message,
        f"en_route_pickup/recipient for {_ref(delivery)}"
    )


# ============================================================
# 📍 4. ARRIVÉ AU RAMASSAGE (ARRIVED_PICKUP)
# ============================================================

def send_arrived_pickup_sender(delivery):
    """Notify SENDER: courier has arrived at the pickup point."""
    config = _get_config()
    if not config.is_enabled('ARRIVED_PICKUP', 'sender'):
        return
    
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    courier_name = delivery.courier.full_name if delivery.courier else "Le coursier"
    
    message = (
        f"📍 *Coursier arrivé !*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"🏍️ {courier_name} est arrivé au point de ramassage.\n\n"
        f"🔐 Code de ramassage : *{delivery.pickup_otp}*\n"
        f"_Donnez ce code au coursier pour confirmer le retrait._"
    )
    
    _safe_send(
        delivery.sender.phone_number, message,
        f"arrived_pickup/sender for {_ref(delivery)}"
    )


def send_arrived_pickup_recipient(delivery):
    """Notify RECIPIENT (optional): courier is at pickup."""
    config = _get_config()
    if not config.is_enabled('ARRIVED_PICKUP', 'recipient'):
        return
    
    if not delivery.recipient_phone:
        return
    
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"📦 *Votre colis est en cours de retrait*\n\n"
        f"Commande #{_ref(delivery)}\n"
        f"Le coursier est au point de ramassage.\n\n"
        f"📍 Suivre :\n{tracking_url}"
    )
    
    _safe_send(
        delivery.recipient_phone, message,
        f"arrived_pickup/recipient for {_ref(delivery)}"
    )


# ============================================================
# 📤 5. COLIS RÉCUPÉRÉ (PICKED_UP)
# ============================================================

def send_pickup_confirmed_notification(delivery):
    """Notify SENDER: package has been picked up."""
    config = _get_config()
    if not config.is_enabled('PICKED_UP', 'sender'):
        return
    
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    courier_name = delivery.courier.full_name if delivery.courier else "Le coursier"
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"📤 *Colis Récupéré !*\n\n"
        f"🏍️ {courier_name} a récupéré votre colis.\n"
        f"📦 Commande #{_ref(delivery)}\n\n"
        f"✅ Votre livraison est en route vers "
        f"*{delivery.recipient_name or 'le destinataire'}*.\n\n"
        f"📍 Suivez en temps réel :\n{tracking_url}\n\n"
        f"✅ _RELAY237 - Livré avec confiance_"
    )
    
    _safe_send(
        delivery.sender.phone_number, message,
        f"picked_up/sender for {_ref(delivery)}"
    )


def send_picked_up_notification_recipient(delivery):
    """Notify RECIPIENT: your package has been collected, it's coming!"""
    config = _get_config()
    if not config.is_enabled('PICKED_UP', 'recipient'):
        return
    
    if not delivery.recipient_phone:
        return
    
    sender_name = delivery.sender.full_name if delivery.sender else "L'expéditeur"
    courier_name = delivery.courier.full_name if delivery.courier else "Le coursier"
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"📤 *Colis récupéré, en route vers vous !*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"👤 De : *{sender_name}*\n"
        f"🏍️ Coursier : *{courier_name}*\n\n"
        f"🔐 Préparez votre code de livraison : *{delivery.otp_code}*\n\n"
        f"📍 Suivre en direct :\n{tracking_url}"
    )
    
    _safe_send(
        delivery.recipient_phone, message,
        f"picked_up/recipient for {_ref(delivery)}"
    )


# ============================================================
# 🚀 6. EN TRANSIT (IN_TRANSIT)
# ============================================================

def send_in_transit_sender(delivery):
    """Notify SENDER: package is on its way to destination."""
    config = _get_config()
    if not config.is_enabled('IN_TRANSIT', 'sender'):
        return
    
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    courier_name = delivery.courier.full_name if delivery.courier else "Le coursier"
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"🚀 *En route vers la destination*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"🏍️ {courier_name} se dirige vers "
        f"*{delivery.recipient_name or 'le destinataire'}*.\n\n"
        f"📍 Suivre en direct :\n{tracking_url}"
    )
    
    _safe_send(
        delivery.sender.phone_number, message,
        f"in_transit/sender for {_ref(delivery)}"
    )


def send_in_transit_recipient(delivery):
    """Notify RECIPIENT: package is on its way + OTP reminder."""
    config = _get_config()
    if not config.is_enabled('IN_TRANSIT', 'recipient'):
        return
    
    if not delivery.recipient_phone:
        return
    
    sender_name = delivery.sender.full_name if delivery.sender else "L'expéditeur"
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"🚀 *Votre colis arrive bientôt !*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"👤 De : *{sender_name}*\n\n"
        f"🔐 *Rappel — Votre code : {delivery.otp_code}*\n"
        f"_Donnez ce code au coursier à la réception._\n\n"
        f"📍 Suivre en direct :\n{tracking_url}"
    )
    
    _safe_send(
        delivery.recipient_phone, message,
        f"in_transit/recipient for {_ref(delivery)}"
    )


# ============================================================
# 📍 7. ARRIVÉ À DESTINATION (ARRIVED_DROPOFF)
# ============================================================

def send_arrived_dropoff_sender(delivery):
    """Notify SENDER: courier has arrived at the destination."""
    config = _get_config()
    if not config.is_enabled('ARRIVED_DROPOFF', 'sender'):
        return
    
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    courier_name = delivery.courier.full_name if delivery.courier else "Le coursier"
    
    message = (
        f"📍 *Arrivé à destination !*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"🏍️ {courier_name} est arrivé chez "
        f"*{delivery.recipient_name or 'le destinataire'}*.\n\n"
        f"⏳ Remise du colis en cours..."
    )
    
    _safe_send(
        delivery.sender.phone_number, message,
        f"arrived_dropoff/sender for {_ref(delivery)}"
    )


def send_arrived_dropoff_recipient(delivery):
    """Notify RECIPIENT: courier is at your door!"""
    config = _get_config()
    if not config.is_enabled('ARRIVED_DROPOFF', 'recipient'):
        return
    
    if not delivery.recipient_phone:
        return
    
    courier_name = delivery.courier.full_name if delivery.courier else "Le coursier"
    
    message = (
        f"🚪 *Le coursier est à votre porte !*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"🏍️ {courier_name} vous attend.\n\n"
        f"🔐 *Code de livraison : {delivery.otp_code}*\n"
        f"_Donnez ce code au coursier pour recevoir votre colis._"
    )
    
    _safe_send(
        delivery.recipient_phone, message,
        f"arrived_dropoff/recipient for {_ref(delivery)}"
    )


# ============================================================
# ✅ 8. LIVRAISON TERMINÉE (COMPLETED)
# ============================================================

def send_delivery_completed_notification(delivery):
    """Notify SENDER: delivery completed!"""
    config = _get_config()
    if not config.is_enabled('COMPLETED', 'sender'):
        return
    
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    tracking_url = _build_tracking_url(delivery)
    
    message = (
        f"✅ *Livraison Terminée !*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"🏁 Le colis a été remis à "
        f"*{delivery.recipient_name or 'le destinataire'}*.\n\n"
        f"💰 Montant : {delivery.total_price:,.0f} XAF\n"
        f"📏 Distance : {delivery.distance_km or 0:.1f} km\n\n"
        f"📋 Détails complets :\n{tracking_url}\n\n"
        f"⭐ Merci de votre confiance !\n"
        f"✅ _RELAY237 - Livré avec confiance_"
    )
    
    _safe_send(
        delivery.sender.phone_number, message,
        f"completed/sender for {_ref(delivery)}"
    )


def send_completed_notification_recipient(delivery):
    """Notify RECIPIENT: your package has been delivered."""
    config = _get_config()
    if not config.is_enabled('COMPLETED', 'recipient'):
        return
    
    if not delivery.recipient_phone:
        return
    
    sender_name = delivery.sender.full_name if delivery.sender else "L'expéditeur"
    
    message = (
        f"✅ *Colis reçu avec succès !*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"👤 De : *{sender_name}*\n\n"
        f"Merci d'avoir utilisé RELAY237 ! 🙏\n\n"
        f"✅ _RELAY237 - Livré avec confiance_"
    )
    
    _safe_send(
        delivery.recipient_phone, message,
        f"completed/recipient for {_ref(delivery)}"
    )


# ============================================================
# ❌ 9. COMMANDE ANNULÉE (CANCELLED)
# ============================================================

def send_cancelled_notification_sender(delivery, reason=""):
    """Notify SENDER: order has been cancelled."""
    config = _get_config()
    if not config.is_enabled('CANCELLED', 'sender'):
        return
    
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    message = (
        f"❌ *Commande Annulée*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
    )
    if reason:
        message += f"📝 Raison : {reason}\n\n"
    message += (
        f"Vous pouvez créer une nouvelle commande à tout moment.\n\n"
        f"📞 _Support : RELAY237_"
    )
    
    _safe_send(
        delivery.sender.phone_number, message,
        f"cancelled/sender for {_ref(delivery)}"
    )


def send_cancelled_notification_recipient(delivery):
    """Notify RECIPIENT: order has been cancelled."""
    config = _get_config()
    if not config.is_enabled('CANCELLED', 'recipient'):
        return
    
    if not delivery.recipient_phone:
        return
    
    sender_name = delivery.sender.full_name if delivery.sender else "L'expéditeur"
    
    message = (
        f"❌ *Commande Annulée*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"👤 De : *{sender_name}*\n\n"
        f"La commande a été annulée.\n\n"
        f"📞 _Support : RELAY237_"
    )
    
    _safe_send(
        delivery.recipient_phone, message,
        f"cancelled/recipient for {_ref(delivery)}"
    )


# ============================================================
# ❌ 10. LIVRAISON ÉCHOUÉE (FAILED)
# ============================================================

def send_failed_notification_sender(delivery):
    """Notify SENDER: delivery has failed."""
    config = _get_config()
    if not config.is_enabled('FAILED', 'sender'):
        return
    
    if not delivery.sender or not delivery.sender.phone_number:
        return
    
    message = (
        f"⚠️ *Livraison Échouée*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"La livraison n'a pas pu être effectuée.\n\n"
        f"Notre équipe va vous contacter pour trouver une solution.\n\n"
        f"📞 _Support : RELAY237_"
    )
    
    _safe_send(
        delivery.sender.phone_number, message,
        f"failed/sender for {_ref(delivery)}"
    )


def send_failed_notification_recipient(delivery):
    """Notify RECIPIENT: delivery has failed."""
    config = _get_config()
    if not config.is_enabled('FAILED', 'recipient'):
        return
    
    if not delivery.recipient_phone:
        return
    
    sender_name = delivery.sender.full_name if delivery.sender else "L'expéditeur"
    
    message = (
        f"⚠️ *Livraison Échouée*\n\n"
        f"📦 Commande #{_ref(delivery)}\n"
        f"👤 De : *{sender_name}*\n\n"
        f"La livraison n'a pas pu être effectuée.\n"
        f"L'expéditeur a été prévenu.\n\n"
        f"📞 _Support : RELAY237_"
    )
    
    _safe_send(
        delivery.recipient_phone, message,
        f"failed/recipient for {_ref(delivery)}"
    )


# ============================================================
# ⚖️ LITIGES
# ============================================================

def send_dispute_notification(dispute):
    """Notify the dispute creator about updates."""
    config = _get_config()
    if not config.notify_dispute_updates:
        return
    
    if not dispute.creator.phone_number:
        return
    
    delivery = dispute.delivery
    status_label = dispute.get_status_display()
    
    message = (
        f"⚖️ *Mise à jour Litige - RELAY237*\n\n"
        f"📦 Commande : *#{_ref(delivery)}*\n"
        f"📑 Dossier : *#{str(dispute.id)[:8].upper()}*\n"
        f"📊 Statut : *{status_label}*\n\n"
    )
    
    if dispute.status == 'RESOLVED':
        message += f"✅ *Résolution :*\n{dispute.resolution_note}\n\n"
        if dispute.refund_amount > 0:
            message += (
                f"💰 Remboursement : "
                f"*{dispute.refund_amount:,.0f} XAF* crédités sur votre wallet.\n\n"
            )
    
    message += "Merci de votre patience.\n✅ _L'équipe Support RELAY237_"
    
    _safe_send(
        dispute.creator.phone_number, message,
        f"dispute update for {str(dispute.id)[:8]}"
    )


# ============================================================
# 🔄 UNIFIED DISPATCHER (called from signals)
# ============================================================

def notify_delivery_status_change(delivery, new_status, reason=""):
    """
    Unified entry point called by Django signals on every status change.
    
    Dispatches to the correct sender + recipient notification functions
    based on the new status. All checks (enabled/disabled) are done
    inside each function.
    
    Args:
        delivery: Delivery model instance
        new_status: New status string (e.g., 'ASSIGNED')
        reason: Optional cancellation reason
    """
    dispatch_map = {
        'ASSIGNED': (
            send_assigned_notification_sender,
            send_assigned_notification_recipient,
        ),
        'EN_ROUTE_PICKUP': (
            send_en_route_pickup_sender,
            send_en_route_pickup_recipient,
        ),
        'ARRIVED_PICKUP': (
            send_arrived_pickup_sender,
            send_arrived_pickup_recipient,
        ),
        'PICKED_UP': (
            send_pickup_confirmed_notification,
            send_picked_up_notification_recipient,
        ),
        'IN_TRANSIT': (
            send_in_transit_sender,
            send_in_transit_recipient,
        ),
        'ARRIVED_DROPOFF': (
            send_arrived_dropoff_sender,
            send_arrived_dropoff_recipient,
        ),
        'COMPLETED': (
            send_delivery_completed_notification,
            send_completed_notification_recipient,
        ),
        'CANCELLED': (
            lambda d: send_cancelled_notification_sender(d, reason),
            send_cancelled_notification_recipient,
        ),
        'FAILED': (
            send_failed_notification_sender,
            send_failed_notification_recipient,
        ),
    }
    
    handlers = dispatch_map.get(new_status)
    if not handlers:
        logger.debug(f"[NOTIF] No notification handlers for status {new_status}")
        return
    
    sender_handler, recipient_handler = handlers
    
    try:
        sender_handler(delivery)
    except Exception as e:
        logger.error(f"[NOTIF] Sender notification failed for {new_status}: {e}")
    
    try:
        recipient_handler(delivery)
    except Exception as e:
        logger.error(f"[NOTIF] Recipient notification failed for {new_status}: {e}")


# Keep backward compatibility
def send_delivery_status_notification(delivery, new_status):
    """Legacy wrapper — delegates to unified dispatcher."""
    notify_delivery_status_change(delivery, new_status)
