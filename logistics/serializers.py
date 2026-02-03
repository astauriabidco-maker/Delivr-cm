"""
Logistics App Serializers - Deliveries & Neighborhoods
"""

from rest_framework import serializers
from django.contrib.gis.geos import Point
from .models import Delivery, Neighborhood, DeliveryStatus, PaymentMethod


class NeighborhoodSerializer(serializers.ModelSerializer):
    """Serializer for Neighborhood model."""
    
    class Meta:
        model = Neighborhood
        fields = ['id', 'city', 'name', 'center_geo', 'radius_km', 'is_active']
        read_only_fields = ['id']


class NeighborhoodListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for neighborhood listings."""
    
    class Meta:
        model = Neighborhood
        fields = ['id', 'city', 'name']


class DeliverySerializer(serializers.ModelSerializer):
    """Full serializer for Delivery model."""
    
    sender_phone = serializers.CharField(source='sender.phone_number', read_only=True)
    courier_phone = serializers.CharField(source='courier.phone_number', read_only=True)
    courier_name = serializers.CharField(source='courier.full_name', read_only=True)
    
    class Meta:
        model = Delivery
        fields = [
            'id', 'sender', 'sender_phone', 'recipient_phone', 'recipient_name',
            'courier', 'courier_phone', 'courier_name',
            'status', 'payment_method',
            'pickup_geo', 'pickup_address', 'dropoff_geo', 'dropoff_address',
            'dropoff_neighborhood', 'package_description', 'package_photo',
            'distance_km', 'total_price', 'platform_fee', 'courier_earning',
            'otp_code', 'created_at', 'assigned_at', 'picked_up_at', 'completed_at',
            'external_order_id', 'shop'
        ]
        read_only_fields = [
            'id', 'sender', 'courier', 'distance_km', 'total_price', 
            'platform_fee', 'courier_earning', 'otp_code',
            'created_at', 'assigned_at', 'picked_up_at', 'completed_at'
        ]


class DeliveryCreateSerializer(serializers.Serializer):
    """Serializer for creating a new delivery (WhatsApp flow)."""
    
    recipient_phone = serializers.CharField(max_length=15)
    recipient_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    pickup_latitude = serializers.FloatField()
    pickup_longitude = serializers.FloatField()
    dropoff_latitude = serializers.FloatField(required=False)
    dropoff_longitude = serializers.FloatField(required=False)
    dropoff_neighborhood_id = serializers.UUIDField(required=False)
    package_description = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH_P2P
    )

    def validate(self, data):
        # Must have either exact GPS or neighborhood
        has_gps = data.get('dropoff_latitude') and data.get('dropoff_longitude')
        has_neighborhood = data.get('dropoff_neighborhood_id')
        
        if not has_gps and not has_neighborhood:
            raise serializers.ValidationError(
                "Vous devez fournir soit les coordonnées GPS exactes, soit un quartier de destination."
            )
        return data


class QuoteRequestSerializer(serializers.Serializer):
    """Serializer for price estimation request (E-commerce API)."""
    
    shop_id = serializers.UUIDField()
    city = serializers.CharField(max_length=20)
    neighborhood = serializers.CharField(max_length=100, required=False)
    neighborhood_id = serializers.UUIDField(required=False)
    
    # Optional: exact destination GPS (higher precision)
    dropoff_latitude = serializers.FloatField(required=False)
    dropoff_longitude = serializers.FloatField(required=False)

    def validate(self, data):
        has_gps = data.get('dropoff_latitude') and data.get('dropoff_longitude')
        has_neighborhood = data.get('neighborhood') or data.get('neighborhood_id')
        
        if not has_gps and not has_neighborhood:
            raise serializers.ValidationError(
                "Fournissez un quartier ou des coordonnées GPS."
            )
        return data


class QuoteResponseSerializer(serializers.Serializer):
    """Serializer for price estimation response."""
    
    distance_km = serializers.FloatField()
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    courier_earning = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(default='XAF')
    estimation_type = serializers.CharField()  # 'exact' or 'neighborhood'


class OrderCreateSerializer(serializers.Serializer):
    """Serializer for creating order via E-commerce API."""
    
    shop_id = serializers.UUIDField()
    customer_phone = serializers.CharField(max_length=15)
    customer_name = serializers.CharField(max_length=150, required=False)
    neighborhood_id = serializers.UUIDField()
    items_description = serializers.CharField()
    external_order_id = serializers.CharField(max_length=100, required=False)


class DeliveryStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating delivery status."""
    
    status = serializers.ChoiceField(choices=DeliveryStatus.choices)
    otp_code = serializers.CharField(max_length=4, required=False)

    def validate(self, data):
        # OTP required for completion
        if data['status'] == DeliveryStatus.COMPLETED and not data.get('otp_code'):
            raise serializers.ValidationError(
                "Le code OTP est requis pour valider la livraison."
            )
        return data


class CourierAssignSerializer(serializers.Serializer):
    """Serializer for courier assignment."""
    
    courier_id = serializers.UUIDField()
