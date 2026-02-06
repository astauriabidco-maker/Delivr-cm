import 'dart:async';
import 'dart:convert';
import 'dart:developer' as dev;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import 'package:connectivity_plus/connectivity_plus.dart';

import '../auth/auth_provider.dart';
import '../../features/notifications/notification_service.dart';

/// WebSocket connection states
enum WebSocketState {
  disconnected,
  connecting,
  connected,
  reconnecting,
  error,
}

/// WebSocket event types from backend
class WsEventType {
  static const connectionEstablished = 'connection_established';
  static const authenticated = 'authenticated';
  static const error = 'error';
  static const pong = 'pong';
  
  // Courier events
  static const newOrder = 'new_order';
  static const orderAssigned = 'order_assigned';
  static const orderCancelled = 'order_cancelled';
  static const locationConfirmed = 'location_confirmed';
  
  // Status updates
  static const statusUpdate = 'status_update';
  static const walletUpdate = 'wallet_update';
  static const levelUp = 'level_up';
  static const badgeUnlocked = 'badge_unlocked';
}

/// WebSocket message model
class WsMessage {
  final String type;
  final Map<String, dynamic> payload;
  final DateTime timestamp;

  WsMessage({
    required this.type,
    required this.payload,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();

  factory WsMessage.fromJson(Map<String, dynamic> json) {
    return WsMessage(
      type: json['type'] ?? 'unknown',
      payload: Map<String, dynamic>.from(json),
      timestamp: json['timestamp'] != null 
          ? DateTime.tryParse(json['timestamp']) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() => {
    'type': type,
    ...payload,
    'timestamp': timestamp.toIso8601String(),
  };
}

/// WebSocket state notifier
final wsStateProvider = StateNotifierProvider<WsStateNotifier, WebSocketState>((ref) {
  return WsStateNotifier();
});

class WsStateNotifier extends StateNotifier<WebSocketState> {
  WsStateNotifier() : super(WebSocketState.disconnected);

  void setConnecting() => state = WebSocketState.connecting;
  void setConnected() => state = WebSocketState.connected;
  void setReconnecting() => state = WebSocketState.reconnecting;
  void setDisconnected() => state = WebSocketState.disconnected;
  void setError() => state = WebSocketState.error;
}

/// WebSocket service provider
final wsServiceProvider = Provider<WebSocketService>((ref) {
  return WebSocketService(ref);
});

/// WebSocket service for courier app
class WebSocketService {
  final Ref _ref;
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  StreamSubscription? _connectivitySubscription;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;
  
  int _reconnectAttempts = 0;
  static const int maxReconnectAttempts = 10;
  static const Duration heartbeatInterval = Duration(seconds: 30);
  
  bool _isManuallyDisconnected = false;

  WebSocketService(this._ref) {
    // Listen to connectivity changes
    _setupConnectivityListener();
  }

  /// WebSocket URL
  String get wsUrl {
    const baseUrl = 'wss://api.delivr.cm';  // Production
    // const baseUrl = 'ws://10.0.2.2:8000';  // Android Emulator
    return '$baseUrl/ws/courier/';
  }

  /// Connect to WebSocket server
  Future<void> connect() async {
    if (_channel != null) return;
    
    _isManuallyDisconnected = false;
    _ref.read(wsStateProvider.notifier).setConnecting();
    
    try {
      dev.log('[WS] Connecting to $wsUrl', name: 'WebSocket');
      
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      
      await _channel!.ready;
      
      _ref.read(wsStateProvider.notifier).setConnected();
      _reconnectAttempts = 0;
      
      dev.log('[WS] Connected successfully', name: 'WebSocket');
      
      // Authenticate after connection
      await _authenticate();
      
      // Start listening to messages
      _subscription = _channel!.stream.listen(
        _handleMessage,
        onError: _handleError,
        onDone: _handleDisconnect,
      );
      
      // Start heartbeat
      _startHeartbeat();
      
    } catch (e) {
      dev.log('[WS] Connection failed: $e', name: 'WebSocket', error: e);
      _ref.read(wsStateProvider.notifier).setError();
      _scheduleReconnect();
    }
  }

  /// Disconnect from WebSocket
  void disconnect() {
    _isManuallyDisconnected = true;
    _cleanup();
    _ref.read(wsStateProvider.notifier).setDisconnected();
    dev.log('[WS] Disconnected manually', name: 'WebSocket');
  }

  /// Send message to server
  void send(String type, Map<String, dynamic> data) {
    if (_channel == null) {
      dev.log('[WS] Cannot send: not connected', name: 'WebSocket');
      return;
    }
    
    final message = {
      'type': type,
      ...data,
    };
    
    _channel!.sink.add(jsonEncode(message));
    dev.log('[WS] Sent: $type', name: 'WebSocket');
  }

  /// Authenticate with the server
  Future<void> _authenticate() async {
    final authState = _ref.read(authStateProvider);
    
    if (authState.courierPhone != null) {
      send('authenticate', {
        'phone_number': authState.courierPhone,
      });
    }
  }

  /// Send location update
  void sendLocationUpdate(double latitude, double longitude) {
    send('location_update', {
      'latitude': latitude,
      'longitude': longitude,
    });
  }

  /// Accept a delivery order
  void acceptOrder(String orderId) {
    send('accept_order', {
      'order_id': orderId,
    });
  }

  /// Handle incoming message
  void _handleMessage(dynamic rawMessage) {
    try {
      final data = jsonDecode(rawMessage as String) as Map<String, dynamic>;
      final message = WsMessage.fromJson(data);
      
      dev.log('[WS] Received: ${message.type}', name: 'WebSocket');
      
      switch (message.type) {
        case WsEventType.authenticated:
          dev.log('[WS] Authenticated as courier ${data['courier_id']}', name: 'WebSocket');
          break;
          
        case WsEventType.newOrder:
          _handleNewOrder(data);
          break;
          
        case WsEventType.orderAssigned:
          _handleOrderAssigned(data);
          break;
          
        case WsEventType.orderCancelled:
          _handleOrderCancelled(data);
          break;
          
        case WsEventType.walletUpdate:
          _handleWalletUpdate(data);
          break;
          
        case WsEventType.levelUp:
          _handleLevelUp(data);
          break;
          
        case WsEventType.badgeUnlocked:
          _handleBadgeUnlocked(data);
          break;
          
        case WsEventType.pong:
          // Heartbeat response, all good
          break;
          
        case WsEventType.error:
          dev.log('[WS] Server error: ${data['message']}', name: 'WebSocket');
          break;
      }
    } catch (e) {
      dev.log('[WS] Failed to parse message: $e', name: 'WebSocket', error: e);
    }
  }

  /// Handle new order notification
  void _handleNewOrder(Map<String, dynamic> data) {
    final notificationService = _ref.read(notificationServiceProvider);
    
    notificationService.showDeliveryNotification(
      title: '🚀 Nouvelle Course Disponible!',
      body: '${data['pickup_address'] ?? 'Retrait'} → ${data['dropoff_address'] ?? 'Livraison'}\n'
            '💰 ${data['courier_earning'] ?? 0} XAF',
      payload: 'new_order:${data['order_id']}',
    );
  }

  /// Handle order assigned notification
  void _handleOrderAssigned(Map<String, dynamic> data) {
    final notificationService = _ref.read(notificationServiceProvider);
    
    notificationService.showDeliveryNotification(
      title: '✅ Course Assignée!',
      body: 'Vous avez été assigné à la course #${data['order_id']?.toString().substring(0, 8) ?? ''}',
      payload: 'order_assigned:${data['order_id']}',
    );
  }

  /// Handle order cancelled notification
  void _handleOrderCancelled(Map<String, dynamic> data) {
    final notificationService = _ref.read(notificationServiceProvider);
    
    notificationService.showNotification(
      title: '❌ Course Annulée',
      body: 'La course #${data['order_id']?.toString().substring(0, 8) ?? ''} a été annulée.',
      payload: 'order_cancelled:${data['order_id']}',
    );
  }

  /// Handle wallet update
  void _handleWalletUpdate(Map<String, dynamic> data) {
    final notificationService = _ref.read(notificationServiceProvider);
    
    final amount = data['amount'] ?? 0;
    final isCredit = (data['type'] ?? '') == 'credit';
    
    notificationService.showNotification(
      title: isCredit ? '💰 Paiement Reçu' : '💳 Débit Wallet',
      body: '${isCredit ? '+' : '-'}$amount XAF\nSolde: ${data['balance'] ?? 0} XAF',
      payload: 'wallet_update',
    );
  }

  /// Handle level up
  void _handleLevelUp(Map<String, dynamic> data) {
    final notificationService = _ref.read(notificationServiceProvider);
    
    notificationService.showNotification(
      title: '🎉 Félicitations!',
      body: 'Vous êtes passé au niveau ${data['new_level'] ?? 'suivant'}!',
      payload: 'level_up:${data['new_level']}',
    );
  }

  /// Handle badge unlocked
  void _handleBadgeUnlocked(Map<String, dynamic> data) {
    final notificationService = _ref.read(notificationServiceProvider);
    
    notificationService.showNotification(
      title: '🏆 Nouveau Badge Débloqué!',
      body: data['badge_name'] ?? 'Bravo pour votre accomplissement!',
      payload: 'badge:${data['badge_id']}',
    );
  }

  /// Handle connection error
  void _handleError(dynamic error) {
    dev.log('[WS] Error: $error', name: 'WebSocket', error: error);
    _ref.read(wsStateProvider.notifier).setError();
    _cleanup();
    _scheduleReconnect();
  }

  /// Handle disconnection
  void _handleDisconnect() {
    dev.log('[WS] Disconnected', name: 'WebSocket');
    _ref.read(wsStateProvider.notifier).setDisconnected();
    _cleanup();
    
    if (!_isManuallyDisconnected) {
      _scheduleReconnect();
    }
  }

  /// Start heartbeat timer
  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(heartbeatInterval, (_) {
      send('ping', {});
    });
  }

  /// Schedule reconnection attempt
  void _scheduleReconnect() {
    if (_isManuallyDisconnected) return;
    if (_reconnectAttempts >= maxReconnectAttempts) {
      dev.log('[WS] Max reconnect attempts reached', name: 'WebSocket');
      return;
    }
    
    _ref.read(wsStateProvider.notifier).setReconnecting();
    
    // Exponential backoff: 1s, 2s, 4s, 8s, ... up to 30s
    final delay = Duration(
      seconds: (1 << _reconnectAttempts).clamp(1, 30),
    );
    
    dev.log('[WS] Reconnecting in ${delay.inSeconds}s (attempt ${_reconnectAttempts + 1})', 
            name: 'WebSocket');
    
    _reconnectTimer = Timer(delay, () {
      _reconnectAttempts++;
      connect();
    });
  }

  /// Setup connectivity listener for auto-reconnect
  void _setupConnectivityListener() {
    _connectivitySubscription = Connectivity().onConnectivityChanged.listen((results) {
      final hasConnection = results.any((r) => 
        r != ConnectivityResult.none
      );
      
      if (hasConnection && 
          _ref.read(wsStateProvider) == WebSocketState.disconnected &&
          !_isManuallyDisconnected) {
        dev.log('[WS] Network restored, reconnecting...', name: 'WebSocket');
        connect();
      }
    });
  }

  /// Cleanup resources
  void _cleanup() {
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close(status.goingAway);
    _channel = null;
  }

  /// Dispose service
  void dispose() {
    _connectivitySubscription?.cancel();
    _cleanup();
  }
}
