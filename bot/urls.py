"""
BOT App URL Configuration

Dual provider support:
- /webhooks/mock-whatsapp/ - Mock webhook for local testing
- /webhooks/twilio/ - Twilio WhatsApp integration
- /webhooks/meta/ - Meta WhatsApp Cloud API integration
"""

from django.urls import path
from .views import MockWhatsAppWebhook, TwilioWebhookView, MetaWebhookView

urlpatterns = [
    # Mock webhook for local testing
    path('mock-whatsapp/', MockWhatsAppWebhook.as_view(), name='mock-whatsapp'),
    
    # Real Twilio WhatsApp webhook
    path('twilio/', TwilioWebhookView.as_view(), name='twilio-webhook'),
    
    # Real Meta WhatsApp Cloud API webhook
    path('meta/', MetaWebhookView.as_view(), name='meta-webhook'),
]
