"""
E2E Tests for DELIVR-CM Delivery Flow

Tests the complete flow: creation → assignment → pickup → delivery → payment → receipt
"""

from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.gis.geos import Point
from django.utils import timezone
from unittest.mock import patch, MagicMock

from core.models import User, UserRole
from logistics.models import Delivery, DeliveryStatus, PaymentMethod, Neighborhood, City
from finance.models import Transaction, TransactionType, Invoice, InvoiceType


class E2EDeliveryFlowTest(TransactionTestCase):
    """
    End-to-end tests for the complete delivery lifecycle.
    """
    
    def setUp(self):
        """Set up test data."""
        # Create sender (client)
        self.sender = User.objects.create_user(
            phone_number='+237699000001',
            full_name='Test Client',
            role=UserRole.CLIENT
        )
        
        # Create courier with initial balance
        self.courier = User.objects.create_user(
            phone_number='+237699000002',
            full_name='Test Courier',
            role=UserRole.COURIER,
            is_verified=True,
            is_online=True,
            wallet_balance=Decimal('5000.00')
        )
        
        # Create business partner with wallet
        self.business = User.objects.create_user(
            phone_number='+237699000003',
            full_name='Test Business',
            role=UserRole.BUSINESS,
            is_business_approved=True,
            wallet_balance=Decimal('50000.00')
        )
        
        # Create neighborhoods
        self.pickup_neighborhood = Neighborhood.objects.create(
            city=City.DOUALA,
            name='Akwa',
            center_geo=Point(9.7042, 4.0502)
        )
        self.dropoff_neighborhood = Neighborhood.objects.create(
            city=City.DOUALA,
            name='Bonapriso',
            center_geo=Point(9.6877, 4.0205)
        )
        
        # GPS coordinates
        self.pickup_point = Point(9.7042, 4.0502)
        self.dropoff_point = Point(9.6877, 4.0205)
    
    def test_full_cash_delivery_flow(self):
        """
        Test complete CASH P2P delivery flow.
        
        Flow: Create → Assign → Pickup → Deliver → Payment processed
        """
        # 1. CREATE DELIVERY
        delivery = Delivery.objects.create(
            sender=self.sender,
            recipient_phone='+237699999999',
            recipient_name='Recipient Test',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            payment_method=PaymentMethod.CASH_P2P,
            distance_km=3.5,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00')
        )
        
        self.assertEqual(delivery.status, DeliveryStatus.PENDING)
        self.assertIsNotNone(delivery.otp_code)
        self.assertIsNotNone(delivery.pickup_otp)
        self.assertEqual(len(delivery.otp_code), 4)
        
        # 2. ASSIGN COURIER
        delivery.courier = self.courier
        delivery.status = DeliveryStatus.ASSIGNED
        delivery.assigned_at = timezone.now()
        delivery.save()
        
        self.assertEqual(delivery.status, DeliveryStatus.ASSIGNED)
        self.assertEqual(delivery.courier, self.courier)
        
        # 3. PICKUP (courier picks up package)
        delivery.status = DeliveryStatus.PICKED_UP
        delivery.picked_up_at = timezone.now()
        delivery.save()
        
        self.assertEqual(delivery.status, DeliveryStatus.PICKED_UP)
        
        # 4. IN TRANSIT
        delivery.status = DeliveryStatus.IN_TRANSIT
        delivery.in_transit_at = timezone.now()
        delivery.save()
        
        # 5. COMPLETE DELIVERY (signal auto-triggers financial processing)
        courier_initial_balance = self.courier.wallet_balance
        
        delivery.status = DeliveryStatus.COMPLETED
        delivery.completed_at = timezone.now()
        delivery.save()
        
        # Signal already calls WalletService.process_cash_delivery()
        # No need to call it manually again
        
        # Refresh courier from DB
        self.courier.refresh_from_db()
        
        # Verify courier balance decreased (owed platform fee)
        # Cash: courier keeps total_price, owes platform_fee
        expected_balance = courier_initial_balance - delivery.platform_fee
        self.assertEqual(self.courier.wallet_balance, expected_balance)
    
    def test_full_prepaid_delivery_flow(self):
        """
        Test complete PREPAID WALLET delivery flow.
        
        Flow: Merchant pays upfront → courier earns on completion
        """
        merchant_initial = self.business.wallet_balance
        courier_initial = self.courier.wallet_balance
        
        # 1. CREATE PREPAID DELIVERY
        delivery = Delivery.objects.create(
            sender=self.business,
            shop=self.business,
            recipient_phone='+237699888888',
            recipient_name='Prepaid Recipient',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            payment_method=PaymentMethod.PREPAID_WALLET,
            distance_km=4.0,
            total_price=Decimal('2000.00'),
            platform_fee=Decimal('400.00'),
            courier_earning=Decimal('1600.00')
        )
        
        # 2. ASSIGN & COMPLETE
        delivery.courier = self.courier
        delivery.status = DeliveryStatus.ASSIGNED
        delivery.assigned_at = timezone.now()
        delivery.save()
        
        delivery.status = DeliveryStatus.COMPLETED
        delivery.completed_at = timezone.now()
        delivery.save()
        
        # Signal already calls WalletService.process_prepaid_delivery()
        # No need to call it manually again
        
        # Refresh from DB
        self.business.refresh_from_db()
        self.courier.refresh_from_db()
        
        # Courier balance should increase by courier_earning
        expected_courier = courier_initial + delivery.courier_earning
        self.assertEqual(self.courier.wallet_balance, expected_courier)
    
    @patch('finance.invoice_service.InvoiceService._render_pdf')
    def test_receipt_generation_on_completion(self, mock_render_pdf):
        """
        Test automatic receipt PDF generation on delivery completion.
        """
        # Mock PDF rendering to return dummy bytes
        mock_render_pdf.return_value = b'%PDF-1.4 dummy pdf content'
        
        # Create and complete a delivery
        delivery = Delivery.objects.create(
            sender=self.sender,
            recipient_phone='+237699777777',
            recipient_name='Receipt Test',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            payment_method=PaymentMethod.CASH_P2P,
            distance_km=2.0,
            total_price=Decimal('1000.00'),
            platform_fee=Decimal('200.00'),
            courier_earning=Decimal('800.00'),
            status=DeliveryStatus.COMPLETED,
            completed_at=timezone.now()
        )
        delivery.courier = self.courier
        delivery.save()
        
        # Generate receipt
        from finance.invoice_service import InvoiceService
        invoice = InvoiceService.generate_delivery_receipt(delivery)
        
        # Verify invoice created
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.invoice_type, InvoiceType.DELIVERY_RECEIPT)
        self.assertEqual(invoice.delivery, delivery)
        self.assertEqual(invoice.amount, delivery.total_price)
        self.assertTrue(invoice.invoice_number.startswith('DLV-'))
        
        # Verify PDF was rendered
        mock_render_pdf.assert_called_once()
    
    def test_courier_debt_blocking(self):
        """
        Test that courier is blocked when debt exceeds ceiling.
        """
        # Set courier to negative balance beyond debt ceiling
        self.courier.wallet_balance = Decimal('-3000.00')
        self.courier.debt_ceiling = Decimal('2500.00')
        self.courier.save()
        
        self.assertTrue(self.courier.is_courier_blocked)
        
        # Positive balance should not block
        self.courier.wallet_balance = Decimal('1000.00')
        self.courier.save()
        
        self.assertFalse(self.courier.is_courier_blocked)
    
    def test_delivery_otp_generation(self):
        """
        Test that OTP codes are generated for both pickup and delivery.
        """
        delivery = Delivery.objects.create(
            sender=self.sender,
            recipient_phone='+237699666666',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            payment_method=PaymentMethod.CASH_P2P,
            total_price=Decimal('1000.00')
        )
        
        # Both OTPs should be generated
        self.assertIsNotNone(delivery.otp_code)
        self.assertIsNotNone(delivery.pickup_otp)
        self.assertEqual(len(delivery.otp_code), 4)
        self.assertEqual(len(delivery.pickup_otp), 4)
        
        # OTPs should be numeric
        self.assertTrue(delivery.otp_code.isdigit())
        self.assertTrue(delivery.pickup_otp.isdigit())


class DeliveryStatusTransitionsTest(TransactionTestCase):
    """
    Tests for valid status transitions.
    """
    
    def setUp(self):
        self.sender = User.objects.create_user(
            phone_number='+237699100001',
            role=UserRole.CLIENT
        )
        self.courier = User.objects.create_user(
            phone_number='+237699100002',
            role=UserRole.COURIER,
            is_verified=True
        )
        
        self.delivery = Delivery.objects.create(
            sender=self.sender,
            recipient_phone='+237699555555',
            pickup_geo=Point(9.7042, 4.0502),
            dropoff_geo=Point(9.6877, 4.0205),
            payment_method=PaymentMethod.CASH_P2P,
            total_price=Decimal('1000.00')
        )
    
    def test_valid_status_flow(self):
        """Test the happy path status transitions."""
        # PENDING → ASSIGNED
        self.delivery.courier = self.courier
        self.delivery.status = DeliveryStatus.ASSIGNED
        self.delivery.save()
        self.assertEqual(self.delivery.status, DeliveryStatus.ASSIGNED)
        
        # ASSIGNED → PICKED_UP
        self.delivery.status = DeliveryStatus.PICKED_UP
        self.delivery.save()
        self.assertEqual(self.delivery.status, DeliveryStatus.PICKED_UP)
        
        # PICKED_UP → IN_TRANSIT
        self.delivery.status = DeliveryStatus.IN_TRANSIT
        self.delivery.save()
        self.assertEqual(self.delivery.status, DeliveryStatus.IN_TRANSIT)
        
        # IN_TRANSIT → COMPLETED
        self.delivery.status = DeliveryStatus.COMPLETED
        self.delivery.save()
        self.assertEqual(self.delivery.status, DeliveryStatus.COMPLETED)
    
    def test_cancellation_from_pending(self):
        """Test cancellation from PENDING status."""
        self.delivery.status = DeliveryStatus.CANCELLED
        self.delivery.save()
        self.assertEqual(self.delivery.status, DeliveryStatus.CANCELLED)
