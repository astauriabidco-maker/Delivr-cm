import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../auth/auth_provider.dart';

/// WebSocket connection state
enum WebSocketState {
  disconnected,
  connecting,
  connected,
  reconnecting,
}

/// WebSocket tracking service with auto-reconnection
class TrackingWebSocketService {
  WebSocketChannel? _channel;
  Timer? _reconnectTimer;
  Timer? _pingTimer;
  StreamSubscription? _subscription;
  
  final String baseUrl;
  String? _authToken;
  
  WebSocketState _state = WebSocketState.disconnected;
  final _stateController = StreamController<WebSocketState>.broadcast();
  final _messageController = StreamController<Map<String, dynamic>>.broadcast();
  
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 5;
  static const Duration _reconnectDelay = Duration(seconds: 3);
  static const Duration _pingInterval = Duration(seconds: 30);
  
  TrackingWebSocketService({required this.baseUrl});
  
  /// Stream of connection state changes
  Stream<WebSocketState> get stateStream => _stateController.stream;
  
  /// Stream of incoming messages
  Stream<Map<String, dynamic>> get messageStream => _messageController.stream;
  
  /// Current connection state
  WebSocketState get state => _state;
  
  /// Whether currently connected
  bool get isConnected => _state == WebSocketState.connected;
  
  /// Connect to WebSocket server
  Future<void> connect(String authToken) async {
    _authToken = authToken;
    await _connect();
  }
  
  Future<void> _connect() async {
    if (_state == WebSocketState.connecting) return;
    
    _updateState(WebSocketState.connecting);
    
    try {
      // Convert http to ws
      final wsUrl = baseUrl
          .replaceFirst('http://', 'ws://')
          .replaceFirst('https://', 'wss://');
      
      final uri = Uri.parse('$wsUrl/ws/courier/tracking/?token=$_authToken');
      
      _channel = WebSocketChannel.connect(uri);
      
      // Wait for connection
      await _channel!.ready;
      
      _updateState(WebSocketState.connected);
      _reconnectAttempts = 0;
      
      // Start ping timer to keep connection alive
      _startPingTimer();
      
      // Listen for messages
      _subscription = _channel!.stream.listen(
        _handleMessage,
        onError: _handleError,
        onDone: _handleDone,
        cancelOnError: false,
      );
      
      debugPrint('📡 WebSocket connected');
    } catch (e) {
      debugPrint('❌ WebSocket connection failed: $e');
      _scheduleReconnect();
    }
  }
  
  void _handleMessage(dynamic data) {
    try {
      if (data is String) {
        final json = jsonDecode(data) as Map<String, dynamic>;
        
        // Handle pong
        if (json['type'] == 'pong') {
          debugPrint('🏓 Pong received');
          return;
        }
        
        _messageController.add(json);
        debugPrint('📩 WebSocket message: ${json['type']}');
      }
    } catch (e) {
      debugPrint('❌ Error parsing WebSocket message: $e');
    }
  }
  
  void _handleError(dynamic error) {
    debugPrint('❌ WebSocket error: $error');
    _scheduleReconnect();
  }
  
  void _handleDone() {
    debugPrint('🔌 WebSocket closed');
    _updateState(WebSocketState.disconnected);
    _scheduleReconnect();
  }
  
  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) {
      debugPrint('❌ Max reconnection attempts reached');
      _updateState(WebSocketState.disconnected);
      return;
    }
    
    _reconnectAttempts++;
    _updateState(WebSocketState.reconnecting);
    
    final delay = _reconnectDelay * _reconnectAttempts;
    debugPrint('🔄 Reconnecting in ${delay.inSeconds}s (attempt $_reconnectAttempts)');
    
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, _connect);
  }
  
  void _startPingTimer() {
    _pingTimer?.cancel();
    _pingTimer = Timer.periodic(_pingInterval, (_) {
      if (isConnected) {
        send({'type': 'ping'});
      }
    });
  }
  
  void _updateState(WebSocketState newState) {
    _state = newState;
    _stateController.add(newState);
  }
  
  /// Send a message through WebSocket
  void send(Map<String, dynamic> data) {
    if (!isConnected) {
      debugPrint('⚠️ Cannot send: WebSocket not connected');
      return;
    }
    
    try {
      _channel!.sink.add(jsonEncode(data));
    } catch (e) {
      debugPrint('❌ Error sending WebSocket message: $e');
    }
  }
  
  /// Send location update
  void sendLocation({
    required double latitude,
    required double longitude,
    double? speed,
    double? heading,
  }) {
    send({
      'type': 'location_update',
      'latitude': latitude,
      'longitude': longitude,
      'speed': speed,
      'heading': heading,
      'timestamp': DateTime.now().toIso8601String(),
    });
  }
  
  /// Send delivery status update
  void sendDeliveryStatusUpdate({
    required String deliveryId,
    required String status,
  }) {
    send({
      'type': 'delivery_status',
      'delivery_id': deliveryId,
      'status': status,
      'timestamp': DateTime.now().toIso8601String(),
    });
  }
  
  /// Disconnect from WebSocket
  void disconnect() {
    _reconnectTimer?.cancel();
    _pingTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    _channel = null;
    _updateState(WebSocketState.disconnected);
    debugPrint('🔌 WebSocket disconnected');
  }
  
  /// Dispose resources
  void dispose() {
    disconnect();
    _stateController.close();
    _messageController.close();
  }
}

/// Provider for WebSocket service
final trackingWebSocketProvider = Provider<TrackingWebSocketService>((ref) {
  final service = TrackingWebSocketService(baseUrl: 'http://localhost:8000');
  ref.onDispose(() => service.dispose());
  return service;
});

/// Provider for WebSocket connection state
final webSocketStateProvider = StreamProvider<WebSocketState>((ref) {
  final service = ref.watch(trackingWebSocketProvider);
  return service.stateStream;
});

/// Provider for incoming WebSocket messages
final webSocketMessagesProvider = StreamProvider<Map<String, dynamic>>((ref) {
  final service = ref.watch(trackingWebSocketProvider);
  return service.messageStream;
});

/// Auto-connect WebSocket when authenticated
final autoConnectWebSocketProvider = Provider<void>((ref) {
  final authState = ref.watch(authStateProvider);
  final wsService = ref.watch(trackingWebSocketProvider);
  
  if (authState.isAuthenticated && authState.accessToken != null) {
    wsService.connect(authState.accessToken!);
  } else {
    wsService.disconnect();
  }
});
