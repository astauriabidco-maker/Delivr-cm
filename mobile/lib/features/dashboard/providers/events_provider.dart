import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

/// Types d'événements trafic
enum TrafficEventType {
  accident('ACCIDENT', '🚗', 'Accident', 0xFFF44336),
  police('POLICE', '👮', 'Contrôle police', 0xFF2196F3),
  roadClosed('ROAD_CLOSED', '🚧', 'Route barrée', 0xFFFF5722),
  flooding('FLOODING', '🌊', 'Inondation', 0xFF00BCD4),
  pothole('POTHOLE', '🕳️', 'Nid-de-poule', 0xFF795548),
  trafficJam('TRAFFIC_JAM', '🚦', 'Embouteillage', 0xFFFF9800),
  roadwork('ROADWORK', '🏗️', 'Travaux', 0xFF607D8B),
  hazard('HAZARD', '⚠️', 'Danger', 0xFFE91E63),
  fuelStation('FUEL_STATION', '⛽', 'Station essence', 0xFF4CAF50),
  other('OTHER', '📍', 'Autre', 0xFF9E9E9E);

  final String value;
  final String emoji;
  final String label;
  final int colorValue;

  const TrafficEventType(this.value, this.emoji, this.label, this.colorValue);

  static TrafficEventType fromString(String? value) {
    return TrafficEventType.values.firstWhere(
      (e) => e.value == value,
      orElse: () => TrafficEventType.other,
    );
  }
}

/// Sévérité
enum EventSeverity {
  low('LOW', 'Faible'),
  medium('MEDIUM', 'Moyen'),
  high('HIGH', 'Élevé'),
  critical('CRITICAL', 'Critique');

  final String value;
  final String label;

  const EventSeverity(this.value, this.label);
}

/// Un événement trafic
class TrafficEventData {
  final String id;
  final TrafficEventType eventType;
  final String severity;
  final double latitude;
  final double longitude;
  final String address;
  final String description;
  final String? photoUrl;
  final int upvotes;
  final int downvotes;
  final int confidenceScore;
  final String reporterName;
  final bool isOwn;
  final String? userVote;
  final String timeAgo;
  final String timeRemaining;
  final String? createdAt;
  final String? expiresAt;

  TrafficEventData({
    required this.id,
    required this.eventType,
    required this.severity,
    required this.latitude,
    required this.longitude,
    this.address = '',
    this.description = '',
    this.photoUrl,
    this.upvotes = 0,
    this.downvotes = 0,
    this.confidenceScore = 50,
    this.reporterName = '',
    this.isOwn = false,
    this.userVote,
    this.timeAgo = '',
    this.timeRemaining = '',
    this.createdAt,
    this.expiresAt,
  });

  factory TrafficEventData.fromJson(Map<String, dynamic> json) {
    return TrafficEventData(
      id: json['id'] ?? '',
      eventType: TrafficEventType.fromString(json['event_type']),
      severity: json['severity'] ?? 'MEDIUM',
      latitude: (json['latitude'] as num?)?.toDouble() ?? 0.0,
      longitude: (json['longitude'] as num?)?.toDouble() ?? 0.0,
      address: json['address'] ?? '',
      description: json['description'] ?? '',
      photoUrl: json['photo_url'],
      upvotes: json['upvotes'] ?? 0,
      downvotes: json['downvotes'] ?? 0,
      confidenceScore: json['confidence_score'] ?? 50,
      reporterName: json['reporter_name'] ?? '',
      isOwn: json['is_own'] ?? false,
      userVote: json['user_vote'],
      timeAgo: json['time_ago'] ?? '',
      timeRemaining: json['time_remaining'] ?? '',
      createdAt: json['created_at'],
      expiresAt: json['expires_at'],
    );
  }
}

/// State
class TrafficEventsState {
  final List<TrafficEventData> events;
  final bool isLoading;
  final String? error;

  const TrafficEventsState({
    this.events = const [],
    this.isLoading = false,
    this.error,
  });

  TrafficEventsState copyWith({
    List<TrafficEventData>? events,
    bool? isLoading,
    String? error,
  }) {
    return TrafficEventsState(
      events: events ?? this.events,
      isLoading: isLoading ?? this.isLoading,
      error: error,
    );
  }
}

/// Provider
final trafficEventsProvider =
    StateNotifierProvider<TrafficEventsNotifier, TrafficEventsState>((ref) {
  return TrafficEventsNotifier(ref);
});

class TrafficEventsNotifier extends StateNotifier<TrafficEventsState> {
  final Ref _ref;
  Timer? _refreshTimer;

  TrafficEventsNotifier(this._ref) : super(const TrafficEventsState());

  Dio get _dio => _ref.read(dioProvider);

  /// Start auto-refresh (every 3 minutes)
  void startAutoRefresh() {
    _refreshTimer?.cancel();
    fetchEvents();
    _refreshTimer = Timer.periodic(
      const Duration(minutes: 3),
      (_) => fetchEvents(),
    );
  }

  void stopAutoRefresh() {
    _refreshTimer?.cancel();
    _refreshTimer = null;
  }

  /// Fetch events near a location
  Future<void> fetchEvents({double? lat, double? lng, double? radius}) async {
    state = state.copyWith(isLoading: true);

    try {
      final queryParams = <String, dynamic>{};
      if (lat != null) queryParams['lat'] = lat;
      if (lng != null) queryParams['lng'] = lng;
      if (radius != null) queryParams['radius'] = radius;

      final response = await _dio.get(
        '/api/traffic/events/',
        queryParameters: queryParams.isNotEmpty ? queryParams : null,
      );

      if (response.statusCode == 200) {
        final data = response.data;
        final eventsList = (data['events'] as List?)
                ?.map((e) => TrafficEventData.fromJson(e))
                .toList() ??
            [];

        state = state.copyWith(
          events: eventsList,
          isLoading: false,
        );
      }
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Erreur chargement événements',
      );
    }
  }

  /// Report a new traffic event
  Future<TrafficEventData?> reportEvent({
    required TrafficEventType type,
    required double latitude,
    required double longitude,
    String severity = 'MEDIUM',
    String address = '',
    String description = '',
  }) async {
    try {
      final response = await _dio.post(
        '/api/traffic/events/',
        data: {
          'event_type': type.value,
          'latitude': latitude,
          'longitude': longitude,
          'severity': severity,
          'address': address,
          'description': description,
        },
      );

      if (response.statusCode == 201) {
        final event = TrafficEventData.fromJson(response.data);
        // Add to local state
        state = state.copyWith(
          events: [event, ...state.events],
        );
        return event;
      }
    } catch (e) {
      // Error handled by caller
    }
    return null;
  }

  /// Vote on an event
  Future<bool> voteEvent(String eventId, bool isUpvote) async {
    try {
      final response = await _dio.post(
        '/api/traffic/events/$eventId/vote/',
        data: {'vote': isUpvote ? 'up' : 'down'},
      );

      if (response.statusCode == 200) {
        // Update local state
        final updatedEvents = state.events.map((e) {
          if (e.id == eventId) {
            return TrafficEventData(
              id: e.id,
              eventType: e.eventType,
              severity: e.severity,
              latitude: e.latitude,
              longitude: e.longitude,
              address: e.address,
              description: e.description,
              photoUrl: e.photoUrl,
              upvotes: response.data['upvotes'] ?? e.upvotes,
              downvotes: response.data['downvotes'] ?? e.downvotes,
              confidenceScore:
                  response.data['confidence_score'] ?? e.confidenceScore,
              reporterName: e.reporterName,
              isOwn: e.isOwn,
              userVote: isUpvote ? 'up' : 'down',
              timeAgo: e.timeAgo,
              timeRemaining: e.timeRemaining,
            );
          }
          return e;
        }).toList();

        state = state.copyWith(events: updatedEvents);
        return true;
      }
    } catch (e) {
      // Error handled by caller
    }
    return false;
  }

  /// Delete own event
  Future<bool> deleteEvent(String eventId) async {
    try {
      final response = await _dio.delete('/api/traffic/events/$eventId/');
      if (response.statusCode == 200) {
        state = state.copyWith(
          events: state.events.where((e) => e.id != eventId).toList(),
        );
        return true;
      }
    } catch (e) {
      // Error handled by caller
    }
    return false;
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }
}
