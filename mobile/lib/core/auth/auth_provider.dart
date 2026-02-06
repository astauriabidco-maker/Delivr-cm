import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../api/api_client.dart';

/// Keys for secure storage
class StorageKeys {
  static const accessToken = 'access_token';
  static const refreshToken = 'refresh_token';
  static const courierId = 'courier_id';
  static const courierPhone = 'courier_phone';
}

/// Authentication state
class AuthState {
  final bool isAuthenticated;
  final bool isLoading;
  final String? courierId;
  final String? courierPhone;
  final String? error;
  
  const AuthState({
    this.isAuthenticated = false,
    this.isLoading = true,
    this.courierId,
    this.courierPhone,
    this.error,
  });
  
  AuthState copyWith({
    bool? isAuthenticated,
    bool? isLoading,
    String? courierId,
    String? courierPhone,
    String? error,
  }) {
    return AuthState(
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      isLoading: isLoading ?? this.isLoading,
      courierId: courierId ?? this.courierId,
      courierPhone: courierPhone ?? this.courierPhone,
      error: error,
    );
  }
}

/// Auth state provider
final authStateProvider = StateNotifierProvider<AuthStateNotifier, AuthState>((ref) {
  return AuthStateNotifier(ref);
});

/// Auth service provider
final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(ref);
});

/// Auth state notifier
class AuthStateNotifier extends StateNotifier<AuthState> {
  final Ref _ref;
  
  AuthStateNotifier(this._ref) : super(const AuthState()) {
    _checkAuthStatus();
  }
  
  Future<void> _checkAuthStatus() async {
    try {
      // Add timeout to prevent infinite loading on web
      final authService = _ref.read(authServiceProvider);
      final isAuthenticated = await authService.isAuthenticated()
          .timeout(const Duration(seconds: 3), onTimeout: () => false);
      
      if (isAuthenticated) {
        final storage = _ref.read(secureStorageProvider);
        final courierId = await storage.read(key: StorageKeys.courierId)
            .timeout(const Duration(seconds: 2), onTimeout: () => null);
        final courierPhone = await storage.read(key: StorageKeys.courierPhone)
            .timeout(const Duration(seconds: 2), onTimeout: () => null);
        
        state = state.copyWith(
          isAuthenticated: true,
          isLoading: false,
          courierId: courierId,
          courierPhone: courierPhone,
        );
      } else {
        state = state.copyWith(
          isAuthenticated: false,
          isLoading: false,
        );
      }
    } catch (e) {
      // On error, default to unauthenticated
      state = state.copyWith(
        isAuthenticated: false,
        isLoading: false,
      );
    }
  }
  
  void setAuthenticated({
    required String courierId,
    required String courierPhone,
  }) {
    state = state.copyWith(
      isAuthenticated: true,
      isLoading: false,
      courierId: courierId,
      courierPhone: courierPhone,
      error: null,
    );
  }
  
  void setUnauthenticated() {
    state = const AuthState(
      isAuthenticated: false,
      isLoading: false,
    );
  }
  
  void setError(String error) {
    state = state.copyWith(
      isLoading: false,
      error: error,
    );
  }
  
  void setLoading() {
    state = state.copyWith(isLoading: true, error: null);
  }
}

/// Authentication service
class AuthService {
  final Ref _ref;
  
  AuthService(this._ref);
  
  FlutterSecureStorage get _storage => _ref.read(secureStorageProvider);
  Dio get _dio => _ref.read(dioProvider);
  
  /// Check if user is authenticated
  Future<bool> isAuthenticated() async {
    final token = await _storage.read(key: StorageKeys.accessToken);
    return token != null;
  }
  
  /// Get access token
  Future<String?> getAccessToken() async {
    return _storage.read(key: StorageKeys.accessToken);
  }
  
  /// Activate with code (from WhatsApp)
  Future<bool> activateWithCode(String code) async {
    try {
      final response = await _dio.post(
        '/api/mobile/activate/',
        data: {'activation_code': code},
      );
      
      if (response.statusCode == 200) {
        final data = response.data;
        await _saveTokens(
          accessToken: data['access'],
          refreshToken: data['refresh'],
          courierId: data['courier_id'],
          courierPhone: data['phone'],
        );
        
        _ref.read(authStateProvider.notifier).setAuthenticated(
          courierId: data['courier_id'],
          courierPhone: data['phone'],
        );
        
        return true;
      }
      return false;
    } on DioException catch (e) {
      final message = e.response?.data?['detail'] ?? 'Code invalide';
      _ref.read(authStateProvider.notifier).setError(message);
      return false;
    }
  }
  
  /// Login with phone and password
  Future<bool> login(String phone, String password) async {
    try {
      _ref.read(authStateProvider.notifier).setLoading();
      
      final response = await _dio.post(
        '/api/auth/token/',
        data: {
          'phone_number': phone,
          'password': password,
        },
      );
      
      if (response.statusCode == 200) {
        final data = response.data;
        await _saveTokens(
          accessToken: data['access'],
          refreshToken: data['refresh'],
          courierId: data['courier_id'] ?? '',
          courierPhone: phone,
        );
        
        _ref.read(authStateProvider.notifier).setAuthenticated(
          courierId: data['courier_id'] ?? '',
          courierPhone: phone,
        );
        
        return true;
      }
      return false;
    } on DioException catch (e) {
      final message = e.response?.data?['detail'] ?? 'Identifiants incorrects';
      _ref.read(authStateProvider.notifier).setError(message);
      return false;
    }
  }
  
  /// Refresh access token
  Future<bool> refreshToken() async {
    try {
      final refreshToken = await _storage.read(key: StorageKeys.refreshToken);
      if (refreshToken == null) return false;
      
      final response = await _dio.post(
        '/api/auth/token/refresh/',
        data: {'refresh': refreshToken},
      );
      
      if (response.statusCode == 200) {
        await _storage.write(
          key: StorageKeys.accessToken,
          value: response.data['access'],
        );
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }
  
  /// Logout
  Future<void> logout() async {
    await _storage.deleteAll();
    _ref.read(authStateProvider.notifier).setUnauthenticated();
  }
  
  /// Save tokens securely
  Future<void> _saveTokens({
    required String accessToken,
    required String refreshToken,
    required String courierId,
    required String courierPhone,
  }) async {
    await _storage.write(key: StorageKeys.accessToken, value: accessToken);
    await _storage.write(key: StorageKeys.refreshToken, value: refreshToken);
    await _storage.write(key: StorageKeys.courierId, value: courierId);
    await _storage.write(key: StorageKeys.courierPhone, value: courierPhone);
  }
}
