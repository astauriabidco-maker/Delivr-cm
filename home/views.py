"""
Home App Views - Landing Page
"""

from django.views.generic import TemplateView
from logistics.models import Delivery


class HomeView(TemplateView):
    """
    Public landing page for DELIVR-CM.
    
    Displays:
    - Hero section with value proposition
    - Pain points section
    - Solution for Instagram and WooCommerce sellers
    - Developer API section
    - Pricing information
    - Social proof statistics with dynamic delivery count
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
        
        # Additional stats
        context['stats'] = {
            'success_rate': 98,
            'cities': 2,
            'avg_time': 30,
        }
        
        return context
