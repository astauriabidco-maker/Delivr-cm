from django.test import TestCase
from asgiref.sync import async_to_sync
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

    def test_courier_handles_dispatch_status_events(self):
        consumer = CourierConsumer()
        messages = []

        async def capture(message):
            messages.append(message)

        consumer.send_json = capture

        async_to_sync(consumer.delivery_status_change)({
            'delivery_id': 'delivery-123',
            'new_status': 'PICKED_UP',
        })

        self.assertEqual(messages, [{
            'type': 'delivery_update',
            'delivery_id': 'delivery-123',
            'new_status': 'PICKED_UP',
        }])
