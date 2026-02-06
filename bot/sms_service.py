"""
Orange SMS Service for DELIVR-CM

Fallback SMS provider using Orange Cameroun API.
Used when WhatsApp is unavailable.
"""

import logging
import requests
from typing import Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class OrangeSMSService:
    """
    Orange Cameroun SMS API integration.
    
    API Documentation: https://developer.orange.com/apis/sms-cm/overview
    
    Flow:
    1. Authenticate with OAuth2 to get access token
    2. Send SMS using the messaging API
    
    Access token is cached for performance.
    """
    
    AUTH_URL = "https://api.orange.com/oauth/v3/token"
    SMS_URL = "https://api.orange.com/smsmessaging/v1/outbound"
    
    TOKEN_CACHE_KEY = "orange_sms_access_token"
    TOKEN_CACHE_TTL = 3500  # Slightly less than 1 hour
    
    @classmethod
    def _get_access_token(cls) -> Optional[str]:
        """
        Get OAuth2 access token, using cache when available.
        
        Returns:
            Access token string or None if failed
        """
        # Check cache first
        cached_token = cache.get(cls.TOKEN_CACHE_KEY)
        if cached_token:
            return cached_token
        
        client_id = getattr(settings, 'ORANGE_SMS_CLIENT_ID', '')
        client_secret = getattr(settings, 'ORANGE_SMS_CLIENT_SECRET', '')
        
        if not client_id or not client_secret:
            logger.error("[ORANGE SMS] Missing ORANGE_SMS_CLIENT_ID or ORANGE_SMS_CLIENT_SECRET")
            return None
        
        try:
            response = requests.post(
                cls.AUTH_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "client_credentials",
                },
                auth=(client_id, client_secret),
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            access_token = data.get('access_token')
            
            if access_token:
                # Cache the token
                cache.set(cls.TOKEN_CACHE_KEY, access_token, cls.TOKEN_CACHE_TTL)
                logger.info("[ORANGE SMS] Access token obtained and cached")
                return access_token
            
            logger.error(f"[ORANGE SMS] No access token in response: {data}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"[ORANGE SMS] OAuth failed: {e}")
            return None
    
    @classmethod
    def send_sms(cls, to_number: str, text: str) -> Optional[str]:
        """
        Send SMS via Orange API.
        
        Args:
            to_number: Recipient phone number (format: +237XXXXXXXXX)
            text: SMS text (max 160 chars for single SMS)
            
        Returns:
            Message ID if successful, None if failed
        """
        access_token = cls._get_access_token()
        if not access_token:
            return None
        
        sender_address = getattr(settings, 'ORANGE_SMS_SENDER', 'DELIVR-CM')
        
        # Clean phone number (Orange expects tel:+237...)
        phone_clean = to_number.replace('+', '').replace('whatsapp:', '').strip()
        if not phone_clean.startswith('237'):
            phone_clean = '237' + phone_clean[-9:]
        
        sender_encoded = requests.utils.quote(f"tel:+{sender_address}")
        
        url = f"{cls.SMS_URL}/{sender_encoded}/requests"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "outboundSMSMessageRequest": {
                "address": f"tel:+{phone_clean}",
                "senderAddress": f"tel:+{sender_address}",
                "senderName": "DELIVR-CM",
                "outboundSMSTextMessage": {
                    "message": text[:160]  # Truncate to single SMS
                }
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract message ID from response
            resource_url = data.get('outboundSMSMessageRequest', {}).get('resourceURL', '')
            message_id = resource_url.split('/')[-1] if resource_url else 'sent'
            
            logger.info(f"[ORANGE SMS] Sent to +{phone_clean}: {message_id}")
            return message_id
            
        except requests.RequestException as e:
            logger.error(f"[ORANGE SMS] Failed to send to +{phone_clean}: {e}")
            return None
    
    @classmethod
    def get_delivery_status(cls, message_id: str) -> Optional[str]:
        """
        Check delivery status of a sent SMS.
        
        Args:
            message_id: Message ID returned from send_sms
            
        Returns:
            Status string or None if failed
        """
        access_token = cls._get_access_token()
        if not access_token:
            return None
        
        sender_address = getattr(settings, 'ORANGE_SMS_SENDER', 'DELIVR-CM')
        sender_encoded = requests.utils.quote(f"tel:+{sender_address}")
        
        url = f"{cls.SMS_URL}/{sender_encoded}/requests/{message_id}/deliveryInfos"
        
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            infos = data.get('deliveryInfoList', {}).get('deliveryInfo', [])
            
            if infos:
                return infos[0].get('deliveryStatus')
            
            return None
            
        except requests.RequestException as e:
            logger.error(f"[ORANGE SMS] Status check failed: {e}")
            return None
