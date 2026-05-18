from decimal import Decimal
from unittest.mock import patch

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone

from core.models import User, UserRole
from logistics.models import Delivery, DeliveryStatus, PaymentMethod
from logistics.signals import (
    DELIVERY_WEBHOOK_EVENTS,
    _handle_new_delivery,
    _handle_delivery_update,
    _send_partner_webhook,
)
from partners.models import WebhookConfig


class PartnerWebhookSignalTest(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            phone_number='+237699100001',
            full_name='Sender',
            role=UserRole.CLIENT,
        )
        self.shop = User.objects.create_user(
            phone_number='+237699100002',
            full_name='Partner Shop',
            role=UserRole.BUSINESS,
            is_business_approved=True,
        )
        self.courier = User.objects.create_user(
            phone_number='+237699100003',
            full_name='Courier',
            role=UserRole.COURIER,
        )
        WebhookConfig.objects.create(
            user=self.shop,
            url='https://example.test/webhooks',
            events=[
                'order.created',
                'order.assigned',
                'order.picked_up',
                'order.completed',
                'order.cancelled',
            ],
            is_active=True,
        )
        self.delivery = Delivery.objects.create(
            sender=self.sender,
            shop=self.shop,
            courier=self.courier,
            recipient_phone='+237699100004',
            recipient_name='Recipient',
            pickup_geo=Point(9.7042, 4.0502),
            dropoff_geo=Point(9.6877, 4.0205),
            pickup_address='Akwa',
            dropoff_address='Bonapriso',
            package_description='Books',
            payment_method=PaymentMethod.PREPAID_WALLET,
            distance_km=3.5,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00'),
            external_order_id='SHOP-42',
        )

    @patch('partners.services.WebhookService.send')
    def test_send_partner_webhook_uses_shop_config_and_stable_payload(self, mock_send):
        _send_partner_webhook(self.delivery, 'order.created')

        mock_send.assert_called_once()
        user, event_type, payload = mock_send.call_args.args
        order = payload['order']

        self.assertEqual(user, self.shop)
        self.assertEqual(event_type, 'order.created')
        self.assertEqual(order['id'], str(self.delivery.id))
        self.assertEqual(order['external_order_id'], 'SHOP-42')
        self.assertEqual(order['status'], DeliveryStatus.PENDING)
        self.assertEqual(order['recipient']['phone'], '+237699100004')
        self.assertEqual(order['pickup']['location']['latitude'], 4.0502)
        self.assertEqual(order['pickup']['location']['longitude'], 9.7042)
        self.assertEqual(order['pricing']['currency'], 'XAF')
        self.assertEqual(order['pricing']['total_price'], '1500.00')
        self.assertEqual(order['courier']['id'], str(self.courier.id))
        self.assertNotIn('otp_code', str(payload))
        self.assertNotIn('pickup_otp', str(payload))

    @patch('logistics.services.smart_dispatch.smart_dispatch_order')
    @patch('logistics.events.broadcast_new_delivery')
    @patch('bot.whatsapp_service.send_otp_to_recipient')
    @patch('bot.whatsapp_service.send_order_confirmation_to_sender')
    @patch('logistics.signals._send_partner_webhook')
    def test_new_pending_delivery_triggers_created_webhook(
        self,
        mock_webhook,
        mock_sender_notification,
        mock_recipient_notification,
        mock_broadcast,
        mock_dispatch,
    ):
        _handle_new_delivery(self.delivery)

        mock_webhook.assert_called_once_with(self.delivery, 'order.created')

    @patch('logistics.signals._handle_delivery_assigned')
    @patch('logistics.signals._handle_delivery_completed')
    @patch('bot.whatsapp_service.notify_delivery_status_change')
    @patch('logistics.events.broadcast_delivery_status')
    @patch('logistics.signals._send_partner_webhook')
    def test_main_status_changes_trigger_expected_webhook_events(
        self,
        mock_webhook,
        mock_broadcast,
        mock_whatsapp,
        mock_completed,
        mock_assigned,
    ):
        for status, event_type in DELIVERY_WEBHOOK_EVENTS.items():
            with self.subTest(status=status):
                mock_webhook.reset_mock()
                self.delivery.status = status
                if status == DeliveryStatus.ASSIGNED:
                    self.delivery.assigned_at = timezone.now()
                elif status == DeliveryStatus.PICKED_UP:
                    self.delivery.picked_up_at = timezone.now()
                elif status == DeliveryStatus.COMPLETED:
                    self.delivery.completed_at = timezone.now()

                _handle_delivery_update(self.delivery, DeliveryStatus.PENDING)

                mock_webhook.assert_called_once_with(self.delivery, event_type)
