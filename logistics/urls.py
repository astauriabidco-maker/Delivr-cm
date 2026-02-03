"""
Logistics App URLs
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryViewSet, NeighborhoodViewSet,
    QuoteAPIView, OrderAPIView
)

router = DefaultRouter()
router.register(r'deliveries', DeliveryViewSet, basename='delivery')
router.register(r'neighborhoods', NeighborhoodViewSet, basename='neighborhood')

urlpatterns = [
    # E-commerce API endpoints
    path('quote/', QuoteAPIView.as_view(), name='quote'),
    path('orders/', OrderAPIView.as_view(), name='orders'),
    
    # Router URLs
    path('', include(router.urls)),
]
