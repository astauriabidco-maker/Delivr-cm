"""
Partners App Models - Partner API Keys, Webhook Configuration & Notifications

Key security model: PartnerAPIKey links each API key to a specific
partner User, ensuring API calls can only act on behalf of the
correct partner (preventing cross-partner impersonation).
"""
import secrets
from django.db import models
from django.conf import settings
from rest_framework_api_key.models import AbstractAPIKey


class PartnerAPIKey(AbstractAPIKey):
    """
    Custom API Key model linked to a specific partner user.
    
    This extends AbstractAPIKey to add a ForeignKey to the User model,
    allowing the system to identify WHICH partner is making an API call.
    
    Without this link, any valid API key could pass any shop_id
    and create orders / debit wallets of other partners.
    
    Usage in views:
        key = PartnerAPIKey.objects.get_from_key(raw_key)
        partner = key.partner  # The authenticated partner User
    """
    
    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name="Partenaire",
        help_text="Le partenaire propriétaire de cette clé API"
    )
    
    class Meta(AbstractAPIKey.Meta):
        verbose_name = "Clé API Partenaire"
        verbose_name_plural = "Clés API Partenaires"
    
    def __str__(self):
        return f"API Key: {self.partner.full_name} - {self.name}"


class WebhookConfig(models.Model):
    """
    Webhook configuration for a partner.
    
    Allows partners to receive HTTP callbacks when delivery events occur.
    """
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='webhook_config'
    )
    
    url = models.URLField(
        blank=True,
        help_text="URL to receive webhook POST requests"
    )
    
    secret = models.CharField(
        max_length=64,
        default=secrets.token_hex,
        help_text="HMAC secret for signature verification"
    )
    
    events = models.JSONField(
        default=list,
        help_text="List of event types to subscribe to"
    )
    
    is_active = models.BooleanField(
        default=False,
        help_text="Enable/disable webhook"
    )
    
    last_triggered = models.DateTimeField(
        null=True, blank=True
    )
    
    last_status_code = models.IntegerField(
        null=True, blank=True
    )
    
    failure_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuration Webhook"
        verbose_name_plural = "Configurations Webhook"
    
    def __str__(self):
        return f"Webhook: {self.user.full_name} - {'Active' if self.is_active else 'Inactive'}"
    
    def regenerate_secret(self):
        """Generate a new HMAC secret."""
        self.secret = secrets.token_hex(32)
        self.save(update_fields=['secret'])
        return self.secret


class NotificationType(models.TextChoices):
    """Types of partner notifications."""
    ORDER_CREATED = 'order_created', 'Nouvelle commande'
    ORDER_ASSIGNED = 'order_assigned', 'Coursier assigné'
    ORDER_PICKED_UP = 'order_picked_up', 'Colis récupéré'
    ORDER_COMPLETED = 'order_completed', 'Livraison terminée'
    ORDER_CANCELLED = 'order_cancelled', 'Commande annulée'
    PAYMENT_RECEIVED = 'payment_received', 'Paiement reçu'
    INVOICE_GENERATED = 'invoice_generated', 'Facture générée'
    SYSTEM = 'system', 'Système'


class PartnerNotification(models.Model):
    """
    Notification for a partner about delivery events.
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='partner_notifications'
    )
    
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM
    )
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Optional link to related delivery
    delivery = models.ForeignKey(
        'logistics.Delivery',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='partner_notifications'
    )
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Notification Partenaire"
        verbose_name_plural = "Notifications Partenaires"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.full_name}"
    
    @classmethod
    def create_for_delivery(cls, delivery, notification_type, title, message):
        """Create a notification for the delivery sender."""
        if delivery.sender:
            return cls.objects.create(
                user=delivery.sender,
                notification_type=notification_type,
                title=title,
                message=message,
                delivery=delivery
            )
        return None
