import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../../core/api/api_client.dart';

/// Smart Route data from backend
class SmartRouteData {
  final List<List<double>> coordinates;
  final List<List<double>> waypoints;
  final double distanceKm;
  final double baseEtaMinutes;
  final double smartEtaMinutes;
  final double trafficScore;
  final int congestedSegments;
  final int totalSegments;
  final List<RouteWarning> warnings;
  final List<RouteAlternative> alternatives;
  final NavigationLinks navigation;

  SmartRouteData({
    required this.coordinates,
    required this.waypoints,
    required this.distanceKm,
    required this.baseEtaMinutes,
    required this.smartEtaMinutes,
    required this.trafficScore,
    required this.congestedSegments,
    required this.totalSegments,
    required this.warnings,
    required this.alternatives,
    required this.navigation,
  });

  /// Extra time due to traffic
  double get trafficDelay => smartEtaMinutes - baseEtaMinutes;

  /// Whether traffic significantly affects the route
  bool get hasTrafficImpact => trafficDelay > 2.0;

  /// Human-readable ETA
  String get etaText {
    final min = smartEtaMinutes.round();
    if (min < 60) return '$min min';
    final h = min ~/ 60;
    final m = min % 60;
    return '${h}h${m > 0 ? " ${m}min" : ""}';
  }

  /// Human-readable distance 
  String get distanceText {
    if (distanceKm < 1) return '${(distanceKm * 1000).round()} m';
    return '${distanceKm.toStringAsFixed(1)} km';
  }

  factory SmartRouteData.fromJson(Map<String, dynamic> json) {
    return SmartRouteData(
      coordinates: (json['coordinates'] as List)
          .map((c) => (c as List).map((v) => (v as num).toDouble()).toList())
          .toList(),
      waypoints: (json['waypoints'] as List)
          .map((c) => (c as List).map((v) => (v as num).toDouble()).toList())
          .toList(),
      distanceKm: (json['distance_km'] as num).toDouble(),
      baseEtaMinutes: (json['base_eta_minutes'] as num).toDouble(),
      smartEtaMinutes: (json['smart_eta_minutes'] as num).toDouble(),
      trafficScore: (json['traffic_score'] as num).toDouble(),
      congestedSegments: json['congested_segments'] as int,
      totalSegments: json['total_segments'] as int,
      warnings: (json['warnings'] as List?)
              ?.map((w) => RouteWarning.fromJson(w))
              .toList() ??
          [],
      alternatives: (json['alternatives'] as List?)
              ?.map((a) => RouteAlternative.fromJson(a))
              .toList() ??
          [],
      navigation: NavigationLinks.fromJson(json['navigation'] ?? {}),
    );
  }
}

class RouteWarning {
  final String type;
  final String severity;
  final String message;
  final double latitude;
  final double longitude;
  final double penaltyMinutes;

  RouteWarning({
    required this.type,
    required this.severity,
    required this.message,
    required this.latitude,
    required this.longitude,
    required this.penaltyMinutes,
  });

  factory RouteWarning.fromJson(Map<String, dynamic> json) {
    return RouteWarning(
      type: json['type'] ?? '',
      severity: json['severity'] ?? 'info',
      message: json['message'] ?? '',
      latitude: (json['latitude'] as num?)?.toDouble() ?? 0,
      longitude: (json['longitude'] as num?)?.toDouble() ?? 0,
      penaltyMinutes: (json['penalty_minutes'] as num?)?.toDouble() ?? 0,
    );
  }

  bool get isDanger => severity == 'danger';
  bool get isWarning => severity == 'warning';
}

class RouteAlternative {
  final double distanceKm;
  final double baseEtaMinutes;
  final double smartEtaMinutes;
  final double trafficScore;
  final int congestedSegments;
  final int warningsCount;

  RouteAlternative({
    required this.distanceKm,
    required this.baseEtaMinutes,
    required this.smartEtaMinutes,
    required this.trafficScore,
    required this.congestedSegments,
    required this.warningsCount,
  });

  factory RouteAlternative.fromJson(Map<String, dynamic> json) {
    return RouteAlternative(
      distanceKm: (json['distance_km'] as num?)?.toDouble() ?? 0,
      baseEtaMinutes: (json['base_eta_minutes'] as num?)?.toDouble() ?? 0,
      smartEtaMinutes: (json['smart_eta_minutes'] as num?)?.toDouble() ?? 0,
      trafficScore: (json['traffic_score'] as num?)?.toDouble() ?? 0,
      congestedSegments: json['congested_segments'] ?? 0,
      warningsCount: json['warnings_count'] ?? 0,
    );
  }
}

class NavigationLinks {
  final String googleMaps;
  final String waze;
  final String appleMaps;

  NavigationLinks({
    required this.googleMaps,
    required this.waze,
    required this.appleMaps,
  });

  factory NavigationLinks.fromJson(Map<String, dynamic> json) {
    return NavigationLinks(
      googleMaps: json['google_maps'] ?? '',
      waze: json['waze'] ?? '',
      appleMaps: json['apple_maps'] ?? '',
    );
  }
}

/// State for smart route
class SmartRouteState {
  final SmartRouteData? route;
  final bool isLoading;
  final String? error;

  const SmartRouteState({
    this.route,
    this.isLoading = false,
    this.error,
  });

  SmartRouteState copyWith({
    SmartRouteData? route,
    bool? isLoading,
    String? error,
  }) {
    return SmartRouteState(
      route: route ?? this.route,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

/// Notifier for smart routing
class SmartRouteNotifier extends StateNotifier<SmartRouteState> {
  final Dio _dio;

  SmartRouteNotifier(this._dio) : super(const SmartRouteState());

  /// Calculate smart route from origin to destination
  Future<SmartRouteData?> calculateRoute({
    required double originLat,
    required double originLng,
    required double destLat,
    required double destLng,
  }) async {
    state = state.copyWith(isLoading: true, error: null);

    try {
      final response = await _dio.post(
        '/api/traffic/smart-route/',
        data: {
          'origin': [originLat, originLng],
          'destination': [destLat, destLng],
        },
      );

      if (response.statusCode == 200) {
        final routeData = SmartRouteData.fromJson(response.data);
        state = SmartRouteState(route: routeData, isLoading: false);
        return routeData;
      }
    } on DioException catch (e) {
      final msg = e.response?.data?['error'] ?? 'Erreur réseau';
      state = state.copyWith(isLoading: false, error: msg.toString());
      debugPrint('[SmartRoute] Error: $e');
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
      debugPrint('[SmartRoute] Error: $e');
    }

    return null;
  }

  /// Clear current route
  void clearRoute() {
    state = const SmartRouteState();
  }
}

/// Provider
final smartRouteProvider =
    StateNotifierProvider<SmartRouteNotifier, SmartRouteState>((ref) {
  final dio = ref.watch(dioProvider);
  return SmartRouteNotifier(dio);
});
