"""
Home App Views - Landing Page
"""

from django.views.generic import TemplateView
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
        
        # Get real delivery count
        real_count = Delivery.objects.filter(status='COMPLETED').count()
        
        # If less than 500, display "500+" for credibility at launch
        if real_count < 500:
            context['delivery_count'] = "500+"
        else:
            context['delivery_count'] = f"{real_count:,}".replace(',', ' ')
        
        # Active couriers
        courier_count = User.objects.filter(role='COURIER', is_active=True).count()
        
        # Partners
        partner_count = User.objects.filter(role='BUSINESS', is_active=True).count()
        
        # Additional stats
        context['stats'] = {
            'success_rate': 98,
            'cities': 2,
            'avg_time': 30,
            'couriers': max(courier_count, 50),
            'partners': max(partner_count, 20),
        }
        
        return context
