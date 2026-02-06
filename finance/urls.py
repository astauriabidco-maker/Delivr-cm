"""
Finance App URLs
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import TransactionViewSet, WalletViewSet
from . import payment_api

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    # Wallet endpoints
    path('wallet/balance/', WalletViewSet.as_view({'get': 'balance'}), name='wallet-balance'),
    path('wallet/deposit/', WalletViewSet.as_view({'post': 'deposit'}), name='wallet-deposit'),
    path('wallet/withdraw/', WalletViewSet.as_view({'post': 'request_withdrawal'}), name='wallet-withdraw'),
    path('wallet/history/', WalletViewSet.as_view({'get': 'history'}), name='wallet-history'),
    
    # Mobile Money Payments
    path('payments/mobile/init/', payment_api.init_mobile_payment, name='mobile-payment-init'),
    path('payments/mobile/status/<uuid:payment_id>/', payment_api.get_payment_status, name='mobile-payment-status'),
    path('payments/mobile/providers/', payment_api.payment_providers_status, name='mobile-payment-providers'),
    path('payments/mobile/callback/mtn/', payment_api.mtn_callback, name='mtn-callback'),
    path('payments/mobile/callback/orange/', payment_api.orange_callback, name='orange-callback'),
    
    # Router URLs
    path('', include(router.urls)),
]

