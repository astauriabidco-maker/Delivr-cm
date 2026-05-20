from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User, UserRole
from logistics.consumers import CourierConsumer


class CourierWebSocketAuthTest(TestCase):
    def setUp(self):
        self.courier = User.objects.create_user(
            phone_number='+237690510001',
            password='1234',
            role=UserRole.COURIER,
            full_name='Socket Courier',
            is_verified=True,
        )
        self.business = User.objects.create_user(
            phone_number='+237690510002',
            password='1234',
            role=UserRole.BUSINESS,
            full_name='Socket Business',
        )

    def test_courier_token_authenticates_socket(self):
        token = str(RefreshToken.for_user(self.courier).access_token)

        courier = CourierConsumer.authenticate_courier_token_sync(token)

        self.assertIsNotNone(courier)
        self.assertEqual(courier['id'], self.courier.id)

    def test_invalid_token_rejects_socket_auth(self):
        courier = CourierConsumer.authenticate_courier_token_sync('not-a-jwt')

        self.assertIsNone(courier)

    def test_non_courier_token_rejects_socket_auth(self):
        token = str(RefreshToken.for_user(self.business).access_token)

        courier = CourierConsumer.authenticate_courier_token_sync(token)

        self.assertIsNone(courier)
