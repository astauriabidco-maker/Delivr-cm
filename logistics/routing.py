"""
LOGISTICS App - WebSocket Routing Configuration

Maps WebSocket URLs to consumers for real-time tracking.
"""

from django.urls import re_path
from . import consumers


websocket_urlpatterns = [
    # Track a specific delivery in real-time
    # ws://localhost:8000/ws/delivery/<uuid>/
    re_path(
        r'ws/delivery/(?P<delivery_id>[0-9a-f-]+)/$',
        consumers.DeliveryTrackingConsumer.as_asgi()
    ),
    
    # Courier app - receive new orders and send location updates
    # ws://localhost:8000/ws/courier/
    re_path(
        r'ws/courier/$',
        consumers.CourierConsumer.as_asgi()
    ),
    
    # Courier tracking (legacy or alternative URL used by mobile app)
    # ws://localhost:8000/ws/courier/tracking/
    re_path(
        r'ws/courier/tracking/$',
        consumers.CourierConsumer.as_asgi()
    ),
    
    # Dispatch zone - monitor all deliveries in a city
    # ws://localhost:8000/ws/dispatch/<city>/
    re_path(
        r'ws/dispatch/(?P<city>\w+)/$',
        consumers.DispatchZoneConsumer.as_asgi()
    ),
]
