import 'dart:async';
import 'dart:developer' as dev;

import 'package:battery_plus/battery_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../websocket/websocket_service.dart';

/// GPS tracking modes
enum LocationTrackingMode {
  /// High accuracy, frequent updates (10s interval)
  active,
  
  /// Balanced accuracy, moderate updates (30s interval)  
  idle,
  
  /// Low power, infrequent updates (60s interval)
  batterySaving,
  
  /// Tracking paused
  stopped,
}

/// Location state
class LocationState {
  final Position? currentPosition;
  final LocationTrackingMode mode;
  final bool isTracking;
  final int batteryLevel;
  final DateTime? lastUpdate;
  final String? error;

  const LocationState({
    this.currentPosition,
    this.mode = LocationTrackingMode.stopped,
    this.isTracking = false,
    this.batteryLevel = 100,
    this.lastUpdate,
    this.error,
  });

  LocationState copyWith({
    Position? currentPosition,
    LocationTrackingMode? mode,
    bool? isTracking,
    int? batteryLevel,
    DateTime? lastUpdate,
    String? error,
  }) {
    return LocationState(
      currentPosition: currentPosition ?? this.currentPosition,
      mode: mode ?? this.mode,
      isTracking: isTracking ?? this.isTracking,
      batteryLevel: batteryLevel ?? this.batteryLevel,
      lastUpdate: lastUpdate ?? this.lastUpdate,
      error: error,
    );
  }
}

/// Location state provider
final locationStateProvider = StateNotifierProvider<LocationStateNotifier, LocationState>((ref) {
  return LocationStateNotifier(ref);
});

class LocationStateNotifier extends StateNotifier<LocationState> {
  final Ref _ref;
  StreamSubscription<Position>? _positionSubscription;
  StreamSubscription<BatteryState>? _batterySubscription;
  Timer? _updateTimer;
  
  final Battery _battery = Battery();
  bool _hasActiveDelivery = false;

  LocationStateNotifier(this._ref) : super(const LocationState()) {
    _initBatteryMonitor();
  }

  /// Initialize battery monitoring
  void _initBatteryMonitor() async {
    // Get initial battery level
    final level = await _battery.batteryLevel;
    state = state.copyWith(batteryLevel: level);
    
    // Listen to battery state changes
    _batterySubscription = _battery.onBatteryStateChanged.listen((batteryState) async {
      final level = await _battery.batteryLevel;
      state = state.copyWith(batteryLevel: level);
      
      // Auto-switch to battery saving mode if below 20%
      if (state.isTracking && level < 20 && state.mode != LocationTrackingMode.batterySaving) {
        dev.log('[GPS] Battery low ($level%), switching to battery saving mode', name: 'Location');
        await _switchMode(LocationTrackingMode.batterySaving);
      }
      
      // Return to appropriate mode if battery recovers above 30%
      if (state.isTracking && level > 30 && state.mode == LocationTrackingMode.batterySaving) {
        final newMode = _hasActiveDelivery 
            ? LocationTrackingMode.active 
            : LocationTrackingMode.idle;
        dev.log('[GPS] Battery recovered ($level%), switching to $newMode', name: 'Location');
        await _switchMode(newMode);
      }
    });
  }

  /// Start GPS tracking
  Future<bool> startTracking({bool hasActiveDelivery = false}) async {
    _hasActiveDelivery = hasActiveDelivery;
    
    // Check and request permissions
    final hasPermission = await _checkAndRequestPermission();
    if (!hasPermission) {
      state = state.copyWith(
        error: 'Permission de localisation refusée',
        isTracking: false,
      );
      return false;
    }
    
    // Determine initial mode based on battery and delivery status
    LocationTrackingMode initialMode;
    if (state.batteryLevel < 20) {
      initialMode = LocationTrackingMode.batterySaving;
    } else if (hasActiveDelivery) {
      initialMode = LocationTrackingMode.active;
    } else {
      initialMode = LocationTrackingMode.idle;
    }
    
    state = state.copyWith(
      isTracking: true,
      mode: initialMode,
      error: null,
    );
    
    // Start position stream
    await _startPositionStream(initialMode);
    
    dev.log('[GPS] Tracking started in $initialMode mode', name: 'Location');
    return true;
  }

  /// Stop GPS tracking
  void stopTracking() {
    _positionSubscription?.cancel();
    _positionSubscription = null;
    _updateTimer?.cancel();
    _updateTimer = null;
    
    state = state.copyWith(
      isTracking: false,
      mode: LocationTrackingMode.stopped,
    );
    
    dev.log('[GPS] Tracking stopped', name: 'Location');
  }

  /// Set active delivery status (affects tracking frequency)
  Future<void> setActiveDelivery(bool hasActiveDelivery) async {
    _hasActiveDelivery = hasActiveDelivery;
    
    if (!state.isTracking) return;
    
    // Don't change mode if in battery saving
    if (state.mode == LocationTrackingMode.batterySaving) return;
    
    final newMode = hasActiveDelivery 
        ? LocationTrackingMode.active 
        : LocationTrackingMode.idle;
    
    if (state.mode != newMode) {
      await _switchMode(newMode);
    }
  }

  /// Switch tracking mode
  Future<void> _switchMode(LocationTrackingMode mode) async {
    if (state.mode == mode) return;
    
    // Cancel current stream
    _positionSubscription?.cancel();
    _updateTimer?.cancel();
    
    state = state.copyWith(mode: mode);
    
    // Start new stream with updated settings
    await _startPositionStream(mode);
    
    dev.log('[GPS] Switched to $mode mode', name: 'Location');
  }

  /// Start position stream with mode-specific settings
  Future<void> _startPositionStream(LocationTrackingMode mode) async {
    final settings = _getLocationSettings(mode);
    
    try {
      // Get initial position
      final position = await Geolocator.getCurrentPosition(
        locationSettings: settings,
      );
      _handlePositionUpdate(position);
      
      // Start listening to position updates
      _positionSubscription = Geolocator.getPositionStream(
        locationSettings: settings,
      ).listen(
        _handlePositionUpdate,
        onError: _handlePositionError,
      );
      
      // Setup periodic timer for backend updates (throttling)
      final interval = _getUpdateInterval(mode);
      _updateTimer = Timer.periodic(interval, (_) {
        _sendLocationToBackend();
      });
      
    } catch (e) {
      dev.log('[GPS] Failed to start position stream: $e', name: 'Location', error: e);
      state = state.copyWith(error: 'Erreur GPS: $e');
    }
  }

  /// Get location settings based on mode
  LocationSettings _getLocationSettings(LocationTrackingMode mode) {
    switch (mode) {
      case LocationTrackingMode.active:
        // High accuracy for active deliveries
        return AndroidSettings(
          accuracy: LocationAccuracy.high,
          distanceFilter: 10, // Update every 10 meters
          intervalDuration: const Duration(seconds: 5),
          foregroundNotificationConfig: const ForegroundNotificationConfig(
            notificationTitle: 'DELIVR-CM',
            notificationText: 'Suivi GPS actif pour votre course',
            enableWakeLock: true,
          ),
        );
        
      case LocationTrackingMode.idle:
        // Balanced for idle couriers
        return AndroidSettings(
          accuracy: LocationAccuracy.medium,
          distanceFilter: 50, // Update every 50 meters
          intervalDuration: const Duration(seconds: 15),
          foregroundNotificationConfig: const ForegroundNotificationConfig(
            notificationTitle: 'DELIVR-CM',
            notificationText: 'En attente de courses',
            enableWakeLock: false,
          ),
        );
        
      case LocationTrackingMode.batterySaving:
        // Low power mode
        return AndroidSettings(
          accuracy: LocationAccuracy.low,
          distanceFilter: 100, // Update every 100 meters
          intervalDuration: const Duration(seconds: 30),
          foregroundNotificationConfig: const ForegroundNotificationConfig(
            notificationTitle: 'DELIVR-CM',
            notificationText: 'Mode économie batterie',
            enableWakeLock: false,
          ),
        );
        
      case LocationTrackingMode.stopped:
        // Shouldn't happen, but return default
        return const LocationSettings(
          accuracy: LocationAccuracy.lowest,
          distanceFilter: 1000,
        );
    }
  }

  /// Get backend update interval based on mode
  Duration _getUpdateInterval(LocationTrackingMode mode) {
    switch (mode) {
      case LocationTrackingMode.active:
        return const Duration(seconds: 10);
      case LocationTrackingMode.idle:
        return const Duration(seconds: 30);
      case LocationTrackingMode.batterySaving:
        return const Duration(seconds: 60);
      case LocationTrackingMode.stopped:
        return const Duration(seconds: 60);
    }
  }

  /// Handle position update from GPS
  void _handlePositionUpdate(Position position) {
    state = state.copyWith(
      currentPosition: position,
      lastUpdate: DateTime.now(),
      error: null,
    );
    
    dev.log(
      '[GPS] Position: ${position.latitude.toStringAsFixed(5)}, '
      '${position.longitude.toStringAsFixed(5)} '
      '(accuracy: ${position.accuracy.toStringAsFixed(0)}m)',
      name: 'Location',
    );
  }

  /// Handle position error
  void _handlePositionError(dynamic error) {
    dev.log('[GPS] Position error: $error', name: 'Location', error: error);
    state = state.copyWith(error: 'Erreur de localisation');
  }

  /// Send current location to backend via WebSocket
  void _sendLocationToBackend() {
    final position = state.currentPosition;
    if (position == null) return;
    
    try {
      final wsService = _ref.read(wsServiceProvider);
      wsService.sendLocationUpdate(position.latitude, position.longitude);
    } catch (e) {
      dev.log('[GPS] Failed to send location: $e', name: 'Location', error: e);
    }
  }

  /// Check and request location permission
  Future<bool> _checkAndRequestPermission() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      dev.log('[GPS] Location services disabled', name: 'Location');
      return false;
    }
    
    LocationPermission permission = await Geolocator.checkPermission();
    
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        dev.log('[GPS] Permission denied', name: 'Location');
        return false;
      }
    }
    
    if (permission == LocationPermission.deniedForever) {
      dev.log('[GPS] Permission denied forever', name: 'Location');
      return false;
    }
    
    // For background tracking, we need "always" permission
    if (permission == LocationPermission.whileInUse) {
      // Request background permission
      permission = await Geolocator.requestPermission();
    }
    
    return permission == LocationPermission.always || 
           permission == LocationPermission.whileInUse;
  }

  /// Get distance to a point
  double distanceTo(double latitude, double longitude) {
    final position = state.currentPosition;
    if (position == null) return double.infinity;
    
    return Geolocator.distanceBetween(
      position.latitude,
      position.longitude,
      latitude,
      longitude,
    );
  }

  @override
  void dispose() {
    _positionSubscription?.cancel();
    _batterySubscription?.cancel();
    _updateTimer?.cancel();
    super.dispose();
  }
}

/// Provider for quick access to current position
final currentPositionProvider = Provider<Position?>((ref) {
  return ref.watch(locationStateProvider).currentPosition;
});

/// Provider for tracking mode
final trackingModeProvider = Provider<LocationTrackingMode>((ref) {
  return ref.watch(locationStateProvider).mode;
});

/// Provider for battery level
final batteryLevelProvider = Provider<int>((ref) {
  return ref.watch(locationStateProvider).batteryLevel;
});
