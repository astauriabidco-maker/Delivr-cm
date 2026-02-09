import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

/// Traffic level enum matching backend
enum TrafficLevel {
  fluide,
  modere,
  dense,
  bloque,
  unknown;

  static TrafficLevel fromString(String? value) {
    switch (value?.toUpperCase()) {
      case 'FLUIDE':
        return TrafficLevel.fluide;
      case 'MODERE':
        return TrafficLevel.modere;
      case 'DENSE':
        return TrafficLevel.dense;
      case 'BLOQUE':
        return TrafficLevel.bloque;
      default:
        return TrafficLevel.unknown;
    }
  }

  String get label {
    switch (this) {
      case TrafficLevel.fluide:
        return 'Fluide';
      case TrafficLevel.modere:
        return 'Modéré';
      case TrafficLevel.dense:
        return 'Dense';
      case TrafficLevel.bloque:
        return 'Bloqué';
      case TrafficLevel.unknown:
        return 'Inconnu';
    }
  }

  String get emoji {
    switch (this) {
      case TrafficLevel.fluide:
        return '🟢';
      case TrafficLevel.modere:
        return '🟡';
      case TrafficLevel.dense:
        return '🔴';
      case TrafficLevel.bloque:
        return '⛔';
      case TrafficLevel.unknown:
        return '⚪';
    }
  }

  int get colorValue {
    switch (this) {
      case TrafficLevel.fluide:
        return 0xFF4CAF50;
      case TrafficLevel.modere:
        return 0xFFFF9800;
      case TrafficLevel.dense:
        return 0xFFF44336;
      case TrafficLevel.bloque:
        return 0xFF880E4F;
      case TrafficLevel.unknown:
        return 0xFF9E9E9E;
    }
  }

  double get opacity {
    switch (this) {
      case TrafficLevel.fluide:
        return 0.3;
      case TrafficLevel.modere:
        return 0.45;
      case TrafficLevel.dense:
        return 0.6;
      case TrafficLevel.bloque:
        return 0.75;
      case TrafficLevel.unknown:
        return 0.15;
    }
  }
}

/// A single traffic cell from the heatmap
class TrafficCell {
  final String cellId;
  final double lat;
  final double lng;
  final double avgSpeed;
  final TrafficLevel level;
  final String color;
  final int samples;
  final String? updated;

  TrafficCell({
    required this.cellId,
    required this.lat,
    required this.lng,
    required this.avgSpeed,
    required this.level,
    required this.color,
    required this.samples,
    this.updated,
  });

  factory TrafficCell.fromJson(Map<String, dynamic> json) {
    return TrafficCell(
      cellId: json['cell_id'] ?? '',
      lat: (json['lat'] as num?)?.toDouble() ?? 0.0,
      lng: (json['lng'] as num?)?.toDouble() ?? 0.0,
      avgSpeed: (json['avg_speed'] as num?)?.toDouble() ?? 0.0,
      level: TrafficLevel.fromString(json['level']),
      color: json['color'] ?? '#9E9E9E',
      samples: json['samples'] ?? 0,
      updated: json['updated'],
    );
  }
}

/// City-wide traffic statistics
class TrafficStats {
  final int activeCells;
  final int onlineCouriers;
  final double avgCitySpeed;
  final TrafficLevel overallLevel;
  final Map<String, int> cellsByLevel;

  TrafficStats({
    required this.activeCells,
    required this.onlineCouriers,
    required this.avgCitySpeed,
    required this.overallLevel,
    required this.cellsByLevel,
  });

  factory TrafficStats.fromJson(Map<String, dynamic> json) {
    final levelMap = <String, int>{};
    final cellsData = json['cells_by_level'];
    if (cellsData is Map) {
      cellsData.forEach((key, value) {
        levelMap[key.toString()] = (value as num?)?.toInt() ?? 0;
      });
    }

    return TrafficStats(
      activeCells: json['active_cells'] ?? 0,
      onlineCouriers: json['online_couriers'] ?? 0,
      avgCitySpeed: (json['avg_city_speed_kmh'] as num?)?.toDouble() ?? 0.0,
      overallLevel: TrafficLevel.fromString(json['overall_level']),
      cellsByLevel: levelMap,
    );
  }
}

/// Traffic heatmap state
class TrafficHeatmapState {
  final List<TrafficCell> cells;
  final TrafficStats? stats;
  final bool isLoading;
  final String? error;
  final DateTime? lastFetched;

  const TrafficHeatmapState({
    this.cells = const [],
    this.stats,
    this.isLoading = false,
    this.error,
    this.lastFetched,
  });

  TrafficHeatmapState copyWith({
    List<TrafficCell>? cells,
    TrafficStats? stats,
    bool? isLoading,
    String? error,
    DateTime? lastFetched,
  }) {
    return TrafficHeatmapState(
      cells: cells ?? this.cells,
      stats: stats ?? this.stats,
      isLoading: isLoading ?? this.isLoading,
      error: error,
      lastFetched: lastFetched ?? this.lastFetched,
    );
  }
}

/// Traffic heatmap provider
final trafficHeatmapProvider =
    StateNotifierProvider<TrafficHeatmapNotifier, TrafficHeatmapState>((ref) {
  return TrafficHeatmapNotifier(ref);
});

class TrafficHeatmapNotifier extends StateNotifier<TrafficHeatmapState> {
  final Ref _ref;
  Timer? _refreshTimer;

  TrafficHeatmapNotifier(this._ref) : super(const TrafficHeatmapState());

  Dio get _dio => _ref.read(dioProvider);

  /// Start auto-refresh (every 2 minutes)
  void startAutoRefresh() {
    _refreshTimer?.cancel();
    fetchHeatmap(); // Immediate fetch
    _refreshTimer = Timer.periodic(
      const Duration(minutes: 2),
      (_) => fetchHeatmap(),
    );
  }

  /// Stop auto-refresh
  void stopAutoRefresh() {
    _refreshTimer?.cancel();
    _refreshTimer = null;
  }

  /// Fetch traffic heatmap from API
  Future<void> fetchHeatmap({
    double? minLat,
    double? maxLat,
    double? minLng,
    double? maxLng,
  }) async {
    state = state.copyWith(isLoading: true);

    try {
      final queryParams = <String, dynamic>{};
      if (minLat != null) queryParams['min_lat'] = minLat;
      if (maxLat != null) queryParams['max_lat'] = maxLat;
      if (minLng != null) queryParams['min_lng'] = minLng;
      if (maxLng != null) queryParams['max_lng'] = maxLng;

      final response = await _dio.get(
        '/api/traffic/heatmap/',
        queryParameters: queryParams.isNotEmpty ? queryParams : null,
      );

      if (response.statusCode == 200) {
        final data = response.data;
        final cellsList = (data['cells'] as List?)
                ?.map((c) => TrafficCell.fromJson(c))
                .toList() ??
            [];

        state = state.copyWith(
          cells: cellsList,
          isLoading: false,
          lastFetched: DateTime.now(),
        );
      }
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: e.response?.data?['error'] ?? 'Erreur réseau',
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Erreur: $e',
      );
    }
  }

  /// Fetch traffic statistics
  Future<void> fetchStats() async {
    try {
      final response = await _dio.get('/api/traffic/stats/');

      if (response.statusCode == 200) {
        final stats = TrafficStats.fromJson(response.data);
        state = state.copyWith(stats: stats);
      }
    } catch (e) {
      // Stats are non-critical, just log
    }
  }

  /// Get traffic data along a route
  Future<List<TrafficCell>> getRouteTraffic(
      List<List<double>> waypoints) async {
    try {
      final response = await _dio.post(
        '/api/traffic/route/',
        data: {'waypoints': waypoints},
      );

      if (response.statusCode == 200) {
        return (response.data['segments'] as List?)
                ?.map((s) => TrafficCell.fromJson(s))
                .toList() ??
            [];
      }
    } catch (e) {
      // Route traffic is non-critical
    }
    return [];
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }
}
