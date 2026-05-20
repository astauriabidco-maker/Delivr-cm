"""
E2E Tests for RELAY237 Delivery Flow

Tests the complete flow: creation → assignment → pickup → delivery → payment → receipt
"""

from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient
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
        self.api_client = APIClient()

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

    @patch('finance.invoice_service.InvoiceService.send_receipt_via_whatsapp')
    @patch('finance.invoice_service.InvoiceService.generate_delivery_receipt')
    @patch('logistics.rating_service.RatingService.send_rating_request_via_whatsapp')
    def test_api_completion_processes_cash_finances_once(
        self,
        mock_rating_request,
        mock_generate_receipt,
        mock_send_receipt,
    ):
        """Completing via the API should not process wallet transactions twice."""
        mock_generate_receipt.return_value = MagicMock(invoice_number='DLV-TEST')

        delivery = Delivery.objects.create(
            sender=self.sender,
            courier=self.courier,
            recipient_phone='+237699999998',
            recipient_name='API Recipient',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            payment_method=PaymentMethod.CASH_P2P,
            status=DeliveryStatus.IN_TRANSIT,
            distance_km=3.5,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00')
        )
        courier_initial_balance = self.courier.wallet_balance

        self.api_client.force_authenticate(user=self.courier)
        response = self.api_client.post(
            f'/api/deliveries/{delivery.id}/update_status/',
            {
                'status': DeliveryStatus.COMPLETED,
                'otp_code': delivery.otp_code,
            },
            format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.courier.refresh_from_db()
        self.assertEqual(
            self.courier.wallet_balance,
            courier_initial_balance - delivery.platform_fee
        )
        self.assertEqual(
            Transaction.objects.filter(
                delivery=delivery,
                user=self.courier,
                transaction_type=TransactionType.COMMISSION,
            ).count(),
            1
        )

    @patch('bot.whatsapp_service.send_delivery_completed_notification')
    @patch('logistics.events.broadcast_delivery_update')
    @patch('finance.invoice_service.InvoiceService.send_receipt_via_whatsapp')
    @patch('finance.invoice_service.InvoiceService.generate_delivery_receipt')
    @patch('logistics.rating_service.RatingService.send_rating_request_via_whatsapp')
    def test_mobile_cash_dropoff_debits_commission_once(
        self,
        mock_rating_request,
        mock_generate_receipt,
        mock_send_receipt,
        mock_broadcast,
        mock_completed_notification,
    ):
        """Mobile cash completion should debit only the platform fee."""
        mock_generate_receipt.return_value = MagicMock(invoice_number='DLV-TEST')

        delivery = Delivery.objects.create(
            sender=self.sender,
            courier=self.courier,
            recipient_phone='+237699999997',
            recipient_name='Mobile Cash Recipient',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            payment_method=PaymentMethod.CASH_P2P,
            status=DeliveryStatus.IN_TRANSIT,
            distance_km=3.5,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00')
        )
        courier_initial_balance = self.courier.wallet_balance

        self.api_client.force_authenticate(user=self.courier)
        response = self.api_client.post(
            f'/api/mobile/deliveries/{delivery.id}/confirm-dropoff/',
            {'otp': delivery.otp_code},
            format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['wallet_delta'], -300.0)
        self.assertEqual(
            response.data['wallet_balance'],
            float(courier_initial_balance - delivery.platform_fee)
        )
        self.assertEqual(response.data['wallet_transaction_type'], TransactionType.COMMISSION)
        self.courier.refresh_from_db()
        self.assertEqual(
            self.courier.wallet_balance,
            courier_initial_balance - delivery.platform_fee
        )
        self.assertEqual(
            Transaction.objects.filter(
                delivery=delivery,
                user=self.courier,
                transaction_type=TransactionType.COMMISSION,
            ).count(),
            1
        )
        self.assertEqual(
            Transaction.objects.filter(
                delivery=delivery,
                user=self.courier,
                transaction_type=TransactionType.DELIVERY_CREDIT,
            ).count(),
            0
        )

    def test_mobile_dashboard_serializes_active_and_recent_deliveries(self):
        """Dashboard should expose the active delivery and recent completed deliveries."""
        active_delivery = Delivery.objects.create(
            sender=self.sender,
            courier=self.courier,
            recipient_phone='+237699999991',
            recipient_name='Active Recipient',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            pickup_address='Akwa pickup',
            dropoff_address='Bonapriso dropoff',
            payment_method=PaymentMethod.CASH_P2P,
            status=DeliveryStatus.ARRIVED_PICKUP,
            assigned_at=timezone.now(),
            distance_km=3.5,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00')
        )
        recent_delivery = Delivery.objects.create(
            sender=self.sender,
            courier=self.courier,
            recipient_phone='+237699999990',
            recipient_name='Recent Recipient',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            pickup_address='Akwa recent pickup',
            dropoff_address='Bonapriso recent dropoff',
            payment_method=PaymentMethod.CASH_P2P,
            status=DeliveryStatus.ASSIGNED,
            distance_km=4.0,
            total_price=Decimal('2000.00'),
            platform_fee=Decimal('400.00'),
            courier_earning=Decimal('1600.00')
        )
        completed_at = timezone.now()
        Delivery.objects.filter(id=recent_delivery.id).update(
            status=DeliveryStatus.COMPLETED,
            completed_at=completed_at,
        )

        self.api_client.force_authenticate(user=self.courier)
        response = self.api_client.get('/api/mobile/dashboard/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_active_delivery'])
        self.assertEqual(response.data['active_delivery_id'], str(active_delivery.id))
        self.assertEqual(response.data['active_delivery']['id'], str(active_delivery.id))
        self.assertEqual(
            response.data['active_delivery']['status'],
            DeliveryStatus.ARRIVED_PICKUP,
        )
        self.assertEqual(
            response.data['active_delivery']['pickup_address'],
            'Akwa pickup',
        )
        self.assertEqual(len(response.data['recent_deliveries']), 1)
        self.assertEqual(
            response.data['recent_deliveries'][0]['id'],
            str(recent_delivery.id),
        )
        self.assertEqual(
            response.data['recent_deliveries'][0]['completed_at'],
            completed_at.isoformat(),
        )

    @patch('bot.whatsapp_service.send_delivery_completed_notification')
    @patch('logistics.events.broadcast_delivery_update')
    @patch('finance.invoice_service.InvoiceService.send_receipt_via_whatsapp')
    @patch('finance.invoice_service.InvoiceService.generate_delivery_receipt')
    @patch('logistics.rating_service.RatingService.send_rating_request_via_whatsapp')
    def test_mobile_prepaid_dropoff_credits_courier_once(
        self,
        mock_rating_request,
        mock_generate_receipt,
        mock_send_receipt,
        mock_broadcast,
        mock_completed_notification,
    ):
        """Mobile prepaid completion should credit courier earning once."""
        mock_generate_receipt.return_value = MagicMock(invoice_number='DLV-TEST')

        delivery = Delivery.objects.create(
            sender=self.business,
            shop=self.business,
            courier=self.courier,
            recipient_phone='+237699999996',
            recipient_name='Mobile Prepaid Recipient',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            payment_method=PaymentMethod.PREPAID_WALLET,
            status=DeliveryStatus.IN_TRANSIT,
            distance_km=4.0,
            total_price=Decimal('2000.00'),
            platform_fee=Decimal('400.00'),
            courier_earning=Decimal('1600.00')
        )
        courier_initial_balance = self.courier.wallet_balance

        self.api_client.force_authenticate(user=self.courier)
        response = self.api_client.post(
            f'/api/mobile/deliveries/{delivery.id}/confirm-dropoff/',
            {'otp': delivery.otp_code},
            format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['wallet_delta'], 1600.0)
        self.assertEqual(
            response.data['wallet_balance'],
            float(courier_initial_balance + delivery.courier_earning)
        )
        self.assertEqual(response.data['wallet_transaction_type'], TransactionType.DELIVERY_CREDIT)
        self.courier.refresh_from_db()
        self.assertEqual(
            self.courier.wallet_balance,
            courier_initial_balance + delivery.courier_earning
        )
        self.assertEqual(
            Transaction.objects.filter(
                delivery=delivery,
                user=self.courier,
                transaction_type=TransactionType.DELIVERY_CREDIT,
            ).count(),
            1
        )

    @patch('logistics.events.broadcast_delivery_update')
    def test_mobile_status_update_cannot_complete_without_otp(self, mock_broadcast):
        """The generic mobile status endpoint must not bypass dropoff OTP."""
        delivery = Delivery.objects.create(
            sender=self.sender,
            courier=self.courier,
            recipient_phone='+237699999994',
            recipient_name='Mobile Status Recipient',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            payment_method=PaymentMethod.CASH_P2P,
            status=DeliveryStatus.ARRIVED_DROPOFF,
            distance_km=3.5,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00')
        )
        courier_initial_balance = self.courier.wallet_balance

        self.api_client.force_authenticate(user=self.courier)
        response = self.api_client.patch(
            f'/api/mobile/deliveries/{delivery.id}/status/',
            {'status': DeliveryStatus.COMPLETED},
            format='json'
        )

        self.assertEqual(response.status_code, 400)
        delivery.refresh_from_db()
        self.courier.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.ARRIVED_DROPOFF)
        self.assertEqual(self.courier.wallet_balance, courier_initial_balance)
        self.assertEqual(Transaction.objects.filter(delivery=delivery).count(), 0)
        mock_broadcast.assert_not_called()

    @patch('logistics.events.broadcast_delivery_update')
    def test_mobile_status_update_cannot_pickup_without_otp(self, mock_broadcast):
        """The generic mobile status endpoint must not bypass pickup OTP."""
        delivery = Delivery.objects.create(
            sender=self.sender,
            courier=self.courier,
            recipient_phone='+237699999993',
            recipient_name='Mobile Pickup Recipient',
            pickup_geo=self.pickup_point,
            dropoff_geo=self.dropoff_point,
            payment_method=PaymentMethod.CASH_P2P,
            status=DeliveryStatus.ARRIVED_PICKUP,
            distance_km=3.5,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00')
        )

        self.api_client.force_authenticate(user=self.courier)
        response = self.api_client.patch(
            f'/api/mobile/deliveries/{delivery.id}/status/',
            {'status': DeliveryStatus.PICKED_UP},
            format='json'
        )

        self.assertEqual(response.status_code, 400)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, DeliveryStatus.ARRIVED_PICKUP)
        mock_broadcast.assert_not_called()

    def test_b2b_order_rolls_back_when_wallet_debit_fails(self):
        """A prepaid B2B order must not dispatch if the wallet debit fails."""
        self.business.last_location = self.pickup_point
        self.business.save(update_fields=['last_location'])

        fake_pricing_engine = MagicMock()
        fake_pricing_engine.estimate_from_neighborhood.return_value = (
            3.5,
            Decimal('1500.00'),
            Decimal('300.00'),
            Decimal('1200.00'),
        )

        with patch('logistics.views.pricing_engine', return_value=fake_pricing_engine), \
            patch(
                'logistics.views.WalletService.debit_business_for_order',
                side_effect=ValueError('Solde insuffisant: débit concurrent'),
            ) as mock_debit, \
            patch('bot.whatsapp_service.send_order_confirmation_to_sender') as mock_confirmation, \
            patch('bot.whatsapp_service.send_otp_to_recipient') as mock_otp, \
            patch('logistics.events.broadcast_new_delivery') as mock_broadcast, \
            patch('logistics.services.smart_dispatch.smart_dispatch_order') as mock_dispatch:
            self.api_client.force_authenticate(user=self.business)
            response = self.api_client.post(
                '/api/orders/',
                {
                    'shop_id': str(self.business.id),
                    'customer_phone': '+237699999995',
                    'customer_name': 'Rollback Client',
                    'neighborhood_id': str(self.dropoff_neighborhood.id),
                    'items_description': 'Test package',
                    'external_order_id': 'rollback-test',
                },
                format='json'
            )

        self.assertEqual(response.status_code, 402)
        self.assertTrue(mock_debit.called)
        self.assertFalse(
            Delivery.objects.filter(external_order_id='rollback-test').exists()
        )
        self.assertFalse(
            User.objects.filter(phone_number='+237699999995').exists()
        )
        mock_confirmation.assert_not_called()
        mock_otp.assert_not_called()
        mock_broadcast.assert_not_called()
        mock_dispatch.assert_not_called()

    def test_b2b_order_creation_is_idempotent_for_external_order_id(self):
        """A WooCommerce retry must not create or debit the same order twice."""
        self.business.last_location = self.pickup_point
        self.business.save(update_fields=['last_location'])
        initial_balance = self.business.wallet_balance

        fake_pricing_engine = MagicMock()
        fake_pricing_engine.estimate_from_neighborhood.return_value = (
            3.5,
            Decimal('1500.00'),
            Decimal('300.00'),
            Decimal('1200.00'),
        )
        payload = {
            'shop_id': str(self.business.id),
            'customer_phone': '+237699999994',
            'customer_name': 'Idempotent Client',
            'neighborhood_id': str(self.dropoff_neighborhood.id),
            'items_description': 'Retry-safe package',
            'external_order_id': 'woo-4242',
        }

        with patch('logistics.views.pricing_engine', return_value=fake_pricing_engine), \
            patch('bot.whatsapp_service.send_order_confirmation_to_sender'), \
            patch('bot.whatsapp_service.send_otp_to_recipient'), \
            patch('logistics.events.broadcast_new_delivery'), \
            patch('logistics.services.smart_dispatch.smart_dispatch_order'):
            self.api_client.force_authenticate(user=self.business)
            first_response = self.api_client.post('/api/orders/', payload, format='json')
            second_response = self.api_client.post('/api/orders/', payload, format='json')

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertTrue(second_response.data['idempotent'])
        self.assertEqual(
            first_response.data['delivery_id'],
            second_response.data['delivery_id']
        )
        self.assertEqual(
            Delivery.objects.filter(
                shop=self.business,
                external_order_id='woo-4242',
            ).count(),
            1
        )
        self.assertEqual(
            User.objects.filter(phone_number='+237699999994').count(),
            1
        )
        self.business.refresh_from_db()
        self.assertEqual(
            self.business.wallet_balance,
            initial_balance - Decimal('1500.00')
        )
        self.assertEqual(fake_pricing_engine.estimate_from_neighborhood.call_count, 1)

    def test_mobile_location_updates_user_location_fields(self):
        """The mobile HTTP fallback should update the courier GPS fields."""
        self.assertIsNone(self.courier.last_location)
        self.assertIsNone(self.courier.last_location_updated)

        with patch('logistics.services.traffic_service.TrafficService.ingest_location') as mock_ingest:
            mock_ingest.return_value = None
            self.api_client.force_authenticate(user=self.courier)
            response = self.api_client.post(
                '/api/mobile/location/',
                {
                    'latitude': 4.0511,
                    'longitude': 9.7679,
                },
                format='json'
            )

        self.assertEqual(response.status_code, 200)
        self.courier.refresh_from_db()
        self.assertIsNotNone(self.courier.last_location)
        self.assertEqual(self.courier.last_location.y, 4.0511)
        self.assertEqual(self.courier.last_location.x, 9.7679)
        self.assertIsNotNone(self.courier.last_location_updated)
        mock_ingest.assert_called_once_with(
            courier_id=str(self.courier.id),
            latitude=4.0511,
            longitude=9.7679
        )

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
