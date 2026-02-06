"""
DELIVR-CM Main URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.decorators import api_view
from rest_framework.response import Response


# ===========================================
# ADMIN SITE CUSTOMIZATION
# ===========================================
admin.site.site_header = "🚀 DELIVR-CM Control Tower"
admin.site.site_title = "DELIVR-CM Admin"
admin.site.index_title = "Supervision des Opérations"


@api_view(['GET'])
def api_root(request):
    """API Root endpoint with available routes."""
    return Response({
        'name': 'DELIVR-CM API',
        'version': '1.0.0',
        'endpoints': {
            'auth': {
                'token': '/api/auth/token/',
                'refresh': '/api/auth/token/refresh/',
            },
            'users': '/api/users/',
            'courier': {
                'profile': '/api/courier/profile/',
                'location': '/api/courier/location/',
                'wallet': '/api/courier/wallet/',
            },
            'deliveries': '/api/deliveries/',
            'neighborhoods': '/api/neighborhoods/',
            'quote': '/api/quote/',
            'orders': '/api/orders/',
            'wallet': {
                'balance': '/api/wallet/balance/',
                'deposit': '/api/wallet/deposit/',
                'withdraw': '/api/wallet/withdraw/',
                'history': '/api/wallet/history/',
            },
            'transactions': '/api/transactions/',
        }
    })


urlpatterns = [
    # Landing Page (Home)
    path('', include('home.urls')),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # API Root
    path('api/', api_root, name='api-root'),
    
    # App URLs
    path('api/', include('core.urls')),
    path('api/', include('logistics.urls')),
    path('api/', include('finance.urls')),
    
    # Partner Portal (Developer Dashboard)
    path('partners/', include('partners.urls')),
    
    # Backoffice (Admin Dashboard)
    path('backoffice/integrations/', include('integrations.urls')),
    
    # Public Checkout (Magic Link - No login required)
    path('book/<slug:shop_slug>/', 
         # Import here to avoid circular imports
         __import__('partners.views', fromlist=['PublicShopView']).PublicShopView.as_view(), 
         name='public_shop'),
    
    # Courier Dashboard (Mobile-first for couriers)
    path('courier/', include('courier.urls')),
    
    # Mobile API (Flutter App)
    path('api/mobile/', include('courier.urls_mobile')),
    
    # Fleet Management Admin Dashboard
    path('fleet/', include('fleet.urls')),
    
    # PDF Reports
    path('reports/', include('reports.urls')),
    
    # Webhooks (WhatsApp Bot)
    path('webhooks/', include('bot.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
