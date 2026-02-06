"""
MTN Mobile Money Service for DELIVR-CM

Handles RequestToPay (STK Push) for MTN MoMo payments in Cameroon.
API Reference: https://momodeveloper.mtn.com/docs
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


class MTNMoMoService:
    """
    MTN Mobile Money API integration.
    
    Flow:
    1. Get OAuth2 access token (cached)
    2. RequestToPay (STK Push to user's phone)
    3. Poll or receive callback for status
    """
    
    SANDBOX_URL = "https://sandbox.momodeveloper.mtn.com"
    PRODUCTION_URL = "https://proxy.momoapi.mtn.com"
    
    TOKEN_CACHE_KEY = "mtn_momo_access_token"
    TOKEN_CACHE_TTL = 3500  # Slightly less than 1 hour
    
    @classmethod
    def _get_base_url(cls) -> str:
        """Get base URL based on environment."""
        env = getattr(settings, 'MTN_MOMO_ENVIRONMENT', 'sandbox')
        return cls.PRODUCTION_URL if env == 'production' else cls.SANDBOX_URL
    
    @classmethod
    def _get_access_token(cls) -> Optional[str]:
        """
        Get OAuth2 access token, using cache when available.
        
        Uses Basic Auth with API User UUID and API Key.
        """
        # Check cache first
        cached_token = cache.get(cls.TOKEN_CACHE_KEY)
        if cached_token:
            return cached_token
        
        api_user = getattr(settings, 'MTN_MOMO_API_USER', '')
        api_key = getattr(settings, 'MTN_MOMO_API_KEY', '')
        subscription_key = getattr(settings, 'MTN_MOMO_SUBSCRIPTION_KEY', '')
        
        if not all([api_user, api_key, subscription_key]):
            logger.error("[MTN MOMO] Missing credentials")
            return None
        
        try:
            url = f"{cls._get_base_url()}/collection/token/"
            
            response = requests.post(
                url,
                headers={
                    "Ocp-Apim-Subscription-Key": subscription_key,
                },
                auth=(api_user, api_key),
                timeout=15
            )
            response.raise_for_status()
            
            data = response.json()
            access_token = data.get('access_token')
            
            if access_token:
                expires_in = int(data.get('expires_in', 3600))
                cache.set(cls.TOKEN_CACHE_KEY, access_token, min(expires_in - 60, cls.TOKEN_CACHE_TTL))
                logger.info("[MTN MOMO] Access token obtained and cached")
                return access_token
            
            logger.error(f"[MTN MOMO] No access token in response: {data}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"[MTN MOMO] Token request failed: {e}")
            return None
    
    @classmethod
    def request_to_pay(
        cls,
        phone: str,
        amount: Decimal,
        external_reference: str,
        payer_message: str = "Paiement DELIVR-CM",
        payee_note: str = "Livraison"
    ) -> dict:
        """
        Initiate a RequestToPay (STK Push).
        
        This triggers a payment prompt on the user's phone.
        
        Args:
            phone: 9-digit phone number (e.g., 677123456)
            amount: Amount in XAF
            external_reference: Our unique reference (UUID)
            payer_message: Message shown to payer
            payee_note: Internal note
            
        Returns:
            Dict with success status and reference_id
        """
        access_token = cls._get_access_token()
        if not access_token:
            return {'success': False, 'error': 'Could not get access token'}
        
        subscription_key = getattr(settings, 'MTN_MOMO_SUBSCRIPTION_KEY', '')
        environment = getattr(settings, 'MTN_MOMO_ENVIRONMENT', 'sandbox')
        callback_url = getattr(settings, 'MTN_MOMO_CALLBACK_URL', '')
        
        # Generate unique reference ID for this request
        reference_id = str(uuid.uuid4())
        
        # Normalize phone to local format (remove +237)
        phone_clean = ''.join(filter(str.isdigit, phone))
        if phone_clean.startswith('237') and len(phone_clean) > 9:
            phone_clean = phone_clean[3:]
        
        url = f"{cls._get_base_url()}/collection/v1_0/requesttopay"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Reference-Id": reference_id,
            "X-Target-Environment": environment,
            "Ocp-Apim-Subscription-Key": subscription_key,
            "Content-Type": "application/json",
        }
        
        if callback_url:
            headers["X-Callback-Url"] = callback_url
        
        payload = {
            "amount": str(int(amount)),  # MTN expects string, no decimals for XAF
            "currency": "XAF",
            "externalId": external_reference,
            "payer": {
                "partyIdType": "MSISDN",
                "partyId": phone_clean
            },
            "payerMessage": payer_message,
            "payeeNote": payee_note
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            # 202 Accepted means request was received
            if response.status_code == 202:
                logger.info(f"[MTN MOMO] RequestToPay initiated: {reference_id}")
                return {
                    'success': True,
                    'reference_id': reference_id,
                    'status': 'PENDING',
                    'message': 'Payment request sent to phone'
                }
            else:
                error_data = response.json() if response.text else {}
                logger.error(f"[MTN MOMO] RequestToPay failed: {response.status_code} - {error_data}")
                return {
                    'success': False,
                    'error': error_data.get('message', f'HTTP {response.status_code}'),
                    'error_code': error_data.get('code', 'UNKNOWN')
                }
                
        except requests.RequestException as e:
            logger.error(f"[MTN MOMO] RequestToPay exception: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def check_status(cls, reference_id: str) -> dict:
        """
        Check status of a RequestToPay.
        
        Args:
            reference_id: The X-Reference-Id used in the original request
            
        Returns:
            Dict with status and details
        """
        access_token = cls._get_access_token()
        if not access_token:
            return {'success': False, 'error': 'Could not get access token'}
        
        subscription_key = getattr(settings, 'MTN_MOMO_SUBSCRIPTION_KEY', '')
        environment = getattr(settings, 'MTN_MOMO_ENVIRONMENT', 'sandbox')
        
        url = f"{cls._get_base_url()}/collection/v1_0/requesttopay/{reference_id}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Target-Environment": environment,
            "Ocp-Apim-Subscription-Key": subscription_key,
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            status = data.get('status', 'UNKNOWN')
            
            logger.info(f"[MTN MOMO] Status check {reference_id}: {status}")
            
            return {
                'success': True,
                'status': status,
                'amount': data.get('amount'),
                'currency': data.get('currency'),
                'payer': data.get('payer', {}).get('partyId'),
                'external_id': data.get('externalId'),
                'financial_transaction_id': data.get('financialTransactionId'),
                'reason': data.get('reason'),
                'raw': data
            }
            
        except requests.RequestException as e:
            logger.error(f"[MTN MOMO] Status check failed: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if MTN MoMo is properly configured."""
        return all([
            getattr(settings, 'MTN_MOMO_SUBSCRIPTION_KEY', ''),
            getattr(settings, 'MTN_MOMO_API_USER', ''),
            getattr(settings, 'MTN_MOMO_API_KEY', ''),
        ])
