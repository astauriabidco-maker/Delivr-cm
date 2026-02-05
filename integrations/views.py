"""
Integrations App - Backoffice Views

Modern dashboard for managing integrations, accessible at /backoffice/integrations/.
"""

import json
from django.views.generic import TemplateView, View
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages

from .models import IntegrationConfig
from .services import ConfigService, ConnectionTester


@method_decorator(staff_member_required, name='dispatch')
class IntegrationsDashboardView(TemplateView):
    """
    Main dashboard view for integrations management.
    """
    
    template_name = 'integrations/backoffice_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        config = IntegrationConfig.get_solo()
        secrets = ConfigService.get_env_secrets_display()
        
        context['config'] = config
        context['secrets'] = secrets
        context['pricing_sim'] = config.calculate_sample_price(5.0)
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle form submission."""
        config = IntegrationConfig.get_solo()
        
        # Update WhatsApp settings
        if 'active_whatsapp_provider' in request.POST:
            config.active_whatsapp_provider = request.POST.get('active_whatsapp_provider', 'twilio')
            config.twilio_whatsapp_number = request.POST.get('twilio_whatsapp_number', '')
            config.meta_phone_number_id = request.POST.get('meta_phone_number_id', '')
            config.meta_verify_token = request.POST.get('meta_verify_token', '')
        
        # Update Pricing settings
        if 'pricing_base_fare' in request.POST:
            config.pricing_base_fare = int(request.POST.get('pricing_base_fare', 500))
            config.pricing_cost_per_km = int(request.POST.get('pricing_cost_per_km', 150))
            config.pricing_minimum_fare = int(request.POST.get('pricing_minimum_fare', 1000))
            config.platform_fee_percent = int(request.POST.get('platform_fee_percent', 20))
            config.courier_debt_ceiling = int(request.POST.get('courier_debt_ceiling', 2500))
        
        # Update Services settings
        if 'osrm_base_url' in request.POST:
            config.osrm_base_url = request.POST.get('osrm_base_url', '')
            config.nominatim_base_url = request.POST.get('nominatim_base_url', '')
        
        config.updated_by = request.user
        config.save()
        
        # Invalidate cache
        ConfigService.invalidate_cache()
        
        messages.success(request, 'Configuration mise à jour avec succès.')
        return redirect('integrations:dashboard')


@method_decorator(staff_member_required, name='dispatch')
class TestConnectionView(View):
    """AJAX endpoint for testing individual connections."""
    
    def get(self, request, service=None):
        if service == 'all':
            results = ConnectionTester.test_all()
        elif service == 'osrm':
            results = {'osrm': ConnectionTester.test_osrm()}
        elif service == 'nominatim':
            results = {'nominatim': ConnectionTester.test_nominatim()}
        elif service == 'redis':
            results = {'redis': ConnectionTester.test_redis()}
        elif service == 'twilio':
            results = {'twilio': ConnectionTester.test_twilio()}
        elif service == 'meta':
            results = {'meta': ConnectionTester.test_meta()}
        else:
            results = ConnectionTester.test_all()
        
        return JsonResponse(results)


@method_decorator(staff_member_required, name='dispatch')
class PricingSimulatorView(View):
    """AJAX endpoint for price simulation."""
    
    def get(self, request):
        try:
            distance = float(request.GET.get('distance', 5))
        except ValueError:
            distance = 5.0
        
        config = IntegrationConfig.get_solo()
        result = config.calculate_sample_price(distance)
        
        return JsonResponse(result)
