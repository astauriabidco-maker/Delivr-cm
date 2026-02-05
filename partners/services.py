"""
Partners App Services - Webhook Delivery
"""
import json
import hmac
import hashlib
import logging
import requests
from typing import Tuple
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service for sending webhooks to partner endpoints.
    """
    
    TIMEOUT = 10  # seconds
    
    @classmethod
    def send(cls, user, event_type: str, payload: dict) -> bool:
        """
        Send a webhook to a partner.
        
        Args:
            user: The partner User object
            event_type: Type of event (e.g. 'order.created')
            payload: Event data
            
        Returns:
            bool: True if successful
        """
        try:
            config = user.webhook_config
        except Exception:
            return False
        
        if not config.is_active or not config.url:
            return False
        
        if event_type not in config.events:
            return False
        
        # Prepare payload
        data = {
            'event': event_type,
            'timestamp': timezone.now().isoformat(),
            'data': payload
        }
        
        body = json.dumps(data, default=str)
        
        # Compute HMAC signature
        signature = hmac.new(
            config.secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': f'sha256={signature}',
            'X-Webhook-Event': event_type,
            'User-Agent': 'DELIVR-CM-Webhook/1.0'
        }
        
        try:
            response = requests.post(
                config.url,
                data=body,
                headers=headers,
                timeout=cls.TIMEOUT
            )
            
            # Update config
            config.last_triggered = timezone.now()
            config.last_status_code = response.status_code
            
            if response.status_code < 400:
                config.failure_count = 0
                config.save()
                logger.info(f"[WEBHOOK] Sent {event_type} to {config.url}: {response.status_code}")
                return True
            else:
                config.failure_count += 1
                config.save()
                logger.warning(f"[WEBHOOK] Failed {event_type} to {config.url}: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            config.last_triggered = timezone.now()
            config.failure_count += 1
            config.save()
            logger.error(f"[WEBHOOK] Error sending to {config.url}: {e}")
            return False
    
    @classmethod
    def test_webhook(cls, config) -> Tuple[bool, str]:
        """
        Test a webhook configuration.
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        if not config.url:
            return False, "URL non configurée"
        
        test_payload = {
            'event': 'test',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'message': 'Ceci est un test webhook DELIVR-CM',
                'test': True
            }
        }
        
        body = json.dumps(test_payload, default=str)
        
        signature = hmac.new(
            config.secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': f'sha256={signature}',
            'X-Webhook-Event': 'test',
            'User-Agent': 'DELIVR-CM-Webhook/1.0'
        }
        
        try:
            response = requests.post(
                config.url,
                data=body,
                headers=headers,
                timeout=cls.TIMEOUT
            )
            
            if response.status_code < 400:
                return True, f"Réponse {response.status_code}"
            else:
                return False, f"Erreur HTTP {response.status_code}"
                
        except requests.RequestException as e:
            return False, str(e)
