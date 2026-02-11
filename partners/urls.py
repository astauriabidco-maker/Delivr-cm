"""
Partners App URLs - Partner Portal Routes
"""
from django.urls import path
from django.contrib.auth.decorators import login_required
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views import (
    PartnerLoginView,
    PartnerLogoutView,
    PartnerSignupView,
    PartnerPendingView,
    PartnerDashboardView,
    RevokeAPIKeyView,
    PartnerOrdersView,
    PartnerOrderDetailView,
    PartnerOrderExportView,
    PartnerWebhooksView,
    PartnerBrandingView,
    PartnerInvoicesView,
    PartnerTrackingView,
    PartnerAnalyticsView,
    PartnerNotificationsView,
    PartnerProfileView,
    PartnerWalletView,
    PartnerDisputeListView,
    PartnerDisputeCreateView,
    PartnerDisputeDetailView,
)

app_name = 'partners'

urlpatterns = [
    # Authentication
    path('login/', PartnerLoginView.as_view(), name='login'),
    path('logout/', PartnerLogoutView.as_view(), name='logout'),
    
    # Partner Registration
    path('signup/', PartnerSignupView.as_view(), name='signup'),
    path('pending/', PartnerPendingView.as_view(), name='pending'),
    
    # Partner Dashboard
    path('dashboard/', PartnerDashboardView.as_view(), name='dashboard'),
    path('api-keys/<uuid:key_id>/revoke/', RevokeAPIKeyView.as_view(), name='revoke_key'),
    
    # Orders Management
    path('orders/', PartnerOrdersView.as_view(), name='orders'),
    path('orders/<uuid:order_id>/', PartnerOrderDetailView.as_view(), name='order_detail'),
    path('orders/export/', PartnerOrderExportView.as_view(), name='orders_export'),
    
    # Wallet & Finance
    path('wallet/', PartnerWalletView.as_view(), name='wallet'),
    
    # Profile & Settings
    path('profile/', PartnerProfileView.as_view(), name='profile'),
    
    # Webhooks Configuration
    path('webhooks/', PartnerWebhooksView.as_view(), name='webhooks'),
    
    # Branding / Customization
    path('branding/', PartnerBrandingView.as_view(), name='branding'),
    
    # Invoices / Billing
    path('invoices/', PartnerInvoicesView.as_view(), name='invoices'),
    
    # Tracking (Real-time map)
    path('tracking/', PartnerTrackingView.as_view(), name='tracking'),
    
    # Analytics (Advanced stats)
    path('analytics/', PartnerAnalyticsView.as_view(), name='analytics'),
    
    # Notifications
    path('notifications/', PartnerNotificationsView.as_view(), name='notifications'),
    
    # Disputes
    path('disputes/', PartnerDisputeListView.as_view(), name='disputes'),
    path('disputes/new/<uuid:order_id>/', PartnerDisputeCreateView.as_view(), name='dispute_create'),
    path('disputes/<uuid:dispute_id>/', PartnerDisputeDetailView.as_view(), name='dispute_detail'),

    # API Documentation (Protected - Login Required)
    path('docs/schema/', login_required(SpectacularAPIView.as_view()), name='schema'),
    path('docs/', login_required(SpectacularSwaggerView.as_view(url_name='partners:schema')), name='docs'),
]
