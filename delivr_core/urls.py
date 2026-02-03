"""
DELIVR-CM Main URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.decorators import api_view
from rest_framework.response import Response


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
    # Admin
    path('admin/', admin.site.urls),
    
    # API Root
    path('api/', api_root, name='api-root'),
    
    # App URLs
    path('api/', include('core.urls')),
    path('api/', include('logistics.urls')),
    path('api/', include('finance.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
