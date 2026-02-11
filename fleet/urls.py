"""
FLEET App - URL Configuration

Admin dashboard routes for fleet management.
"""

from django.urls import path
from . import views

app_name = 'fleet'

urlpatterns = [
    # Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Courier Management
    path('couriers/', views.CourierListView.as_view(), name='courier-list'),
    path('couriers/<uuid:pk>/', views.CourierDetailView.as_view(), name='courier-detail'),
    path('couriers/<uuid:pk>/verify/', views.verify_courier, name='verify-courier'),
    path('couriers/<uuid:pk>/block/', views.toggle_block_courier, name='toggle-block'),
    path('couriers/<uuid:pk>/adjust-debt/', views.adjust_debt_ceiling, name='adjust-debt'),
    
    # Live Map
    path('live-map/', views.LiveMapView.as_view(), name='live-map'),
    
    # Alerts
    path('alerts/', views.AlertsView.as_view(), name='alerts'),
    path('alerts/acknowledge/<int:pk>/', views.acknowledge_alert, name='acknowledge-alert'),
    
    # Analytics
    path('analytics/', views.AnalyticsView.as_view(), name='analytics'),
    path('analytics/advanced/', views.AdvancedAnalyticsView.as_view(), name='analytics-advanced'),
    path('coverage/', views.CoverageView.as_view(), name='coverage'),
    
    # Withdrawals Management
    path('withdrawals/', views.WithdrawalsListView.as_view(), name='withdrawals'),
    path('withdrawals/<uuid:pk>/approve/', views.approve_withdrawal, name='approve-withdrawal'),
    path('withdrawals/<uuid:pk>/reject/', views.reject_withdrawal, name='reject-withdrawal'),
    path('withdrawals/<uuid:pk>/complete/', views.complete_withdrawal, name='complete-withdrawal'),
    
    # Onboarding Admin
    path('onboarding/', views.OnboardingAdminView.as_view(), name='onboarding-admin'),
    path('onboarding/<uuid:pk>/approve/', views.approve_onboarding, name='onboarding-approve'),
    path('onboarding/<uuid:pk>/reject/', views.reject_onboarding, name='onboarding-reject'),
    
    # API Endpoints
    path('api/stats/', views.api_fleet_stats, name='api-stats'),
    path('api/couriers/online/', views.api_online_couriers, name='api-online-couriers'),
    path('api/courier-positions/', views.api_courier_positions, name='api-courier-positions'),
    path('api/alerts/', views.api_check_alerts, name='api-check-alerts'),
    
    # Finance Dashboard
    path('finance/', views.FinanceDashboardView.as_view(), name='finance-dashboard'),
    
    # Reports
    path('reports/', views.ReportView.as_view(), name='reports'),
    
    # Settings (Super Admin only)
    path('settings/', views.SettingsView.as_view(), name='settings'),
]

