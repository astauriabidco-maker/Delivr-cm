"""
Mobile Payment API for DELIVR-CM

REST endpoints for initiating and tracking mobile money payments.
"""

import logging
import hashlib
import hmac
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from finance.models import MobilePayment, MobilePaymentStatus
from finance.mobile_payment_service import MobilePaymentService
from logistics.models import Delivery

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def init_mobile_payment(request):
    """
    Initialize a mobile money payment.
    
    POST /api/payments/mobile/init/
    
    Body:
    {
        "delivery_id": "uuid",
        "phone": "+237677123456"
    }
    
    Returns:
    {
        "success": true,
        "payment_id": "uuid",
        "provider": "MTN",
        "status": "PENDING",
        "payment_url": "https://..." (for Orange Money)
    }
    """
    delivery_id = request.data.get('delivery_id')
    phone = request.data.get('phone')
    
    if not delivery_id or not phone:
        return Response(
            {'error': 'delivery_id and phone are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        delivery = Delivery.objects.get(id=delivery_id)
    except Delivery.DoesNotExist:
        return Response(
            {'error': 'Delivery not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if already has pending payment
    existing = MobilePayment.objects.filter(
        delivery=delivery,
        status=MobilePaymentStatus.PENDING
    ).first()
    
    if existing:
        return Response({
            'success': True,
            'payment_id': str(existing.id),
            'provider': existing.provider,
            'status': existing.status,
            'payment_url': existing.payment_url,
            'message': 'Payment already initiated'
        })
    
    try:
        payment = MobilePaymentService.initiate_payment(
            delivery=delivery,
            phone=phone
        )
        
        if payment.status == MobilePaymentStatus.FAILED:
            return Response({
                'success': False,
                'error': payment.error_message,
                'error_code': payment.error_code
            }, status=status.HTTP_502_BAD_GATEWAY)
        
        return Response({
            'success': True,
            'payment_id': str(payment.id),
            'provider': payment.provider,
            'provider_display': payment.get_provider_display(),
            'status': payment.status,
            'payment_url': payment.payment_url,
            'message': 'Payment request sent'
        })
        
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.exception(f"Payment init error: {e}")
        return Response(
            {'error': 'Payment initialization failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_status(request, payment_id):
    """
    Get status of a mobile payment.
    
    GET /api/payments/mobile/status/<uuid>/
    
    Query params:
    - poll=true: Force refresh from provider
    """
    try:
        payment = MobilePayment.objects.get(id=payment_id)
    except MobilePayment.DoesNotExist:
        return Response(
            {'error': 'Payment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Poll provider if requested and payment is pending
    if request.GET.get('poll') == 'true':
        if payment.status == MobilePaymentStatus.PENDING:
            payment = MobilePaymentService.poll_status(payment)
    
    return Response({
        'id': str(payment.id),
        'delivery_id': str(payment.delivery_id),
        'provider': payment.provider,
        'provider_display': payment.get_provider_display(),
        'phone': payment.phone_number,
        'amount': payment.amount,
        'status': payment.status,
        'status_display': payment.get_status_display(),
        'payment_url': payment.payment_url,
        'created_at': payment.created_at,
        'confirmed_at': payment.confirmed_at,
    })


@csrf_exempt
@require_http_methods(['POST'])
def mtn_callback(request):
    """
    Webhook callback for MTN MoMo.
    
    POST /api/payments/mobile/callback/mtn/
    """
    logger.info("[MTN CALLBACK] Received callback")
    
    try:
        import json
        data = json.loads(request.body)
        
        # Verify signature if configured
        webhook_secret = getattr(settings, 'MTN_MOMO_WEBHOOK_SECRET', '')
        if webhook_secret:
            signature = request.headers.get('X-Callback-Signature', '')
            expected = hmac.new(
                webhook_secret.encode(),
                request.body,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected):
                logger.warning("[MTN CALLBACK] Invalid signature")
                return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        # Extract fields
        reference_id = data.get('externalId') or data.get('referenceId', '')
        status_value = data.get('status', 'UNKNOWN')
        transaction_id = data.get('financialTransactionId', '')
        
        payment = MobilePaymentService.process_callback(
            provider='MTN',
            reference_id=reference_id,
            status=status_value,
            transaction_id=transaction_id,
            raw_data=data
        )
        
        if payment:
            logger.info(f"[MTN CALLBACK] Processed: {payment.id} -> {payment.status}")
        
        return JsonResponse({'received': True})
        
    except Exception as e:
        logger.exception(f"[MTN CALLBACK] Error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def orange_callback(request):
    """
    Webhook callback for Orange Money.
    
    POST /api/payments/mobile/callback/orange/
    """
    logger.info("[ORANGE CALLBACK] Received callback")
    
    try:
        import json
        data = json.loads(request.body)
        
        # Extract fields (Orange Money callback format)
        order_id = data.get('order_id', '')
        status_value = data.get('status', 'UNKNOWN')
        transaction_id = data.get('txnid', '')
        pay_token = data.get('pay_token', '')
        
        # Find by order_id or pay_token
        reference_id = order_id or pay_token
        
        payment = MobilePaymentService.process_callback(
            provider='OM',
            reference_id=reference_id,
            status=status_value,
            transaction_id=transaction_id,
            raw_data=data
        )
        
        if payment:
            logger.info(f"[ORANGE CALLBACK] Processed: {payment.id} -> {payment.status}")
        
        return JsonResponse({'received': True})
        
    except Exception as e:
        logger.exception(f"[ORANGE CALLBACK] Error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def payment_providers_status(request):
    """
    Check which payment providers are available.
    
    GET /api/payments/mobile/providers/
    """
    availability = MobilePaymentService.is_available()
    
    return Response({
        'providers': [
            {
                'code': 'MTN',
                'name': 'MTN Mobile Money',
                'available': availability['mtn_momo'],
                'prefixes': ['67x', '68x', '650-654']
            },
            {
                'code': 'OM',
                'name': 'Orange Money',
                'available': availability['orange_money'],
                'prefixes': ['69x', '655-659']
            }
        ]
    })
