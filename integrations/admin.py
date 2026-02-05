"""
Integrations App - Django Admin Configuration

Custom admin interface for managing integration configurations.
Features:
- Fieldsets grouped by category
- Read-only display of .env secrets
- Connection test buttons
- Price simulation
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.http import JsonResponse
from django.template.response import TemplateResponse

from .models import IntegrationConfig
from .services import ConfigService, ConnectionTester, mask_secret


@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    """
    Custom admin for IntegrationConfig singleton.
    """
    
    list_display = ['__str__', 'active_whatsapp_provider', 'updated_at', 'updated_by']
    
    fieldsets = (
        ('📱 Configuration WhatsApp', {
            'fields': (
                'active_whatsapp_provider',
                'env_twilio_secrets',
                'twilio_whatsapp_number',
                'env_meta_secrets',
                'meta_phone_number_id',
                'meta_verify_token',
            ),
            'description': 'Configuration des providers WhatsApp (Twilio et Meta)'
        }),
        ('💰 Moteur de Tarification', {
            'fields': (
                'pricing_base_fare',
                'pricing_cost_per_km',
                'pricing_minimum_fare',
                'platform_fee_percent',
                'courier_debt_ceiling',
                'pricing_simulation',
            ),
            'description': 'Configuration du calcul des prix de livraison'
        }),
        ('🗺️ Services Externes', {
            'fields': (
                'osrm_base_url',
                'nominatim_base_url',
                'env_redis_secret',
                'connection_status',
            ),
            'description': 'URLs des services de routing et géocodage'
        }),
        ('📋 Métadonnées', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = [
        'env_twilio_secrets',
        'env_meta_secrets', 
        'env_redis_secret',
        'pricing_simulation',
        'connection_status',
        'updated_at',
        'updated_by',
    ]
    
    def has_add_permission(self, request):
        """Prevent adding new instances (singleton)."""
        return not IntegrationConfig.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deleting the singleton."""
        return False
    
    def save_model(self, request, obj, form, change):
        """Save with user tracking and cache invalidation."""
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        ConfigService.invalidate_cache()
    
    def env_twilio_secrets(self, obj):
        """Display masked Twilio secrets from .env."""
        secrets = ConfigService.get_env_secrets_display()
        return format_html(
            '''
            <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace;">
                <div><strong>Account SID:</strong> <code>{}</code> 🔒</div>
                <div><strong>Auth Token:</strong> <code>{}</code> 🔒</div>
                <small style="color: #666;">Ces valeurs proviennent du fichier .env (lecture seule)</small>
            </div>
            ''',
            secrets['twilio_account_sid'],
            secrets['twilio_auth_token']
        )
    env_twilio_secrets.short_description = 'Secrets Twilio (.env)'
    
    def env_meta_secrets(self, obj):
        """Display masked Meta secrets from .env."""
        secrets = ConfigService.get_env_secrets_display()
        return format_html(
            '''
            <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace;">
                <div><strong>API Token:</strong> <code>{}</code> 🔒</div>
                <small style="color: #666;">Cette valeur provient du fichier .env (lecture seule)</small>
            </div>
            ''',
            secrets['meta_api_token']
        )
    env_meta_secrets.short_description = 'Secrets Meta (.env)'
    
    def env_redis_secret(self, obj):
        """Display masked Redis URL from .env."""
        secrets = ConfigService.get_env_secrets_display()
        return format_html(
            '''
            <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace;">
                <div><strong>Redis URL:</strong> <code>{}</code> 🔒</div>
                <small style="color: #666;">Cette valeur provient du fichier .env (lecture seule)</small>
            </div>
            ''',
            secrets['redis_url']
        )
    env_redis_secret.short_description = 'Redis (.env)'
    
    def pricing_simulation(self, obj):
        """Display price simulation."""
        sim = obj.calculate_sample_price(5.0)
        return format_html(
            '''
            <div style="background: #e8f5e9; padding: 15px; border-radius: 5px; border-left: 4px solid #4caf50;">
                <h4 style="margin: 0 0 10px 0;">📊 Simulation pour 5 km</h4>
                <div>Formule: {} + (5 × {}) = <strong>{} FCFA</strong></div>
                <div style="margin-top: 8px;">
                    <span style="background: #2196f3; color: white; padding: 2px 8px; border-radius: 3px;">
                        Commission: {} FCFA ({}%)
                    </span>
                    <span style="background: #ff9800; color: white; padding: 2px 8px; border-radius: 3px; margin-left: 5px;">
                        Coursier: {} FCFA
                    </span>
                </div>
            </div>
            ''',
            obj.pricing_base_fare,
            obj.pricing_cost_per_km,
            sim['total_price'],
            sim['platform_fee'],
            obj.platform_fee_percent,
            sim['courier_earning']
        )
    pricing_simulation.short_description = 'Simulation de prix'
    
    def connection_status(self, obj):
        """Display connection status for all services."""
        return format_html(
            '''
            <div style="background: #fff3e0; padding: 15px; border-radius: 5px;">
                <p><strong>Cliquez sur "Enregistrer" puis actualisez pour voir les statuts.</strong></p>
                <div id="connection-tests">
                    <button type="button" onclick="testConnections()" 
                            style="background: #1976d2; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer;">
                        🧪 Tester toutes les connexions
                    </button>
                    <div id="test-results" style="margin-top: 10px;"></div>
                </div>
            </div>
            <script>
            function testConnections() {{
                document.getElementById('test-results').innerHTML = 'Test en cours...';
                fetch('/admin/integrations/test-connections/')
                    .then(r => r.json())
                    .then(data => {{
                        let html = '<ul style="list-style: none; padding: 0;">';
                        for (const [service, result] of Object.entries(data)) {{
                            const icon = result.status === 'ok' ? '✅' : 
                                        result.status === 'warning' ? '⚠️' : '❌';
                            html += `<li style="padding: 5px 0;">${{icon}} <strong>${{service}}</strong>: ${{result.message}}</li>`;
                        }}
                        html += '</ul>';
                        document.getElementById('test-results').innerHTML = html;
                    }})
                    .catch(e => {{
                        document.getElementById('test-results').innerHTML = 'Erreur: ' + e;
                    }});
            }}
            </script>
            '''
        )
    connection_status.short_description = 'État des connexions'
    
    def get_urls(self):
        """Add custom URL for connection testing."""
        urls = super().get_urls()
        custom_urls = [
            path('test-connections/',
                 self.admin_site.admin_view(self.test_connections_view),
                 name='integrations_test_connections'),
        ]
        return custom_urls + urls
    
    def test_connections_view(self, request):
        """AJAX endpoint for testing connections."""
        results = ConnectionTester.test_all()
        return JsonResponse(results)
    
    def changelist_view(self, request, extra_context=None):
        """Redirect to the singleton change view."""
        obj = IntegrationConfig.get_solo()
        from django.shortcuts import redirect
        return redirect(f'/admin/integrations/integrationconfig/{obj.pk}/change/')
