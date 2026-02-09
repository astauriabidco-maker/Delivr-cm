"""
COURIER App - Mobile API URL Configuration
"""

from django.urls import path
from .api_mobile import (
    CourierLoginView,
    CourierRefreshTokenView,
    CourierActivateView,
    CourierDashboardView,
    ToggleOnlineView,
    DeliveryListView,
    DeliveryDetailView,
    DeliveryStatusUpdateView,
    ConfirmPickupView,
    ConfirmDropoffView,
    UpdateLocationView,
    UploadDeliveryPhotoView,
    ProfilePhotoUploadView,
    WalletView,
)


app_name = 'mobile_api'

urlpatterns = [
    # Authentication
    path('auth/login/', CourierLoginView.as_view(), name='login'),
    path('auth/refresh/', CourierRefreshTokenView.as_view(), name='refresh'),
    path('activate/', CourierActivateView.as_view(), name='activate'),
    
    # Dashboard
    path('dashboard/', CourierDashboardView.as_view(), name='dashboard'),
    path('toggle-online/', ToggleOnlineView.as_view(), name='toggle_online'),
    
    # Deliveries
    path('deliveries/', DeliveryListView.as_view(), name='delivery_list'),
    path('deliveries/<uuid:delivery_id>/', DeliveryDetailView.as_view(), name='delivery_detail'),
    path('deliveries/<uuid:delivery_id>/status/', DeliveryStatusUpdateView.as_view(), name='delivery_status'),
    path('deliveries/<uuid:delivery_id>/confirm-pickup/', ConfirmPickupView.as_view(), name='confirm_pickup'),
    path('deliveries/<uuid:delivery_id>/confirm-dropoff/', ConfirmDropoffView.as_view(), name='confirm_dropoff'),
    
    # Location
    path('location/', UpdateLocationView.as_view(), name='update_location'),
    
    # Uploads
    path('uploads/delivery-photo/', UploadDeliveryPhotoView.as_view(), name='upload_photo'),
    
    # Profile
    path('profile/photo/', ProfilePhotoUploadView.as_view(), name='profile_photo'),
    
    # Wallet
    path('wallet/', WalletView.as_view(), name='wallet'),
]

