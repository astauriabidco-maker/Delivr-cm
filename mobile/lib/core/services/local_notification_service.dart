import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter/material.dart';

/// Service for local notifications
class LocalNotificationService {
  static final FlutterLocalNotificationsPlugin _plugin = 
      FlutterLocalNotificationsPlugin();
  
  static bool _isInitialized = false;
  
  /// Initialize the notification service
  static Future<void> initialize() async {
    if (_isInitialized) return;
    
    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );
    
    const settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );
    
    await _plugin.initialize(
      settings,
      onDidReceiveNotificationResponse: _onNotificationResponse,
    );
    
    _isInitialized = true;
  }
  
  static void _onNotificationResponse(NotificationResponse response) {
    // Handle notification tap
    debugPrint('Notification tapped: ${response.payload}');
  }
  
  /// Show a simple notification
  static Future<void> showNotification({
    required int id,
    required String title,
    required String body,
    String? payload,
  }) async {
    await initialize();
    
    const androidDetails = AndroidNotificationDetails(
      'delivr_channel',
      'DELIVR Notifications',
      channelDescription: 'Notifications pour les livraisons DELIVR',
      importance: Importance.high,
      priority: Priority.high,
      showWhen: true,
      icon: '@mipmap/ic_launcher',
      color: Color(0xFF6750A4),
    );
    
    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );
    
    const details = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );
    
    await _plugin.show(id, title, body, details, payload: payload);
  }
  
  /// Show notification for new delivery
  static Future<void> showNewDeliveryNotification({
    required String deliveryId,
    required String pickupAddress,
    required String dropoffAddress,
  }) async {
    await showNotification(
      id: deliveryId.hashCode,
      title: '🚚 Nouvelle livraison disponible !',
      body: 'De $pickupAddress à $dropoffAddress',
      payload: 'delivery:$deliveryId',
    );
  }
  
  /// Show reminder for pickup
  static Future<void> showPickupReminder({
    required String deliveryId,
    required String address,
  }) async {
    await showNotification(
      id: deliveryId.hashCode + 1,
      title: '⏰ Rappel : Pickup en attente',
      body: 'N\'oubliez pas de récupérer le colis à $address',
      payload: 'pickup:$deliveryId',
    );
  }
  
  /// Show notification for delivery completion
  static Future<void> showDeliveryCompleted({
    required double earning,
  }) async {
    await showNotification(
      id: DateTime.now().millisecondsSinceEpoch,
      title: '✅ Livraison terminée !',
      body: 'Vous avez gagné ${earning.toStringAsFixed(0)} XAF',
      payload: 'completed',
    );
  }
  
  /// Show notification for going offline
  static Future<void> showOfflineWarning() async {
    await showNotification(
      id: 9999,
      title: '📴 Vous êtes hors ligne',
      body: 'Passez en ligne pour recevoir des livraisons',
      payload: 'online',
    );
  }
  
  /// Cancel a specific notification
  static Future<void> cancel(int id) async {
    await _plugin.cancel(id);
  }
  
  /// Cancel all notifications
  static Future<void> cancelAll() async {
    await _plugin.cancelAll();
  }
  
  /// Request notification permissions (iOS)
  static Future<bool> requestPermissions() async {
    final result = await _plugin
        .resolvePlatformSpecificImplementation<IOSFlutterLocalNotificationsPlugin>()
        ?.requestPermissions(
          alert: true,
          badge: true,
          sound: true,
        );
    return result ?? true;
  }
}
