from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.gis.geos import Point
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User, UserRole
from finance.models import Transaction, TransactionType
from logistics.models import Delivery, DeliveryStatus, PaymentMethod


class CourierFunctionalJourneyTest(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.courier = User.objects.create_user(
            phone_number='+237690500001',
            password='1234',
            role=UserRole.COURIER,
            full_name='Functional Courier',
            is_verified=True,
            is_online=True,
            wallet_balance=Decimal('5000.00'),
        )
        self.courier.last_location = Point(9.7042, 4.0502, srid=4326)
        self.courier.save(update_fields=['last_location'])
        self.sender = User.objects.create_user(
            phone_number='+237690500002',
            role=UserRole.BUSINESS,
            full_name='Sender Shop',
        )

    def _delivery(self, **overrides):
        defaults = {
            'sender': self.sender,
            'recipient_phone': '+237690500003',
            'recipient_name': 'Recipient',
            'pickup_geo': Point(9.7042, 4.0502, srid=4326),
            'dropoff_geo': Point(9.6877, 4.0205, srid=4326),
            'pickup_address': 'Akwa',
            'dropoff_address': 'Bonapriso',
            'payment_method': PaymentMethod.CASH_P2P,
            'status': DeliveryStatus.PENDING,
            'distance_km': 3.5,
            'total_price': Decimal('1500.00'),
            'platform_fee': Decimal('300.00'),
            'courier_earning': Decimal('1200.00'),
        }
        defaults.update(overrides)
        return Delivery.objects.create(**defaults)

    def test_mobile_login_requires_verified_courier(self):
        unverified = User.objects.create_user(
            phone_number='+237690500004',
            password='1234',
            role=UserRole.COURIER,
            is_verified=False,
        )

        response = self.client.post(
            '/api/mobile/auth/login/',
            {'phone_number': unverified.phone_number, 'pin': '1234'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_blocked_courier_cannot_go_online_or_see_available_jobs(self):
        self.courier.is_online = False
        self.courier.wallet_balance = Decimal('-3000.00')
        self.courier.debt_ceiling = Decimal('2500.00')
        self.courier.save(update_fields=['is_online', 'wallet_balance', 'debt_ceiling'])
        self.client.force_authenticate(user=self.courier)
        self._delivery()

        toggle_response = self.client.post('/api/mobile/toggle-online/', {}, format='json')
        available_response = self.client.get('/api/mobile/deliveries/?status=available')

        self.assertEqual(toggle_response.status_code, 403)
        self.assertEqual(available_response.status_code, 403)
        self.courier.refresh_from_db()
        self.assertFalse(self.courier.is_online)

    def test_available_jobs_require_online_location_and_return_pending_orders(self):
        delivery = self._delivery()
        self.client.force_authenticate(user=self.courier)

        response = self.client.get('/api/mobile/deliveries/?status=available')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['deliveries']), 1)
        self.assertEqual(response.json()['deliveries'][0]['id'], str(delivery.id))

    def test_invalid_mobile_location_is_rejected_without_500(self):
        self.client.force_authenticate(user=self.courier)

        response = self.client.post(
            '/api/mobile/location/',
            {'latitude': 'not-a-number', 'longitude': '9.7'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)

    def test_accept_order_requires_online_verified_courier_and_is_exclusive(self):
        delivery = self._delivery()
        other = User.objects.create_user(
            phone_number='+237690500005',
            role=UserRole.COURIER,
            is_verified=True,
            is_online=True,
        )
        self.client.force_authenticate(user=self.courier)

        first_response = self.client.post(f'/api/orders/{delivery.id}/accept/', {}, format='json')
        self.client.force_authenticate(user=other)
        second_response = self.client.post(f'/api/orders/{delivery.id}/accept/', {}, format='json')

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 409)
        delivery.refresh_from_db()
        self.assertEqual(delivery.courier, self.courier)
        self.assertEqual(delivery.status, DeliveryStatus.ASSIGNED)

    def test_offline_courier_cannot_accept_order(self):
        delivery = self._delivery()
        self.courier.is_online = False
        self.courier.save(update_fields=['is_online'])
        self.client.force_authenticate(user=self.courier)

        response = self.client.post(f'/api/orders/{delivery.id}/accept/', {}, format='json')

        self.assertEqual(response.status_code, 409)
        delivery.refresh_from_db()
        self.assertIsNone(delivery.courier)

    @patch('bot.whatsapp_service.send_delivery_completed_notification')
    @patch('bot.whatsapp_service.send_pickup_confirmed_notification')
    @patch('logistics.events.broadcast_delivery_update')
    @patch('finance.invoice_service.InvoiceService.send_receipt_via_whatsapp')
    @patch('finance.invoice_service.InvoiceService.generate_delivery_receipt')
    @patch('logistics.rating_service.RatingService.send_rating_request_via_whatsapp')
    def test_cash_pickup_dropoff_flow_updates_wallet_once(
        self,
        mock_rating_request,
        mock_generate_receipt,
        mock_send_receipt,
        mock_broadcast,
        mock_pickup_notification,
        mock_completed_notification,
    ):
        mock_generate_receipt.return_value = MagicMock(invoice_number='DLV-TEST')
        delivery = self._delivery(
            courier=self.courier,
            status=DeliveryStatus.ARRIVED_PICKUP,
            assigned_at=timezone.now(),
        )
        initial_balance = self.courier.wallet_balance
        self.client.force_authenticate(user=self.courier)

        pickup_response = self.client.post(
            f'/api/mobile/deliveries/{delivery.id}/confirm-pickup/',
            {'otp': delivery.pickup_otp},
            format='json',
        )
        transit_response = self.client.patch(
            f'/api/mobile/deliveries/{delivery.id}/status/',
            {'status': DeliveryStatus.IN_TRANSIT},
            format='json',
        )
        dropoff_response = self.client.post(
            f'/api/mobile/deliveries/{delivery.id}/confirm-dropoff/',
            {'otp': delivery.otp_code},
            format='json',
        )

        self.assertEqual(pickup_response.status_code, 200)
        self.assertEqual(transit_response.status_code, 200)
        self.assertEqual(dropoff_response.status_code, 200)
        self.courier.refresh_from_db()
        self.assertEqual(self.courier.wallet_balance, initial_balance - delivery.platform_fee)
        self.assertEqual(
            Transaction.objects.filter(
                delivery=delivery,
                user=self.courier,
                transaction_type=TransactionType.COMMISSION,
            ).count(),
            1,
        )

    @patch('bot.whatsapp_service.send_delivery_completed_notification')
    @patch('logistics.events.broadcast_delivery_update')
    @patch('finance.invoice_service.InvoiceService.send_receipt_via_whatsapp')
    @patch('finance.invoice_service.InvoiceService.generate_delivery_receipt')
    @patch('logistics.rating_service.RatingService.send_rating_request_via_whatsapp')
    def test_prepaid_dropoff_credits_courier_once(
        self,
        mock_rating_request,
        mock_generate_receipt,
        mock_send_receipt,
        mock_broadcast,
        mock_completed_notification,
    ):
        mock_generate_receipt.return_value = MagicMock(invoice_number='DLV-TEST')
        delivery = self._delivery(
            courier=self.courier,
            status=DeliveryStatus.IN_TRANSIT,
            payment_method=PaymentMethod.PREPAID_WALLET,
        )
        initial_balance = self.courier.wallet_balance
        self.client.force_authenticate(user=self.courier)

        response = self.client.post(
            f'/api/mobile/deliveries/{delivery.id}/confirm-dropoff/',
            {'otp': delivery.otp_code},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.courier.refresh_from_db()
        self.assertEqual(self.courier.wallet_balance, initial_balance + delivery.courier_earning)
        self.assertEqual(
            Transaction.objects.filter(
                delivery=delivery,
                user=self.courier,
                transaction_type=TransactionType.DELIVERY_CREDIT,
            ).count(),
            1,
        )
