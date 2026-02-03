"""
Finance App Views - Transactions & Wallet API
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum

from .models import Transaction, TransactionType, WalletService
from .serializers import (
    TransactionSerializer, TransactionListSerializer,
    DepositSerializer, WithdrawalSerializer, WalletSummarySerializer
)
from core.models import UserRole


class IsAdminUser(permissions.BasePermission):
    """Permission for admin users only."""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == UserRole.ADMIN


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Transaction (read-only).
    Users can only see their own transactions.
    """
    
    queryset = Transaction.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TransactionListSerializer
        return TransactionSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.role == UserRole.ADMIN:
            return Transaction.objects.all()
        return Transaction.objects.filter(user=user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get transaction summary for current user."""
        user = request.user
        transactions = Transaction.objects.filter(user=user)
        
        credits = transactions.filter(amount__gt=0).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        debits = transactions.filter(amount__lt=0).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        return Response({
            'total_transactions': transactions.count(),
            'total_credits': credits,
            'total_debits': abs(debits),
            'net': credits + debits
        })


class WalletViewSet(viewsets.ViewSet):
    """
    ViewSet for wallet operations.
    """
    
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get current wallet balance."""
        user = request.user
        
        # Calculate totals
        earned = Transaction.objects.filter(
            user=user,
            transaction_type=TransactionType.DELIVERY_CREDIT
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        commission = Transaction.objects.filter(
            user=user,
            transaction_type=TransactionType.COMMISSION
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        data = {
            'balance': user.wallet_balance,
            'debt_ceiling': user.debt_ceiling,
            'is_blocked': getattr(user, 'is_courier_blocked', False),
            'available_for_withdrawal': max(0, user.wallet_balance),
            'total_earned': earned,
            'total_commission_paid': abs(commission)
        }
        
        return Response(WalletSummarySerializer(data).data)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def deposit(self, request):
        """
        Make a deposit to a user's wallet (Admin only).
        Used for manual top-ups or refunds.
        """
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            user = User.objects.get(pk=data['user_id'])
        except User.DoesNotExist:
            return Response(
                {'error': 'Utilisateur non trouvé.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        transaction = WalletService.credit(
            user=user,
            amount=data['amount'],
            transaction_type=TransactionType.DEPOSIT,
            description=data.get('description', 'Dépôt manuel')
        )
        
        return Response({
            'message': f"Dépôt de {data['amount']} XAF effectué.",
            'new_balance': user.wallet_balance,
            'transaction_id': str(transaction.id)
        })

    @action(detail=False, methods=['post'])
    def request_withdrawal(self, request):
        """
        Request a withdrawal.
        Only available if balance is positive.
        """
        serializer = WithdrawalSerializer(
            data=request.data,
            context={'user': request.user}
        )
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        
        if request.user.wallet_balance < amount:
            return Response(
                {'error': 'Solde insuffisant.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create pending withdrawal transaction
        transaction = WalletService.debit(
            user=request.user,
            amount=amount,
            transaction_type=TransactionType.WITHDRAWAL,
            description='Demande de retrait'
        )
        
        return Response({
            'message': 'Demande de retrait enregistrée.',
            'amount': amount,
            'new_balance': request.user.wallet_balance,
            'transaction_id': str(transaction.id)
        })

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get wallet transaction history."""
        transactions = Transaction.objects.filter(
            user=request.user
        ).order_by('-created_at')[:50]
        
        serializer = TransactionListSerializer(transactions, many=True)
        return Response(serializer.data)
