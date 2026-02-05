"""
Partners App Models - Webhook Configuration
"""
import secrets
from django.db import models
from django.conf import settings


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
