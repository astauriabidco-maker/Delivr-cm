"""
COURIER App - URL Configuration

Dashboard routes for courier self-service portal.
"""

from django.urls import path
from . import views
from . import onboarding_views

app_name = 'courier'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Stats & Performance
    path('earnings/', views.EarningsView.as_view(), name='earnings'),
    path('performance/', views.PerformanceView.as_view(), name='performance'),
    path('leaderboard/', views.LeaderboardView.as_view(), name='leaderboard'),
    
    # Availability Management
    path('availability/', views.AvailabilityView.as_view(), name='availability'),
    path('availability/toggle/', views.toggle_online_status, name='toggle-online'),
    path('availability/slot/add/', views.add_availability_slot, name='add-slot'),
    path('availability/slot/<uuid:slot_id>/delete/', views.delete_availability_slot, name='delete-slot'),
    
    # Wallet
    path('wallet/', views.WalletView.as_view(), name='wallet'),
    path('wallet/history/', views.TransactionHistoryView.as_view(), name='transaction-history'),
    
    # Profile & Badges
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('badges/', views.BadgesView.as_view(), name='badges'),
    
    # API Endpoints (for AJAX)
    path('api/stats/', views.api_get_stats, name='api-stats'),
    path('api/toggle-online/', views.api_toggle_online, name='api-toggle-online'),
    path('api/withdrawal/status/', views.api_withdrawal_status, name='api-withdrawal-status'),
    path('api/withdrawal/request/', views.api_request_withdrawal, name='api-withdrawal-request'),
    
    # Delivery History
    path('history/', views.DeliveryHistoryView.as_view(), name='delivery-history'),
    path('history/export/', views.export_delivery_history_csv, name='delivery-history-csv'),
    
    # Onboarding Wizard
    path('onboarding/', onboarding_views.onboarding_router, name='onboarding'),
    path('onboarding/phone/', onboarding_views.onboarding_phone, name='onboarding-phone'),
    path('onboarding/phone/send-otp/', onboarding_views.onboarding_send_otp, name='onboarding-send-otp'),
    path('onboarding/phone/verify/', onboarding_views.onboarding_verify_otp, name='onboarding-verify-otp'),
    path('onboarding/documents/', onboarding_views.onboarding_documents, name='onboarding-documents'),
    path('onboarding/emergency/', onboarding_views.onboarding_emergency, name='onboarding-emergency'),
    path('onboarding/caution/', onboarding_views.onboarding_caution, name='onboarding-caution'),
    path('onboarding/contract/', onboarding_views.onboarding_contract, name='onboarding-contract'),
    path('onboarding/status/', onboarding_views.onboarding_status, name='onboarding-status'),
]

