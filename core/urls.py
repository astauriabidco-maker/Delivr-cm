"""
Core App URLs
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import UserViewSet, CourierViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    # JWT Authentication
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Courier-specific endpoints
    path('courier/profile/', CourierViewSet.as_view({'get': 'profile'}), name='courier-profile'),
    path('courier/location/', CourierViewSet.as_view({'post': 'update_location'}), name='courier-location'),
    path('courier/documents/', CourierViewSet.as_view({'post': 'upload_documents'}), name='courier-documents'),
    path('courier/wallet/', CourierViewSet.as_view({'get': 'wallet'}), name='courier-wallet'),
    
    # Router URLs
    path('', include(router.urls)),
]
