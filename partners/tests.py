from django.test import Client, TestCase
from django.urls import reverse

from core.models import User, UserRole


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
