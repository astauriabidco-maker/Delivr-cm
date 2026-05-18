from decimal import Decimal
from unittest.mock import patch

from django.contrib.gis.geos import Point
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import User, UserRole
from logistics.models import City, Neighborhood


class PublicCheckoutGpsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.shop = User.objects.create_user(
            phone_number='+237690100001',
            full_name='Shop No GPS',
            role=UserRole.BUSINESS,
            is_business_approved=True,
            wallet_balance=Decimal('10000.00'),
        )
        self.neighborhood = Neighborhood.objects.create(
            city=City.DOUALA,
            name='Bonapriso',
            center_geo=Point(9.6877, 4.0205),
        )

    def test_public_quote_rejects_shop_without_real_gps(self):
        response = self.client.post(
            '/api/public/quote/',
            {
                'shop_id': str(self.shop.id),
                'neighborhood_id': str(self.neighborhood.id),
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('position GPS', response.data['error'])

    @patch('logistics.views.pricing_engine')
    def test_public_order_rejects_shop_without_real_gps_before_pricing(self, mock_pricing_engine):
        response = self.client.post(
            '/api/public/orders/',
            {
                'shop_id': str(self.shop.id),
                'client_name': 'Client Test',
                'client_phone': '+237690100002',
                'neighborhood_id': str(self.neighborhood.id),
                'package_description': 'Colis test',
                'payment_method': 'CASH',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('position GPS', response.data['error'])
        mock_pricing_engine.assert_not_called()
