from decimal import Decimal

from django.contrib.gis.geos import Point
from django.test import Client, TestCase
from django.utils import timezone

from core.models import User, UserRole
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
