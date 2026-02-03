"""
Finance App URLs
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import TransactionViewSet, WalletViewSet

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    # Wallet endpoints
    path('wallet/balance/', WalletViewSet.as_view({'get': 'balance'}), name='wallet-balance'),
    path('wallet/deposit/', WalletViewSet.as_view({'post': 'deposit'}), name='wallet-deposit'),
    path('wallet/withdraw/', WalletViewSet.as_view({'post': 'request_withdrawal'}), name='wallet-withdraw'),
    path('wallet/history/', WalletViewSet.as_view({'get': 'history'}), name='wallet-history'),
    
    # Router URLs
    path('', include(router.urls)),
]
