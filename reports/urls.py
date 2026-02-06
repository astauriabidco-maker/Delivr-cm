"""
REPORTS App - URL Configuration
"""

from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Courier reports (self-service)
    path('courier/performance/', 
         views.CourierPerformanceReportView.as_view(), 
         name='courier-performance'),
    path('courier/earnings/', 
         views.CourierEarningsReportView.as_view(), 
         name='courier-earnings'),
    
    # Admin reports
    path('admin/courier/<uuid:pk>/', 
         views.admin_courier_report, 
         name='admin-courier-report'),
    path('admin/fleet-kpi/', 
         views.fleet_kpi_report, 
         name='fleet-kpi'),
    
    # Operator Dashboard (Real-time)
    path('operator/', 
         views.OperatorDashboardView.as_view(), 
         name='operator-dashboard'),
    path('api/live-stats/', 
         views.live_stats_api, 
         name='live-stats'),
    
    # Pricing Simulator
    path('pricing-simulator/', 
         views.PricingSimulatorView.as_view(), 
         name='pricing-simulator'),
    path('pricing-simulator/csv/', 
         views.pricing_csv_export, 
         name='pricing-csv'),
]

