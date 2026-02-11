"""
BOT App - Tests for Notification Configuration and WhatsApp Service.

Tests cover:
- NotificationConfiguration singleton behavior
- Toggle enable/disable per status and target
- Custom message templates
- Notification dispatch pipeline (mocked)
- All 10 delivery statuses
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase

from .models import NotificationConfiguration


class NotificationConfigurationModelTest(TestCase):
    """Test the NotificationConfiguration singleton model."""
    
    def setUp(self):
        """Clear cache to prevent stale objects from production DB."""
        from django.core.cache import cache
        cache.delete('notification_configuration')
    
    def test_get_config_creates_instance(self):
        """get_config should create config if none exists."""
        self.assertEqual(NotificationConfiguration.objects.count(), 0)
        config = NotificationConfiguration.get_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.pk, 1)
        self.assertEqual(NotificationConfiguration.objects.count(), 1)
    
    def test_singleton_enforcement(self):
        """Only one instance should exist, even with multiple saves."""
        config1 = NotificationConfiguration.get_config()
        self.assertEqual(NotificationConfiguration.objects.count(), 1)
        # Saving another instance should overwrite (pk=1)
        config2 = NotificationConfiguration()
        config2.notify_sender_completed = False  # change something
        config2.save()
        self.assertEqual(NotificationConfiguration.objects.count(), 1)
        self.assertEqual(config2.pk, 1)
        # Verify the change persisted
        config_check = NotificationConfiguration.objects.get(pk=1)
        self.assertFalse(config_check.notify_sender_completed)
    
    def test_default_sender_enabled(self):
        """Sender notifications should be enabled by default for most statuses."""
        config = NotificationConfiguration.get_config()
        enabled_statuses = [
            'PENDING', 'ASSIGNED', 'EN_ROUTE_PICKUP', 'ARRIVED_PICKUP',
            'PICKED_UP', 'IN_TRANSIT', 'ARRIVED_DROPOFF', 'COMPLETED',
            'CANCELLED', 'FAILED',
        ]
        for status in enabled_statuses:
            self.assertTrue(
                config.is_enabled(status, 'sender'),
                f"Sender notification for {status} should be enabled by default"
            )
    
    def test_default_recipient_disabled_for_early_stages(self):
        """Recipient notifications should be OFF by default for EN_ROUTE_PICKUP and ARRIVED_PICKUP."""
        config = NotificationConfiguration.get_config()
        self.assertFalse(config.is_enabled('EN_ROUTE_PICKUP', 'recipient'))
        self.assertFalse(config.is_enabled('ARRIVED_PICKUP', 'recipient'))
    
    def test_default_recipient_enabled_for_key_stages(self):
        """Recipient should be notified for key stages by default."""
        config = NotificationConfiguration.get_config()
        for status in ['PENDING', 'ASSIGNED', 'PICKED_UP', 'IN_TRANSIT',
                       'ARRIVED_DROPOFF', 'COMPLETED', 'CANCELLED', 'FAILED']:
            self.assertTrue(
                config.is_enabled(status, 'recipient'),
                f"Recipient notification for {status} should be enabled by default"
            )
    
    def test_toggle_off(self):
        """Toggling a notification OFF should work."""
        config = NotificationConfiguration.get_config()
        config.notify_sender_completed = False
        config.save()
        
        # Re-fetch  
        config = NotificationConfiguration.objects.get(pk=1)
        self.assertFalse(config.is_enabled('COMPLETED', 'sender'))
    
    def test_toggle_on(self):
        """Toggling a notification ON should work."""
        config = NotificationConfiguration.get_config()
        config.notify_recipient_en_route_pickup = True
        config.save()
        
        config = NotificationConfiguration.objects.get(pk=1)
        self.assertTrue(config.is_enabled('EN_ROUTE_PICKUP', 'recipient'))
    
    def test_unknown_status_returns_false(self):
        """Unknown status should return False."""
        config = NotificationConfiguration.get_config()
        self.assertFalse(config.is_enabled('UNKNOWN_STATUS', 'sender'))
        self.assertFalse(config.is_enabled('UNKNOWN_STATUS', 'recipient'))
    
    def test_custom_message(self):
        """Custom messages should be retrievable."""
        config = NotificationConfiguration.get_config()
        config.msg_sender_order_created = "Hello {ref}!"
        config.save()
        
        config = NotificationConfiguration.objects.get(pk=1)
        msg = config.get_custom_message('PENDING', 'sender')
        self.assertEqual(msg, "Hello {ref}!")
    
    def test_empty_custom_message(self):
        """Empty custom message should return empty string (use default)."""
        config = NotificationConfiguration.get_config()
        msg = config.get_custom_message('ASSIGNED', 'sender')
        self.assertEqual(msg, "")
    
    def test_summary(self):
        """Summary should show correct format."""
        config = NotificationConfiguration.get_config()
        summary = config.summary
        self.assertIn("/20", summary)
        self.assertIn("actives", summary)
    
    def test_cache_invalidation_on_save(self):
        """Saving config should clear cache."""
        config = NotificationConfiguration.get_config()
        
        with patch('django.core.cache.cache.delete') as mock_delete:
            config.save()
            mock_delete.assert_called_with('notification_configuration')


class WhatsAppServiceTest(TestCase):
    """Test WhatsApp notification dispatch with mocked sending."""
    
    def setUp(self):
        """Set up test data."""
        from django.core.cache import cache
        cache.delete('notification_configuration')
        
        self.config = NotificationConfiguration.get_config()
        
        # Create mock delivery
        self.delivery = MagicMock()
        self.delivery.id = 'abcd1234-5678-9012-3456-789012345678'
        self.delivery.total_price = 2500
        self.delivery.distance_km = 3.5
        self.delivery.pickup_otp = '1234'
        self.delivery.otp_code = '5678'
        self.delivery.recipient_phone = '+237690000001'
        self.delivery.recipient_name = 'Jean Test'
        self.delivery.dropoff_address = '123 Rue Test'
        
        # Mock sender
        self.delivery.sender = MagicMock()
        self.delivery.sender.phone_number = '+237690000002'
        self.delivery.sender.full_name = 'Anne Expéditeur'
        
        # Mock courier
        self.delivery.courier = MagicMock()
        self.delivery.courier.phone_number = '+237690000003'
        self.delivery.courier.full_name = 'Pierre Coursier'
    
    @patch('bot.whatsapp_service.send_notification_with_fallback')
    def test_order_created_sender(self, mock_send):
        """Test sender notification on order creation (default message)."""
        mock_send.return_value = ('msg_id_123', 'whatsapp')
        
        # Make sure no custom message is set (use default template)
        config = NotificationConfiguration.get_config()
        config.msg_sender_order_created = ''
        config.save()
        
        from bot.whatsapp_service import send_order_confirmation_to_sender
        result = send_order_confirmation_to_sender(self.delivery)
        
        mock_send.assert_called_once()
        args = mock_send.call_args
        self.assertEqual(args[0][0], '+237690000002')
        self.assertIn('ABCD1234', args[0][1])  # Reference
        self.assertIn('1234', args[0][1])  # Pickup OTP
        self.assertIn('5678', args[0][1])  # Delivery OTP
    
    @patch('bot.whatsapp_service.send_notification_with_fallback')
    def test_order_created_recipient(self, mock_send):
        """Test recipient notification on order creation."""
        mock_send.return_value = ('msg_id_123', 'whatsapp')
        
        from bot.whatsapp_service import send_otp_to_recipient
        send_otp_to_recipient(self.delivery)
        
        mock_send.assert_called_once()
        args = mock_send.call_args
        self.assertEqual(args[0][0], '+237690000001')  # Recipient phone
        self.assertIn('5678', args[0][1])  # OTP code
    
    @patch('bot.whatsapp_service.send_notification_with_fallback')
    def test_disabled_notification_skipped(self, mock_send):
        """When a notification is disabled, no message should be sent."""
        # Disable sender completed notification
        self.config.notify_sender_completed = False
        self.config.save()
        
        from bot.whatsapp_service import send_delivery_completed_notification
        send_delivery_completed_notification(self.delivery)
        
        mock_send.assert_not_called()
    
    @patch('bot.whatsapp_service.send_notification_with_fallback')
    def test_no_phone_skipped(self, mock_send):
        """When recipient has no phone, notification should be skipped."""
        self.delivery.recipient_phone = None
        
        from bot.whatsapp_service import send_otp_to_recipient
        send_otp_to_recipient(self.delivery)
        
        mock_send.assert_not_called()
    
    @patch('bot.whatsapp_service.send_notification_with_fallback')
    def test_unified_dispatcher_calls_both(self, mock_send):
        """notify_delivery_status_change should call sender + recipient handlers."""
        mock_send.return_value = ('msg_id', 'whatsapp')
        
        from bot.whatsapp_service import notify_delivery_status_change
        notify_delivery_status_change(self.delivery, 'PICKED_UP')
        
        # Should have called twice (sender + recipient)
        self.assertEqual(mock_send.call_count, 2)
    
    @patch('bot.whatsapp_service.send_notification_with_fallback')
    def test_custom_message_used(self, mock_send):
        """When a custom message is set, it should be used instead of default."""
        mock_send.return_value = ('msg_id', 'whatsapp')
        
        self.config.msg_sender_order_created = "Commande {ref} créée! Prix: {price} XAF"
        self.config.save()
        
        from bot.whatsapp_service import send_order_confirmation_to_sender
        send_order_confirmation_to_sender(self.delivery)
        
        args = mock_send.call_args
        self.assertIn('ABCD1234', args[0][1])
        self.assertIn('2,500', args[0][1])
    
    @patch('bot.whatsapp_service.send_notification_with_fallback')
    def test_all_statuses_have_handlers(self, mock_send):
        """Every status should have notification handlers."""
        mock_send.return_value = ('msg_id', 'whatsapp')
        
        from bot.whatsapp_service import notify_delivery_status_change
        
        statuses = [
            'ASSIGNED', 'EN_ROUTE_PICKUP', 'ARRIVED_PICKUP', 'PICKED_UP',
            'IN_TRANSIT', 'ARRIVED_DROPOFF', 'COMPLETED', 'CANCELLED', 'FAILED',
        ]
        
        for status in statuses:
            mock_send.reset_mock()
            # Should not raise
            notify_delivery_status_change(self.delivery, status)
    
    @patch('bot.whatsapp_service.send_notification_with_fallback')
    def test_cancelled_with_reason(self, mock_send):
        """Cancelled notification should include reason when provided."""
        mock_send.return_value = ('msg_id', 'whatsapp')
        
        from bot.whatsapp_service import send_cancelled_notification_sender
        send_cancelled_notification_sender(self.delivery, reason="Stock épuisé")
        
        args = mock_send.call_args
        self.assertIn('Stock épuisé', args[0][1])
