import 'dart:developer' as dev;
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_provider.dart';

/// Interceptor for adding JWT token to requests
class AuthInterceptor extends Interceptor {
  final Ref _ref;
  
  AuthInterceptor(this._ref);
  
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    // Skip auth for public endpoints
    final publicPaths = [
      '/api/mobile/activate/',
      '/api/auth/token/',
      '/api/public/',
    ];
    
    final isPublic = publicPaths.any((path) => options.path.startsWith(path));
    
    if (!isPublic) {
      final authService = _ref.read(authServiceProvider);
      final token = await authService.getAccessToken();
      
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }
    
    handler.next(options);
  }
  
  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    // Handle 401 - Try to refresh token
    if (err.response?.statusCode == 401) {
      final authService = _ref.read(authServiceProvider);
      final success = await authService.refreshToken();
      
      if (success) {
        // Retry the request with new token
        final opts = err.requestOptions;
        final token = await authService.getAccessToken();
        opts.headers['Authorization'] = 'Bearer $token';
        
        try {
          final response = await Dio().fetch(opts);
          handler.resolve(response);
          return;
        } catch (e) {
          // Refresh failed, logout
          await authService.logout();
        }
      } else {
        // Refresh failed, logout
        await authService.logout();
      }
    }
    
    handler.next(err);
  }
}

/// Logging interceptor for debugging
class LoggingInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    dev.log(
      '→ ${options.method} ${options.path}',
      name: 'API',
    );
    handler.next(options);
  }
  
  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    dev.log(
      '← ${response.statusCode} ${response.requestOptions.path}',
      name: 'API',
    );
    handler.next(response);
  }
  
  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    dev.log(
      '✗ ${err.response?.statusCode ?? 'ERR'} ${err.requestOptions.path}: ${err.message}',
      name: 'API',
      error: err,
    );
    handler.next(err);
  }
}

/// Retry interceptor for handling network errors
class RetryInterceptor extends Interceptor {
  final Dio _dio;
  final int maxRetries;
  
  RetryInterceptor(this._dio, {this.maxRetries = 3});
  
  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    // Only retry on connection errors
    if (err.type == DioExceptionType.connectionError ||
        err.type == DioExceptionType.connectionTimeout) {
      
      final retryCount = err.requestOptions.extra['retryCount'] ?? 0;
      
      if (retryCount < maxRetries) {
        dev.log('Retry ${retryCount + 1}/$maxRetries for ${err.requestOptions.path}', name: 'API');
        
        await Future.delayed(Duration(seconds: retryCount + 1));
        
        err.requestOptions.extra['retryCount'] = retryCount + 1;
        
        try {
          final response = await _dio.fetch(err.requestOptions);
          handler.resolve(response);
          return;
        } catch (e) {
          // Continue to error handler
        }
      }
    }
    
    handler.next(err);
  }
}
