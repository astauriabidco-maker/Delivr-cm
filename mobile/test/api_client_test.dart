import 'package:flutter_test/flutter_test.dart';
import 'package:delivr_courier/core/api/api_client.dart';

void main() {
  group('ApiResponse', () {
    test('success factory creates successful response', () {
      final response = ApiResponse<Map<String, dynamic>>.success(
        {'key': 'value'},
        statusCode: 200,
      );

      expect(response.success, true);
      expect(response.data, {'key': 'value'});
      expect(response.statusCode, 200);
      expect(response.error, isNull);
    });

    test('error factory creates error response', () {
      final response = ApiResponse<Map<String, dynamic>>.error(
        'Something went wrong',
        statusCode: 400,
      );

      expect(response.success, false);
      expect(response.data, isNull);
      expect(response.statusCode, 400);
      expect(response.error, 'Something went wrong');
    });
  });

  group('ApiException', () {
    test('toString includes message and status code', () {
      const exception = ApiException(
        message: 'Not found',
        statusCode: 404,
      );

      expect(exception.toString(), 'ApiException: Not found (status: 404)');
    });

    test('handles null status code', () {
      const exception = ApiException(
        message: 'Network error',
      );

      expect(exception.toString(), 'ApiException: Network error (status: null)');
    });
  });
}
