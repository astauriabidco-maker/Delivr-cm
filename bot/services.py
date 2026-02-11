"""
BOT App - WhatsApp Chatbot State Management for DELIVR-CM

Uses Redis to manage conversation states for WhatsApp bot interactions.
Includes Twilio integration for real WhatsApp messaging.
"""

import json
import logging
from enum import Enum
from typing import Optional, Any, Dict
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


# ===========================================
# TWILIO SERVICE
# ===========================================

class TwilioService:
    """
    Twilio WhatsApp integration service.
    
    Handles sending WhatsApp messages and parsing incoming webhook data.
    """
    
    _client = None
    
    @classmethod
    def get_client(cls):
        """Get or create Twilio client (singleton pattern)."""
        if cls._client is None:
            try:
                from twilio.rest import Client
                cls._client = Client(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN
                )
            except ImportError:
                logger.error("[TWILIO] Twilio SDK not installed. Run: pip install twilio")
                raise
            except Exception as e:
                logger.error(f"[TWILIO] Failed to initialize client: {e}")
                raise
        return cls._client
    
    @classmethod
    def send_message(cls, to_number: str, text: str) -> Optional[str]:
        """
        Send a WhatsApp message via Twilio.
        
        Args:
            to_number: Recipient phone number (format: +237XXXXXXXXX or whatsapp:+237XXXXXXXXX)
            text: Message text to send
            
        Returns:
            Message SID if successful, None if failed
        """
        # Ensure WhatsApp format
        if not to_number.startswith('whatsapp:'):
            to_number = f"whatsapp:{to_number}"
        
        from_number = settings.TWILIO_WHATSAPP_NUMBER
        
        try:
            client = cls.get_client()
            message = client.messages.create(
                from_=from_number,
                to=to_number,
                body=text
            )
            logger.info(f"[TWILIO] Message sent: SID={message.sid} to={to_number}")
            return message.sid
        except Exception as e:
            logger.error(f"[TWILIO] Failed to send message to {to_number}: {e}")
            return None
    
    @staticmethod
    def parse_incoming_data(request_data: Dict) -> Dict:
        """
        Parse incoming Twilio webhook data.
        
        Twilio sends data as application/x-www-form-urlencoded.
        
        Args:
            request_data: Django request.POST or request.data dictionary
            
        Returns:
            Parsed data dictionary with keys:
            - from_number: Sender's WhatsApp number (e.g., 'whatsapp:+237699123456')
            - phone_normalized: Phone without 'whatsapp:' prefix (e.g., '+237699123456')
            - body: Message text content
            - has_location: Boolean indicating if location data is present
            - latitude: Float latitude if location message
            - longitude: Float longitude if location message
        """
        # Extract sender number (format: whatsapp:+237XXXXXXXXX)
        from_number = request_data.get('From', '')
        
        # Normalize phone number (remove whatsapp: prefix)
        phone_normalized = from_number.replace('whatsapp:', '').strip()
        
        # Extract message body
        body = request_data.get('Body', '').strip()
        
        # Extract location data (only present for location messages)
        latitude = request_data.get('Latitude')
        longitude = request_data.get('Longitude')
        
        has_location = latitude is not None and longitude is not None
        
        parsed = {
            'from_number': from_number,
            'phone_normalized': phone_normalized,
            'body': body,
            'has_location': has_location,
            'latitude': float(latitude) if latitude else None,
            'longitude': float(longitude) if longitude else None,
        }
        
        logger.info(f"[TWILIO] Parsed incoming: from={phone_normalized}, body={body[:30]}..., location={has_location}")
        
        return parsed


# ===========================================
# META WHATSAPP CLOUD API SERVICE
# ===========================================

class MetaWhatsAppService:
    """
    Meta WhatsApp Cloud API integration service.
    
    Handles sending WhatsApp messages and parsing incoming webhook data
    from Meta's Graph API.
    """
    
    API_URL = "https://graph.facebook.com/v17.0/"
    
    @classmethod
    def send_message(cls, to_number: str, text: str) -> Optional[str]:
        """
        Send a WhatsApp message via Meta Cloud API.
        
        Args:
            to_number: Recipient phone number (format: +237XXXXXXXXX)
            text: Message text to send
            
        Returns:
            Message ID if successful, None if failed
        """
        import requests
        
        # Clean phone number (remove + and any prefix)
        phone = to_number.replace('+', '').replace('whatsapp:', '').strip()
        
        phone_number_id = settings.META_PHONE_NUMBER_ID
        access_token = settings.META_API_TOKEN
        
        if not phone_number_id or not access_token:
            logger.error("[META] Missing META_PHONE_NUMBER_ID or META_API_TOKEN")
            return None
        
        url = f"{settings.META_API_URL}/{phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            message_id = data.get('messages', [{}])[0].get('id')
            
            logger.info(f"[META] Message sent: ID={message_id} to={phone}")
            return message_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[META] Failed to send message to {phone}: {e}")
            return None
    
    @staticmethod
    def parse_incoming_data(request_data: Dict) -> Dict:
        """
        Parse incoming Meta webhook data.
        
        Meta sends a complex nested JSON structure.
        
        Args:
            request_data: Django request.data (JSON)
            
        Returns:
            Parsed data dictionary with keys:
            - from_number: Sender's phone number (e.g., '+237699123456')
            - phone_normalized: Same as from_number for Meta
            - body: Message text content
            - has_location: Boolean indicating if location data is present
            - latitude: Float latitude if location message
            - longitude: Float longitude if location message
            - message_type: 'text' or 'location'
        """
        parsed = {
            'from_number': '',
            'phone_normalized': '',
            'body': '',
            'has_location': False,
            'latitude': None,
            'longitude': None,
            'message_type': 'text',
        }
        
        try:
            # Navigate the nested Meta structure
            # {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [...]}}]}]}
            entry = request_data.get('entry', [])
            if not entry:
                return parsed
            
            changes = entry[0].get('changes', [])
            if not changes:
                return parsed
            
            value = changes[0].get('value', {})
            messages = value.get('messages', [])
            
            if not messages:
                return parsed
            
            message = messages[0]
            
            # Extract phone number
            from_number = message.get('from', '')
            parsed['from_number'] = f"+{from_number}" if from_number and not from_number.startswith('+') else from_number
            parsed['phone_normalized'] = parsed['from_number']
            
            # Determine message type
            msg_type = message.get('type', 'text')
            parsed['message_type'] = msg_type
            
            if msg_type == 'text':
                parsed['body'] = message.get('text', {}).get('body', '')
            
            elif msg_type == 'location':
                location = message.get('location', {})
                parsed['has_location'] = True
                parsed['latitude'] = float(location.get('latitude', 0))
                parsed['longitude'] = float(location.get('longitude', 0))
                parsed['body'] = ''  # Location messages have no text body
            
            elif msg_type == 'interactive':
                # Handle button/list replies
                interactive = message.get('interactive', {})
                if interactive.get('type') == 'button_reply':
                    parsed['body'] = interactive.get('button_reply', {}).get('id', '')
                elif interactive.get('type') == 'list_reply':
                    parsed['body'] = interactive.get('list_reply', {}).get('id', '')
            
            logger.info(f"[META] Parsed incoming: from={parsed['phone_normalized']}, type={msg_type}, body={parsed['body'][:30]}...")
            
        except Exception as e:
            logger.error(f"[META] Failed to parse incoming data: {e}")
        
        return parsed


# ===========================================
# UNIFIED WHATSAPP NOTIFICATION UTILITY
# ===========================================

def send_whatsapp_notification(to_number: str, text: str) -> Optional[str]:
    """
    Send a WhatsApp notification using the active provider.
    
    This utility function reads the active provider from IntegrationConfig
    (via ConfigService) and routes the message to the appropriate service.
    
    Args:
        to_number: Recipient phone number
        text: Message text to send
        
    Returns:
        Message ID/SID if successful, None if failed
    """
    # Try to get provider from ConfigService, fallback to settings
    try:
        from integrations.services import ConfigService
        config = ConfigService.get_whatsapp_config()
        provider = config.get('provider', 'twilio').lower()
    except Exception:
        provider = getattr(settings, 'ACTIVE_WHATSAPP_PROVIDER', 'twilio').lower()
    
    if provider == 'meta':
        logger.info(f"[NOTIFICATION] Using Meta provider for {to_number}")
        return MetaWhatsAppService.send_message(to_number, text)
    else:
        # Default to Twilio
        logger.info(f"[NOTIFICATION] Using Twilio provider for {to_number}")
        return TwilioService.send_message(to_number, text)


def send_notification_with_fallback(to_number: str, text: str) -> tuple[Optional[str], str]:
    """
    Send notification with SMS fallback if WhatsApp fails.
    
    Flow:
    1. Try WhatsApp (active provider)
    2. If fails and SMS_FALLBACK_ENABLED -> try Orange SMS
    
    Args:
        to_number: Recipient phone number
        text: Message text to send
        
    Returns:
        Tuple of (message_id, channel_used) where channel is 'whatsapp' or 'sms'
    """
    # Try WhatsApp first
    result = send_whatsapp_notification(to_number, text)
    
    if result:
        logger.info(f"[NOTIFICATION] Sent via WhatsApp: {result}")
        return (result, 'whatsapp')
    
    # Check if SMS fallback is enabled
    sms_fallback_enabled = getattr(settings, 'SMS_FALLBACK_ENABLED', False)
    
    if not sms_fallback_enabled:
        logger.warning(f"[NOTIFICATION] WhatsApp failed, SMS fallback disabled")
        return (None, 'failed')
    
    # Fallback to SMS
    logger.info(f"[NOTIFICATION] WhatsApp failed, trying SMS fallback for {to_number}")
    
    try:
        from bot.sms_service import OrangeSMSService
        sms_result = OrangeSMSService.send_sms(to_number, text)
        
        if sms_result:
            logger.info(f"[NOTIFICATION] Sent via SMS: {sms_result}")
            return (sms_result, 'sms')
        else:
            logger.error(f"[NOTIFICATION] Both WhatsApp and SMS failed for {to_number}")
            return (None, 'failed')
            
    except Exception as e:
        logger.error(f"[NOTIFICATION] SMS fallback error: {e}")
        return (None, 'failed')


def send_whatsapp_message(to_number: str, text: str) -> Optional[str]:
    """
    Alias for send_notification_with_fallback (for backward compatibility).
    
    Returns just the message ID (discards channel info).
    """
    result, _ = send_notification_with_fallback(to_number, text)
    return result


def send_whatsapp_document(
    phone: str,
    document_url: str,
    filename: str,
    caption: str = ""
) -> Optional[str]:
    """
    Send a document (PDF) via WhatsApp using Meta Cloud API.
    
    Args:
        phone: Recipient phone number
        document_url: Public URL to the document
        filename: Display filename for the document
        caption: Optional caption text
        
    Returns:
        Message ID if successful, None if failed
    """
    import requests
    
    # Clean phone number
    phone_clean = phone.replace('+', '').replace('whatsapp:', '').strip()
    
    phone_number_id = getattr(settings, 'META_PHONE_NUMBER_ID', None)
    access_token = getattr(settings, 'META_API_TOKEN', None)
    api_url = getattr(settings, 'META_API_URL', 'https://graph.facebook.com/v17.0')
    
    if not phone_number_id or not access_token:
        logger.error("[META] Missing META_PHONE_NUMBER_ID or META_API_TOKEN for document send")
        return None
    
    url = f"{api_url}/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_clean,
        "type": "document",
        "document": {
            "link": document_url,
            "filename": filename,
            "caption": caption
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        message_id = data.get('messages', [{}])[0].get('id')
        
        logger.info(f"[META] Document sent: ID={message_id} to={phone_clean} file={filename}")
        return message_id
        
    except requests.exceptions.RequestException as e:
        logger.error(f"[META] Failed to send document to {phone_clean}: {e}")
        return None



class BotState(str, Enum):
    """Conversation state enumeration for the WhatsApp bot."""
    IDLE = 'IDLE'
    ASK_PICKUP_GEO = 'ASK_PICKUP_GEO'
    ASK_DROPOFF_GEO = 'ASK_DROPOFF_GEO'
    ASK_RECIPIENT_PHONE = 'ASK_RECIPIENT_PHONE'
    ASK_CONFIRMATION = 'ASK_CONFIRMATION'


class BotStateManager:
    """
    Manages conversation state in Redis for WhatsApp bot.
    
    Each user (identified by phone number) has:
    - State key: Current conversation state
    - Data key: Temporary data collected during conversation
    
    TTL: 1 hour (conversations expire after inactivity)
    """
    
    STATE_PREFIX = 'bot_state:'
    DATA_PREFIX = 'bot_data:'
    TTL_SECONDS = 3600  # 1 hour
    
    def __init__(self, phone_number: str):
        """
        Initialize state manager for a specific user.
        
        Args:
            phone_number: User's WhatsApp phone number (format: +237XXXXXXXXX)
        """
        self.phone_number = self._normalize_phone(phone_number)
        self.state_key = f"{self.STATE_PREFIX}{self.phone_number}"
        self.data_key = f"{self.DATA_PREFIX}{self.phone_number}"
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to consistent format."""
        phone = phone.strip().replace(' ', '')
        if not phone.startswith('+'):
            if phone.startswith('237'):
                phone = f'+{phone}'
            else:
                phone = f'+237{phone}'
        return phone
    
    def get_state(self) -> BotState:
        """Get current conversation state."""
        state_value = cache.get(self.state_key)
        if state_value is None:
            return BotState.IDLE
        try:
            return BotState(state_value)
        except ValueError:
            return BotState.IDLE
    
    def set_state(self, state: BotState) -> None:
        """Set conversation state with TTL."""
        cache.set(self.state_key, state.value, timeout=self.TTL_SECONDS)
        logger.info(f"[BOT] State set: {self.phone_number} -> {state.value}")
    
    def get_data(self) -> dict:
        """Get all conversation data."""
        data = cache.get(self.data_key)
        if data is None:
            return {}
        if isinstance(data, str):
            return json.loads(data)
        return data
    
    def set_data(self, key: str, value: Any) -> None:
        """Set a single data field (preserves other fields)."""
        data = self.get_data()
        data[key] = value
        cache.set(self.data_key, json.dumps(data), timeout=self.TTL_SECONDS)
        logger.info(f"[BOT] Data set: {self.phone_number} -> {key}={value}")
    
    def get_data_value(self, key: str, default: Any = None) -> Any:
        """Get a specific data field."""
        return self.get_data().get(key, default)
    
    def clear(self) -> None:
        """Clear all state and data (reset conversation)."""
        cache.delete(self.state_key)
        cache.delete(self.data_key)
        logger.info(f"[BOT] Cleared conversation data for {self.phone_number}")
    
    def reset_to_new_order(self) -> None:
        """Reset and start a new order flow."""
        self.clear()
        self.set_state(BotState.ASK_PICKUP_GEO)


class BotMessageBuilder:
    """Helper class to build WhatsApp response messages."""
    
    @staticmethod
    def welcome() -> str:
        return (
            "👋 Bienvenue sur *DELIVR-CM* !\n\n"
            "📍 Envoyez votre *position GPS* de retrait du colis.\n\n"
            "✅ _Livré avec confiance_"
        )
    
    @staticmethod
    def ask_dropoff() -> str:
        return (
            "✅ Position de retrait reçue !\n\n"
            "📍 Maintenant, envoyez la *position GPS de livraison*.\n\n"
            "_Où le colis doit-il être livré ?_"
        )
    
    @staticmethod
    def ask_recipient_phone() -> str:
        return (
            "✅ Position de livraison reçue !\n\n"
            "📱 Quel est le *numéro WhatsApp du destinataire* ?\n\n"
            "_Exemple: 699123456_"
        )
    
    @staticmethod
    def confirm_order(distance_km: float, price: int) -> str:
        return (
            f"📦 *Récapitulatif de votre commande*\n\n"
            f"📏 Distance : *{distance_km:.1f} km*\n"
            f"💰 Prix : *{price:,} FCFA*\n\n"
            f"Tapez *OUI* pour confirmer et lancer la recherche d'un coursier.\n"
            f"Tapez *NON* pour annuler."
        )
    
    @staticmethod
    def order_created(delivery_id: str, otp_code: str) -> str:
        return (
            f"🎉 *Commande créée avec succès !*\n\n"
            f"📦 Numéro : *#{delivery_id[:8].upper()}*\n"
            f"🔐 Code OTP : *{otp_code}*\n\n"
            f"🔍 _Recherche d'un coursier en cours..._\n\n"
            f"⚠️ Conservez le code OTP, il sera demandé à la livraison."
        )
    
    @staticmethod
    def order_cancelled() -> str:
        return (
            "❌ Commande annulée.\n\n"
            "Pour passer une nouvelle commande, tapez *NOUVEAU*"
        )
    
    @staticmethod
    def invalid_location() -> str:
        return (
            "⚠️ Je n'ai pas reçu de position GPS valide.\n\n"
            "📍 Veuillez utiliser le bouton *📎 > Localisation* "
            "dans WhatsApp pour partager votre position."
        )
    
    @staticmethod
    def invalid_phone() -> str:
        return (
            "⚠️ Numéro de téléphone invalide.\n\n"
            "📱 Entrez un numéro camerounais valide.\n"
            "_Exemple: 699123456 ou +237699123456_"
        )
    
    @staticmethod
    def unknown_command() -> str:
        return (
            "🤔 Je n'ai pas compris.\n\n"
            "Pour passer une commande, tapez *NOUVEAU*\n"
            "Pour obtenir de l'aide, tapez *AIDE*"
        )
    
    @staticmethod
    def help_message() -> str:
        return (
            "✅ *DELIVR-CM - Aide*\n\n"
            "📦 *NOUVEAU* - Passer une nouvelle commande\n"
            "❓ *AIDE* - Afficher ce message\n\n"
            "_Livré avec confiance à Douala et Yaoundé_"
        )
