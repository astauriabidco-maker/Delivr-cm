"""
Integrations App - Configuration Service

Hybrid configuration service that reads from DB with fallback to settings/.env.
Uses Redis caching for performance.
"""

import logging
from typing import Any, Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """
    Mask a secret value for display.
    
    Args:
        value: The secret string to mask
        visible_chars: Number of characters to show at start
        
    Returns:
        Masked string like 'ACxx••••••••••'
    """
    if not value:
        return '(non configuré)'
    if len(value) <= visible_chars:
        return '•' * len(value)
    return value[:visible_chars] + '•' * min(12, len(value) - visible_chars)


class ConfigService:
    """
    Hybrid configuration service.
    
    Reads from DB (IntegrationConfig) with fallback to Django settings/.env.
    Caches results in Redis for performance.
    """
    
    CACHE_KEY = 'integration_config_v1'
    CACHE_TTL = 300  # 5 minutes
    
    @classmethod
    def get_config(cls) -> dict:
        """
        Get merged configuration from DB + settings.
        
        Priority:
        1. Database (IntegrationConfig)
        2. Django settings (from .env)
        3. Default values
        
        Returns:
            dict: Complete configuration dictionary
        """
        # Try cache first
        cached = cache.get(cls.CACHE_KEY)
        if cached:
            return cached
        
        # Import here to avoid circular imports
        from .models import IntegrationConfig
        
        try:
            config = IntegrationConfig.get_solo()
            
            result = {
                # WhatsApp Provider
                'active_whatsapp_provider': config.active_whatsapp_provider,
                'twilio_whatsapp_number': config.twilio_whatsapp_number,
                'meta_phone_number_id': config.meta_phone_number_id,
                'meta_verify_token': config.meta_verify_token,
                
                # Secrets from .env (read-only)
                'twilio_account_sid': getattr(settings, 'TWILIO_ACCOUNT_SID', ''),
                'twilio_auth_token': getattr(settings, 'TWILIO_AUTH_TOKEN', ''),
                'meta_api_token': getattr(settings, 'META_API_TOKEN', ''),
                
                # Pricing Engine
                'pricing_base_fare': config.pricing_base_fare,
                'pricing_cost_per_km': config.pricing_cost_per_km,
                'pricing_minimum_fare': config.pricing_minimum_fare,
                'platform_fee_percent': config.platform_fee_percent,
                'courier_debt_ceiling': config.courier_debt_ceiling,
                
                # External Services
                'osrm_base_url': config.osrm_base_url,
                'nominatim_base_url': config.nominatim_base_url,
                'redis_url': getattr(settings, 'REDIS_URL', ''),
            }
            
            # Cache the result
            cache.set(cls.CACHE_KEY, result, timeout=cls.CACHE_TTL)
            
            return result
            
        except Exception as e:
            logger.warning(f"[ConfigService] Failed to load from DB, using settings: {e}")
            return cls._get_fallback_config()
    
    @classmethod
    def _get_fallback_config(cls) -> dict:
        """Get configuration from Django settings as fallback."""
        return {
            'active_whatsapp_provider': getattr(settings, 'ACTIVE_WHATSAPP_PROVIDER', 'twilio'),
            'twilio_whatsapp_number': getattr(settings, 'TWILIO_WHATSAPP_NUMBER', ''),
            'meta_phone_number_id': getattr(settings, 'META_PHONE_NUMBER_ID', ''),
            'meta_verify_token': getattr(settings, 'META_VERIFY_TOKEN', ''),
            'twilio_account_sid': getattr(settings, 'TWILIO_ACCOUNT_SID', ''),
            'twilio_auth_token': getattr(settings, 'TWILIO_AUTH_TOKEN', ''),
            'meta_api_token': getattr(settings, 'META_API_TOKEN', ''),
            'pricing_base_fare': getattr(settings, 'PRICING_BASE_FARE', 500),
            'pricing_cost_per_km': getattr(settings, 'PRICING_COST_PER_KM', 150),
            'pricing_minimum_fare': getattr(settings, 'PRICING_MINIMUM_FARE', 1000),
            'platform_fee_percent': getattr(settings, 'PLATFORM_FEE_PERCENT', 20),
            'courier_debt_ceiling': getattr(settings, 'COURIER_DEBT_CEILING', 2500),
            'osrm_base_url': getattr(settings, 'OSRM_BASE_URL', 'http://osrm:5000'),
            'nominatim_base_url': getattr(settings, 'NOMINATIM_BASE_URL', 'http://nominatim:8080'),
            'redis_url': getattr(settings, 'REDIS_URL', ''),
        }
    
    @classmethod
    def invalidate_cache(cls) -> None:
        """Invalidate the configuration cache."""
        cache.delete(cls.CACHE_KEY)
        logger.info("[ConfigService] Cache invalidated")
    
    @classmethod
    def get_env_secrets_display(cls) -> dict:
        """
        Get secrets from .env for display (masked).
        
        Returns:
            dict: Masked secret values for UI display
        """
        return {
            'twilio_account_sid': mask_secret(getattr(settings, 'TWILIO_ACCOUNT_SID', '')),
            'twilio_auth_token': mask_secret(getattr(settings, 'TWILIO_AUTH_TOKEN', '')),
            'meta_api_token': mask_secret(getattr(settings, 'META_API_TOKEN', '')),
            'redis_url': mask_secret(getattr(settings, 'REDIS_URL', ''), visible_chars=10),
            'db_password': '••••••••',
            'secret_key': '••••••••',
        }
    
    @classmethod
    def get_pricing_config(cls) -> dict:
        """Get only pricing-related configuration."""
        config = cls.get_config()
        return {
            'base_fare': config['pricing_base_fare'],
            'cost_per_km': config['pricing_cost_per_km'],
            'minimum_fare': config['pricing_minimum_fare'],
            'platform_fee_percent': config['platform_fee_percent'],
            'courier_debt_ceiling': config['courier_debt_ceiling'],
        }
    
    @classmethod
    def get_whatsapp_config(cls) -> dict:
        """Get only WhatsApp-related configuration."""
        config = cls.get_config()
        return {
            'provider': config['active_whatsapp_provider'],
            'twilio_sid': config['twilio_account_sid'],
            'twilio_token': config['twilio_auth_token'],
            'twilio_number': config['twilio_whatsapp_number'],
            'meta_token': config['meta_api_token'],
            'meta_phone_id': config['meta_phone_number_id'],
            'meta_verify_token': config['meta_verify_token'],
        }


class ConnectionTester:
    """Test connections to external services."""
    
    @staticmethod
    def test_osrm(url: str = None) -> dict:
        """Test OSRM connection."""
        import requests
        
        if not url:
            url = ConfigService.get_config().get('osrm_base_url', 'http://osrm:5000')
        
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                return {'status': 'ok', 'message': 'OSRM connecté'}
            return {'status': 'error', 'message': f'OSRM: HTTP {response.status_code}'}
        except requests.exceptions.RequestException as e:
            return {'status': 'error', 'message': f'OSRM: {str(e)[:50]}'}
    
    @staticmethod
    def test_nominatim(url: str = None) -> dict:
        """Test Nominatim connection."""
        import requests
        
        if not url:
            url = ConfigService.get_config().get('nominatim_base_url', 'http://nominatim:8080')
        
        try:
            response = requests.get(f"{url}/status", timeout=5)
            if response.status_code == 200:
                return {'status': 'ok', 'message': 'Nominatim connecté'}
            return {'status': 'error', 'message': f'Nominatim: HTTP {response.status_code}'}
        except requests.exceptions.RequestException as e:
            return {'status': 'error', 'message': f'Nominatim: {str(e)[:50]}'}
    
    @staticmethod
    def test_redis() -> dict:
        """Test Redis connection."""
        try:
            from django.core.cache import cache
            cache.set('_test_connection', 'ok', timeout=5)
            result = cache.get('_test_connection')
            cache.delete('_test_connection')
            
            if result == 'ok':
                return {'status': 'ok', 'message': 'Redis connecté'}
            return {'status': 'error', 'message': 'Redis: lecture échouée'}
        except Exception as e:
            return {'status': 'error', 'message': f'Redis: {str(e)[:50]}'}
    
    @staticmethod
    def test_twilio() -> dict:
        """Test Twilio connection."""
        try:
            from twilio.rest import Client
            
            sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
            token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            
            if not sid or not token:
                return {'status': 'warning', 'message': 'Twilio: credentials manquants'}
            
            client = Client(sid, token)
            account = client.api.accounts(sid).fetch()
            
            return {'status': 'ok', 'message': f'Twilio: {account.friendly_name}'}
        except Exception as e:
            return {'status': 'error', 'message': f'Twilio: {str(e)[:50]}'}
    
    @staticmethod
    def test_meta() -> dict:
        """Test Meta WhatsApp API connection."""
        import requests
        
        token = getattr(settings, 'META_API_TOKEN', '')
        phone_id = ConfigService.get_config().get('meta_phone_number_id', '')
        
        if not token or not phone_id:
            return {'status': 'warning', 'message': 'Meta: credentials manquants'}
        
        try:
            url = f"{getattr(settings, 'META_API_URL', 'https://graph.facebook.com/v17.0')}/{phone_id}"
            headers = {'Authorization': f'Bearer {token}'}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return {'status': 'ok', 'message': 'Meta API connecté'}
            return {'status': 'error', 'message': f'Meta: HTTP {response.status_code}'}
        except requests.exceptions.RequestException as e:
            return {'status': 'error', 'message': f'Meta: {str(e)[:50]}'}
    
    @classmethod
    def test_all(cls) -> dict:
        """Test all connections."""
        return {
            'osrm': cls.test_osrm(),
            'nominatim': cls.test_nominatim(),
            'redis': cls.test_redis(),
            'twilio': cls.test_twilio(),
            'meta': cls.test_meta(),
        }
