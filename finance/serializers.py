"""
Finance App Serializers - Transactions & Wallet
"""

from rest_framework import serializers
from .models import Transaction, TransactionType


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model."""
    
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    delivery_id = serializers.UUIDField(source='delivery.id', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'user', 'user_phone', 'transaction_type', 'amount',
            'balance_before', 'balance_after', 'status',
            'delivery', 'delivery_id', 'description', 'reference', 'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'balance_before', 'balance_after', 
            'status', 'created_at'
        ]


class TransactionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for transaction listings."""
    
    class Meta:
        model = Transaction
        fields = ['id', 'transaction_type', 'amount', 'balance_after', 'created_at']


class DepositSerializer(serializers.Serializer):
    """Serializer for wallet deposit (Admin only)."""
    
    user_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=100)
    reference = serializers.CharField(max_length=100, required=False)
    description = serializers.CharField(max_length=255, required=False)


class WithdrawalSerializer(serializers.Serializer):
    """Serializer for wallet withdrawal request."""
    
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=500)
    
    def validate_amount(self, value):
        user = self.context.get('user')
        if user and user.wallet_balance < value:
            raise serializers.ValidationError(
                f"Solde insuffisant. Disponible: {user.wallet_balance} XAF"
            )
        return value


class WalletSummarySerializer(serializers.Serializer):
    """Serializer for wallet summary response."""
    
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    debt_ceiling = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_blocked = serializers.BooleanField()
    available_for_withdrawal = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_earned = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_commission_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
