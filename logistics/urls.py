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
from .api.traffic_api import (
    traffic_heatmap, traffic_stats, traffic_route, traffic_cell_detail,
    smart_route
)
from .api.events_api import (
    traffic_events_list, traffic_event_detail, traffic_event_vote
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
    
    # Traffic API endpoints (crowdsourced real-time traffic)
    path('traffic/heatmap/', traffic_heatmap, name='traffic-heatmap'),
    path('traffic/stats/', traffic_stats, name='traffic-stats'),
    path('traffic/route/', traffic_route, name='traffic-route'),
    path('traffic/cell/<str:cell_id>/', traffic_cell_detail, name='traffic-cell'),
    path('traffic/smart-route/', smart_route, name='smart-route'),
    
    # Traffic Events API (Waze-like incident reporting)
    path('traffic/events/', traffic_events_list, name='traffic-events-list'),
    path('traffic/events/<uuid:event_id>/', traffic_event_detail, name='traffic-event-detail'),
    path('traffic/events/<uuid:event_id>/vote/', traffic_event_vote, name='traffic-event-vote'),
    
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

