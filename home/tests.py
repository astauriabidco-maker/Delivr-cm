from django.test import TestCase, override_settings
from django.urls import reverse


class HomeLandingPageTest(TestCase):
    """Tests for production-facing landing page content."""

    @override_settings(
        LANDING_CONTACT_EMAIL='hello@delivr.cm',
        LANDING_CONTACT_WHATSAPP='+237699111222',
        LANDING_FACEBOOK_URL='',
        LANDING_INSTAGRAM_URL='',
        LANDING_LINKEDIN_URL='',
        LANDING_X_URL='',
    )
    def test_landing_uses_configured_contact_and_no_placeholder_links(self):
        response = self.client.get(reverse('home:home'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('https://wa.me/237699111222', content)
        self.assertIn('mailto:hello@delivr.cm', content)
        self.assertNotIn('https://wa.me/237690000000', content)
        self.assertNotIn('href="#"', content)

    def test_landing_stats_are_not_artificially_inflated(self):
        response = self.client.get(reverse('home:home'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['delivery_count'], '0')
        self.assertEqual(response.context['stats']['couriers'], 0)
        self.assertEqual(response.context['stats']['partners'], 0)
