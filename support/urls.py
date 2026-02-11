from django.urls import path
from .views import SupportBackofficeView, ClientDisputeCreateView

app_name = 'support'

urlpatterns = [
    path('backoffice/disputes/', SupportBackofficeView.as_view(), name='backoffice_disputes'),
    path('report/<uuid:delivery_id>/', ClientDisputeCreateView.as_view(), name='client_report_dispute'),
]
