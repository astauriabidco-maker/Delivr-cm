"""
BOT App - Notification Configuration Model

Singleton model that allows super-admins to toggle each delivery
notification ON or OFF, for both sender and recipient, at each
stage of the delivery lifecycle.

Also allows customizing notification messages without code changes.
"""

from django.db import models
from django.conf import settings


class NotificationConfiguration(models.Model):
    """
    Singleton configuration for delivery lifecycle notifications.
    
    Super-admins can toggle each notification for sender and recipient
    independently via Django Admin, and customize the message templates.
    
    Only ONE instance should exist (enforced by save()).
    """
    
    class Meta:
        verbose_name = "Configuration des notifications"
        verbose_name_plural = "Configuration des notifications"
    
    # =========================================================
    # 📦 COMMANDE CRÉÉE (PENDING)
    # =========================================================
    
    # Sender
    notify_sender_order_created = models.BooleanField(
        default=True,
        verbose_name="📤 Expéditeur → Commande créée",
        help_text="Envoyer confirmation + codes OTP à l'expéditeur"
    )
    msg_sender_order_created = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text=(
            "Variables disponibles : {ref}, {price}, {distance}, "
            "{pickup_otp}, {delivery_otp}, {tracking_url}, {recipient_name}"
        )
    )
    
    # Recipient
    notify_recipient_order_created = models.BooleanField(
        default=True,
        verbose_name="📥 Destinataire → Commande créée",
        help_text="Envoyer le code OTP de livraison au destinataire"
    )
    msg_recipient_order_created = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {sender_name}, {otp}, {tracking_url}"
    )
    
    # =========================================================
    # 🏍️ COURSIER ASSIGNÉ (ASSIGNED)
    # =========================================================
    
    notify_sender_assigned = models.BooleanField(
        default=True,
        verbose_name="📤 Expéditeur → Coursier assigné",
        help_text="Notifier l'expéditeur qu'un coursier a accepté"
    )
    msg_sender_assigned = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {courier_name}, {courier_phone}, {tracking_url}"
    )
    
    notify_recipient_assigned = models.BooleanField(
        default=True,
        verbose_name="📥 Destinataire → Coursier assigné",
        help_text="Informer le destinataire qu'un coursier est en route"
    )
    msg_recipient_assigned = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {courier_name}, {tracking_url}"
    )
    
    # =========================================================
    # 🚗 EN ROUTE VERS LE RAMASSAGE (EN_ROUTE_PICKUP)
    # =========================================================
    
    notify_sender_en_route_pickup = models.BooleanField(
        default=True,
        verbose_name="📤 Expéditeur → En route pickup",
        help_text="Le coursier part vers le lieu de ramassage"
    )
    msg_sender_en_route_pickup = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {courier_name}, {tracking_url}"
    )
    
    notify_recipient_en_route_pickup = models.BooleanField(
        default=False,
        verbose_name="📥 Destinataire → En route pickup",
        help_text="Informer le destinataire que le coursier va chercher le colis"
    )
    
    # =========================================================
    # 📍 ARRIVÉ AU RAMASSAGE (ARRIVED_PICKUP)
    # =========================================================
    
    notify_sender_arrived_pickup = models.BooleanField(
        default=True,
        verbose_name="📤 Expéditeur → Arrivé au pickup",
        help_text="Le coursier est arrivé au point de ramassage"
    )
    msg_sender_arrived_pickup = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {courier_name}, {pickup_otp}"
    )
    
    notify_recipient_arrived_pickup = models.BooleanField(
        default=False,
        verbose_name="📥 Destinataire → Arrivé au pickup",
        help_text="Informer le destinataire que le coursier est au point de retrait"
    )
    
    # =========================================================
    # 📤 COLIS RÉCUPÉRÉ (PICKED_UP)
    # =========================================================
    
    notify_sender_picked_up = models.BooleanField(
        default=True,
        verbose_name="📤 Expéditeur → Colis récupéré",
        help_text="Le coursier a récupéré le colis"
    )
    msg_sender_picked_up = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {courier_name}, {recipient_name}, {tracking_url}"
    )
    
    notify_recipient_picked_up = models.BooleanField(
        default=True,
        verbose_name="📥 Destinataire → Colis récupéré",
        help_text="Informer le destinataire que le colis est en préparation de livraison"
    )
    msg_recipient_picked_up = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {sender_name}, {courier_name}, {tracking_url}"
    )
    
    # =========================================================
    # 🚀 EN TRANSIT (IN_TRANSIT)
    # =========================================================
    
    notify_sender_in_transit = models.BooleanField(
        default=True,
        verbose_name="📤 Expéditeur → En transit",
        help_text="Le colis est en route vers la destination"
    )
    msg_sender_in_transit = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {courier_name}, {tracking_url}"
    )
    
    notify_recipient_in_transit = models.BooleanField(
        default=True,
        verbose_name="📥 Destinataire → En transit",
        help_text="Rappeler le code OTP au destinataire + le colis arrive bientôt"
    )
    msg_recipient_in_transit = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {sender_name}, {otp}, {tracking_url}"
    )
    
    # =========================================================
    # 📍 ARRIVÉ À DESTINATION (ARRIVED_DROPOFF)
    # =========================================================
    
    notify_sender_arrived_dropoff = models.BooleanField(
        default=True,
        verbose_name="📤 Expéditeur → Arrivé destination",
        help_text="Le coursier est arrivé chez le destinataire"
    )
    msg_sender_arrived_dropoff = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {courier_name}, {recipient_name}"
    )
    
    notify_recipient_arrived_dropoff = models.BooleanField(
        default=True,
        verbose_name="📥 Destinataire → Arrivé destination",
        help_text="Prévenir le destinataire que le coursier est à sa porte"
    )
    msg_recipient_arrived_dropoff = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {courier_name}, {otp}"
    )
    
    # =========================================================
    # ✅ LIVRAISON TERMINÉE (COMPLETED)
    # =========================================================
    
    notify_sender_completed = models.BooleanField(
        default=True,
        verbose_name="📤 Expéditeur → Livraison terminée",
        help_text="Confirmation de livraison réussie à l'expéditeur"
    )
    msg_sender_completed = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {recipient_name}, {price}, {distance}, {tracking_url}"
    )
    
    notify_recipient_completed = models.BooleanField(
        default=True,
        verbose_name="📥 Destinataire → Livraison terminée",
        help_text="Confirmation + reçu PDF au destinataire"
    )
    msg_recipient_completed = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {sender_name}"
    )
    
    # =========================================================
    # ❌ COMMANDE ANNULÉE (CANCELLED)
    # =========================================================
    
    notify_sender_cancelled = models.BooleanField(
        default=True,
        verbose_name="📤 Expéditeur → Commande annulée",
        help_text="Notifier l'expéditeur de l'annulation"
    )
    msg_sender_cancelled = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {reason}"
    )
    
    notify_recipient_cancelled = models.BooleanField(
        default=True,
        verbose_name="📥 Destinataire → Commande annulée",
        help_text="Notifier le destinataire de l'annulation"
    )
    msg_recipient_cancelled = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {sender_name}"
    )
    
    # =========================================================
    # ❌ LIVRAISON ÉCHOUÉE (FAILED)
    # =========================================================
    
    notify_sender_failed = models.BooleanField(
        default=True,
        verbose_name="📤 Expéditeur → Livraison échouée",
        help_text="Notifier l'expéditeur de l'échec"
    )
    msg_sender_failed = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}"
    )
    
    notify_recipient_failed = models.BooleanField(
        default=True,
        verbose_name="📥 Destinataire → Livraison échouée",
        help_text="Notifier le destinataire de l'échec"
    )
    msg_recipient_failed = models.TextField(
        blank=True,
        verbose_name="Message personnalisé",
        help_text="Variables : {ref}, {sender_name}"
    )
    
    # =========================================================
    # ⚖️ LITIGES
    # =========================================================
    
    notify_dispute_updates = models.BooleanField(
        default=True,
        verbose_name="⚖️ Mises à jour litiges",
        help_text="Notifier le créateur du litige des mises à jour"
    )
    
    # =========================================================
    # 📊 RÉSUMÉS & RAPPELS
    # =========================================================
    
    notify_daily_summary = models.BooleanField(
        default=True,
        verbose_name="📊 Résumé quotidien coursiers",
        help_text="Envoyer un résumé des revenus du jour aux coursiers"
    )
    
    notify_rating_request = models.BooleanField(
        default=True,
        verbose_name="⭐ Demande de note",
        help_text="Demander au client de noter la livraison après complétion"
    )
    
    # =========================================================
    # METADATA
    # =========================================================
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Modifié par"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes admin",
        help_text="Notes internes sur les changements effectués"
    )
    
    def __str__(self):
        return "📱 Configuration des notifications"
    
    def save(self, *args, **kwargs):
        """Enforce singleton — only one instance."""
        self.pk = 1
        super().save(*args, **kwargs)
        # Invalidate cache
        from django.core.cache import cache
        cache.delete('notification_configuration')
    
    @classmethod
    def get_config(cls):
        """Get the active notification config (cached)."""
        from django.core.cache import cache
        
        config = cache.get('notification_configuration')
        if config is None:
            config, _ = cls.objects.get_or_create(pk=1)
            cache.set('notification_configuration', config, 600)
        return config
    
    def is_enabled(self, status: str, target: str) -> bool:
        """
        Check if a notification is enabled for a given status and target.
        
        Args:
            status: Delivery status (e.g., 'ASSIGNED', 'PICKED_UP')
            target: 'sender' or 'recipient'
        
        Returns:
            True if the notification is enabled
        """
        status_map = {
            'PENDING': 'order_created',
            'ASSIGNED': 'assigned',
            'EN_ROUTE_PICKUP': 'en_route_pickup',
            'ARRIVED_PICKUP': 'arrived_pickup',
            'PICKED_UP': 'picked_up',
            'IN_TRANSIT': 'in_transit',
            'ARRIVED_DROPOFF': 'arrived_dropoff',
            'COMPLETED': 'completed',
            'CANCELLED': 'cancelled',
            'FAILED': 'failed',
        }
        
        status_key = status_map.get(status)
        if not status_key:
            return False
        
        field_name = f"notify_{target}_{status_key}"
        return getattr(self, field_name, False)
    
    def get_custom_message(self, status: str, target: str) -> str:
        """
        Get the custom message template for a status/target combo.
        Returns empty string if no custom message defined (use default).
        """
        status_map = {
            'PENDING': 'order_created',
            'ASSIGNED': 'assigned',
            'EN_ROUTE_PICKUP': 'en_route_pickup',
            'ARRIVED_PICKUP': 'arrived_pickup',
            'PICKED_UP': 'picked_up',
            'IN_TRANSIT': 'in_transit',
            'ARRIVED_DROPOFF': 'arrived_dropoff',
            'COMPLETED': 'completed',
            'CANCELLED': 'cancelled',
            'FAILED': 'failed',
        }
        
        status_key = status_map.get(status)
        if not status_key:
            return ""
        
        field_name = f"msg_{target}_{status_key}"
        return getattr(self, field_name, "")
    
    @property
    def summary(self):
        """Quick summary of enabled/disabled notifications."""
        statuses = [
            'PENDING', 'ASSIGNED', 'EN_ROUTE_PICKUP', 'ARRIVED_PICKUP',
            'PICKED_UP', 'IN_TRANSIT', 'ARRIVED_DROPOFF', 'COMPLETED',
            'CANCELLED', 'FAILED',
        ]
        enabled = 0
        total = 0
        for status in statuses:
            for target in ['sender', 'recipient']:
                total += 1
                if self.is_enabled(status, target):
                    enabled += 1
        return f"{enabled}/{total} notifications actives"
