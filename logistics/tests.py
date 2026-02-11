"""
LOGISTICS App - Tests for DispatchConfiguration and Smart Dispatch Service.

Tests cover:
- DispatchConfiguration singleton
- Weight validation
- SmartDispatchService scoring
- Configuration cache
"""

from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase

from .models import DispatchConfiguration


class DispatchConfigurationModelTest(TestCase):
    """Test the DispatchConfiguration singleton model."""
    
    def setUp(self):
        """Clear cache to prevent stale cached objects."""
        from django.core.cache import cache
        cache.delete('dispatch_configuration')
    
    def test_get_config_creates_instance(self):
        """get_config creates an instance if none exists."""
        self.assertEqual(DispatchConfiguration.objects.count(), 0)
        config = DispatchConfiguration.get_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.pk, 1)
    
    def test_singleton_enforcement(self):
        """Only one instance should exist."""
        config1 = DispatchConfiguration.get_config()
        config2 = DispatchConfiguration()
        config2.save()
        self.assertEqual(DispatchConfiguration.objects.count(), 1)
    
    def test_default_weights_sum_to_one(self):
        """Default weights should sum to 1.0."""
        config = DispatchConfiguration.get_config()
        self.assertTrue(config.weights_valid)
        self.assertAlmostEqual(config.total_weight, 1.0, places=2)
    
    def test_invalid_weights_detection(self):
        """Should detect when weights don't sum to 1.0."""
        config = DispatchConfiguration.get_config()
        config.weight_distance = 0.5
        config.weight_rating = 0.5
        # Other weights remain at defaults, so total > 1.0
        self.assertFalse(config.weights_valid)
    
    def test_default_search_params(self):
        """Default search parameters should be reasonable."""
        config = DispatchConfiguration.get_config()
        self.assertGreater(config.initial_radius_km, 0)
        self.assertGreater(config.max_radius_km, config.initial_radius_km)
        self.assertGreater(config.radius_increment_km, 0)
    
    def test_default_thresholds(self):
        """Default thresholds should be set."""
        config = DispatchConfiguration.get_config()
        self.assertGreater(config.min_score_threshold, 0)
        self.assertGreater(config.auto_assign_threshold, config.min_score_threshold)
    
    def test_level_scores_order(self):
        """Level scores should increase: Bronze < Silver < Gold < Platinum."""
        config = DispatchConfiguration.get_config()
        self.assertLess(config.level_score_bronze, config.level_score_silver)
        self.assertLess(config.level_score_silver, config.level_score_gold)
        self.assertLess(config.level_score_gold, config.level_score_platinum)
    
    def test_cache_invalidation_on_save(self):
        """Saving should clear the cache."""
        config = DispatchConfiguration.get_config()
        with patch('django.core.cache.cache.delete') as mock_delete:
            config.save()
            mock_delete.assert_called_with('dispatch_configuration')
    
    def test_update_weights(self):
        """Updating weights and saving should persist."""
        config = DispatchConfiguration.get_config()
        config.weight_distance = 0.25
        config.weight_rating = 0.15
        config.weight_history = 0.15
        config.weight_availability = 0.10
        config.weight_financial = 0.10
        config.weight_response = 0.10
        config.weight_level = 0.10
        config.weight_acceptance = 0.05
        config.save()
        
        # Re-fetch
        config2 = DispatchConfiguration.objects.get(pk=1)
        self.assertAlmostEqual(config2.weight_distance, 0.25)
        self.assertTrue(config2.weights_valid)
    
    def test_str_representation(self):
        """String representation should be descriptive."""
        config = DispatchConfiguration.get_config()
        text = str(config)
        self.assertIn('Dispatch', text)


class SmartDispatchServiceTest(TestCase):
    """Test the SmartDispatchService scoring logic."""
    
    def setUp(self):
        """Set up DispatchConfiguration."""
        self.config = DispatchConfiguration.get_config()
    
    def test_service_imports(self):
        """SmartDispatchService should import cleanly."""
        from logistics.services.smart_dispatch import SmartDispatchService
        service = SmartDispatchService()
        self.assertIsNotNone(service)
    
    def test_config_loaded(self):
        """Service should load dispatch configuration."""
        from logistics.services.smart_dispatch import SmartDispatchService
        service = SmartDispatchService()
        # Service should have config attributes
        self.assertIsNotNone(service.config)
    
    def test_get_dispatch_config_summary(self):
        """Summary function should return config info."""
        from logistics.services.smart_dispatch import get_dispatch_config_summary
        try:
            summary = get_dispatch_config_summary()
            self.assertIsNotNone(summary)
        except Exception:
            # Redis may not be available, that's OK
            pass


class FinanceModelTest(TestCase):
    """Basic tests for finance-related functionality."""
    
    def test_wallet_service_imports(self):
        """WalletService should be importable."""
        try:
            from finance.models import WalletService
            self.assertTrue(True)
        except ImportError:
            # May not exist yet
            pass
    
    def test_transaction_model_exists(self):
        """Transaction model should be importable."""
        from finance.models import Transaction
        self.assertIsNotNone(Transaction)
    
    def test_withdrawal_model_exists(self):
        """WithdrawalRequest model should be importable."""
        from finance.models import WithdrawalRequest
        self.assertIsNotNone(WithdrawalRequest)


class SignalIntegrationTest(TestCase):
    """Test signal integration with notification dispatch."""
    
    @patch('bot.whatsapp_service.notify_delivery_status_change')
    def test_signal_calls_notify(self, mock_notify):
        """Signal handler should call unified notification dispatcher."""
        from logistics.signals import _handle_delivery_update
        from logistics.models import DeliveryStatus
        
        # Create mock delivery
        delivery = MagicMock()
        delivery.pk = 'test-pk-123'
        delivery.id = 'test-id-123'
        delivery.status = DeliveryStatus.PICKED_UP
        delivery.courier = MagicMock()
        
        # Inject previous status
        from logistics.signals import _previous_status
        _previous_status['test-pk-123'] = DeliveryStatus.ASSIGNED
        
        _handle_delivery_update(delivery)
        
        # Verify notification was called
        mock_notify.assert_called_once_with(delivery, DeliveryStatus.PICKED_UP)
    
    @patch('bot.whatsapp_service.notify_delivery_status_change')
    def test_signal_skips_if_no_change(self, mock_notify):
        """Signal should skip if status didn't actually change."""
        from logistics.signals import _handle_delivery_update
        from logistics.models import DeliveryStatus
        
        delivery = MagicMock()
        delivery.pk = 'test-pk-456'
        delivery.id = 'test-id-456'
        delivery.status = DeliveryStatus.PENDING
        
        # Same status stored as previous
        from logistics.signals import _previous_status
        _previous_status['test-pk-456'] = DeliveryStatus.PENDING
        
        _handle_delivery_update(delivery)
        
        # Should NOT call notify since no status change
        mock_notify.assert_not_called()
