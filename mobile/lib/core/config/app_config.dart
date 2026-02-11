// DELIVR-CM Environment Configuration
// =====================================
// Centralizes all environment-specific configuration.
// Switch between environments by changing the active config in main.dart.
//
// Usage:
//   - Development: AppConfig.development()
//   - Staging:     AppConfig.staging()
//   - Production:  AppConfig.production()

/// Centralized environment configuration for the DELIVR courier app.
class AppConfig {
  /// API base URL (HTTP)
  final String apiBaseUrl;

  /// WebSocket base URL
  final String wsBaseUrl;

  /// Environment name
  final String environment;

  /// Enable debug logging
  final bool enableLogging;

  /// API request timeout
  final Duration connectTimeout;
  final Duration receiveTimeout;

  const AppConfig._({
    required this.apiBaseUrl,
    required this.wsBaseUrl,
    required this.environment,
    required this.enableLogging,
    this.connectTimeout = const Duration(seconds: 30),
    this.receiveTimeout = const Duration(seconds: 30),
  });

  // =============================================
  // Environment Factories
  // =============================================

  /// Local development (web browser)
  factory AppConfig.development() {
    return const AppConfig._(
      apiBaseUrl: 'http://localhost:8000',
      wsBaseUrl: 'ws://localhost:8000',
      environment: 'development',
      enableLogging: true,
    );
  }

  /// Android emulator (10.0.2.2 maps to host localhost)
  factory AppConfig.emulator() {
    return const AppConfig._(
      apiBaseUrl: 'http://10.0.2.2:8000',
      wsBaseUrl: 'ws://10.0.2.2:8000',
      environment: 'emulator',
      enableLogging: true,
    );
  }

  /// Local network testing (physical device on same WiFi)
  /// Replace with your machine's local IP
  factory AppConfig.localNetwork(String localIp) {
    return AppConfig._(
      apiBaseUrl: 'http://$localIp:8000',
      wsBaseUrl: 'ws://$localIp:8000',
      environment: 'local_network',
      enableLogging: true,
    );
  }

  /// Staging server
  factory AppConfig.staging() {
    return const AppConfig._(
      apiBaseUrl: 'https://staging.delivr.cm',
      wsBaseUrl: 'wss://staging.delivr.cm',
      environment: 'staging',
      enableLogging: true,
    );
  }

  /// Production
  factory AppConfig.production() {
    return const AppConfig._(
      apiBaseUrl: 'https://api.delivr.cm',
      wsBaseUrl: 'wss://api.delivr.cm',
      environment: 'production',
      enableLogging: false,
      connectTimeout: Duration(seconds: 15),
      receiveTimeout: Duration(seconds: 15),
    );
  }

  // =============================================
  // Singleton Pattern
  // =============================================

  static AppConfig? _instance;

  /// Initialize config (call once in main.dart)
  static void init(AppConfig config) {
    _instance = config;
  }

  /// Get current config
  static AppConfig get current {
    assert(_instance != null, 'AppConfig.init() must be called before accessing config');
    return _instance!;
  }

  /// Check if initialized
  static bool get isInitialized => _instance != null;

  // =============================================
  // Derived URLs
  // =============================================

  /// WebSocket URL for courier connection
  String get courierWsUrl => '$wsBaseUrl/ws/courier/';

  /// WebSocket URL for delivery tracking
  String deliveryTrackingWsUrl(String deliveryId) =>
      '$wsBaseUrl/ws/tracking/$deliveryId/';

  /// WebSocket URL for dispatch zone
  String get dispatchZoneWsUrl => '$wsBaseUrl/ws/dispatch-zone/';

  /// Whether this is a production build
  bool get isProduction => environment == 'production';

  /// Whether this is a development build
  bool get isDevelopment =>
      environment == 'development' || environment == 'emulator' || environment == 'local_network';

  @override
  String toString() => 'AppConfig($environment: $apiBaseUrl)';
}
