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

    @staticmethod
    def _format_datetime(value):
        return value.isoformat() if value else None

    @staticmethod
    def _format_point(point):
        if not point:
            return None

        return {
            'latitude': point.y,
            'longitude': point.x,
        }

    @classmethod
    def build_delivery_payload(cls, delivery) -> dict:
        """
        Build the stable delivery payload sent for partner order events.

        OTP codes and internal-only fields are intentionally excluded.
        """
        courier = delivery.courier
        dropoff_neighborhood = delivery.dropoff_neighborhood

        return {
            'order': {
                'id': str(delivery.id),
                'external_order_id': delivery.external_order_id or '',
                'status': delivery.status,
                'payment_method': delivery.payment_method,
                'package_description': delivery.package_description or '',
                'recipient': {
                    'name': delivery.recipient_name or '',
                    'phone': delivery.recipient_phone or '',
                },
                'pickup': {
                    'address': delivery.pickup_address or '',
                    'location': cls._format_point(delivery.pickup_geo),
                },
                'dropoff': {
                    'address': delivery.dropoff_address or '',
                    'location': cls._format_point(delivery.dropoff_geo),
                    'neighborhood': {
                        'id': str(dropoff_neighborhood.id),
                        'name': dropoff_neighborhood.name,
                        'city': dropoff_neighborhood.city,
                    } if dropoff_neighborhood else None,
                },
                'courier': {
                    'id': str(courier.id),
                    'name': courier.full_name or '',
                    'phone': courier.phone_number or '',
                } if courier else None,
                'pricing': {
                    'currency': 'XAF',
                    'distance_km': delivery.distance_km,
                    'total_price': str(delivery.total_price),
                    'platform_fee': str(delivery.platform_fee),
                    'courier_earning': str(delivery.courier_earning),
                },
                'timestamps': {
                    'created_at': cls._format_datetime(delivery.created_at),
                    'assigned_at': cls._format_datetime(delivery.assigned_at),
                    'picked_up_at': cls._format_datetime(delivery.picked_up_at),
                    'in_transit_at': cls._format_datetime(delivery.in_transit_at),
                    'completed_at': cls._format_datetime(delivery.completed_at),
                },
            },
        }
    
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
            'User-Agent': 'RELAY237-Webhook/1.0'
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
                'message': 'Ceci est un test webhook RELAY237',
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
            'User-Agent': 'RELAY237-Webhook/1.0'
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
