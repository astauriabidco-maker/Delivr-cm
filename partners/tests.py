from decimal import Decimal

from django.contrib.gis.geos import Point
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import User, UserRole
from finance.models import Invoice, InvoiceType
from logistics.models import City, Delivery, Neighborhood, PaymentMethod
from partners.models import PartnerAPIKey


class PartnerApprovalAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.partner = User.objects.create_user(
            phone_number='+237690400001',
            role=UserRole.BUSINESS,
            full_name='Pending Shop',
            is_business_approved=False,
        )
        self.client.force_login(self.partner)

    def test_pending_partner_can_view_dashboard(self):
        response = self.client.get(reverse('partners:dashboard'))

        self.assertEqual(response.status_code, 200)

    def test_pending_partner_is_blocked_from_operational_pages(self):
        protected_urls = [
            reverse('partners:profile'),
            reverse('partners:wallet'),
            reverse('partners:webhooks'),
            reverse('partners:orders'),
        ]

        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, reverse('partners:pending'))


class SellerFunctionalJourneyTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.api_client = APIClient()
        self.partner = User.objects.create_user(
            phone_number='+237690400010',
            role=UserRole.BUSINESS,
            full_name='Functional Shop',
            is_business_approved=True,
            wallet_balance=Decimal('10000.00'),
        )
        self.partner.set_password('strongpass123')
        self.partner.last_location = Point(9.7042, 4.0502, srid=4326)
        self.partner.save()
        self.neighborhood = Neighborhood.objects.create(
            city=City.DOUALA,
            name='Bonapriso Functional',
            center_geo=Point(9.6877, 4.0205, srid=4326),
        )

    def test_signup_creates_pending_business_account(self):
        response = self.client.post(
            reverse('partners:signup'),
            {
                'phone_number': '+237690400011',
                'full_name': 'New Seller',
                'business_type': 'SOCIAL',
                'company_name': 'New Shop',
                'password': 'strongpass123',
                'password_confirm': 'strongpass123',
            },
        )

        self.assertRedirects(response, reverse('partners:pending'))
        seller = User.objects.get(phone_number='+237690400011')
        self.assertEqual(seller.role, UserRole.BUSINESS)
        self.assertFalse(seller.is_business_approved)
        self.assertTrue(seller.check_password('strongpass123'))

    def test_unapproved_business_cannot_use_b2b_quote_or_order_api(self):
        pending = User.objects.create_user(
            phone_number='+237690400012',
            role=UserRole.BUSINESS,
            full_name='Pending API Shop',
            is_business_approved=False,
            wallet_balance=Decimal('10000.00'),
        )
        pending.last_location = Point(9.7042, 4.0502, srid=4326)
        pending.save(update_fields=['last_location'])
        self.api_client.force_authenticate(user=pending)

        quote_response = self.api_client.post(
            '/api/quote/',
            {
                'shop_id': str(pending.id),
                'neighborhood_id': str(self.neighborhood.id),
            },
            format='json',
        )
        order_response = self.api_client.post(
            '/api/orders/',
            {
                'shop_id': str(pending.id),
                'customer_phone': '+237690400013',
                'customer_name': 'Blocked Customer',
                'neighborhood_id': str(self.neighborhood.id),
                'items_description': 'Blocked package',
                'external_order_id': 'pending-api-order',
            },
            format='json',
        )

        self.assertEqual(quote_response.status_code, 403)
        self.assertEqual(order_response.status_code, 403)
        self.assertFalse(Delivery.objects.filter(external_order_id='pending-api-order').exists())

    def test_unapproved_business_api_key_cannot_create_order(self):
        pending = User.objects.create_user(
            phone_number='+237690400014',
            role=UserRole.BUSINESS,
            full_name='Pending Key Shop',
            is_business_approved=False,
            wallet_balance=Decimal('10000.00'),
        )
        pending.last_location = Point(9.7042, 4.0502, srid=4326)
        pending.save(update_fields=['last_location'])
        api_key, _ = PartnerAPIKey.objects.create_key(name='pending-key', partner=pending)

        response = self.api_client.post(
            '/api/orders/',
            {
                'shop_id': str(pending.id),
                'customer_phone': '+237690400015',
                'customer_name': 'Blocked Customer',
                'neighborhood_id': str(self.neighborhood.id),
                'items_description': 'Blocked package',
                'external_order_id': 'pending-key-order',
            },
            format='json',
            HTTP_AUTHORIZATION=f'Api-Key {api_key}',
        )

        self.assertIn(response.status_code, [401, 403])
        self.assertFalse(Delivery.objects.filter(external_order_id='pending-key-order').exists())

    def test_approved_partner_can_create_prepaid_order_and_see_it(self):
        self.api_client.force_authenticate(user=self.partner)
        response = self.api_client.post(
            '/api/orders/',
            {
                'shop_id': str(self.partner.id),
                'customer_phone': '+237690400016',
                'customer_name': 'Approved Customer',
                'neighborhood_id': str(self.neighborhood.id),
                'items_description': 'Approved package',
                'external_order_id': 'approved-order',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        delivery = Delivery.objects.get(external_order_id='approved-order')
        self.assertEqual(delivery.shop, self.partner)
        self.assertEqual(delivery.payment_method, PaymentMethod.PREPAID_WALLET)

        self.client.force_login(self.partner)
        orders_response = self.client.get(reverse('partners:orders'))
        detail_response = self.client.get(reverse('partners:order_detail', args=[delivery.id]))

        self.assertEqual(orders_response.status_code, 200)
        self.assertContains(orders_response, 'Approved Customer')
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'Approved package')

    def test_invoice_year_filter_invalid_value_does_not_500(self):
        Invoice.objects.create(
            invoice_number='DLV-2026-000001',
            invoice_type=InvoiceType.B2B_INVOICE,
            user=self.partner,
            amount=Decimal('1500.00'),
        )
        self.client.force_login(self.partner)

        response = self.client.get(reverse('partners:invoices'), {'year': 'bad-year'})

        self.assertEqual(response.status_code, 200)

    def test_profile_rejects_out_of_range_gps_coordinates(self):
        self.client.force_login(self.partner)

        response = self.client.post(
            reverse('partners:profile'),
            {
                'action': 'update_profile',
                'full_name': 'Functional Shop',
                'latitude': '999',
                'longitude': '9.7042',
            },
        )

        self.assertRedirects(response, reverse('partners:profile'))
        self.partner.refresh_from_db()
        self.assertAlmostEqual(self.partner.last_location.y, 4.0502)
