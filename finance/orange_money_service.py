"""
Orange Money Service for DELIVR-CM

Handles WebPayment flow for Orange Money payments in Cameroon.
API Reference: https://developer.orange.com/apis/om-webpay/overview
"""

import uuid
import logging
import requests
from typing import Optional
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class OrangeMoneyService:
    """
    Orange Money WebPayment API integration.
    
    Flow:
    1. Get OAuth2 access token (cached)
    2. Init WebPayment (get pay_token + payment_url)
    3. User completes payment (redirect or phone confirmation)
    4. Poll or receive callback for status
    """
    
    SANDBOX_URL = "https://api.orange.com/orange-money-webpay/dev/v1"
    PRODUCTION_URL = "https://api.orange.com/orange-money-webpay/cm/v1"
    AUTH_URL = "https://api.orange.com/oauth/v3/token"
    
    TOKEN_CACHE_KEY = "orange_money_access_token"
    TOKEN_CACHE_TTL = 3500  # Slightly less than 1 hour
    
    @classmethod
    def _get_base_url(cls) -> str:
        """Get base URL based on environment."""
        env = getattr(settings, 'ORANGE_MONEY_ENVIRONMENT', 'sandbox')
        return cls.PRODUCTION_URL if env == 'production' else cls.SANDBOX_URL
    
    @classmethod
    def _get_access_token(cls) -> Optional[str]:
        """
        Get OAuth2 access token, using cache when available.
        """
        # Check cache first
        cached_token = cache.get(cls.TOKEN_CACHE_KEY)
        if cached_token:
            return cached_token
        
        merchant_key = getattr(settings, 'ORANGE_MONEY_MERCHANT_KEY', '')
        merchant_secret = getattr(settings, 'ORANGE_MONEY_MERCHANT_SECRET', '')
        
        if not all([merchant_key, merchant_secret]):
            logger.error("[ORANGE MONEY] Missing credentials")
            return None
        
        try:
            response = requests.post(
                cls.AUTH_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={"grant_type": "client_credentials"},
                auth=(merchant_key, merchant_secret),
                timeout=15
            )
            response.raise_for_status()
            
            data = response.json()
            access_token = data.get('access_token')
            
            if access_token:
                expires_in = int(data.get('expires_in', 3600))
                cache.set(cls.TOKEN_CACHE_KEY, access_token, min(expires_in - 60, cls.TOKEN_CACHE_TTL))
                logger.info("[ORANGE MONEY] Access token obtained and cached")
                return access_token
            
            logger.error(f"[ORANGE MONEY] No access token in response: {data}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"[ORANGE MONEY] Token request failed: {e}")
            return None
    
    @classmethod
    def init_payment(
        cls,
        phone: str,
        amount: Decimal,
        external_reference: str,
        description: str = "Paiement livraison DELIVR-CM"
    ) -> dict:
        """
        Initialize a WebPayment.
        
        Returns a pay_token and payment_url.
        
        Args:
            phone: 9-digit phone number (e.g., 699123456)
            amount: Amount in XAF
            external_reference: Our unique reference
            description: Payment description
            
        Returns:
            Dict with pay_token, payment_url, or error
        """
        access_token = cls._get_access_token()
        if not access_token:
            return {'success': False, 'error': 'Could not get access token'}
        
        callback_url = getattr(settings, 'ORANGE_MONEY_CALLBACK_URL', '')
        return_url = getattr(settings, 'ORANGE_MONEY_RETURN_URL', callback_url)
        
        # Normalize phone
        phone_clean = ''.join(filter(str.isdigit, phone))
        if phone_clean.startswith('237') and len(phone_clean) > 9:
            phone_clean = phone_clean[3:]
        
        url = f"{cls._get_base_url()}/webpayment"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        payload = {
            "merchant_key": getattr(settings, 'ORANGE_MONEY_MERCHANT_KEY', ''),
            "currency": "OUV",  # Orange Universal Value (XAF equivalent)
            "order_id": external_reference,
            "amount": int(amount),
            "return_url": return_url,
            "cancel_url": return_url,
            "notif_url": callback_url,
            "lang": "fr",
            "reference": description,
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code in (200, 201):
                data = response.json()
                
                pay_token = data.get('pay_token')
                payment_url = data.get('payment_url')
                
                if pay_token:
                    logger.info(f"[ORANGE MONEY] Payment initialized: {pay_token[:20]}...")
                    return {
                        'success': True,
                        'pay_token': pay_token,
                        'payment_url': payment_url,
                        'status': 'PENDING',
                        'message': 'Payment link generated'
                    }
                else:
                    logger.error(f"[ORANGE MONEY] No pay_token in response: {data}")
                    return {'success': False, 'error': 'No pay_token returned'}
            else:
                error_data = response.json() if response.text else {}
                logger.error(f"[ORANGE MONEY] Init failed: {response.status_code} - {error_data}")
                return {
                    'success': False,
                    'error': error_data.get('message', f'HTTP {response.status_code}'),
                    'error_code': error_data.get('code', 'UNKNOWN')
                }
                
        except requests.RequestException as e:
            logger.error(f"[ORANGE MONEY] Init exception: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def check_status(cls, pay_token: str = None, order_id: str = None) -> dict:
        """
        Check status of a WebPayment.
        
        Args:
            pay_token: The pay_token from init_payment
            order_id: Alternative: our order reference
            
        Returns:
            Dict with status and details
        """
        access_token = cls._get_access_token()
        if not access_token:
            return {'success': False, 'error': 'Could not get access token'}
        
        if pay_token:
            url = f"{cls._get_base_url()}/transactionstatus"
            params = {"pay_token": pay_token}
        elif order_id:
            url = f"{cls._get_base_url()}/transactionstatus"
            params = {"order_id": order_id}
        else:
            return {'success': False, 'error': 'pay_token or order_id required'}
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', 'UNKNOWN')
                
                # Map Orange Money status to our standard
                status_map = {
                    'SUCCESS': 'SUCCESSFUL',
                    'SUCCESSFULL': 'SUCCESSFUL',
                    'PENDING': 'PENDING',
                    'INITIATED': 'PENDING',
                    'FAILED': 'FAILED',
                    'EXPIRED': 'TIMEOUT',
                    'CANCELLED': 'CANCELLED',
                }
                
                normalized_status = status_map.get(status.upper(), status)
                
                logger.info(f"[ORANGE MONEY] Status check: {status} -> {normalized_status}")
                
                return {
                    'success': True,
                    'status': normalized_status,
                    'original_status': status,
                    'amount': data.get('amount'),
                    'order_id': data.get('order_id'),
                    'transaction_id': data.get('txnid'),
                    'raw': data
                }
            else:
                error_data = response.json() if response.text else {}
                logger.error(f"[ORANGE MONEY] Status check failed: {response.status_code}")
                return {
                    'success': False,
                    'error': error_data.get('message', f'HTTP {response.status_code}')
                }
                
        except requests.RequestException as e:
            logger.error(f"[ORANGE MONEY] Status check exception: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if Orange Money is properly configured."""
        return all([
            getattr(settings, 'ORANGE_MONEY_MERCHANT_KEY', ''),
            getattr(settings, 'ORANGE_MONEY_MERCHANT_SECRET', ''),
        ])
