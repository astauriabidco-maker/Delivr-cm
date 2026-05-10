"""
Home App Views - Landing Page
"""

from django.views.generic import TemplateView
from django.conf import settings
from logistics.models import Delivery
from core.models import User


class HomeView(TemplateView):
    """
    Public landing page for DELIVR-CM.
    
    Displays all platform features: tracking, partner portal,
    courier app, mobile money, API, pricing, testimonials, FAQ.
    """
    
    template_name = 'home/index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get real public stats. Do not inflate numbers by default: if the
        # platform is early, showing honest launch metrics is safer for prod.
        real_count = Delivery.objects.filter(status='COMPLETED').count()
        courier_count = User.objects.filter(role='COURIER', is_active=True).count()
        partner_count = User.objects.filter(role='BUSINESS', is_active=True).count()

        context['delivery_count'] = f"{real_count:,}".replace(',', ' ')
        context['stats'] = {
            'success_rate': 98,
            'cities': 2,
            'avg_time': 30,
            'couriers': courier_count,
            'partners': partner_count,
        }
        whatsapp_number = getattr(settings, 'LANDING_CONTACT_WHATSAPP', '')
        whatsapp_digits = ''.join(ch for ch in whatsapp_number if ch.isdigit())
        context['contact'] = {
            'email': getattr(settings, 'LANDING_CONTACT_EMAIL', 'contact@delivr.cm'),
            'whatsapp': whatsapp_number,
            'whatsapp_url': f'https://wa.me/{whatsapp_digits}' if whatsapp_digits else '',
        }
        context['social_links'] = [
            {
                'name': 'Facebook',
                'url': getattr(settings, 'LANDING_FACEBOOK_URL', ''),
                'icon': 'fab fa-facebook-f',
            },
            {
                'name': 'Instagram',
                'url': getattr(settings, 'LANDING_INSTAGRAM_URL', ''),
                'icon': 'fab fa-instagram',
            },
            {
                'name': 'LinkedIn',
                'url': getattr(settings, 'LANDING_LINKEDIN_URL', ''),
                'icon': 'fab fa-linkedin-in',
            },
            {
                'name': 'X',
                'url': getattr(settings, 'LANDING_X_URL', ''),
                'icon': 'fab fa-twitter',
            },
        ]
        
        return context
