from decimal import Decimal
from unittest.mock import patch

from django.contrib.gis.geos import Point
from django.test import Client, TestCase
from django.utils import timezone

from core.models import User, UserRole
from logistics.models import Delivery, PaymentMethod
from support.models import Dispute


class ClientDisputeCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.sender = User.objects.create_user(
            phone_number='+237690300001',
            role=UserRole.BUSINESS,
            full_name='Sender Shop',
        )
        self.delivery = Delivery.objects.create(
            sender=self.sender,
            recipient_phone='+237690300002',
            recipient_name='Recipient Client',
            pickup_geo=Point(9.7042, 4.0502),
            payment_method=PaymentMethod.CASH_P2P,
            total_price=Decimal('1500.00'),
        )

    @patch('bot.whatsapp_service.send_dispute_notification')
    def test_anonymous_report_is_created_for_recipient_not_sender(self, mock_notification):
        response = self.client.post(
            f'/backoffice/support/report/{self.delivery.id}/',
            {
                'reason': 'ITEM_DAMAGED',
                'description': 'Le colis est endommage.',
            },
        )

        self.assertEqual(response.status_code, 302)
        dispute = Dispute.objects.get(delivery=self.delivery)
        self.assertNotEqual(dispute.creator, self.sender)
        self.assertEqual(dispute.creator.phone_number, self.delivery.recipient_phone)
        self.assertEqual(dispute.creator.role, UserRole.CLIENT)
        mock_notification.assert_called_once()

    def test_old_delivery_public_report_is_rejected(self):
        Delivery.objects.filter(pk=self.delivery.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=31)
        )

        response = self.client.post(
            f'/backoffice/support/report/{self.delivery.id}/',
            {
                'reason': 'ITEM_DAMAGED',
                'description': 'Trop ancien.',
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Dispute.objects.filter(delivery=self.delivery).exists())
