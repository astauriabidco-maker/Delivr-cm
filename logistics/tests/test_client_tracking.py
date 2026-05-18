from decimal import Decimal

from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from core.models import User, UserRole
from logistics.models import Delivery, DeliveryStatus, PaymentMethod


class ClientTrackingJourneyTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.sender = User.objects.create_user(
            phone_number='+237690600001',
            role=UserRole.BUSINESS,
            full_name='Tracking Shop',
        )
        self.courier = User.objects.create_user(
            phone_number='+237690600002',
            role=UserRole.COURIER,
            full_name='Tracking Courier',
            is_verified=True,
        )
        self.delivery = Delivery.objects.create(
            sender=self.sender,
            courier=self.courier,
            recipient_phone='+237690600003',
            recipient_name='Tracking Recipient',
            pickup_geo=Point(9.7042, 4.0502, srid=4326),
            dropoff_geo=Point(9.6877, 4.0205, srid=4326),
            pickup_address='Akwa',
            dropoff_address='Bonapriso',
            payment_method=PaymentMethod.CASH_P2P,
            status=DeliveryStatus.IN_TRANSIT,
            total_price=Decimal('1500.00'),
            platform_fee=Decimal('300.00'),
            courier_earning=Decimal('1200.00'),
        )

    def test_public_tracking_url_renders_customer_page(self):
        response = self.client.get(f'/track/{self.delivery.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.delivery.id)[:8])
        self.assertContains(response, 'const API_BASE = `/api/track/${DELIVERY_ID}`;')

    def test_share_link_opens_tracking_page(self):
        response = self.client.post(f'/api/track/{self.delivery.id}/share/')

        self.assertEqual(response.status_code, 200)
        share_url = response.json()['share_url']
        self.assertIn('/track/s/', share_url)
        path = '/' + share_url.split('/', 3)[3]

        shared_response = self.client.get(path)

        self.assertRedirects(
            shared_response,
            reverse('public-delivery-tracking', args=[self.delivery.id]),
            fetch_redirect_response=False,
        )

    def test_history_api_does_not_expose_otp_or_phone(self):
        response = self.client.get(f'/api/track/{self.delivery.id}/history/')

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertNotIn(self.delivery.otp_code, body)
        self.assertNotIn(self.delivery.pickup_otp, body)
        self.assertNotIn(self.delivery.recipient_phone, body)
        self.assertEqual(response.json()['recipient_name'], self.delivery.recipient_name)

    def test_eta_returns_clean_unavailable_response_without_courier_position(self):
        response = self.client.get(f'/api/track/{self.delivery.id}/eta/')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['success'])

    def test_public_proof_upload_is_forbidden(self):
        photo = SimpleUploadedFile('proof.jpg', b'fake-image', content_type='image/jpeg')

        response = self.client.post(
            f'/api/track/{self.delivery.id}/proof/',
            {'photo': photo},
        )

        self.assertEqual(response.status_code, 403)

    def test_assigned_courier_can_upload_tracking_proof(self):
        self.client.force_login(self.courier)
        photo = SimpleUploadedFile('proof.jpg', b'fake-image', content_type='image/jpeg')

        response = self.client.post(
            f'/api/track/{self.delivery.id}/proof/',
            {'photo': photo},
        )

        self.assertEqual(response.status_code, 200)
        self.delivery.refresh_from_db()
        self.assertTrue(self.delivery.proof_photo)

    def test_public_dispute_with_share_token_redirects_to_public_tracking(self):
        share_token = 'client-share-token'
        cache.set(f'share_link_{share_token}', str(self.delivery.id), timeout=86400)

        response = self.client.post(
            f'/backoffice/support/report/{self.delivery.id}/',
            {
                'share_token': share_token,
                'reason': 'ITEM_DAMAGED',
                'description': 'Colis abime.',
            },
        )

        self.assertRedirects(
            response,
            reverse('public-delivery-tracking', args=[self.delivery.id]),
            fetch_redirect_response=False,
        )
