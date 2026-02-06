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


# ===========================================
# WITHDRAWAL MANAGEMENT
# ===========================================

class WithdrawalStatus(models.TextChoices):
    """Withdrawal request status."""
    PENDING = 'PENDING', 'En attente'
    PROCESSING = 'PROCESSING', 'En cours'
    COMPLETED = 'COMPLETED', 'Terminé'
    FAILED = 'FAILED', 'Échoué'
    REJECTED = 'REJECTED', 'Rejeté'


class MobileMoneyProvider(models.TextChoices):
    """Supported Mobile Money providers."""
    MTN_MOMO = 'MTN_MOMO', 'MTN Mobile Money'
    ORANGE_MONEY = 'ORANGE_MONEY', 'Orange Money'


class WithdrawalRequest(models.Model):
    """
    Courier withdrawal request to Mobile Money.
    
    Coureurs peuvent demander un retrait de leur solde positif
    vers leur compte Mobile Money (MTN ou Orange).
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='withdrawal_requests',
        verbose_name="Coursier"
    )
    
    # Amount
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant (XAF)"
    )
    
    # Mobile Money details
    provider = models.CharField(
        max_length=20,
        choices=MobileMoneyProvider.choices,
        verbose_name="Fournisseur"
    )
    phone_number = models.CharField(
        max_length=20,
        verbose_name="Numéro Mobile Money"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=WithdrawalStatus.choices,
        default=WithdrawalStatus.PENDING,
        verbose_name="Statut"
    )
    
    # External reference
    external_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID Transaction Mobile Money"
    )
    
    # Admin handling
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_withdrawals',
        verbose_name="Traité par"
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name="Raison du rejet"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Related transaction
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='withdrawal_request',
        verbose_name="Transaction associée"
    )
    
    class Meta:
        verbose_name = "Demande de retrait"
        verbose_name_plural = "Demandes de retrait"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['courier', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Retrait {self.amount} XAF - {self.courier.phone_number} - {self.status}"


class WithdrawalService:
    """
    Service for handling courier withdrawals.
    
    Validates requests, creates transactions, and handles Mobile Money API calls.
    """
    
    MINIMUM_WITHDRAWAL = Decimal('1000')  # Minimum 1000 XAF
    MAXIMUM_WITHDRAWAL = Decimal('500000')  # Maximum 500,000 XAF
    
    @classmethod
    @transaction.atomic
    def create_request(
        cls,
        courier,
        amount: Decimal,
        provider: str,
        phone_number: str = None
    ) -> WithdrawalRequest:
        """
        Create a withdrawal request.
        
        Args:
            courier: User instance (must be courier)
            amount: Amount to withdraw
            provider: MobileMoneyProvider value
            phone_number: Mobile money number (defaults to courier phone)
            
        Returns:
            WithdrawalRequest instance
            
        Raises:
            ValueError: If validation fails
        """
        from core.models import UserRole
        
        # Validate courier
        if courier.role != UserRole.COURIER:
            raise ValueError("Seuls les coursiers peuvent faire des retraits")
        
        if not courier.is_verified:
            raise ValueError("Compte coursier non vérifié")
        
        # Validate amount
        if amount < cls.MINIMUM_WITHDRAWAL:
            raise ValueError(f"Montant minimum: {cls.MINIMUM_WITHDRAWAL} XAF")
        
        if amount > cls.MAXIMUM_WITHDRAWAL:
            raise ValueError(f"Montant maximum: {cls.MAXIMUM_WITHDRAWAL} XAF")
        
        # Check balance
        if courier.wallet_balance < amount:
            raise ValueError(
                f"Solde insuffisant. Disponible: {courier.wallet_balance} XAF"
            )
        
        # Check for pending requests
        pending = WithdrawalRequest.objects.filter(
            courier=courier,
            status__in=[WithdrawalStatus.PENDING, WithdrawalStatus.PROCESSING]
        ).exists()
        
        if pending:
            raise ValueError("Vous avez déjà une demande de retrait en cours")
        
        # Use courier phone if not specified
        if not phone_number:
            phone_number = courier.phone_number
        
        # Create request
        withdrawal = WithdrawalRequest.objects.create(
            courier=courier,
            amount=amount,
            provider=provider,
            phone_number=phone_number
        )
        
        return withdrawal
    
    @classmethod
    @transaction.atomic
    def approve_request(cls, withdrawal: WithdrawalRequest, admin_user) -> Transaction:
        """
        Approve a withdrawal request and debit courier wallet.
        
        Args:
            withdrawal: WithdrawalRequest instance
            admin_user: Admin performing the action
            
        Returns:
            Transaction instance
        """
        from django.utils import timezone
        
        if withdrawal.status != WithdrawalStatus.PENDING:
            raise ValueError(f"Demande non en attente (statut: {withdrawal.status})")
        
        # Re-verify balance
        courier = withdrawal.courier
        if courier.wallet_balance < withdrawal.amount:
            raise ValueError("Solde insuffisant au moment de l'approbation")
        
        # Debit courier wallet
        tx = WalletService.debit(
            user=courier,
            amount=withdrawal.amount,
            transaction_type=TransactionType.WITHDRAWAL,
            description=f"Retrait {withdrawal.provider} - {withdrawal.phone_number}"
        )
        
        # Update withdrawal
        withdrawal.status = WithdrawalStatus.PROCESSING
        withdrawal.processed_by = admin_user
        withdrawal.processed_at = timezone.now()
        withdrawal.transaction = tx
        withdrawal.save()
        
        return tx
    
    @classmethod
    @transaction.atomic
    def complete_request(
        cls,
        withdrawal: WithdrawalRequest,
        external_transaction_id: str
    ):
        """
        Mark withdrawal as completed after Mobile Money confirmation.
        
        Args:
            withdrawal: WithdrawalRequest instance
            external_transaction_id: ID from Mobile Money provider
        """
        if withdrawal.status != WithdrawalStatus.PROCESSING:
            raise ValueError(f"Demande non en cours (statut: {withdrawal.status})")
        
        withdrawal.status = WithdrawalStatus.COMPLETED
        withdrawal.external_transaction_id = external_transaction_id
        withdrawal.save()
        
        # Send notification to courier
        cls._notify_courier(withdrawal, success=True)
    
    @classmethod
    @transaction.atomic
    def fail_request(cls, withdrawal: WithdrawalRequest, reason: str):
        """
        Mark withdrawal as failed and refund courier.
        
        Args:
            withdrawal: WithdrawalRequest instance
            reason: Failure reason
        """
        if withdrawal.status not in [WithdrawalStatus.PENDING, WithdrawalStatus.PROCESSING]:
            raise ValueError(f"Impossible d'échouer cette demande (statut: {withdrawal.status})")
        
        # Refund if already debited
        if withdrawal.transaction:
            WalletService.credit(
                user=withdrawal.courier,
                amount=withdrawal.amount,
                transaction_type=TransactionType.REFUND,
                description=f"Remboursement retrait échoué: {reason[:50]}"
            )
        
        withdrawal.status = WithdrawalStatus.FAILED
        withdrawal.rejection_reason = reason
        withdrawal.save()
        
        # Notify courier
        cls._notify_courier(withdrawal, success=False, reason=reason)
    
    @classmethod
    @transaction.atomic
    def reject_request(cls, withdrawal: WithdrawalRequest, admin_user, reason: str):
        """
        Reject a pending withdrawal request.
        
        Args:
            withdrawal: WithdrawalRequest instance
            admin_user: Admin performing the action
            reason: Rejection reason
        """
        from django.utils import timezone
        
        if withdrawal.status != WithdrawalStatus.PENDING:
            raise ValueError("Seules les demandes en attente peuvent être rejetées")
        
        withdrawal.status = WithdrawalStatus.REJECTED
        withdrawal.processed_by = admin_user
        withdrawal.processed_at = timezone.now()
        withdrawal.rejection_reason = reason
        withdrawal.save()
        
        # Notify courier
        cls._notify_courier(withdrawal, success=False, reason=reason)
    
    @staticmethod
    def _notify_courier(withdrawal: WithdrawalRequest, success: bool, reason: str = None):
        """Send WhatsApp notification to courier about withdrawal status."""
        try:
            from bot.courier_notifications import CourierNotificationService
            
            if success:
                message = (
                    f"✅ *Retrait Effectué!*\n\n"
                    f"💰 Montant: {withdrawal.amount:,.0f} XAF\n"
                    f"📱 Envoyé vers: {withdrawal.phone_number}\n\n"
                    f"Vérifiez votre compte {withdrawal.get_provider_display()}!"
                )
            else:
                message = (
                    f"❌ *Retrait Échoué*\n\n"
                    f"💰 Montant: {withdrawal.amount:,.0f} XAF\n"
                    f"📋 Raison: {reason or 'Non spécifiée'}\n\n"
                    f"Votre solde a été remboursé si applicable."
                )
            
            CourierNotificationService._send_message(
                withdrawal.courier.phone_number,
                message
            )
        except Exception:
            pass  # Non-critical, don't fail the operation


# ===========================================
# INVOICING SYSTEM
# ===========================================

class InvoiceType(models.TextChoices):
    """Invoice type enumeration."""
    DELIVERY_RECEIPT = 'DELIVERY_RECEIPT', 'Reçu de livraison'
    COURIER_STATEMENT = 'COURIER_STATEMENT', 'Relevé coursier'
    B2B_INVOICE = 'B2B_INVOICE', 'Facture partenaire'


class Invoice(models.Model):
    """
    Invoice/Receipt document with PDF generation.
    
    Supports three types:
    - DELIVERY_RECEIPT: Auto-generated on delivery completion
    - COURIER_STATEMENT: Monthly summary for couriers
    - B2B_INVOICE: Monthly billing for business partners
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Sequential invoice number (DLV-2026-000001)
    invoice_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Numéro de facture"
    )
    
    invoice_type = models.CharField(
        max_length=20,
        choices=InvoiceType.choices,
        verbose_name="Type"
    )
    
    # Related entities
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='invoices',
        verbose_name="Utilisateur"
    )
    
    delivery = models.ForeignKey(
        'logistics.Delivery',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name="Livraison liée"
    )
    
    # Financial summary
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant total (XAF)"
    )
    
    # Period (for statements/invoices)
    period_start = models.DateField(
        null=True,
        blank=True,
        verbose_name="Début période"
    )
    period_end = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fin période"
    )
    
    # Generated PDF
    pdf_file = models.FileField(
        upload_to='invoices/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Fichier PDF"
    )
    
    # Metadata
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'invoice_type']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.get_invoice_type_display()}"
    
    @classmethod
    def get_next_invoice_number(cls) -> str:
        """
        Generate next sequential invoice number.
        Format: DLV-YYYY-XXXXXX
        """
        from django.utils import timezone
        
        year = timezone.now().year
        prefix = f"DLV-{year}-"
        
        # Get the last invoice number for this year
        last_invoice = cls.objects.filter(
            invoice_number__startswith=prefix
        ).order_by('-invoice_number').first()
        
        if last_invoice:
            # Extract and increment the sequence
            try:
                last_seq = int(last_invoice.invoice_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"{prefix}{next_seq:06d}"


# ===========================================
# MOBILE PAYMENT (MTN MoMo, Orange Money)
# ===========================================

class MobilePaymentProvider(models.TextChoices):
    """Mobile payment provider enumeration."""
    MTN_MOMO = 'MTN', 'MTN Mobile Money'
    ORANGE_MONEY = 'OM', 'Orange Money'


class MobilePaymentStatus(models.TextChoices):
    """Mobile payment status enumeration."""
    PENDING = 'PENDING', 'En attente'
    SUCCESSFUL = 'SUCCESSFUL', 'Réussi'
    FAILED = 'FAILED', 'Échoué'
    CANCELLED = 'CANCELLED', 'Annulé'
    TIMEOUT = 'TIMEOUT', 'Expiré'
    REJECTED = 'REJECTED', 'Rejeté'


class MobilePayment(models.Model):
    """
    Mobile Money payment transaction.
    
    Tracks STK Push payments via MTN MoMo or Orange Money.
    Linked to a Delivery for payment confirmation flow.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to delivery
    delivery = models.ForeignKey(
        'logistics.Delivery',
        on_delete=models.CASCADE,
        related_name='mobile_payments',
        verbose_name="Livraison"
    )
    
    # Provider info
    provider = models.CharField(
        max_length=10,
        choices=MobilePaymentProvider.choices,
        verbose_name="Opérateur"
    )
    
    # Payer info
    phone_number = models.CharField(
        max_length=15,
        verbose_name="Numéro payeur"
    )
    
    # Amount
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant (XAF)"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=MobilePaymentStatus.choices,
        default=MobilePaymentStatus.PENDING,
        verbose_name="Statut"
    )
    
    # Provider references
    external_reference = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Référence externe",
        help_text="Notre UUID pour cette transaction"
    )
    provider_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID transaction opérateur"
    )
    
    # For Orange Money WebPayment
    pay_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Pay Token"
    )
    payment_url = models.URLField(
        blank=True,
        verbose_name="URL de paiement"
    )
    
    # Error tracking
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    
    # Callbacks
    callback_received = models.BooleanField(default=False)
    callback_data = models.JSONField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Paiement Mobile"
        verbose_name_plural = "Paiements Mobile"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['external_reference']),
            models.Index(fields=['delivery', 'status']),
            models.Index(fields=['provider', 'status']),
        ]
    
    def __str__(self):
        return f"{self.provider} | {self.amount} XAF | {self.status}"
    
    @classmethod
    def detect_provider(cls, phone: str) -> str:
        """
        Detect mobile money provider from phone number prefix.
        
        Cameroon prefixes:
        - MTN: 67x, 650-654, 68x
        - Orange: 69x, 655-659
        
        Args:
            phone: 9-digit phone number (e.g., 677123456)
            
        Returns:
            Provider choice value
        """
        # Normalize to 9 digits
        clean = ''.join(filter(str.isdigit, phone))
        if clean.startswith('237') and len(clean) > 9:
            clean = clean[3:]
        
        if len(clean) != 9 or not clean.startswith('6'):
            raise ValueError(f"Invalid Cameroon phone number: {phone}")
        
        prefix = clean[:2]
        prefix3 = clean[:3]
        
        # MTN prefixes
        if prefix in ('67', '68'):
            return MobilePaymentProvider.MTN_MOMO
        if prefix3 in ('650', '651', '652', '653', '654'):
            return MobilePaymentProvider.MTN_MOMO
        
        # Orange prefixes
        if prefix == '69':
            return MobilePaymentProvider.ORANGE_MONEY
        if prefix3 in ('655', '656', '657', '658', '659'):
            return MobilePaymentProvider.ORANGE_MONEY
        
        # Default to MTN for other 6x prefixes
        return MobilePaymentProvider.MTN_MOMO
