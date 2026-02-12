"""
Core App Views - User Management API
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.db import models

from .serializers import (
    UserSerializer, UserCreateSerializer, 
    CourierProfileSerializer, CourierLocationUpdateSerializer,
    CourierDocumentsSerializer
)
from .models import UserRole

User = get_user_model()


class IsAdminUser(permissions.BasePermission):
    """Permission for admin users only."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == UserRole.ADMIN


class IsCourier(permissions.BasePermission):
    """Permission for courier users only."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == UserRole.COURIER


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User model.
    
    - List/Retrieve: Admin only
    - Create: Public (registration)
    - Update: Self only
    """
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        elif self.action in ['list', 'destroy']:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.ADMIN:
            return User.objects.all()
        # Non-admin can only see their own profile
        return User.objects.filter(pk=user.pk)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def couriers(self, request):
        """List all couriers (Admin only)."""
        couriers = User.objects.filter(role=UserRole.COURIER)
        serializer = self.get_serializer(couriers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def pending_verification(self, request):
        """List couriers pending verification (Admin only)."""
        pending = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=False,
            cni_document__isnull=False
        )
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        """Verify a courier's documents (Admin only)."""
        courier = self.get_object()
        if courier.role != UserRole.COURIER:
            return Response(
                {'error': 'Seuls les coursiers peuvent être vérifiés.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        courier.is_verified = True
        courier.save(update_fields=['is_verified'])
        return Response({'message': f'Coursier {courier.phone_number} vérifié.'})


class CourierViewSet(viewsets.ViewSet):
    """
    ViewSet for courier-specific operations.
    """
    
    permission_classes = [permissions.IsAuthenticated, IsCourier]

    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get courier profile with wallet info."""
        serializer = CourierProfileSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def update_location(self, request):
        """Update courier GPS location."""
        serializer = CourierLocationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        lat = serializer.validated_data['latitude']
        lng = serializer.validated_data['longitude']
        
        request.user.last_location = Point(lng, lat, srid=4326)
        request.user.last_location_updated = timezone.now()
        request.user.save(update_fields=['last_location', 'last_location_updated'])
        
        return Response({
            'message': 'Position mise à jour.',
            'location': {'latitude': lat, 'longitude': lng}
        })

    @action(detail=False, methods=['post'])
    def upload_documents(self, request):
        """Upload CNI and moto photos."""
        serializer = CourierDocumentsSerializer(
            request.user, 
            data=request.data, 
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message': 'Documents uploadés. En attente de validation.'
        })

    @action(detail=False, methods=['get'])
    def wallet(self, request):
        """Get courier wallet summary."""
        user = request.user
        from finance.models import Transaction, TransactionType
        
        # Calculate totals
        total_earned = Transaction.objects.filter(
            user=user,
            transaction_type=TransactionType.DELIVERY_CREDIT
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        total_commission = Transaction.objects.filter(
            user=user,
            transaction_type=TransactionType.COMMISSION
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        return Response({
            'balance': user.wallet_balance,
            'debt_ceiling': user.debt_ceiling,
            'is_blocked': user.is_courier_blocked,
            'available_for_withdrawal': max(0, user.wallet_balance),
            'total_earned': total_earned,
            'total_commission_paid': abs(total_commission)
        })
