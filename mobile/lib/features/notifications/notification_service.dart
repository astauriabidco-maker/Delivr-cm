import 'dart:developer' as dev;
import 'dart:ui';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Notification service provider
final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService();
});

/// Local notification service for displaying push notifications
class NotificationService {
  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  bool _isInitialized = false;

  /// Notification channel IDs
  static const String deliveryChannelId = 'delivr_deliveries';
  static const String deliveryChannelName = 'Courses';
  static const String deliveryChannelDesc = 'Notifications pour les nouvelles courses et mises à jour';

  static const String generalChannelId = 'delivr_general';
  static const String generalChannelName = 'Général';
  static const String generalChannelDesc = 'Notifications générales';

  /// Initialize the notification service
  Future<void> initialize() async {
    if (_isInitialized) return;

    // Android settings
    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    
    // iOS settings (for future use)
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const initSettings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _plugin.initialize(
      initSettings,
      onDidReceiveNotificationResponse: _onNotificationTapped,
    );

    // Create notification channels for Android
    await _createNotificationChannels();

    _isInitialized = true;
    dev.log('[NOTIF] Notification service initialized', name: 'Notification');
  }

  /// Create Android notification channels
  Future<void> _createNotificationChannels() async {
    final androidPlugin = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    
    if (androidPlugin == null) return;

    // Delivery channel (high importance)
    await androidPlugin.createNotificationChannel(
      const AndroidNotificationChannel(
        deliveryChannelId,
        deliveryChannelName,
        description: deliveryChannelDesc,
        importance: Importance.high,
        playSound: true,
        enableVibration: true,
        enableLights: true,
      ),
    );

    // General channel
    await androidPlugin.createNotificationChannel(
      const AndroidNotificationChannel(
        generalChannelId,
        generalChannelName,
        description: generalChannelDesc,
        importance: Importance.defaultImportance,
      ),
    );
  }

  /// Handle notification tap
  void _onNotificationTapped(NotificationResponse response) {
    final payload = response.payload;
    if (payload == null) return;

    dev.log('[NOTIF] Notification tapped: $payload', name: 'Notification');
    
    // Parse payload and navigate
    if (payload.startsWith('new_order:')) {
      final orderId = payload.replaceFirst('new_order:', '');
      // TODO: Navigate to order details
      dev.log('[NOTIF] Navigate to new order: $orderId', name: 'Notification');
    } else if (payload.startsWith('order_assigned:')) {
      final orderId = payload.replaceFirst('order_assigned:', '');
      // TODO: Navigate to assigned order
      dev.log('[NOTIF] Navigate to assigned order: $orderId', name: 'Notification');
    }
    // Add more payload handlers as needed
  }

  /// Show a delivery notification (high priority)
  Future<void> showDeliveryNotification({
    required String title,
    required String body,
    String? payload,
  }) async {
    await _ensureInitialized();

    final androidDetails = AndroidNotificationDetails(
      deliveryChannelId,
      deliveryChannelName,
      channelDescription: deliveryChannelDesc,
      importance: Importance.high,
      priority: Priority.high,
      ticker: title,
      icon: '@drawable/ic_notification',
      color: const Color(0xFFFF6B35), // DELIVR primary color
      styleInformation: BigTextStyleInformation(
        body,
        contentTitle: title,
      ),
      actions: [
        const AndroidNotificationAction(
          'accept',
          '✓ Accepter',
          showsUserInterface: true,
        ),
        const AndroidNotificationAction(
          'ignore',
          '✗ Ignorer',
          cancelNotification: true,
        ),
      ],
    );

    final details = NotificationDetails(android: androidDetails);

    await _plugin.show(
      DateTime.now().millisecondsSinceEpoch.remainder(100000),
      title,
      body,
      details,
      payload: payload,
    );
  }

  /// Show a general notification
  Future<void> showNotification({
    required String title,
    required String body,
    String? payload,
  }) async {
    await _ensureInitialized();

    const androidDetails = AndroidNotificationDetails(
      generalChannelId,
      generalChannelName,
      channelDescription: generalChannelDesc,
      importance: Importance.defaultImportance,
      priority: Priority.defaultPriority,
    );

    const details = NotificationDetails(android: androidDetails);

    await _plugin.show(
      DateTime.now().millisecondsSinceEpoch.remainder(100000),
      title,
      body,
      details,
      payload: payload,
    );
  }

  /// Cancel a specific notification
  Future<void> cancelNotification(int id) async {
    await _plugin.cancel(id);
  }

  /// Cancel all notifications
  Future<void> cancelAllNotifications() async {
    await _plugin.cancelAll();
  }

  /// Request notification permissions
  Future<bool> requestPermissions() async {
    final androidPlugin = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    
    if (androidPlugin != null) {
      final granted = await androidPlugin.requestNotificationsPermission();
      return granted ?? false;
    }
    
    return true;
  }

  /// Ensure service is initialized
  Future<void> _ensureInitialized() async {
    if (!_isInitialized) {
      await initialize();
    }
  }
}
