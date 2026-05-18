import 'dart:async';
import 'dart:math';
import 'package:flutter/foundation.dart';

import 'package:dio/dio.dart';

import '../providers/events_provider.dart';

/// Détecteur intelligent de ralentissements basé sur le GPS.
///
/// Analyse la vitesse du coursier en temps réel et :
/// 1. Détecte automatiquement les ralentissements
/// 2. Calcule la sévérité à partir de la vitesse
/// 3. Déclenche des notifications proactives ("Que se passe-t-il ?")
/// 4. Crée des événements "embouteillage" automatiques si aucun signalement
class SpeedAnomalyDetector {
  // === Configuration ===
  
  /// Seuils de vitesse (km/h) pour détecter un ralentissement
  static const double _speedThresholdSlow = 8.0;      // En dessous → ralentissement
  static const double _speedThresholdStopped = 3.0;    // En dessous → arrêté
  // ignore: unused_field
  static const double _normalSpeedMin = 20.0;          // Au dessus → circulation normale
  
  /// Durée minimum du ralentissement avant alerte (secondes)
  static const int _minSlowDurationSec = 30;
  
  /// Intervalle minimum entre deux alertes (secondes)
  static const int _alertCooldownSec = 300; // 5 min
  
  /// Nombre minimum de points GPS pour confirmer un ralentissement
  static const int _minDataPoints = 3;
  
  /// Distance minimum entre deux auto-reports (mètres)
  static const double _minDistBetweenReports = 200;
  
  // === State ===
  final List<_SpeedPoint> _recentSpeeds = [];
  DateTime? _slowdownStart;
  DateTime? _lastAlertTime;
  double? _lastReportLat;
  double? _lastReportLng;
  bool _isInSlowdown = false;
  
  // Callbacks
  Function(SlowdownAlert alert)? onSlowdownDetected;
  Function(AutoTrafficEvent event)? onAutoEventCreated;
  
  /// Ajouter un point GPS et analyser
  SlowdownAnalysis? addGPSPoint({
    required double latitude,
    required double longitude,
    required double speedKmh,
    required DateTime timestamp,
  }) {
    final point = _SpeedPoint(
      lat: latitude,
      lng: longitude,
      speed: speedKmh,
      time: timestamp,
    );
    
    _recentSpeeds.add(point);
    
    // Garder seulement les 2 dernières minutes
    _recentSpeeds.removeWhere(
      (p) => timestamp.difference(p.time).inSeconds > 120,
    );
    
    return _analyze(point);
  }
  
  /// Analyser la situation actuelle
  SlowdownAnalysis? _analyze(_SpeedPoint current) {
    if (_recentSpeeds.length < _minDataPoints) return null;
    
    final now = current.time;
    final avgSpeed = _recentAvgSpeed();
    final isSlow = avgSpeed < _speedThresholdSlow;
    final isStopped = avgSpeed < _speedThresholdStopped;
    
    if (isSlow && !_isInSlowdown) {
      // Début de ralentissement
      _slowdownStart = now;
      _isInSlowdown = true;
    } else if (!isSlow && _isInSlowdown) {
      // Fin de ralentissement
      _isInSlowdown = false;
      _slowdownStart = null;
    }
    
    if (!_isInSlowdown) return null;
    
    // Vérifier durée minimum
    final slowDuration = now.difference(_slowdownStart!).inSeconds;
    if (slowDuration < _minSlowDurationSec) return null;
    
    // Vérifier cooldown
    if (_lastAlertTime != null &&
        now.difference(_lastAlertTime!).inSeconds < _alertCooldownSec) {
      return null;
    }
    
    // Vérifier distance minimum par rapport au dernier report
    if (_lastReportLat != null && _lastReportLng != null) {
      final dist = _distanceMeters(
        current.lat, current.lng,
        _lastReportLat!, _lastReportLng!,
      );
      if (dist < _minDistBetweenReports) return null;
    }
    
    // === Ralentissement confirmé ! ===
    final severity = _computeSeverity(avgSpeed);
    final speedDrop = _computeSpeedDrop();
    
    _lastAlertTime = now;
    _lastReportLat = current.lat;
    _lastReportLng = current.lng;
    
    final analysis = SlowdownAnalysis(
      latitude: current.lat,
      longitude: current.lng,
      currentSpeed: avgSpeed,
      previousSpeed: speedDrop.previousSpeed,
      speedDropPercent: speedDrop.dropPercent,
      severity: severity,
      durationSeconds: slowDuration,
      isStopped: isStopped,
    );
    
    // Notifier
    if (onSlowdownDetected != null) {
      onSlowdownDetected!(SlowdownAlert(
        analysis: analysis,
        suggestedType: isStopped 
            ? TrafficEventType.trafficJam 
            : TrafficEventType.trafficJam,
        message: isStopped
            ? '🛑 Vous êtes à l\'arrêt depuis ${slowDuration}s'
            : '🚦 Ralentissement détecté (${avgSpeed.toStringAsFixed(0)} km/h)',
      ));
    }
    
    return analysis;
  }
  
  /// Vitesse moyenne récente (dernières 30 secondes)
  double _recentAvgSpeed() {
    final now = _recentSpeeds.last.time;
    final recent = _recentSpeeds.where(
      (p) => now.difference(p.time).inSeconds <= 30,
    );
    if (recent.isEmpty) return 0;
    return recent.map((p) => p.speed).reduce((a, b) => a + b) / recent.length;
  }
  
  /// Calculer la chute de vitesse
  _SpeedDrop _computeSpeedDrop() {
    if (_recentSpeeds.length < 4) {
      return _SpeedDrop(previousSpeed: 0, dropPercent: 0);
    }
    
    // Vitesse moyenne des premiers points vs derniers points
    final half = _recentSpeeds.length ~/ 2;
    final firstHalf = _recentSpeeds.sublist(0, half);
    final secondHalf = _recentSpeeds.sublist(half);
    
    final avgFirst = firstHalf.map((p) => p.speed).reduce((a, b) => a + b) / firstHalf.length;
    final avgSecond = secondHalf.map((p) => p.speed).reduce((a, b) => a + b) / secondHalf.length;
    
    final drop = avgFirst > 0 ? ((avgFirst - avgSecond) / avgFirst * 100) : 0;
    
    return _SpeedDrop(
      previousSpeed: avgFirst,
      dropPercent: drop.clamp(0, 100).toDouble(),
    );
  }
  
  /// Calculer la sévérité automatiquement depuis la vitesse
  static EventSeverity _computeSeverity(double speedKmh) {
    if (speedKmh < 3) return EventSeverity.critical;
    if (speedKmh < 8) return EventSeverity.high;
    if (speedKmh < 15) return EventSeverity.medium;
    return EventSeverity.low;
  }
  
  /// Sévérité exportable pour l'API
  static String computeSeverityValue(double speedKmh) {
    return _computeSeverity(speedKmh).value;
  }
  
  /// Distance en mètres entre deux points GPS (formule Haversine)
  static double _distanceMeters(
    double lat1, double lng1,
    double lat2, double lng2,
  ) {
    const R = 6371000.0; // Rayon de la Terre en mètres
    final dLat = _toRad(lat2 - lat1);
    final dLng = _toRad(lng2 - lng1);
    final a = sin(dLat / 2) * sin(dLat / 2) +
        cos(_toRad(lat1)) * cos(_toRad(lat2)) *
        sin(dLng / 2) * sin(dLng / 2);
    final c = 2 * atan2(sqrt(a), sqrt(1 - a));
    return R * c;
  }
  
  static double _toRad(double deg) => deg * pi / 180;
  
  /// Reset
  void reset() {
    _recentSpeeds.clear();
    _slowdownStart = null;
    _lastAlertTime = null;
    _isInSlowdown = false;
  }
}

// === Data classes ===

class _SpeedPoint {
  final double lat;
  final double lng;
  final double speed;
  final DateTime time;
  
  _SpeedPoint({
    required this.lat,
    required this.lng,
    required this.speed,
    required this.time,
  });
}

class _SpeedDrop {
  final double previousSpeed;
  final double dropPercent;
  _SpeedDrop({required this.previousSpeed, required this.dropPercent});
}

/// Résultat d'analyse de ralentissement
class SlowdownAnalysis {
  final double latitude;
  final double longitude;
  final double currentSpeed;
  final double previousSpeed;
  final double speedDropPercent;
  final EventSeverity severity;
  final int durationSeconds;
  final bool isStopped;
  
  const SlowdownAnalysis({
    required this.latitude,
    required this.longitude,
    required this.currentSpeed,
    required this.previousSpeed,
    required this.speedDropPercent,
    required this.severity,
    required this.durationSeconds,
    required this.isStopped,
  });
}

/// Alerte de ralentissement (pour l'UI)
class SlowdownAlert {
  final SlowdownAnalysis analysis;
  final TrafficEventType suggestedType;
  final String message;
  
  const SlowdownAlert({
    required this.analysis,
    required this.suggestedType,
    required this.message,
  });
}

/// Événement créé automatiquement
class AutoTrafficEvent {
  final double latitude;
  final double longitude;
  final String severity;
  final double speed;
  
  const AutoTrafficEvent({
    required this.latitude,
    required this.longitude,
    required this.severity,
    required this.speed,
  });
}

/// Reverse geocoding via Nominatim (OSM, gratuit)
class ReverseGeocoder {
  static final Dio _dio = Dio();
  static String? _lastAddress;
  static double? _lastLat;
  static double? _lastLng;
  
  /// Obtenir l'adresse approximative à partir de coordonnées GPS
  static Future<String> getAddress(double lat, double lng) async {
    // Cache simple : si même zone (~50m), retourner le cache
    if (_lastLat != null && _lastLng != null) {
      final dist = SpeedAnomalyDetector._distanceMeters(
        lat, lng, _lastLat!, _lastLng!,
      );
      if (dist < 50 && _lastAddress != null) return _lastAddress!;
    }
    
    try {
      final response = await _dio.get(
        'https://nominatim.openstreetmap.org/reverse',
        queryParameters: {
          'lat': lat,
          'lon': lng,
          'format': 'json',
          'zoom': 16,
          'addressdetails': 1,
        },
        options: Options(
          headers: {'User-Agent': 'RELAY237/1.0'},
          receiveTimeout: const Duration(seconds: 5),
        ),
      );
      
      if (response.statusCode == 200) {
        final data = response.data;
        final address = data['address'] ?? {};
        
        // Construire une adresse courte type "Ndokotti, Douala"
        final parts = <String>[];
        final road = address['road'] ?? address['pedestrian'] ?? '';
        final suburb = address['suburb'] ?? address['neighbourhood'] ?? '';
        final city = address['city'] ?? address['town'] ?? '';
        
        if (road.isNotEmpty) parts.add(road);
        if (suburb.isNotEmpty) parts.add(suburb);
        if (parts.isEmpty && city.isNotEmpty) parts.add(city);
        
        final result = parts.join(', ');
        _lastAddress = result;
        _lastLat = lat;
        _lastLng = lng;
        return result;
      }
    } catch (e) {
      debugPrint('[ReverseGeocoder] Error: $e');
    }
    
    return '${lat.toStringAsFixed(4)}, ${lng.toStringAsFixed(4)}';
  }
}
