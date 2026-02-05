"""
Logistics App URLs
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryViewSet, NeighborhoodViewSet,
    QuoteAPIView, OrderAPIView,
    CourierLocationView, OrderAcceptView,
    PublicQuoteAPIView, PublicOrderCreateAPIView,
    DeliveryTrackingView
)
from .api.tracking_api import (
    ShareLinkView, ETACalculationView, DeliveryHistoryView,
    ProofUploadView, SharedTrackingView
)

router = DefaultRouter()
router.register(r'deliveries', DeliveryViewSet, basename='delivery')
router.register(r'neighborhoods', NeighborhoodViewSet, basename='neighborhood')

urlpatterns = [
    # Public tracking page (WebSocket real-time)
    path('track/<uuid:delivery_id>/', DeliveryTrackingView.as_view(), name='delivery-tracking'),
    
    # Shared tracking link (short URL)
    path('track/s/<str:share_token>/', SharedTrackingView.as_view(), name='shared-tracking'),
    
    # Tracking API endpoints
    path('api/track/<uuid:delivery_id>/share/', ShareLinkView.as_view(), name='track-share'),
    path('api/track/<uuid:delivery_id>/eta/', ETACalculationView.as_view(), name='track-eta'),
    path('api/track/<uuid:delivery_id>/history/', DeliveryHistoryView.as_view(), name='track-history'),
    path('api/track/<uuid:delivery_id>/proof/', ProofUploadView.as_view(), name='track-proof'),
    
    # Public E-commerce API (WooCommerce, Shopify, etc.)
    path('public/quote/', PublicQuoteAPIView.as_view(), name='public-quote'),
    path('public/orders/', PublicOrderCreateAPIView.as_view(), name='public-orders'),
    
    # E-commerce API endpoints (authenticated)
    path('quote/', QuoteAPIView.as_view(), name='quote'),
    path('orders/', OrderAPIView.as_view(), name='orders'),
    
    # Courier endpoints
    path('courier/location/', CourierLocationView.as_view(), name='courier-location'),
    
    # Order acceptance (courier)
    path('orders/<uuid:order_id>/accept/', OrderAcceptView.as_view(), name='order-accept'),
    
    # Router URLs
    path('', include(router.urls)),
]

