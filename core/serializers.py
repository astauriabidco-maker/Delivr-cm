"""
Core App Serializers - User Management
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model (read operations)."""
    
    is_courier_blocked = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'id', 'phone_number', 'full_name', 'role',
            'wallet_balance', 'debt_ceiling', 'is_verified',
            'is_courier_blocked', 'is_active', 'date_joined'
        ]
        read_only_fields = ['id', 'wallet_balance', 'is_verified', 'date_joined']


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password]
    )
    
    class Meta:
        model = User
        fields = ['phone_number', 'password', 'full_name', 'role']
    
    def create(self, validated_data):
        user = User.objects.create_user(
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
            full_name=validated_data.get('full_name', ''),
            role=validated_data.get('role', 'CLIENT')
        )
        return user


class CourierProfileSerializer(serializers.ModelSerializer):
    """Serializer for courier profile with location update."""
    
    class Meta:
        model = User
        fields = [
            'id', 'phone_number', 'full_name', 'role',
            'wallet_balance', 'debt_ceiling', 'is_verified',
            'is_courier_blocked', 'last_location', 'last_location_updated'
        ]
        read_only_fields = [
            'id', 'phone_number', 'role', 'wallet_balance', 
            'debt_ceiling', 'is_verified', 'is_courier_blocked'
        ]


class CourierLocationUpdateSerializer(serializers.Serializer):
    """Serializer for updating courier GPS location."""
    
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class CourierDocumentsSerializer(serializers.ModelSerializer):
    """Serializer for courier document upload."""
    
    class Meta:
        model = User
        fields = ['cni_document', 'moto_document']
