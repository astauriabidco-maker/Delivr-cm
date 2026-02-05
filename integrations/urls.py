"""
Integrations App - URL Configuration
"""

from django.urls import path
from .views import IntegrationsDashboardView, TestConnectionView, PricingSimulatorView

app_name = 'integrations'

urlpatterns = [
    path('', IntegrationsDashboardView.as_view(), name='dashboard'),
    path('test/<str:service>/', TestConnectionView.as_view(), name='test-connection'),
    path('simulate-price/', PricingSimulatorView.as_view(), name='simulate-price'),
]
