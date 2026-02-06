"""
BOT App - WhatsApp Webhook Views for DELIVR-CM

Includes:
- MockWhatsAppWebhook: Simulates WhatsApp for testing
- TwilioWebhookView: Real WhatsApp integration via Twilio
"""

import re
import logging
from decimal import Decimal
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.gis.geos import Point
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .services import BotState, BotStateManager, BotMessageBuilder, TwilioService, MetaWhatsAppService
from .courier_commands import CourierBotCommands
from logistics.models import Delivery, PaymentMethod, DeliveryStatus
from logistics.utils import get_routing_data, calculate_delivery_price
from core.models import User, UserRole

logger = logging.getLogger(__name__)


class MockWhatsAppWebhook(APIView):
    """
    Mock WhatsApp Webhook endpoint for testing bot flow.
    
    Simulates incoming WhatsApp messages and processes them through
    the chatbot state machine.
    
    POST /webhooks/mock-whatsapp/
    
    Request body:
    {
        "from": "237699123456",       # Sender phone number
        "message": "...",              # Text message (if type=text)
        "type": "text|location",       # Message type
        "lat": 4.0511,                 # Latitude (if type=location)
        "lng": 9.6942                  # Longitude (if type=location)
    }
    """
    
    permission_classes = [AllowAny]  # Webhooks are verified by token, not auth
    
    def post(self, request):
        """Process incoming WhatsApp message."""
        data = request.data
        
        # Extract message data
        phone = data.get('from', '')
        message = data.get('message', '').strip().upper()
        msg_type = data.get('type', 'text')
        lat = data.get('lat')
        lng = data.get('lng')
        
        if not phone:
            return Response(
                {'error': 'Missing "from" field'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Initialize state manager
        state_mgr = BotStateManager(phone)
        current_state = state_mgr.get_state()
        
        logger.info(f"[WEBHOOK] From: {phone} | State: {current_state.value} | Type: {msg_type} | Msg: {message[:50]}")
        
        # ============================================
        # COMMAND HANDLING (Any state)
        # ============================================
        
        if message in ['NOUVEAU', '/START', 'START', 'COMMENCER']:
            state_mgr.reset_to_new_order()
            return self._respond(BotMessageBuilder.welcome())
        
        if message in ['AIDE', 'HELP', '?']:
            return self._respond(BotMessageBuilder.help_message())
        
        # ============================================
        # STATE MACHINE
        # ============================================
        
        if current_state == BotState.IDLE:
            return self._respond(BotMessageBuilder.unknown_command())
        
        elif current_state == BotState.ASK_PICKUP_GEO:
            return self._handle_pickup_geo(state_mgr, msg_type, lat, lng)
        
        elif current_state == BotState.ASK_RECIPIENT_PHONE:
            return self._handle_recipient_phone(state_mgr, message, data.get('message', ''))
        
        elif current_state == BotState.ASK_CONFIRMATION:
            return self._handle_confirmation(state_mgr, message, phone)
        
        return self._respond(BotMessageBuilder.unknown_command())
    
    def _respond(self, message: str, extra: dict = None) -> Response:
        """Build JSON response."""
        response_data = {
            'status': 'ok',
            'reply': message
        }
        if extra:
            response_data.update(extra)
        return Response(response_data)
    
    def _handle_pickup_geo(self, state_mgr: BotStateManager, msg_type: str, lat, lng) -> Response:
        """
        Handle pickup location state.
        
        Flow simplification: We only ask for pickup GPS.
        Dropoff will be determined when the recipient confirms their location.
        For price estimation, we use a simulated 5km delivery distance.
        """
        if msg_type != 'location' or lat is None or lng is None:
            return self._respond(BotMessageBuilder.invalid_location())
        
        # Save pickup coordinates
        state_mgr.set_data('pickup_lat', float(lat))
        state_mgr.set_data('pickup_lng', float(lng))
        
        # Simulate dropoff location (offset ~5km for price estimation)
        # In production, this would be collected from recipient via WhatsApp
        state_mgr.set_data('dropoff_lat', float(lat) + 0.045)  # ~5km north
        state_mgr.set_data('dropoff_lng', float(lng) + 0.045)  # ~5km east
        
        # Go directly to asking for recipient phone
        state_mgr.set_state(BotState.ASK_RECIPIENT_PHONE)
        
        return self._respond(BotMessageBuilder.ask_recipient_phone())
    
    def _handle_recipient_phone(self, state_mgr: BotStateManager, message: str, raw_message: str) -> Response:
        """Handle recipient phone number state."""
        # Normalize phone number
        phone = raw_message.strip().replace(' ', '').replace('-', '')
        
        # Basic validation (Cameroon numbers)
        phone_pattern = r'^(\+?237)?[26][0-9]{8}$'
        if not re.match(phone_pattern, phone):
            return self._respond(BotMessageBuilder.invalid_phone())
        
        # Normalize to +237 format
        if not phone.startswith('+'):
            if phone.startswith('237'):
                phone = f'+{phone}'
            else:
                phone = f'+237{phone}'
        
        state_mgr.set_data('recipient_phone', phone)
        
        # Calculate price using the pricing engine
        pickup_lat = state_mgr.get_data_value('pickup_lat')
        pickup_lng = state_mgr.get_data_value('pickup_lng')
        dropoff_lat = state_mgr.get_data_value('dropoff_lat')
        dropoff_lng = state_mgr.get_data_value('dropoff_lng')
        
        # Get route and price
        routing = get_routing_data(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        pricing = calculate_delivery_price(routing['distance_km'])
        
        # Save pricing data
        state_mgr.set_data('distance_km', routing['distance_km'])
        state_mgr.set_data('duration_min', routing['duration_min'])
        state_mgr.set_data('client_price', pricing['client_price'])
        state_mgr.set_data('platform_fee', pricing['platform_fee'])
        state_mgr.set_data('courier_earning', pricing['courier_earning'])
        
        state_mgr.set_state(BotState.ASK_CONFIRMATION)
        
        return self._respond(
            BotMessageBuilder.confirm_order(
                distance_km=routing['distance_km'],
                price=pricing['client_price']
            )
        )
    
    @transaction.atomic
    def _handle_confirmation(self, state_mgr: BotStateManager, message: str, sender_phone: str) -> Response:
        """Handle order confirmation state."""
        if message in ['NON', 'NO', 'ANNULER', 'CANCEL']:
            state_mgr.clear()
            return self._respond(BotMessageBuilder.order_cancelled())
        
        if message not in ['OUI', 'YES', 'OK', 'CONFIRMER']:
            return self._respond(
                "⚠️ Tapez *OUI* pour confirmer ou *NON* pour annuler."
            )
        
        # Get all collected data
        data = state_mgr.get_data()
        
        # Get or create sender user
        sender, _ = User.objects.get_or_create(
            phone_number=state_mgr._normalize_phone(sender_phone),
            defaults={'role': UserRole.CLIENT}
        )
        
        # Build GPS points
        pickup_point = Point(
            data['pickup_lng'],
            data['pickup_lat'],
            srid=4326
        )
        dropoff_point = Point(
            data['dropoff_lng'],
            data['dropoff_lat'],
            srid=4326
        )
        
        # Create delivery
        delivery = Delivery.objects.create(
            sender=sender,
            recipient_phone=data['recipient_phone'],
            pickup_geo=pickup_point,
            dropoff_geo=dropoff_point,
            payment_method=PaymentMethod.CASH_P2P,
            distance_km=data['distance_km'],
            total_price=Decimal(str(data['client_price'])),
            platform_fee=Decimal(str(data['platform_fee'])),
            courier_earning=Decimal(str(data['courier_earning'])),
            status=DeliveryStatus.PENDING
        )
        
        logger.info(f"[WEBHOOK] Created delivery {delivery.id} for {sender_phone}")
        
        # Clear conversation state
        state_mgr.clear()
        
        return self._respond(
            BotMessageBuilder.order_created(
                delivery_id=str(delivery.id),
                otp_code=delivery.otp_code
            ),
            extra={
                'delivery_id': str(delivery.id),
                'otp_code': delivery.otp_code
            }
        )


# ===========================================
# TWILIO WEBHOOK VIEW (Real WhatsApp)
# ===========================================

@method_decorator(csrf_exempt, name='dispatch')
class TwilioWebhookView(APIView):
    """
    Real WhatsApp Webhook endpoint via Twilio.
    
    Receives incoming WhatsApp messages from Twilio and processes them
    through the chatbot state machine, sending responses back to users
    on their actual WhatsApp.
    
    POST /webhooks/twilio/
    
    Twilio sends data as: application/x-www-form-urlencoded
    - From: whatsapp:+237XXXXXXXXX
    - Body: Text message content
    - Latitude/Longitude: If location message
    """
    
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Process incoming Twilio WhatsApp webhook."""
        # Parse Twilio data
        parsed = TwilioService.parse_incoming_data(request.data)
        
        phone = parsed['phone_normalized']
        body = parsed['body'].strip().upper()
        has_location = parsed['has_location']
        lat = parsed['latitude']
        lng = parsed['longitude']
        
        if not phone:
            logger.warning("[TWILIO] Received webhook without phone number")
            return HttpResponse("OK")
        
        # Initialize state manager
        state_mgr = BotStateManager(phone)
        current_state = state_mgr.get_state()
        
        logger.info(f"[TWILIO] From: {phone} | State: {current_state.value} | Location: {has_location} | Body: {body[:30]}")
        
        # ============================================
        # COURIER COMMAND HANDLING (Priority)
        # ============================================
        
        # Check if this is a courier command
        courier_response, was_handled = CourierBotCommands.handle_command(phone, parsed['body'])
        if was_handled:
            self._send_reply(phone, courier_response)
            return HttpResponse("OK")
        
        # Courier help
        if body in ['AIDE COURSIER', 'HELP COURSIER', 'COURRIER']:
            self._send_reply(phone, CourierBotCommands.get_courier_help_message())
            return HttpResponse("OK")
        
        # ============================================
        # CLIENT COMMAND HANDLING (Any state)
        # ============================================
        
        if body in ['NOUVEAU', '/START', 'START', 'COMMENCER', 'JOIN YOURCODE']:
            # 'JOIN YOURCODE' is Twilio sandbox join command
            state_mgr.reset_to_new_order()
            self._send_reply(phone, BotMessageBuilder.welcome())
            return HttpResponse("OK")
        
        if body in ['AIDE', 'HELP', '?']:
            self._send_reply(phone, BotMessageBuilder.help_message())
            return HttpResponse("OK")
        
        # ============================================
        # STATE MACHINE
        # ============================================
        
        if current_state == BotState.IDLE:
            self._send_reply(phone, BotMessageBuilder.unknown_command())
            return HttpResponse("OK")
        
        elif current_state == BotState.ASK_PICKUP_GEO:
            self._handle_pickup_geo(state_mgr, phone, has_location, lat, lng)
            return HttpResponse("OK")
        
        elif current_state == BotState.ASK_RECIPIENT_PHONE:
            self._handle_recipient_phone(state_mgr, phone, parsed['body'])
            return HttpResponse("OK")
        
        elif current_state == BotState.ASK_CONFIRMATION:
            self._handle_confirmation(state_mgr, phone, body)
            return HttpResponse("OK")
        
        self._send_reply(phone, BotMessageBuilder.unknown_command())
        return HttpResponse("OK")
    
    def _send_reply(self, to_phone: str, message: str) -> None:
        """Send WhatsApp reply via Twilio."""
        TwilioService.send_message(to_phone, message)
    
    def _handle_pickup_geo(self, state_mgr: BotStateManager, phone: str, has_location: bool, lat, lng) -> None:
        """Handle pickup location state."""
        if not has_location or lat is None or lng is None:
            self._send_reply(phone, BotMessageBuilder.invalid_location())
            return
        
        # Save pickup coordinates
        state_mgr.set_data('pickup_lat', float(lat))
        state_mgr.set_data('pickup_lng', float(lng))
        
        # Simulate dropoff location (offset ~5km for price estimation)
        state_mgr.set_data('dropoff_lat', float(lat) + 0.045)
        state_mgr.set_data('dropoff_lng', float(lng) + 0.045)
        
        # Go directly to asking for recipient phone
        state_mgr.set_state(BotState.ASK_RECIPIENT_PHONE)
        
        self._send_reply(phone, BotMessageBuilder.ask_recipient_phone())
    
    def _handle_recipient_phone(self, state_mgr: BotStateManager, phone: str, raw_message: str) -> None:
        """Handle recipient phone number state."""
        # Normalize phone number
        recipient_phone = raw_message.strip().replace(' ', '').replace('-', '')
        
        # Basic validation (Cameroon numbers)
        phone_pattern = r'^(\+?237)?[26][0-9]{8}$'
        if not re.match(phone_pattern, recipient_phone):
            self._send_reply(phone, BotMessageBuilder.invalid_phone())
            return
        
        # Normalize to +237 format
        if not recipient_phone.startswith('+'):
            if recipient_phone.startswith('237'):
                recipient_phone = f'+{recipient_phone}'
            else:
                recipient_phone = f'+237{recipient_phone}'
        
        state_mgr.set_data('recipient_phone', recipient_phone)
        
        # Calculate price
        pickup_lat = state_mgr.get_data_value('pickup_lat')
        pickup_lng = state_mgr.get_data_value('pickup_lng')
        dropoff_lat = state_mgr.get_data_value('dropoff_lat')
        dropoff_lng = state_mgr.get_data_value('dropoff_lng')
        
        routing = get_routing_data(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        pricing = calculate_delivery_price(routing['distance_km'])
        
        # Save pricing data
        state_mgr.set_data('distance_km', routing['distance_km'])
        state_mgr.set_data('duration_min', routing['duration_min'])
        state_mgr.set_data('client_price', pricing['client_price'])
        state_mgr.set_data('platform_fee', pricing['platform_fee'])
        state_mgr.set_data('courier_earning', pricing['courier_earning'])
        
        state_mgr.set_state(BotState.ASK_CONFIRMATION)
        
        self._send_reply(
            phone,
            BotMessageBuilder.confirm_order(
                distance_km=routing['distance_km'],
                price=pricing['client_price']
            )
        )
    
    @transaction.atomic
    def _handle_confirmation(self, state_mgr: BotStateManager, phone: str, message: str) -> None:
        """Handle order confirmation state."""
        if message in ['NON', 'NO', 'ANNULER', 'CANCEL']:
            state_mgr.clear()
            self._send_reply(phone, BotMessageBuilder.order_cancelled())
            return
        
        if message not in ['OUI', 'YES', 'OK', 'CONFIRMER']:
            self._send_reply(phone, "⚠️ Tapez *OUI* pour confirmer ou *NON* pour annuler.")
            return
        
        # Get all collected data
        data = state_mgr.get_data()
        
        # Get or create sender user
        sender, _ = User.objects.get_or_create(
            phone_number=state_mgr._normalize_phone(phone),
            defaults={'role': UserRole.CLIENT}
        )
        
        # Build GPS points
        pickup_point = Point(data['pickup_lng'], data['pickup_lat'], srid=4326)
        dropoff_point = Point(data['dropoff_lng'], data['dropoff_lat'], srid=4326)
        
        # Create delivery
        delivery = Delivery.objects.create(
            sender=sender,
            recipient_phone=data['recipient_phone'],
            pickup_geo=pickup_point,
            dropoff_geo=dropoff_point,
            payment_method=PaymentMethod.CASH_P2P,
            distance_km=data['distance_km'],
            total_price=Decimal(str(data['client_price'])),
            platform_fee=Decimal(str(data['platform_fee'])),
            courier_earning=Decimal(str(data['courier_earning'])),
            status=DeliveryStatus.PENDING
        )
        
        logger.info(f"[TWILIO] Created delivery {delivery.id} for {phone}")
        
        # Clear conversation state
        state_mgr.clear()
        
        # Send success message
        self._send_reply(
            phone,
            BotMessageBuilder.order_created(
                delivery_id=str(delivery.id),
                otp_code=delivery.otp_code
            )
        )
        
        # Also notify recipient
        recipient_msg = (
            f"📦 *Livraison en cours vers vous !*\n\n"
            f"Un colis vous sera livré prochainement.\n"
            f"🔐 Code OTP : *{delivery.otp_code}*\n\n"
            f"_Conservez ce code, il sera demandé à la réception._"
        )
        TwilioService.send_message(data['recipient_phone'], recipient_msg)


# ===========================================
# META WHATSAPP CLOUD API WEBHOOK VIEW
# ===========================================

@method_decorator(csrf_exempt, name='dispatch')
class MetaWebhookView(APIView):
    """
    Meta WhatsApp Cloud API Webhook endpoint.
    
    Handles both webhook verification (GET) and incoming messages (POST).
    
    GET /webhooks/meta/ - Webhook verification handshake
    POST /webhooks/meta/ - Incoming message from WhatsApp
    """
    
    permission_classes = [AllowAny]
    
    def get(self, request):
        """
        Webhook verification handshake for Meta.
        
        Meta sends:
        - hub.mode: 'subscribe'
        - hub.verify_token: Your configured token
        - hub.challenge: Random string to return
        """
        from django.conf import settings
        
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        verify_token = getattr(settings, 'META_VERIFY_TOKEN', '')
        
        if mode == 'subscribe' and token == verify_token:
            logger.info("[META] Webhook verification successful")
            return HttpResponse(challenge, content_type='text/plain')
        
        logger.warning(f"[META] Webhook verification failed: mode={mode}, token_match={token == verify_token}")
        return HttpResponse("Verification failed", status=403)
    
    def post(self, request):
        """Process incoming Meta WhatsApp webhook."""
        # Parse Meta data
        parsed = MetaWhatsAppService.parse_incoming_data(request.data)
        
        phone = parsed['phone_normalized']
        body = parsed['body'].strip().upper()
        has_location = parsed['has_location']
        lat = parsed['latitude']
        lng = parsed['longitude']
        
        if not phone:
            # Could be a status update, not a message
            logger.debug("[META] Received webhook without phone (possibly status update)")
            return HttpResponse("OK")
        
        # Initialize state manager
        state_mgr = BotStateManager(phone)
        current_state = state_mgr.get_state()
        
        logger.info(f"[META] From: {phone} | State: {current_state.value} | Location: {has_location} | Body: {body[:30]}")
        
        # ============================================
        # COURIER COMMAND HANDLING (Priority)
        # ============================================
        
        # Check if this is a courier command
        courier_response, was_handled = CourierBotCommands.handle_command(phone, parsed['body'])
        if was_handled:
            self._send_reply(phone, courier_response)
            return HttpResponse("OK")
        
        # Courier help
        if body in ['AIDE COURSIER', 'HELP COURSIER', 'COURRIER']:
            self._send_reply(phone, CourierBotCommands.get_courier_help_message())
            return HttpResponse("OK")
        
        # ============================================
        # CLIENT COMMAND HANDLING (Any state)
        # ============================================
        
        if body in ['NOUVEAU', '/START', 'START', 'COMMENCER', 'BONJOUR', 'HELLO', 'HI']:
            state_mgr.reset_to_new_order()
            self._send_reply(phone, BotMessageBuilder.welcome())
            return HttpResponse("OK")
        
        if body in ['AIDE', 'HELP', '?']:
            self._send_reply(phone, BotMessageBuilder.help_message())
            return HttpResponse("OK")
        
        # ============================================
        # STATE MACHINE
        # ============================================
        
        if current_state == BotState.IDLE:
            self._send_reply(phone, BotMessageBuilder.unknown_command())
            return HttpResponse("OK")
        
        elif current_state == BotState.ASK_PICKUP_GEO:
            self._handle_pickup_geo(state_mgr, phone, has_location, lat, lng)
            return HttpResponse("OK")
        
        elif current_state == BotState.ASK_RECIPIENT_PHONE:
            self._handle_recipient_phone(state_mgr, phone, parsed['body'])
            return HttpResponse("OK")
        
        elif current_state == BotState.ASK_CONFIRMATION:
            self._handle_confirmation(state_mgr, phone, body)
            return HttpResponse("OK")
        
        self._send_reply(phone, BotMessageBuilder.unknown_command())
        return HttpResponse("OK")
    
    def _send_reply(self, to_phone: str, message: str) -> None:
        """Send WhatsApp reply via Meta Cloud API."""
        # Always respond on the same channel (Meta)
        MetaWhatsAppService.send_message(to_phone, message)
    
    def _handle_pickup_geo(self, state_mgr: BotStateManager, phone: str, has_location: bool, lat, lng) -> None:
        """Handle pickup location state."""
        if not has_location or lat is None or lng is None:
            self._send_reply(phone, BotMessageBuilder.invalid_location())
            return
        
        # Save pickup coordinates
        state_mgr.set_data('pickup_lat', float(lat))
        state_mgr.set_data('pickup_lng', float(lng))
        
        # Simulate dropoff location (offset ~5km for price estimation)
        state_mgr.set_data('dropoff_lat', float(lat) + 0.045)
        state_mgr.set_data('dropoff_lng', float(lng) + 0.045)
        
        # Go directly to asking for recipient phone
        state_mgr.set_state(BotState.ASK_RECIPIENT_PHONE)
        
        self._send_reply(phone, BotMessageBuilder.ask_recipient_phone())
    
    def _handle_recipient_phone(self, state_mgr: BotStateManager, phone: str, raw_message: str) -> None:
        """Handle recipient phone number state."""
        # Normalize phone number
        recipient_phone = raw_message.strip().replace(' ', '').replace('-', '')
        
        # Basic validation (Cameroon numbers)
        phone_pattern = r'^(\+?237)?[26][0-9]{8}$'
        if not re.match(phone_pattern, recipient_phone):
            self._send_reply(phone, BotMessageBuilder.invalid_phone())
            return
        
        # Normalize to +237 format
        if not recipient_phone.startswith('+'):
            if recipient_phone.startswith('237'):
                recipient_phone = f'+{recipient_phone}'
            else:
                recipient_phone = f'+237{recipient_phone}'
        
        state_mgr.set_data('recipient_phone', recipient_phone)
        
        # Calculate price
        pickup_lat = state_mgr.get_data_value('pickup_lat')
        pickup_lng = state_mgr.get_data_value('pickup_lng')
        dropoff_lat = state_mgr.get_data_value('dropoff_lat')
        dropoff_lng = state_mgr.get_data_value('dropoff_lng')
        
        routing = get_routing_data(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        pricing = calculate_delivery_price(routing['distance_km'])
        
        # Save pricing data
        state_mgr.set_data('distance_km', routing['distance_km'])
        state_mgr.set_data('duration_min', routing['duration_min'])
        state_mgr.set_data('client_price', pricing['client_price'])
        state_mgr.set_data('platform_fee', pricing['platform_fee'])
        state_mgr.set_data('courier_earning', pricing['courier_earning'])
        
        state_mgr.set_state(BotState.ASK_CONFIRMATION)
        
        self._send_reply(
            phone,
            BotMessageBuilder.confirm_order(
                distance_km=routing['distance_km'],
                price=pricing['client_price']
            )
        )
    
    @transaction.atomic
    def _handle_confirmation(self, state_mgr: BotStateManager, phone: str, message: str) -> None:
        """Handle order confirmation state."""
        if message in ['NON', 'NO', 'ANNULER', 'CANCEL']:
            state_mgr.clear()
            self._send_reply(phone, BotMessageBuilder.order_cancelled())
            return
        
        if message not in ['OUI', 'YES', 'OK', 'CONFIRMER']:
            self._send_reply(phone, "⚠️ Tapez *OUI* pour confirmer ou *NON* pour annuler.")
            return
        
        # Get all collected data
        data = state_mgr.get_data()
        
        # Get or create sender user
        sender, _ = User.objects.get_or_create(
            phone_number=state_mgr._normalize_phone(phone),
            defaults={'role': UserRole.CLIENT}
        )
        
        # Build GPS points
        pickup_point = Point(data['pickup_lng'], data['pickup_lat'], srid=4326)
        dropoff_point = Point(data['dropoff_lng'], data['dropoff_lat'], srid=4326)
        
        # Create delivery
        delivery = Delivery.objects.create(
            sender=sender,
            recipient_phone=data['recipient_phone'],
            pickup_geo=pickup_point,
            dropoff_geo=dropoff_point,
            payment_method=PaymentMethod.CASH_P2P,
            distance_km=data['distance_km'],
            total_price=Decimal(str(data['client_price'])),
            platform_fee=Decimal(str(data['platform_fee'])),
            courier_earning=Decimal(str(data['courier_earning'])),
            status=DeliveryStatus.PENDING
        )
        
        logger.info(f"[META] Created delivery {delivery.id} for {phone}")
        
        # Clear conversation state
        state_mgr.clear()
        
        # Send success message
        self._send_reply(
            phone,
            BotMessageBuilder.order_created(
                delivery_id=str(delivery.id),
                otp_code=delivery.otp_code
            )
        )
        
        # Also notify recipient (using Meta since sender is on Meta)
        recipient_msg = (
            f"📦 *Livraison en cours vers vous !*\n\n"
            f"Un colis vous sera livré prochainement.\n"
            f"🔐 Code OTP : *{delivery.otp_code}*\n\n"
            f"_Conservez ce code, il sera demandé à la réception._"
        )
        MetaWhatsAppService.send_message(data['recipient_phone'], recipient_msg)
