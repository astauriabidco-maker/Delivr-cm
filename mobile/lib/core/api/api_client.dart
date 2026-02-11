import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config/app_config.dart';
import 'interceptors.dart';

/// Secure storage for tokens
final secureStorageProvider = Provider<FlutterSecureStorage>((ref) {
  return const FlutterSecureStorage(
    aOptions: AndroidOptions(
      encryptedSharedPreferences: true,
    ),
  );
});

/// Dio HTTP client provider — reads URL from centralized AppConfig
final dioProvider = Provider<Dio>((ref) {
  final config = AppConfig.current;
  
  final dio = Dio(
    BaseOptions(
      baseUrl: config.apiBaseUrl,
      connectTimeout: config.connectTimeout,
      receiveTimeout: config.receiveTimeout,
      sendTimeout: config.connectTimeout,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ),
  );
  
  // Add interceptors
  dio.interceptors.addAll([
    AuthInterceptor(ref),
    if (config.enableLogging) LoggingInterceptor(),
    RetryInterceptor(dio),
  ]);
  
  return dio;
});

/// API response wrapper
class ApiResponse<T> {
  final T? data;
  final String? error;
  final int? statusCode;
  final bool success;
  
  const ApiResponse._({
    this.data,
    this.error,
    this.statusCode,
    required this.success,
  });
  
  factory ApiResponse.success(T data, {int? statusCode}) {
    return ApiResponse._(
      data: data,
      statusCode: statusCode,
      success: true,
    );
  }
  
  factory ApiResponse.error(String message, {int? statusCode}) {
    return ApiResponse._(
      error: message,
      statusCode: statusCode,
      success: false,
    );
  }
}

/// API exception
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic data;
  
  const ApiException({
    required this.message,
    this.statusCode,
    this.data,
  });
  
  @override
  String toString() => 'ApiException: $message (status: $statusCode)';
}

/// API client provider
final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(ref.watch(dioProvider));
});

/// API client wrapper with typed responses
class ApiClient {
  final Dio _dio;
  
  ApiClient(this._dio);
  
  /// GET request
  Future<ApiResponse<Map<String, dynamic>>> get(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      final response = await _dio.get(
        path,
        queryParameters: queryParameters,
      );
      return ApiResponse.success(
        response.data as Map<String, dynamic>,
        statusCode: response.statusCode,
      );
    } on DioException catch (e) {
      return _handleError(e);
    }
  }
  
  /// POST request
  Future<ApiResponse<Map<String, dynamic>>> post(
    String path, {
    Object? data,
  }) async {
    try {
      final response = await _dio.post(path, data: data);
      return ApiResponse.success(
        response.data as Map<String, dynamic>,
        statusCode: response.statusCode,
      );
    } on DioException catch (e) {
      return _handleError(e);
    }
  }
  
  /// PATCH request
  Future<ApiResponse<Map<String, dynamic>>> patch(
    String path, {
    Object? data,
  }) async {
    try {
      final response = await _dio.patch(path, data: data);
      return ApiResponse.success(
        response.data as Map<String, dynamic>,
        statusCode: response.statusCode,
      );
    } on DioException catch (e) {
      return _handleError(e);
    }
  }
  
  /// Upload file
  Future<ApiResponse<Map<String, dynamic>>> uploadFile(
    String path,
    File file, {
    String fieldName = 'file',
    Map<String, dynamic>? extraData,
  }) async {
    try {
      final formData = FormData.fromMap({
        fieldName: await MultipartFile.fromFile(
          file.path,
          filename: file.path.split('/').last,
        ),
        ...?extraData,
      });
      
      final response = await _dio.post(
        path,
        data: formData,
        options: Options(contentType: 'multipart/form-data'),
      );
      
      return ApiResponse.success(
        response.data as Map<String, dynamic>,
        statusCode: response.statusCode,
      );
    } on DioException catch (e) {
      return _handleError(e);
    }
  }
  
  /// Handle Dio errors
  ApiResponse<Map<String, dynamic>> _handleError(DioException e) {
    String message;
    
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        message = 'Délai de connexion dépassé';
        break;
      case DioExceptionType.badResponse:
        final data = e.response?.data;
        if (data is Map<String, dynamic>) {
          message = data['detail'] ?? data['message'] ?? 'Erreur du serveur';
        } else {
          message = 'Erreur du serveur';
        }
        break;
      case DioExceptionType.connectionError:
        message = 'Pas de connexion internet';
        break;
      default:
        message = 'Une erreur est survenue';
    }
    
    return ApiResponse.error(message, statusCode: e.response?.statusCode);
  }
}
