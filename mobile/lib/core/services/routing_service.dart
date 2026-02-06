import 'package:url_launcher/url_launcher.dart';

/// Service for route calculation and external navigation
class RoutingService {
  /// Calculate distance between two points using Haversine formula
  static double calculateDistance(
    double lat1, double lng1,
    double lat2, double lng2,
  ) {
    const double earthRadius = 6371; // km
    final dLat = _toRadians(lat2 - lat1);
    final dLng = _toRadians(lng2 - lng1);
    final a = _sin(dLat / 2) * _sin(dLat / 2) +
        _cos(_toRadians(lat1)) * _cos(_toRadians(lat2)) *
        _sin(dLng / 2) * _sin(dLng / 2);
    final c = 2 * _atan2(_sqrt(a), _sqrt(1 - a));
    return earthRadius * c;
  }

  /// Estimate travel time based on distance (average 25 km/h in urban areas)
  static int estimateTravelTime(double distanceKm, {double speedKmh = 25}) {
    return (distanceKm / speedKmh * 60).round();
  }

  /// Get directions using Google Maps
  static Future<bool> openGoogleMaps({
    required double destLat,
    required double destLng,
    String? destName,
    double? originLat,
    double? originLng,
  }) async {
    String url;
    
    if (originLat != null && originLng != null) {
      // With origin
      url = 'https://www.google.com/maps/dir/?api=1'
          '&origin=$originLat,$originLng'
          '&destination=$destLat,$destLng'
          '&travelmode=driving';
    } else {
      // Current location as origin
      url = 'https://www.google.com/maps/dir/?api=1'
          '&destination=$destLat,$destLng'
          '&travelmode=driving';
    }

    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      return await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
    return false;
  }

  /// Get directions using Waze
  static Future<bool> openWaze({
    required double destLat,
    required double destLng,
  }) async {
    final url = 'https://waze.com/ul?ll=$destLat,$destLng&navigate=yes';
    final uri = Uri.parse(url);
    
    if (await canLaunchUrl(uri)) {
      return await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
    return false;
  }

  /// Open native maps app
  static Future<bool> openNativeMaps({
    required double destLat,
    required double destLng,
    String? destName,
  }) async {
    final label = destName ?? 'Destination';
    final url = 'geo:$destLat,$destLng?q=$destLat,$destLng($label)';
    final uri = Uri.parse(url);
    
    if (await canLaunchUrl(uri)) {
      return await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
    // Fallback to Google Maps
    return openGoogleMaps(destLat: destLat, destLng: destLng, destName: destName);
  }

  /// Get route overview with waypoints
  static Future<bool> openMultiStopRoute({
    required List<({double lat, double lng, String? name})> waypoints,
  }) async {
    if (waypoints.isEmpty) return false;
    
    final dest = waypoints.last;
    final intermediates = waypoints.length > 1 
        ? waypoints.sublist(0, waypoints.length - 1)
            .map((w) => '${w.lat},${w.lng}')
            .join('|')
        : null;
    
    var url = 'https://www.google.com/maps/dir/?api=1'
        '&destination=${dest.lat},${dest.lng}'
        '&travelmode=driving';
    
    if (intermediates != null) {
      url += '&waypoints=$intermediates';
    }

    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      return await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
    return false;
  }

  // Math helpers (simple implementations for web compatibility)
  static double _toRadians(double deg) => deg * 3.14159 / 180;
  
  static double _sin(double x) {
    x = x % (2 * 3.14159);
    double result = x;
    double term = x;
    for (int n = 1; n <= 7; n++) {
      term *= -x * x / ((2 * n) * (2 * n + 1));
      result += term;
    }
    return result;
  }
  
  static double _cos(double x) {
    x = x % (2 * 3.14159);
    double result = 1;
    double term = 1;
    for (int n = 1; n <= 7; n++) {
      term *= -x * x / ((2 * n - 1) * (2 * n));
      result += term;
    }
    return result;
  }
  
  static double _sqrt(double x) {
    if (x <= 0) return 0;
    double guess = x / 2;
    for (int i = 0; i < 10; i++) {
      guess = (guess + x / guess) / 2;
    }
    return guess;
  }
  
  static double _atan2(double y, double x) {
    if (x > 0) return _taylorAtan(y / x);
    if (x < 0 && y >= 0) return _taylorAtan(y / x) + 3.14159;
    if (x < 0 && y < 0) return _taylorAtan(y / x) - 3.14159;
    if (x == 0 && y > 0) return 3.14159 / 2;
    if (x == 0 && y < 0) return -3.14159 / 2;
    return 0;
  }
  
  static double _taylorAtan(double x) {
    if (x.abs() > 1) {
      return (x > 0 ? 1 : -1) * 3.14159 / 2 - _taylorAtan(1 / x);
    }
    double result = x;
    double term = x;
    for (int n = 1; n <= 15; n++) {
      term *= -x * x;
      result += term / (2 * n + 1);
    }
    return result;
  }
}

/// Route info model
class RouteInfo {
  final double distanceKm;
  final int estimatedMinutes;
  final List<LatLng> polyline;

  const RouteInfo({
    required this.distanceKm,
    required this.estimatedMinutes,
    this.polyline = const [],
  });

  String get formattedDistance => '${distanceKm.toStringAsFixed(1)} km';
  String get formattedTime {
    if (estimatedMinutes < 60) {
      return '$estimatedMinutes min';
    }
    final hours = estimatedMinutes ~/ 60;
    final mins = estimatedMinutes % 60;
    return '${hours}h${mins > 0 ? ' ${mins}min' : ''}';
  }
}

/// Simple LatLng class
class LatLng {
  final double latitude;
  final double longitude;

  const LatLng(this.latitude, this.longitude);
}
