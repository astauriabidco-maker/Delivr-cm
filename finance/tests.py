"""
DELIVR-CM Finance Tests
========================

Tests for:
1. WalletService (credit, debit, atomic transactions)
2. Cash delivery financial processing
3. Prepaid delivery financial processing
4. Debt accumulation & blocking
5. Transaction audit trail
"""

from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError

from core.models import User, UserRole
from logistics.models import Delivery, DeliveryStatus, PaymentMethod, Neighborhood, City
from finance.models import (
    Transaction, TransactionType, TransactionStatus, 
    WalletService
)
from django.contrib.gis.geos import Point


class TestWalletService(TestCase):
    """Tests for WalletService credit/debit operations."""
    
    def setUp(self):
        """Create test users and delivery."""
        self.courier = User.objects.create_user(
            phone_number='+237699100001',
            password='testpass123',
            role=UserRole.COURIER,
            full_name='Test Courier',
            wallet_balance=Decimal('0.00'),
        )
        self.client_user = User.objects.create_user(
            phone_number='+237699100002',
            password='testpass123',
            role=UserRole.CLIENT,
            full_name='Test Client',
        )
        self.business = User.objects.create_user(
            phone_number='+237699100003',
            password='testpass123',
            role=UserRole.BUSINESS,
            full_name='Test Business',
            wallet_balance=Decimal('50000.00'),
        )
    
    # ==========================================
    # Credit Operations
    # ==========================================
    
    def test_credit_increases_balance(self):
        """Crediting should increase wallet balance."""
        initial = self.courier.wallet_balance
        WalletService.credit(
            user=self.courier,
            amount=Decimal('5000.00'),
            transaction_type=TransactionType.DEPOSIT,
            description='Test deposit',
        )
        self.courier.refresh_from_db()
        self.assertEqual(
            self.courier.wallet_balance, 
            initial + Decimal('5000.00')
        )
    
    def test_credit_creates_transaction_record(self):
        """Credit should create a Transaction for audit trail."""
        tx = WalletService.credit(
            user=self.courier,
            amount=Decimal('3000.00'),
            transaction_type=TransactionType.DEPOSIT,
            description='Audit test',
        )
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, Decimal('3000.00'))
        self.assertEqual(tx.transaction_type, TransactionType.DEPOSIT)
        self.assertEqual(tx.status, TransactionStatus.COMPLETED)
        self.assertEqual(tx.user, self.courier)
    
    def test_credit_negative_amount_rejected(self):
        """Credit with negative amount should raise ValueError."""
        with self.assertRaises(ValueError):
            WalletService.credit(
                user=self.courier,
                amount=Decimal('-100.00'),
                transaction_type=TransactionType.DEPOSIT,
            )
    
    def test_credit_zero_amount_rejected(self):
        """Credit with zero amount should raise ValueError."""
        with self.assertRaises(ValueError):
            WalletService.credit(
                user=self.courier,
                amount=Decimal('0.00'),
                transaction_type=TransactionType.DEPOSIT,
            )
    
    # ==========================================
    # Debit Operations
    # ==========================================
    
    def test_debit_decreases_balance(self):
        """Debiting should decrease wallet balance."""
        self.courier.wallet_balance = Decimal('5000.00')
        self.courier.save()
        
        WalletService.debit(
            user=self.courier,
            amount=Decimal('2000.00'),
            transaction_type=TransactionType.COMMISSION,
            description='Commission test',
        )
        self.courier.refresh_from_db()
        self.assertEqual(self.courier.wallet_balance, Decimal('3000.00'))
    
    def test_debit_allows_negative_for_couriers(self):
        """Courier debit should allow negative balance (debt system)."""
        self.courier.wallet_balance = Decimal('0.00')
        self.courier.save()
        
        WalletService.debit(
            user=self.courier,
            amount=Decimal('300.00'),
            transaction_type=TransactionType.COMMISSION,
            allow_negative=True,
        )
        self.courier.refresh_from_db()
        self.assertEqual(self.courier.wallet_balance, Decimal('-300.00'))
    
    def test_debit_rejects_insufficient_funds_when_not_allowed(self):
        """Debit should fail when insufficient funds and negative not allowed."""
        self.client_user.wallet_balance = Decimal('100.00')
        self.client_user.save()
        
        with self.assertRaises(ValueError):
            WalletService.debit(
                user=self.client_user,
                amount=Decimal('500.00'),
                transaction_type=TransactionType.WITHDRAWAL,
                allow_negative=False,
            )
    
    def test_debit_creates_transaction_record(self):
        """Debit should create an audit transaction."""
        self.courier.wallet_balance = Decimal('5000.00')
        self.courier.save()
        
        tx = WalletService.debit(
            user=self.courier,
            amount=Decimal('1500.00'),
            transaction_type=TransactionType.WITHDRAWAL,
        )
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, Decimal('-1500.00'))
    
    # ==========================================
    # Cash Delivery Processing (CASH_P2P)
    # ==========================================
    
    def _create_delivery(self, payment_method, total_price, platform_fee, courier_earning):
        """Helper to create a test delivery."""
        return Delivery.objects.create(
            sender=self.client_user,
            courier=self.courier,
            status=DeliveryStatus.COMPLETED,
            payment_method=payment_method,
            pickup_geo=Point(9.7, 4.05),
            dropoff_geo=Point(9.75, 4.06),
            distance_km=5.0,
            total_price=total_price,
            platform_fee=platform_fee,
            courier_earning=courier_earning,
        )
    
    def test_cash_delivery_debits_platform_fee(self):
        """
        CASH_P2P: Courier keeps 100% cash, 
        platform DEBITS platform_fee from wallet.
        """
        delivery = self._create_delivery(
            payment_method=PaymentMethod.CASH_P2P,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00'),
        )
        
        initial_balance = self.courier.wallet_balance
        WalletService.process_cash_delivery(delivery)
        
        self.courier.refresh_from_db()
        # Platform debits 300 XAF from courier
        self.assertEqual(
            self.courier.wallet_balance, 
            initial_balance - Decimal('300.00')
        )
    
    def test_cash_delivery_creates_debt(self):
        """
        CASH_P2P on zero-balance courier should create debt.
        Example: Balance 0 -> Balance -300 (debt)
        """
        self.courier.wallet_balance = Decimal('0.00')
        self.courier.save()
        
        delivery = self._create_delivery(
            payment_method=PaymentMethod.CASH_P2P,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00'),
        )
        
        WalletService.process_cash_delivery(delivery)
        self.courier.refresh_from_db()
        self.assertEqual(self.courier.wallet_balance, Decimal('-300.00'))
    
    # ==========================================
    # Prepaid Delivery Processing (PREPAID_WALLET)
    # ==========================================
    
    def test_prepaid_delivery_credits_courier(self):
        """
        PREPAID_WALLET: Courier is CREDITED courier_earning.
        Example: Balance -300 -> Balance +900 (if earning is 1200)
        """
        self.courier.wallet_balance = Decimal('-300.00')
        self.courier.save()
        
        delivery = self._create_delivery(
            payment_method=PaymentMethod.PREPAID_WALLET,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00'),
        )
        
        WalletService.process_prepaid_delivery(delivery)
        self.courier.refresh_from_db()
        # -300 + 1200 = 900
        self.assertEqual(self.courier.wallet_balance, Decimal('900.00'))
    
    def test_prepaid_debit_business(self):
        """
        PREPAID: Business is debited total_price at order creation.
        """
        self.business.wallet_balance = Decimal('50000.00')
        self.business.save()
        
        delivery = self._create_delivery(
            payment_method=PaymentMethod.PREPAID_WALLET,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00'),
        )
        
        WalletService.debit_business_for_order(self.business, delivery)
        self.business.refresh_from_db()
        self.assertEqual(
            self.business.wallet_balance,
            Decimal('48500.00')  # 50000 - 1500
        )
    
    # ==========================================
    # Atomic Transaction Integrity
    # ==========================================
    
    def test_multiple_operations_are_atomic(self):
        """Multiple wallet ops should maintain balance consistency."""
        self.courier.wallet_balance = Decimal('10000.00')
        self.courier.save()
        
        # Perform multiple operations
        WalletService.debit(
            self.courier, Decimal('3000.00'), 
            TransactionType.COMMISSION,
        )
        WalletService.credit(
            self.courier, Decimal('5000.00'), 
            TransactionType.DELIVERY_CREDIT,
        )
        WalletService.debit(
            self.courier, Decimal('1000.00'),
            TransactionType.WITHDRAWAL,
        )
        
        self.courier.refresh_from_db()
        # 10000 - 3000 + 5000 - 1000 = 11000
        self.assertEqual(self.courier.wallet_balance, Decimal('11000.00'))
    
    def test_transaction_count_matches_operations(self):
        """Each wallet operation should create exactly one transaction."""
        initial_count = Transaction.objects.filter(user=self.courier).count()
        
        WalletService.credit(
            self.courier, Decimal('1000.00'),
            TransactionType.DEPOSIT,
        )
        WalletService.debit(
            self.courier, Decimal('500.00'),
            TransactionType.COMMISSION,
        )
        
        final_count = Transaction.objects.filter(user=self.courier).count()
        self.assertEqual(final_count, initial_count + 2)


class TestDebtAccumulation(TestCase):
    """Test the accumulation of debt across multiple deliveries."""
    
    def setUp(self):
        self.courier = User.objects.create_user(
            phone_number='+237699200001',
            password='testpass123',
            role=UserRole.COURIER,
            full_name='Debt Test Courier',
            wallet_balance=Decimal('0.00'),
            debt_ceiling=Decimal('2500.00'),
        )
        self.sender = User.objects.create_user(
            phone_number='+237699200002',
            password='testpass123',
            role=UserRole.CLIENT,
        )
    
    def _do_cash_delivery(self, amount, fee):
        """Simulate a cash delivery and process finances."""
        delivery = Delivery.objects.create(
            sender=self.sender,
            courier=self.courier,
            status=DeliveryStatus.COMPLETED,
            payment_method=PaymentMethod.CASH_P2P,
            pickup_geo=Point(9.7, 4.05),
            dropoff_geo=Point(9.75, 4.06),
            distance_km=3.0,
            total_price=amount,
            platform_fee=fee,
            courier_earning=amount - fee,
        )
        WalletService.process_cash_delivery(delivery)
        self.courier.refresh_from_db()
    
    def test_debt_accumulates_over_deliveries(self):
        """Debt should accumulate across multiple cash deliveries."""
        # 3 deliveries at 300 XAF commission each
        self._do_cash_delivery(Decimal('1500.00'), Decimal('300.00'))
        self.assertEqual(self.courier.wallet_balance, Decimal('-300.00'))
        
        self._do_cash_delivery(Decimal('1500.00'), Decimal('300.00'))
        self.assertEqual(self.courier.wallet_balance, Decimal('-600.00'))
        
        self._do_cash_delivery(Decimal('1500.00'), Decimal('300.00'))
        self.assertEqual(self.courier.wallet_balance, Decimal('-900.00'))
    
    def test_courier_blocked_at_ceiling(self):
        """Courier should get blocked when debt exceeds ceiling."""
        # Simulate enough deliveries to exceed 2500 XAF debt
        for _ in range(9):  # 9 * 300 = 2700 > 2500
            self._do_cash_delivery(Decimal('1500.00'), Decimal('300.00'))
        
        self.courier.refresh_from_db()
        self.assertTrue(self.courier.wallet_balance < -self.courier.debt_ceiling)
        self.assertTrue(self.courier.is_courier_blocked)
