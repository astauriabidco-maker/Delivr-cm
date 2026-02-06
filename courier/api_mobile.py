"""
COURIER App - Mobile REST API

Django REST Framework API endpoints for the Flutter mobile app.
All endpoints require JWT authentication.
"""

import logging
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.contrib.gis.geos import Point
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User, UserRole
from core.gamification import GamificationService, LEVEL_THRESHOLDS
from logistics.models import Delivery, DeliveryStatus
from finance.models import Transaction, WalletService, TransactionType

logger = logging.getLogger(__name__)


# ============================================
# PERMISSIONS
# ============================================

class IsCourier(permissions.BasePermission):
    """Allow only authenticated couriers."""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == UserRole.COURIER
        )


# ============================================
# AUTHENTICATION
# ============================================

class CourierLoginView(APIView):
    """
    Login endpoint for courier mobile app.
    
    POST /api/mobile/auth/login/
    {
        "phone_number": "+237612345678",
        "pin": "1234"
    }
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        phone = request.data.get('phone_number', '').strip()
        pin = request.data.get('pin', '').strip()
        
        if not phone or not pin:
            return Response(
                {'error': 'Numéro de téléphone et PIN requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Normalize phone number
        if not phone.startswith('+237'):
            if len(phone) == 9 and phone.isdigit():
                phone = f'+237{phone}'
            else:
                return Response(
                    {'error': 'Format de numéro invalide'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            user = User.objects.get(phone_number=phone, role=UserRole.COURIER)
        except User.DoesNotExist:
            return Response(
                {'error': 'Compte coursier non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify PIN/Password
        if not user.check_password(pin):
            return Response(
                {'error': 'PIN incorrect'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if verified
        if not user.is_verified:
            return Response(
                {'error': 'Compte non vérifié'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'courier': {
                'id': str(user.id),
                'phone_number': user.phone_number,
                'full_name': user.full_name,
                'is_online': user.is_online,
                'courier_level': user.courier_level or 'BRONZE',
            }
        })


class CourierRefreshTokenView(APIView):
    """Refresh JWT token."""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        refresh_token = request.data.get('refresh')
        
        if not refresh_token:
            return Response(
                {'error': 'Refresh token requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            refresh = RefreshToken(refresh_token)
            return Response({
                'access': str(refresh.access_token),
            })
        except Exception:
            return Response(
                {'error': 'Token invalide ou expiré'},
                status=status.HTTP_401_UNAUTHORIZED
            )


# ============================================
# COURIER PROFILE & DASHBOARD
# ============================================

class CourierDashboardView(APIView):
    """
    Dashboard data for courier mobile app.
    
    GET /api/mobile/dashboard/
    """
    permission_classes = [IsCourier]
    
    def get(self, request):
        courier = request.user
        today = timezone.now().date()
        
        # Today's stats
        today_deliveries = Delivery.objects.filter(
            courier=courier,
            completed_at__date=today,
            status=DeliveryStatus.COMPLETED
        )
        
        today_stats = today_deliveries.aggregate(
            count=Count('id'),
            earnings=Sum('courier_earning'),
            distance=Sum('distance_km')
        )
        
        # Active delivery
        active_delivery = Delivery.objects.filter(
            courier=courier,
            status__in=[
                DeliveryStatus.ASSIGNED,
                DeliveryStatus.PICKED_UP,
                DeliveryStatus.IN_TRANSIT,
            ]
        ).first()
        
        # Wallet (balance is on User model)
        wallet_balance = float(courier.wallet_balance)
        
        # Level progress
        next_level = GamificationService.get_next_level_progress(courier)
        
        return Response({
            'courier': {
                'id': str(courier.id),
                'phone_number': courier.phone_number,
                'full_name': courier.full_name,
                'is_online': courier.is_online,
                'courier_level': courier.courier_level or 'BRONZE',
            },
            'today': {
                'deliveries': today_stats['count'] or 0,
                'earnings': float(today_stats['earnings'] or 0),
                'distance': float(today_stats['distance'] or 0),
            },
            'wallet_balance': wallet_balance,
            'level_progress': next_level,
            'has_active_delivery': active_delivery is not None,
            'active_delivery_id': str(active_delivery.id) if active_delivery else None,
            # Compatible fields for mobile app
            'today_deliveries': today_stats['count'] or 0,
            'today_earnings': float(today_stats['earnings'] or 0),
            'today_distance': float(today_stats['distance'] or 0),
            'rating': 5.0,
            'success_streak': 0,
            'level': courier.courier_level or 'BRONZE',
            'active_delivery': None,  # TODO: serialize active delivery
            'recent_deliveries': [],  # TODO: add recent deliveries
        })


class ToggleOnlineView(APIView):
    """
    Toggle courier online/offline status.
    
    POST /api/mobile/toggle-online/
    """
    permission_classes = [IsCourier]
    
    def post(self, request):
        courier = request.user
        
        # Toggle status
        courier.is_online = not courier.is_online
        if courier.is_online:
            courier.last_online_at = timezone.now()
        courier.save(update_fields=['is_online', 'last_online_at'])
        
        return Response({
            'is_online': courier.is_online,
            'message': 'En ligne' if courier.is_online else 'Hors ligne'
        })


# ============================================
# DELIVERIES
# ============================================

class DeliveryListView(APIView):
    """
    List courier's deliveries.
    
    GET /api/mobile/deliveries/?status=active|completed|all
    """
    permission_classes = [IsCourier]
    
    def get(self, request):
        courier = request.user
        status_filter = request.query_params.get('status', 'active')
        
        qs = Delivery.objects.filter(courier=courier)
        
        if status_filter == 'active':
            qs = qs.filter(status__in=[
                DeliveryStatus.ASSIGNED,
                DeliveryStatus.EN_ROUTE_PICKUP,
                DeliveryStatus.ARRIVED_PICKUP,
                DeliveryStatus.PICKED_UP,
                DeliveryStatus.IN_TRANSIT,
                DeliveryStatus.ARRIVED_DROPOFF,
            ])
        elif status_filter == 'completed':
            qs = qs.filter(status=DeliveryStatus.COMPLETED)
        
        qs = qs.select_related(
            'pickup_neighborhood', 
            'dropoff_neighborhood'
        ).order_by('-created_at')[:50]
        
        deliveries = []
        for d in qs:
            deliveries.append(self._serialize_delivery(d))
        
        return Response({'deliveries': deliveries})
    
    def _serialize_delivery(self, d):
        return {
            'id': str(d.id),
            'status': d.status,
            'pickup_address': d.pickup_address or (
                d.pickup_neighborhood.name if d.pickup_neighborhood else 'N/A'
            ),
            'dropoff_address': d.dropoff_address or (
                d.dropoff_neighborhood.name if d.dropoff_neighborhood else 'N/A'
            ),
            'pickup_lat': d.pickup_geo.y if d.pickup_geo else None,
            'pickup_lng': d.pickup_geo.x if d.pickup_geo else None,
            'dropoff_lat': d.dropoff_geo.y if d.dropoff_geo else None,
            'dropoff_lng': d.dropoff_geo.x if d.dropoff_geo else None,
            'sender_phone': d.sender.phone_number if d.sender else None,
            'sender_name': d.sender.full_name if d.sender else None,
            'recipient_phone': d.recipient_phone,
            'recipient_name': d.recipient_name,
            'distance_km': float(d.distance_km or 0),
            'total_price': float(d.total_price or 0),
            'courier_earning': float(d.courier_earning or 0),
            'pickup_otp': d.pickup_otp,
            'dropoff_otp': d.otp_code,
            'notes': d.package_description,
            'created_at': d.created_at.isoformat(),
            'picked_up_at': d.picked_up_at.isoformat() if d.picked_up_at else None,
            'completed_at': d.completed_at.isoformat() if d.completed_at else None,
        }


class DeliveryDetailView(APIView):
    """
    Get delivery details.
    
    GET /api/mobile/deliveries/<id>/
    """
    permission_classes = [IsCourier]
    
    def get(self, request, delivery_id):
        try:
            delivery = Delivery.objects.select_related(
                'sender', 'pickup_neighborhood', 'dropoff_neighborhood'
            ).get(id=delivery_id, courier=request.user)
        except Delivery.DoesNotExist:
            return Response(
                {'error': 'Livraison non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(self._serialize_delivery(delivery))
    
    def _serialize_delivery(self, d):
        return {
            'id': str(d.id),
            'status': d.status,
            'pickup_address': d.pickup_address or (
                d.pickup_neighborhood.name if d.pickup_neighborhood else 'N/A'
            ),
            'dropoff_address': d.dropoff_address or (
                d.dropoff_neighborhood.name if d.dropoff_neighborhood else 'N/A'
            ),
            'pickup_lat': d.pickup_geo.y if d.pickup_geo else None,
            'pickup_lng': d.pickup_geo.x if d.pickup_geo else None,
            'dropoff_lat': d.dropoff_geo.y if d.dropoff_geo else None,
            'dropoff_lng': d.dropoff_geo.x if d.dropoff_geo else None,
            'sender_phone': d.sender.phone_number if d.sender else None,
            'sender_name': d.sender.full_name if d.sender else None,
            'recipient_phone': d.recipient_phone,
            'recipient_name': d.recipient_name,
            'distance_km': float(d.distance_km or 0),
            'total_price': float(d.total_price or 0),
            'courier_earning': float(d.courier_earning or 0),
            'pickup_otp': d.pickup_otp,
            'dropoff_otp': d.otp_code,
            'pickup_photo_url': d.pickup_photo.url if d.pickup_photo else None,
            'proof_photo_url': d.proof_photo.url if d.proof_photo else None,
            'notes': d.package_description,
            'created_at': d.created_at.isoformat(),
            'assigned_at': d.assigned_at.isoformat() if d.assigned_at else None,
            'picked_up_at': d.picked_up_at.isoformat() if d.picked_up_at else None,
            'completed_at': d.completed_at.isoformat() if d.completed_at else None,
        }


class DeliveryStatusUpdateView(APIView):
    """
    Update delivery status.
    
    PATCH /api/mobile/deliveries/<id>/status/
    { "status": "EN_ROUTE_PICKUP" | "ARRIVED_PICKUP" | "IN_TRANSIT" | "ARRIVED_DROPOFF" }
    """
    permission_classes = [IsCourier]
    
    def patch(self, request, delivery_id):
        try:
            delivery = Delivery.objects.get(id=delivery_id, courier=request.user)
        except Delivery.DoesNotExist:
            return Response(
                {'error': 'Livraison non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_status = request.data.get('status')
        
        valid_transitions = {
            DeliveryStatus.ASSIGNED: [DeliveryStatus.EN_ROUTE_PICKUP],
            DeliveryStatus.EN_ROUTE_PICKUP: [DeliveryStatus.ARRIVED_PICKUP],
            DeliveryStatus.ARRIVED_PICKUP: [DeliveryStatus.PICKED_UP],
            DeliveryStatus.PICKED_UP: [DeliveryStatus.IN_TRANSIT],
            DeliveryStatus.IN_TRANSIT: [DeliveryStatus.ARRIVED_DROPOFF],
            DeliveryStatus.ARRIVED_DROPOFF: [DeliveryStatus.COMPLETED],
        }
        
        allowed = valid_transitions.get(delivery.status, [])
        if new_status not in allowed:
            return Response(
                {'error': f'Transition de statut invalide: {delivery.status} -> {new_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        delivery.status = new_status
        delivery.save(update_fields=['status'])
        
        # Broadcast via WebSocket
        from logistics.events import broadcast_delivery_update
        broadcast_delivery_update(delivery)
        
        return Response({
            'success': True,
            'status': delivery.status,
        })


class ConfirmPickupView(APIView):
    """
    Confirm pickup with OTP and optional photo.
    
    POST /api/mobile/deliveries/<id>/confirm-pickup/
    { "otp": "1234", "photo_url": "optional" }
    """
    permission_classes = [IsCourier]
    
    def post(self, request, delivery_id):
        try:
            delivery = Delivery.objects.get(id=delivery_id, courier=request.user)
        except Delivery.DoesNotExist:
            return Response(
                {'error': 'Livraison non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check status
        if delivery.status not in [DeliveryStatus.ARRIVED_PICKUP, DeliveryStatus.EN_ROUTE_PICKUP]:
            return Response(
                {'error': 'La livraison n\'est pas prête pour le retrait'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        otp = request.data.get('otp', '').strip()
        
        # Validate OTP
        if not delivery.pickup_otp or delivery.pickup_otp != otp:
            return Response(
                {'error': 'Code OTP invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save photo URL if provided
        photo_url = request.data.get('photo_url')
        if photo_url:
            delivery.pickup_photo = photo_url
        
        # Update status
        delivery.status = DeliveryStatus.PICKED_UP
        delivery.picked_up_at = timezone.now()
        delivery.save(update_fields=['status', 'picked_up_at', 'pickup_photo'])
        
        # Broadcast update
        from logistics.events import broadcast_delivery_update
        broadcast_delivery_update(delivery)
        
        # Send WhatsApp notification to sender
        from bot.whatsapp_service import send_pickup_confirmed_notification
        send_pickup_confirmed_notification(delivery)
        
        logger.info(f"Pickup confirmed for delivery {delivery_id} by courier {request.user.id}")
        
        return Response({
            'success': True,
            'message': 'Retrait confirmé',
            'status': delivery.status,
        })


class ConfirmDropoffView(APIView):
    """
    Confirm dropoff with OTP and proof of delivery.
    
    POST /api/mobile/deliveries/<id>/confirm-dropoff/
    { "otp": "5678", "photo_url": "optional" }
    """
    permission_classes = [IsCourier]
    
    def post(self, request, delivery_id):
        try:
            delivery = Delivery.objects.get(id=delivery_id, courier=request.user)
        except Delivery.DoesNotExist:
            return Response(
                {'error': 'Livraison non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check status
        if delivery.status not in [DeliveryStatus.ARRIVED_DROPOFF, DeliveryStatus.IN_TRANSIT]:
            return Response(
                {'error': 'La livraison n\'est pas prête pour la remise'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        otp = request.data.get('otp', '').strip()
        
        # Validate OTP
        if not delivery.otp_code or delivery.otp_code != otp:
            return Response(
                {'error': 'Code OTP invalide'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save photo URL if provided
        photo_url = request.data.get('photo_url')
        if photo_url:
            delivery.proof_photo = photo_url
        
        # Update status
        delivery.status = DeliveryStatus.COMPLETED
        delivery.completed_at = timezone.now()
        delivery.save(update_fields=['status', 'completed_at', 'proof_photo'])
        
        # Credit courier wallet (balance is on User model)
        courier = request.user
        WalletService.credit(
            user=courier,
            amount=delivery.courier_earning,
            transaction_type=TransactionType.DELIVERY_CREDIT,
            delivery=delivery,
            description=f'Course #{str(delivery.id)[:8]}'
        )
        
        # Award XP
        GamificationService.award_delivery_xp(courier, delivery)
        
        # Broadcast update
        from logistics.events import broadcast_delivery_update
        broadcast_delivery_update(delivery)
        
        # Send WhatsApp notification
        from bot.whatsapp_service import send_delivery_completed_notification
        send_delivery_completed_notification(delivery)
        
        logger.info(f"Delivery {delivery_id} completed by courier {courier.id}")
        
        return Response({
            'success': True,
            'message': 'Livraison terminée',
            'status': delivery.status,
            'earning': float(delivery.courier_earning),
        })


# ============================================
# LOCATION UPDATES
# ============================================

class UpdateLocationView(APIView):
    """
    Update courier location (via HTTP fallback, WebSocket preferred).
    
    POST /api/mobile/location/
    { "latitude": 4.0511, "longitude": 9.7679 }
    """
    permission_classes = [IsCourier]
    
    def post(self, request):
        lat = request.data.get('latitude')
        lng = request.data.get('longitude')
        
        if lat is None or lng is None:
            return Response(
                {'error': 'Coordonnées requises'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        courier = request.user
        
        # Update location
        courier.current_location = Point(float(lng), float(lat), srid=4326)
        courier.last_location_at = timezone.now()
        courier.save(update_fields=['current_location', 'last_location_at'])
        
        return Response({'success': True})


# ============================================
# PHOTO UPLOAD
# ============================================

class UploadDeliveryPhotoView(APIView):
    """
    Upload delivery photo (pickup or dropoff).
    
    POST /api/mobile/uploads/delivery-photo/
    - photo: File
    - delivery_id: UUID
    - type: "pickup" | "dropoff"
    """
    permission_classes = [IsCourier]
    
    def post(self, request):
        photo = request.FILES.get('photo')
        delivery_id = request.data.get('delivery_id')
        photo_type = request.data.get('type', 'pickup')
        
        if not photo:
            return Response(
                {'error': 'Photo requise'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not delivery_id:
            return Response(
                {'error': 'delivery_id requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            delivery = Delivery.objects.get(id=delivery_id, courier=request.user)
        except Delivery.DoesNotExist:
            return Response(
                {'error': 'Livraison non trouvée'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Save photo
        if photo_type == 'pickup':
            delivery.pickup_photo = photo
            delivery.save(update_fields=['pickup_photo'])
            url = delivery.pickup_photo.url
        else:
            delivery.dropoff_photo = photo
            delivery.save(update_fields=['dropoff_photo'])
            url = delivery.dropoff_photo.url
        
        return Response({
            'success': True,
            'url': url,
        })


# ============================================
# EARNINGS & WALLET
# ============================================

class WalletView(APIView):
    """
    Get wallet details and transaction history.
    
    GET /api/mobile/wallet/
    """
    permission_classes = [IsCourier]
    
    def get(self, request):
        courier = request.user
        
        # Balance is on User model directly
        balance = float(courier.wallet_balance)
        
        # Recent transactions
        transactions = Transaction.objects.filter(
            user=courier
        ).order_by('-created_at')[:20]
        
        return Response({
            'balance': balance,
            'currency': 'XAF',
            'transactions': [
                {
                    'id': str(t.id),
                    'amount': float(t.amount),
                    'type': t.transaction_type,
                    'description': t.description,
                    'created_at': t.created_at.isoformat(),
                }
                for t in transactions
            ]
        })
