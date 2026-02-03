"""
FINANCE App - Wallet & Transaction Management for DELIVR-CM

Handles: Transactions, Wallet Operations, Commission Tracking
"""

import uuid
from django.db import models, transaction
from django.conf import settings
from decimal import Decimal


class TransactionType(models.TextChoices):
    """Transaction type enumeration."""
    # Credits (+)
    DEPOSIT = 'DEPOSIT', 'Dépôt'
    DELIVERY_CREDIT = 'DELIVERY_CREDIT', 'Crédit livraison'
    REFUND = 'REFUND', 'Remboursement'
    
    # Debits (-)
    COMMISSION = 'COMMISSION', 'Commission plateforme'
    WITHDRAWAL = 'WITHDRAWAL', 'Retrait'
    PREPAID_DEBIT = 'PREPAID_DEBIT', 'Débit prépayé'


class TransactionStatus(models.TextChoices):
    """Transaction status enumeration."""
    PENDING = 'PENDING', 'En attente'
    COMPLETED = 'COMPLETED', 'Confirmé'
    FAILED = 'FAILED', 'Échoué'
    REVERSED = 'REVERSED', 'Annulé'


class Transaction(models.Model):
    """
    Financial transaction record.
    
    All wallet movements must create a Transaction for audit trail.
    Amount can be positive (credit) or negative (debit).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name="Utilisateur"
    )
    
    # Transaction Details
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        verbose_name="Type"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant (XAF)"
    )
    balance_before = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Solde avant"
    )
    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Solde après"
    )
    
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.COMPLETED,
        verbose_name="Statut"
    )
    
    # Related Delivery (if applicable)
    delivery = models.ForeignKey(
        'logistics.Delivery',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name="Livraison liée"
    )
    
    # Metadata
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Description"
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence externe"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['transaction_type', 'status']),
        ]

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"{self.user.phone_number} | {sign}{self.amount} XAF | {self.transaction_type}"


class WalletService:
    """
    Service class for wallet operations.
    
    All operations use transaction.atomic() for data integrity.
    """

    @staticmethod
    @transaction.atomic
    def credit(user, amount: Decimal, transaction_type: str, 
               delivery=None, description: str = "") -> Transaction:
        """
        Credit a user's wallet (add money).
        
        Args:
            user: User instance
            amount: Positive decimal amount
            transaction_type: TransactionType value
            delivery: Optional related delivery
            description: Optional description
            
        Returns:
            Transaction instance
        """
        if amount <= 0:
            raise ValueError("Credit amount must be positive")
        
        # Lock user row for update
        user = user.__class__.objects.select_for_update().get(pk=user.pk)
        
        balance_before = user.wallet_balance
        user.wallet_balance += amount
        user.save(update_fields=['wallet_balance'])
        
        return Transaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=user.wallet_balance,
            delivery=delivery,
            description=description,
            status=TransactionStatus.COMPLETED
        )

    @staticmethod
    @transaction.atomic
    def debit(user, amount: Decimal, transaction_type: str,
              delivery=None, description: str = "", 
              allow_negative: bool = False) -> Transaction:
        """
        Debit a user's wallet (remove money).
        
        Args:
            user: User instance
            amount: Positive decimal amount (will be stored as negative)
            transaction_type: TransactionType value
            delivery: Optional related delivery
            description: Optional description
            allow_negative: Allow wallet to go negative (for couriers)
            
        Returns:
            Transaction instance
            
        Raises:
            ValueError: If insufficient funds and allow_negative is False
        """
        if amount <= 0:
            raise ValueError("Debit amount must be positive")
        
        # Lock user row for update
        user = user.__class__.objects.select_for_update().get(pk=user.pk)
        
        if not allow_negative and user.wallet_balance < amount:
            raise ValueError(f"Solde insuffisant: {user.wallet_balance} XAF")
        
        balance_before = user.wallet_balance
        user.wallet_balance -= amount
        user.save(update_fields=['wallet_balance'])
        
        return Transaction.objects.create(
            user=user,
            transaction_type=transaction_type,
            amount=-amount,  # Stored as negative
            balance_before=balance_before,
            balance_after=user.wallet_balance,
            delivery=delivery,
            description=description,
            status=TransactionStatus.COMPLETED
        )

    @staticmethod
    @transaction.atomic
    def process_cash_delivery(delivery) -> tuple:
        """
        Process financial operations for CASH_P2P delivery.
        
        Business Rule:
        - Courier keeps 100% cash from client
        - Platform DEBITS platform_fee from courier wallet (creates debt)
        
        Args:
            delivery: Completed Delivery instance
            
        Returns:
            Tuple of (courier_transaction,)
        """
        from core.models import UserRole
        
        courier = delivery.courier
        if not courier or courier.role != UserRole.COURIER:
            raise ValueError("Invalid courier for delivery")
        
        # Debit platform fee from courier (allow negative = debt)
        courier_tx = WalletService.debit(
            user=courier,
            amount=delivery.platform_fee,
            transaction_type=TransactionType.COMMISSION,
            delivery=delivery,
            description=f"Commission livraison {str(delivery.id)[:8]}",
            allow_negative=True  # Courier debt system
        )
        
        return (courier_tx,)

    @staticmethod
    @transaction.atomic
    def process_prepaid_delivery(delivery) -> tuple:
        """
        Process financial operations for PREPAID_WALLET delivery.
        
        Business Rule:
        - Business is debited total_price at order creation
        - Courier is CREDITED courier_earning at delivery completion
        
        Args:
            delivery: Completed Delivery instance
            
        Returns:
            Tuple of (courier_transaction,)
        """
        from core.models import UserRole
        
        courier = delivery.courier
        if not courier or courier.role != UserRole.COURIER:
            raise ValueError("Invalid courier for delivery")
        
        # Credit courier earning
        courier_tx = WalletService.credit(
            user=courier,
            amount=delivery.courier_earning,
            transaction_type=TransactionType.DELIVERY_CREDIT,
            delivery=delivery,
            description=f"Gain livraison {str(delivery.id)[:8]}"
        )
        
        return (courier_tx,)

    @staticmethod
    @transaction.atomic
    def debit_business_for_order(business, delivery) -> Transaction:
        """
        Debit business wallet when creating prepaid order.
        
        Args:
            business: Business user instance
            delivery: Delivery instance with calculated price
            
        Returns:
            Transaction instance
        """
        return WalletService.debit(
            user=business,
            amount=delivery.total_price,
            transaction_type=TransactionType.PREPAID_DEBIT,
            delivery=delivery,
            description=f"Commande {str(delivery.id)[:8]}",
            allow_negative=False  # Business must have sufficient funds
        )
