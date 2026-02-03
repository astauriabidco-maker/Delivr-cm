"""
Logistics App Views - Deliveries & Neighborhoods API
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal

from .models import Delivery, Neighborhood, DeliveryStatus, PaymentMethod
from .serializers import (
    DeliverySerializer, DeliveryCreateSerializer,
    NeighborhoodSerializer, NeighborhoodListSerializer,
    QuoteRequestSerializer, QuoteResponseSerializer,
    OrderCreateSerializer, DeliveryStatusUpdateSerializer,
    CourierAssignSerializer
)
from .services.pricing import pricing_engine
from core.models import UserRole
from finance.models import WalletService


class IsBusinessOrAdmin(permissions.BasePermission):
    """Permission for business or admin users."""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in [UserRole.BUSINESS, UserRole.ADMIN]


class NeighborhoodViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Neighborhood (read-only for API consumers).
    """
    
    queryset = Neighborhood.objects.filter(is_active=True)
    permission_classes = [permissions.AllowAny]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return NeighborhoodListSerializer
        return NeighborhoodSerializer
    
    def get_queryset(self):
        qs = super().get_queryset()
        city = self.request.query_params.get('city')
        if city:
            qs = qs.filter(city__iexact=city)
        return qs


class DeliveryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Delivery management.
    """
    
    queryset = Delivery.objects.all()
    serializer_class = DeliverySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == UserRole.ADMIN:
            return Delivery.objects.all()
        elif user.role == UserRole.COURIER:
            return Delivery.objects.filter(
                Q(courier=user) | Q(status=DeliveryStatus.PENDING)
            )
        elif user.role == UserRole.BUSINESS:
            return Delivery.objects.filter(shop=user)
        else:
            return Delivery.objects.filter(sender=user)

    @action(detail=False, methods=['post'])
    def create_delivery(self, request):
        """Create a new delivery with price calculation."""
        serializer = DeliveryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        # Build pickup point
        pickup_point = Point(
            data['pickup_longitude'],
            data['pickup_latitude'],
            srid=4326
        )
        
        # Build dropoff point (GPS or neighborhood center)
        if data.get('dropoff_latitude') and data.get('dropoff_longitude'):
            dropoff_point = Point(
                data['dropoff_longitude'],
                data['dropoff_latitude'],
                srid=4326
            )
            neighborhood = None
            estimation_type = 'exact'
        else:
            neighborhood = Neighborhood.objects.get(
                pk=data['dropoff_neighborhood_id']
            )
            dropoff_point = neighborhood.center_geo
            estimation_type = 'neighborhood'
        
        # Calculate price
        safety_margin = 0.2 if estimation_type == 'neighborhood' else 0.0
        distance_km, total_price, platform_fee, courier_earning = pricing_engine.calculate_price(
            origin=pickup_point,
            destination=dropoff_point,
            safety_margin=safety_margin
        )
        
        # Create delivery
        delivery = Delivery.objects.create(
            sender=request.user,
            recipient_phone=data['recipient_phone'],
            recipient_name=data.get('recipient_name', ''),
            pickup_geo=pickup_point,
            dropoff_geo=dropoff_point if estimation_type == 'exact' else None,
            dropoff_neighborhood=neighborhood,
            package_description=data.get('package_description', ''),
            payment_method=data['payment_method'],
            distance_km=distance_km,
            total_price=total_price,
            platform_fee=platform_fee,
            courier_earning=courier_earning
        )
        
        return Response(
            DeliverySerializer(delivery).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def assign_courier(self, request, pk=None):
        """Assign a courier to the delivery."""
        delivery = self.get_object()
        serializer = CourierAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            courier = User.objects.get(
                pk=serializer.validated_data['courier_id'],
                role=UserRole.COURIER
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'Coursier non trouvé.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if courier.is_courier_blocked:
            return Response(
                {'error': 'Ce coursier est bloqué pour dette excessive.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        delivery.courier = courier
        delivery.status = DeliveryStatus.ASSIGNED
        delivery.assigned_at = timezone.now()
        delivery.save(update_fields=['courier', 'status', 'assigned_at'])
        
        return Response(DeliverySerializer(delivery).data)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update delivery status."""
        delivery = self.get_object()
        serializer = DeliveryStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        otp_code = serializer.validated_data.get('otp_code')
        
        # Validate OTP for completion
        if new_status == DeliveryStatus.COMPLETED:
            if otp_code != delivery.otp_code:
                return Response(
                    {'error': 'Code OTP invalide.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            delivery.completed_at = timezone.now()
            
            # Process financial transaction
            if delivery.payment_method == PaymentMethod.CASH_P2P:
                WalletService.process_cash_delivery(delivery)
            else:
                WalletService.process_prepaid_delivery(delivery)
        
        elif new_status == DeliveryStatus.PICKED_UP:
            delivery.picked_up_at = timezone.now()
        
        delivery.status = new_status
        delivery.save()
        
        return Response(DeliverySerializer(delivery).data)

    @action(detail=False, methods=['get'])
    def available(self, request):
        """List available deliveries for couriers."""
        if request.user.role != UserRole.COURIER:
            return Response(
                {'error': 'Réservé aux coursiers.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get courier location
        if not request.user.last_location:
            return Response(
                {'error': 'Partagez votre position GPS.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find deliveries within 3km radius
        radius_km = 3
        nearby = Delivery.objects.filter(
            status=DeliveryStatus.PENDING
        ).annotate(
            distance=Distance('pickup_geo', request.user.last_location)
        ).filter(
            distance__lte=D(km=radius_km)
        ).order_by('distance')[:20]
        
        return Response(DeliverySerializer(nearby, many=True).data)


class QuoteAPIView(APIView):
    """
    API endpoint for price estimation (E-commerce).
    
    POST /api/quote
    """
    
    permission_classes = [IsBusinessOrAdmin]
    
    def post(self, request):
        serializer = QuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        # Get shop location
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            shop = User.objects.get(pk=data['shop_id'], role=UserRole.BUSINESS)
        except User.DoesNotExist:
            return Response(
                {'error': 'Boutique non trouvée.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not shop.last_location:
            return Response(
                {'error': 'La boutique n\'a pas de position GPS enregistrée.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine destination
        if data.get('dropoff_latitude') and data.get('dropoff_longitude'):
            destination = Point(
                data['dropoff_longitude'],
                data['dropoff_latitude'],
                srid=4326
            )
            estimation_type = 'exact'
            safety_margin = 0.0
        else:
            # Find neighborhood
            try:
                if data.get('neighborhood_id'):
                    neighborhood = Neighborhood.objects.get(
                        pk=data['neighborhood_id'],
                        is_active=True
                    )
                else:
                    neighborhood = Neighborhood.objects.get(
                        city__iexact=data['city'],
                        name__iexact=data['neighborhood'],
                        is_active=True
                    )
            except Neighborhood.DoesNotExist:
                return Response(
                    {'error': 'Quartier non trouvé.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            destination = neighborhood.center_geo
            estimation_type = 'neighborhood'
            safety_margin = 0.2  # 20% margin for uncertainty
        
        # Calculate price
        try:
            distance_km, total_price, platform_fee, courier_earning = pricing_engine.calculate_price(
                origin=shop.last_location,
                destination=destination,
                safety_margin=safety_margin
            )
        except Exception as e:
            return Response(
                {'error': f'Erreur calcul prix: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        response_data = {
            'distance_km': distance_km,
            'total_price': total_price,
            'platform_fee': platform_fee,
            'courier_earning': courier_earning,
            'currency': 'XAF',
            'estimation_type': estimation_type
        }
        
        return Response(QuoteResponseSerializer(response_data).data)


class OrderAPIView(APIView):
    """
    API endpoint for creating orders (E-commerce).
    
    POST /api/orders
    """
    
    permission_classes = [IsBusinessOrAdmin]
    
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get shop
        try:
            shop = User.objects.get(pk=data['shop_id'], role=UserRole.BUSINESS)
        except User.DoesNotExist:
            return Response(
                {'error': 'Boutique non trouvée.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get neighborhood
        try:
            neighborhood = Neighborhood.objects.get(
                pk=data['neighborhood_id'],
                is_active=True
            )
        except Neighborhood.DoesNotExist:
            return Response(
                {'error': 'Quartier non trouvé.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not shop.last_location:
            return Response(
                {'error': 'La boutique n\'a pas de position GPS.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate price
        distance_km, total_price, platform_fee, courier_earning = pricing_engine.estimate_from_neighborhood(
            shop_location=shop.last_location,
            neighborhood_center=neighborhood.center_geo
        )
        
        # Check shop wallet for prepaid
        if shop.wallet_balance < total_price:
            return Response(
                {'error': f'Solde insuffisant. Requis: {total_price} XAF'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create or get client user
        client, created = User.objects.get_or_create(
            phone_number=data['customer_phone'],
            defaults={'role': UserRole.CLIENT}
        )
        
        # Create delivery
        delivery = Delivery.objects.create(
            sender=client,
            recipient_phone=data['customer_phone'],
            recipient_name=data.get('customer_name', ''),
            pickup_geo=shop.last_location,
            dropoff_neighborhood=neighborhood,
            package_description=data['items_description'],
            payment_method=PaymentMethod.PREPAID_WALLET,
            distance_km=distance_km,
            total_price=total_price,
            platform_fee=platform_fee,
            courier_earning=courier_earning,
            external_order_id=data.get('external_order_id', ''),
            shop=shop
        )
        
        # Debit shop wallet
        WalletService.debit_business_for_order(shop, delivery)
        
        return Response({
            'delivery_id': str(delivery.id),
            'status': delivery.status,
            'total_price': total_price,
            'message': 'Commande créée. Le client sera contacté sur WhatsApp.'
        }, status=status.HTTP_201_CREATED)
