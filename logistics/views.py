"""
Logistics App Views - Deliveries & Neighborhoods API
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey
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
    CourierAssignSerializer, PublicOrderCreateSerializer
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


class HasAPIKeyOrIsBusinessOrAdmin(permissions.BasePermission):
    """
    Combined permission: Partner API Key OR authenticated business/admin user.
    
    When authenticated via API Key:
    - Looks up the PartnerAPIKey to identify the partner
    - Injects `request.partner` with the partner User instance
    - The view MUST verify that shop_id == request.partner.id
    
    When authenticated via session:
    - request.partner = request.user (for BUSINESS role)
    """
    
    def has_permission(self, request, view):
        from partners.models import PartnerAPIKey
        
        # Try API Key authentication first
        raw_key = self._extract_key(request)
        if raw_key:
            try:
                api_key = PartnerAPIKey.objects.get_from_key(raw_key)
                if api_key and not api_key.revoked:
                    # Inject the partner into the request for downstream use
                    request.partner = api_key.partner
                    return True
            except Exception:
                pass
        
        # Fall back to session-based business/admin check
        if not request.user.is_authenticated:
            return False
        
        if request.user.role in [UserRole.BUSINESS, UserRole.ADMIN]:
            request.partner = request.user
            return True
        
        return False
    
    def _extract_key(self, request):
        """Extract API key from Authorization header."""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Api-Key '):
            return auth_header[8:].strip()
        return None


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
        distance_km, total_price, platform_fee, courier_earning = pricing_engine().calculate_price(
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
        """Update delivery status with validation."""
        delivery = self.get_object()
        serializer = DeliveryStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        otp_code = serializer.validated_data.get('otp_code')
        pickup_otp = serializer.validated_data.get('pickup_otp')
        
        # PICKUP validation - requires OTP from sender + optional photo
        if new_status == DeliveryStatus.PICKED_UP:
            if pickup_otp != delivery.pickup_otp:
                return Response(
                    {'error': 'Code OTP retrait invalide.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save pickup photo if provided
            if 'pickup_photo' in request.FILES:
                delivery.pickup_photo = request.FILES['pickup_photo']
            
            delivery.picked_up_at = timezone.now()
        
        # DELIVERY validation - requires OTP from recipient
        elif new_status == DeliveryStatus.COMPLETED:
            if otp_code != delivery.otp_code:
                return Response(
                    {'error': 'Code OTP livraison invalide.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Save proof photo if provided
            if 'proof_photo' in request.FILES:
                delivery.proof_photo = request.FILES['proof_photo']
            
            delivery.completed_at = timezone.now()
            
            # Process financial transaction
            if delivery.payment_method == PaymentMethod.CASH_P2P:
                WalletService.process_cash_delivery(delivery)
            else:
                WalletService.process_prepaid_delivery(delivery)
        
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


class PublicQuoteAPIView(APIView):
    """
    Public API endpoint for price estimation (E-commerce partners).
    
    This endpoint is designed for WooCommerce and the public checkout page.
    It accepts shop coordinates directly and doesn't require authentication.
    
    POST /api/public/quote/
    
    Request body (WooCommerce - legacy):
    {
        "shop_lat": 4.0511,       # Shop latitude
        "shop_lng": 9.7679,       # Shop longitude  
        "city": "Douala",         # Destination city
        "neighborhood": "Akwa"    # Destination neighborhood name
    }
    
    Request body (Public Checkout - new):
    {
        "shop_id": "uuid",        # Shop user ID (will lookup GPS from user)
        "neighborhood_id": 123    # Neighborhood ID
    }
    
    Response:
    {
        "estimated_price": 1500,
        "distance_km": 3.2,
        "currency": "XAF"
    }
    """
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Support shop_id lookup (for public checkout)
        shop_id = request.data.get('shop_id')
        neighborhood_id = request.data.get('neighborhood_id')
        
        # If shop_id provided, lookup GPS from user
        if shop_id:
            try:
                shop = User.objects.get(pk=shop_id, role=UserRole.BUSINESS)
                if shop.last_location:
                    shop_lat = shop.last_location.y
                    shop_lng = shop.last_location.x
                else:
                    # Default to Akwa center
                    shop_lat = 4.0511
                    shop_lng = 9.7679
            except User.DoesNotExist:
                return Response(
                    {'error': 'Boutique non trouvée.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Legacy: Get shop coordinates directly (from WooCommerce plugin settings)
            shop_lat = request.data.get('shop_lat') or request.data.get('pickup_latitude')
            shop_lng = request.data.get('shop_lng') or request.data.get('pickup_longitude')
        
        # Get destination
        city = request.data.get('city', 'Douala')
        neighborhood_name = request.data.get('neighborhood') or request.data.get('dropoff_neighborhood')
        
        # Support neighborhood_id (for public checkout)
        neighborhood = None
        if neighborhood_id:
            try:
                neighborhood = Neighborhood.objects.get(
                    pk=neighborhood_id,
                    is_active=True
                )
                neighborhood_name = neighborhood.name
                city = neighborhood.city
            except Neighborhood.DoesNotExist:
                return Response(
                    {'error': 'Quartier non trouvé.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Validate required fields
        if not neighborhood_name and not neighborhood_id:
            return Response(
                {'error': 'Le champ neighborhood est requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Default shop location (Akwa center) if not provided
        if not shop_lat or not shop_lng:
            shop_lat = 4.0511
            shop_lng = 9.7679
        
        try:
            shop_lat = float(shop_lat)
            shop_lng = float(shop_lng)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Coordonnées GPS invalides.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Build shop location
        shop_location = Point(shop_lng, shop_lat, srid=4326)
        
        # Find neighborhood (if not already found by ID above)
        if not neighborhood:
            try:
                neighborhood = Neighborhood.objects.get(
                    city__iexact=city,
                    name__iexact=neighborhood_name,
                    is_active=True
                )
            except Neighborhood.DoesNotExist:
                # Fallback: use default price based on city
                fallback_prices = {
                    'douala': 1500,
                    'yaounde': 1500,
                    'yaoundé': 1500,
                }
                fallback_price = fallback_prices.get(city.lower(), 2000)
                
                return Response({
                    'estimated_price': fallback_price,
                    'total_price': fallback_price,
                    'distance_km': 5.0,
                    'currency': 'XAF',
                    'estimation_type': 'fallback',
                    'message': f'Quartier "{neighborhood_name}" non référencé, prix estimé.'
                })
        
        destination = neighborhood.center_geo
        safety_margin = 0.2  # 20% margin for uncertainty
        
        # Calculate price
        try:
            distance_km, total_price, platform_fee, courier_earning = pricing_engine().calculate_price(
                origin=shop_location,
                destination=destination,
                safety_margin=safety_margin
            )
        except Exception as e:
            # Fallback on error
            return Response({
                'estimated_price': 1500,
                'total_price': 1500,
                'distance_km': 5.0,
                'currency': 'XAF',
                'estimation_type': 'fallback',
                'error': str(e)
            })
        
        return Response({
            'estimated_price': total_price,
            'total_price': total_price,
            'distance_km': round(distance_km, 1),
            'currency': 'XAF',
            'estimation_type': 'calculated',
            'neighborhood': neighborhood.name,
            'city': neighborhood.city
        })


class QuoteAPIView(APIView):
    """
    API endpoint for price estimation (E-commerce).
    
    POST /api/quote
    
    Authentication: API Key (via partner portal) OR Session auth.
    """
    
    permission_classes = [HasAPIKeyOrIsBusinessOrAdmin]
    
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
        
        # SECURITY: Verify shop_id matches the authenticated partner
        partner = getattr(request, 'partner', None)
        if partner and partner.role != UserRole.ADMIN and str(shop.pk) != str(partner.pk):
            return Response(
                {'error': 'Vous ne pouvez pas effectuer de devis pour une autre boutique.'},
                status=status.HTTP_403_FORBIDDEN
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
            distance_km, total_price, platform_fee, courier_earning = pricing_engine().calculate_price(
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
    
    Authentication: API Key (via partner portal) OR Session auth.
    """
    
    permission_classes = [HasAPIKeyOrIsBusinessOrAdmin]
    
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
        
        # SECURITY: Verify shop_id matches the authenticated partner
        # Prevents partner A from creating orders and debiting partner B's wallet
        partner = getattr(request, 'partner', None)
        if partner and partner.role != UserRole.ADMIN and str(shop.pk) != str(partner.pk):
            return Response(
                {'error': 'Accès refusé. Vous ne pouvez créer des commandes que pour votre propre boutique.'},
                status=status.HTTP_403_FORBIDDEN
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
        distance_km, total_price, platform_fee, courier_earning = pricing_engine().estimate_from_neighborhood(
            shop_location=shop.last_location,
            neighborhood_center=neighborhood.center_geo
        )
        
        # Check shop wallet for prepaid - CRITICAL B2B PROTECTION
        if shop.wallet_balance < total_price:
            return Response(
                {
                    'error': 'Solde insuffisant',
                    'required': float(total_price),
                    'available': float(shop.wallet_balance),
                    'shortfall': float(total_price - shop.wallet_balance),
                    'currency': 'XAF',
                    'message': f'Veuillez recharger votre wallet. Requis: {total_price} XAF, Disponible: {shop.wallet_balance} XAF'
                },
                status=status.HTTP_402_PAYMENT_REQUIRED
            )
        
        # Create or get client user (for tracking / future orders)
        client, created = User.objects.get_or_create(
            phone_number=data['customer_phone'],
            defaults={
                'role': UserRole.CLIENT,
                'full_name': data.get('customer_name', ''),
            }
        )
        
        # Create delivery
        # B2B: sender = SHOP (expéditeur), recipient = CUSTOMER (destinataire)
        delivery = Delivery.objects.create(
            sender=shop,
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


class PublicOrderCreateAPIView(APIView):
    """
    Public API endpoint for creating orders (Hosted Checkout / Magic Link).
    
    POST /api/public/orders/
    
    This endpoint is PUBLIC (no authentication required).
    Used by the public checkout page for partners.
    
    Request body:
    {
        "shop_id": "uuid",
        "client_name": "Jean Kamga",
        "client_phone": "+237690000000",
        "neighborhood_id": "uuid",
        "package_description": "Description du colis",
        "payment_method": "CASH"
    }
    
    Response:
    {
        "delivery_id": "uuid",
        "status": "PENDING",
        "total_price": 1500,
        "message": "Commande créée!"
    }
    """
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = PublicOrderCreateSerializer(data=request.data)
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
        
        # Check if shop is approved
        if not shop.is_business_approved:
            return Response(
                {'error': 'Cette boutique n\'est pas encore active.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check shop wallet balance (must be >= 0)
        if shop.wallet_balance < Decimal('0'):
            return Response(
                {'error': 'Cette boutique ne peut pas accepter de commandes pour le moment.'},
                status=status.HTTP_400_BAD_REQUEST
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
        
        # Shop location (default to Akwa if not set)
        if shop.last_location:
            shop_location = shop.last_location
        else:
            shop_location = Point(9.7679, 4.0511, srid=4326)  # Default Akwa
        
        # Calculate price
        distance_km, total_price, platform_fee, courier_earning = pricing_engine().estimate_from_neighborhood(
            shop_location=shop_location,
            neighborhood_center=neighborhood.center_geo
        )
        
        # Create or get client user
        client, created = User.objects.get_or_create(
            phone_number=data['client_phone'],
            defaults={
                'role': UserRole.CLIENT,
                'full_name': data['client_name']
            }
        )
        
        # Update client name if provided and user exists
        if not created and data['client_name'] and not client.full_name:
            client.full_name = data['client_name']
            client.save(update_fields=['full_name'])
        
        # Create delivery with CASH payment (COD - Cash on Delivery)
        # Public checkout: sender = SHOP (expéditeur), recipient = CLIENT (destinataire)
        delivery = Delivery.objects.create(
            sender=shop,
            recipient_phone=data['client_phone'],
            recipient_name=data['client_name'],
            pickup_geo=shop_location,
            dropoff_neighborhood=neighborhood,
            package_description=data['package_description'],
            payment_method=PaymentMethod.CASH_P2P,  # Cash payment
            distance_km=distance_km,
            total_price=total_price,
            platform_fee=platform_fee,
            courier_earning=courier_earning,
            shop=shop
        )
        
        # TODO: Send WhatsApp notification to client and shop
        # This will be handled by the WhatsApp bot integration
        
        return Response({
            'delivery_id': str(delivery.id),
            'status': delivery.status,
            'total_price': float(total_price),
            'distance_km': round(distance_km, 1),
            'message': 'Commande créée ! Vérifiez votre WhatsApp pour les mises à jour.'
        }, status=status.HTTP_201_CREATED)


class CourierLocationView(APIView):
    """
    API endpoint for courier location updates.
    
    POST /api/courier/location
    
    Request body:
    {
        "lat": 4.0511,
        "lng": 9.6942
    }
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Update courier's current location."""
        user = request.user
        
        # Validate role
        if user.role != UserRole.COURIER:
            return Response(
                {'error': 'Seuls les coursiers peuvent mettre à jour leur position.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get coordinates
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        
        if lat is None or lng is None:
            return Response(
                {'error': 'Les champs lat et lng sont requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Coordonnées GPS invalides.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate coordinates range
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return Response(
                {'error': 'Coordonnées hors limites.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update location
        user.last_location = Point(lng, lat, srid=4326)
        user.last_location_updated = timezone.now()
        user.save(update_fields=['last_location', 'last_location_updated'])
        
        return Response({
            'status': 'ok',
            'message': 'Position mise à jour.',
            'location': {
                'lat': lat,
                'lng': lng,
                'updated_at': user.last_location_updated.isoformat()
            }
        })
    
    def get(self, request):
        """Get courier's current location."""
        user = request.user
        
        if user.role != UserRole.COURIER:
            return Response(
                {'error': 'Seuls les coursiers peuvent accéder à cette ressource.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not user.last_location:
            return Response({
                'status': 'no_location',
                'message': 'Aucune position enregistrée.'
            })
        
        return Response({
            'status': 'ok',
            'location': {
                'lat': user.last_location.y,
                'lng': user.last_location.x,
                'updated_at': user.last_location_updated.isoformat() if user.last_location_updated else None
            }
        })


class OrderAcceptView(APIView):
    """
    API endpoint for courier to accept an order.
    
    POST /api/orders/{order_id}/accept
    
    Race-condition safe: uses SELECT FOR UPDATE to prevent
    multiple couriers from accepting the same order.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, order_id):
        """Accept an order as a courier."""
        from logistics.services.dispatch import accept_order
        
        user = request.user
        
        # Validate role
        if user.role != UserRole.COURIER:
            return Response(
                {'error': 'Seuls les coursiers peuvent accepter des commandes.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if courier is blocked
        if user.is_courier_blocked:
            return Response(
                {'error': 'Votre compte est bloqué pour dette excessive.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            delivery = accept_order(order_id, user)
            
            return Response({
                'status': 'ok',
                'message': 'Commande acceptée avec succès !',
                'delivery': {
                    'id': str(delivery.id),
                    'status': delivery.status,
                    'pickup_address': delivery.pickup_address or 'GPS',
                    'dropoff_address': delivery.dropoff_address or 'GPS',
                    'total_price': float(delivery.total_price),
                    'courier_earning': float(delivery.courier_earning),
                    'otp_code': delivery.otp_code,
                    'recipient_phone': delivery.recipient_phone
                }
            })
            
        except ValueError as e:
            # Order already taken or other validation error
            return Response(
                {'error': str(e)},
                status=status.HTTP_409_CONFLICT
            )


# ============================================
# REAL-TIME TRACKING PAGE
# ============================================

from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404


class DeliveryTrackingView(TemplateView):
    """
    Public tracking page for a delivery.
    
    Uses WebSocket for real-time updates.
    No authentication required - tracking is public.
    """
    template_name = 'logistics/tracking.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        delivery_id = self.kwargs.get('delivery_id')
        
        # Verify delivery exists (but still show page)
        try:
            delivery = Delivery.objects.get(pk=delivery_id)
            context['delivery'] = delivery
            context['delivery_id'] = str(delivery_id)
        except Delivery.DoesNotExist:
            context['delivery'] = None
            context['delivery_id'] = str(delivery_id)
        
        return context
