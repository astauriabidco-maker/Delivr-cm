from decimal import Decimal

from django.contrib.gis.geos import Point
from django.test import Client, TestCase
from django.utils import timezone

from core.models import User, UserRole
from finance.models import MobileMoneyProvider, Transaction, TransactionType, WithdrawalRequest, WithdrawalStatus
from logistics.models import Delivery, DeliveryStatus, PaymentMethod


class FleetApiTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            phone_number='+237690200001',
            role=UserRole.ADMIN,
        )
        self.courier = User.objects.create_user(
            phone_number='+237690200002',
            role=UserRole.COURIER,
            full_name='Online Courier',
            is_verified=True,
            is_online=True,
        )
        self.courier.last_location = Point(9.7042, 4.0502)
        self.courier.last_location_updated = timezone.now()
        self.courier.save(update_fields=['last_location', 'last_location_updated'])
        self.sender = User.objects.create_user(
            phone_number='+237690200003',
            role=UserRole.CLIENT,
        )
        self.client.force_login(self.admin)

    def test_online_couriers_marks_active_delivery(self):
        Delivery.objects.create(
            sender=self.sender,
            recipient_phone='+237690200004',
            courier=self.courier,
            status=DeliveryStatus.IN_TRANSIT,
            pickup_geo=Point(9.7042, 4.0502),
            payment_method=PaymentMethod.CASH_P2P,
            total_price=Decimal('1500.00'),
        )

        response = self.client.get('/fleet/api/couriers/online/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['couriers']), 1)
        self.assertTrue(response.json()['couriers'][0]['in_delivery'])

    def test_live_map_api_returns_pending_delivery_markers(self):
        delivery = Delivery.objects.create(
            sender=self.sender,
            recipient_phone='+237690200005',
            status=DeliveryStatus.PENDING,
            pickup_geo=Point(9.7042, 4.0502),
            pickup_address='Akwa',
            payment_method=PaymentMethod.CASH_P2P,
            total_price=Decimal('1500.00'),
        )

        response = self.client.get('/fleet/api/courier-positions/')

        self.assertEqual(response.status_code, 200)
        deliveries = response.json()['deliveries']
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0]['id'], str(delivery.id))
        self.assertEqual(deliveries[0]['address'], 'Akwa')

    def test_live_map_template_draws_delivery_markers(self):
        response = self.client.get('/fleet/live-map/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'updateDeliveryMarkers(data.deliveries || [])')
        self.assertContains(response, 'createDeliveryMarker(delivery)')


class FleetBackofficeFunctionalTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            phone_number='+237690210001',
            role=UserRole.ADMIN,
            is_staff=True,
        )
        self.staff = User.objects.create_user(
            phone_number='+237690210002',
            role=UserRole.CLIENT,
            is_staff=True,
        )
        self.courier = User.objects.create_user(
            phone_number='+237690210003',
            role=UserRole.COURIER,
            full_name='Backoffice Courier',
            is_verified=True,
            wallet_balance=Decimal('10000.00'),
            debt_ceiling=Decimal('2500.00'),
        )

    def test_staff_user_can_access_fleet_backoffice(self):
        self.client.force_login(self.staff)

        response = self.client.get('/fleet/')

        self.assertEqual(response.status_code, 200)

    def test_non_admin_user_cannot_access_fleet_backoffice(self):
        user = User.objects.create_user(
            phone_number='+237690210004',
            role=UserRole.CLIENT,
        )
        self.client.force_login(user)

        response = self.client.get('/fleet/')

        self.assertEqual(response.status_code, 403)

    def test_complete_withdrawal_requires_transaction_id(self):
        withdrawal = WithdrawalRequest.objects.create(
            courier=self.courier,
            amount=Decimal('2000.00'),
            provider=MobileMoneyProvider.MTN_MOMO,
            phone_number=self.courier.phone_number,
            status=WithdrawalStatus.PROCESSING,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            f'/fleet/withdrawals/{withdrawal.id}/complete/',
            {'transaction_id': '   '},
        )

        self.assertEqual(response.status_code, 302)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, WithdrawalStatus.PROCESSING)
        self.assertEqual(withdrawal.external_transaction_id, '')

    def test_approve_withdrawal_debits_wallet_once_and_moves_processing(self):
        withdrawal = WithdrawalRequest.objects.create(
            courier=self.courier,
            amount=Decimal('2000.00'),
            provider=MobileMoneyProvider.MTN_MOMO,
            phone_number=self.courier.phone_number,
            status=WithdrawalStatus.PENDING,
        )
        self.client.force_login(self.admin)

        response = self.client.post(f'/fleet/withdrawals/{withdrawal.id}/approve/')

        self.assertEqual(response.status_code, 302)
        withdrawal.refresh_from_db()
        self.courier.refresh_from_db()
        self.assertEqual(withdrawal.status, WithdrawalStatus.PROCESSING)
        self.assertEqual(self.courier.wallet_balance, Decimal('8000.00'))
        self.assertEqual(
            Transaction.objects.filter(
                user=self.courier,
                transaction_type=TransactionType.WITHDRAWAL,
            ).count(),
            1,
        )

    def test_negative_debt_ceiling_is_rejected(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            f'/fleet/couriers/{self.courier.id}/adjust-debt/',
            {'debt_ceiling': '-1'},
        )

        self.assertEqual(response.status_code, 302)
        self.courier.refresh_from_db()
        self.assertEqual(self.courier.debt_ceiling, Decimal('2500.00'))
