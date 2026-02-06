import 'dart:async';
import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

/// Offline mode state
class OfflineState {
  final bool isOnline;
  final int pendingActionsCount;
  final bool isSyncing;
  final DateTime? lastSyncTime;
  
  const OfflineState({
    this.isOnline = true,
    this.pendingActionsCount = 0,
    this.isSyncing = false,
    this.lastSyncTime,
  });
  
  OfflineState copyWith({
    bool? isOnline,
    int? pendingActionsCount,
    bool? isSyncing,
    DateTime? lastSyncTime,
  }) {
    return OfflineState(
      isOnline: isOnline ?? this.isOnline,
      pendingActionsCount: pendingActionsCount ?? this.pendingActionsCount,
      isSyncing: isSyncing ?? this.isSyncing,
      lastSyncTime: lastSyncTime ?? this.lastSyncTime,
    );
  }
}

/// Pending action to be synced
class PendingAction {
  final String id;
  final String type;
  final String endpoint;
  final String method;
  final Map<String, dynamic> data;
  final DateTime createdAt;
  int retryCount;
  
  PendingAction({
    required this.id,
    required this.type,
    required this.endpoint,
    required this.method,
    required this.data,
    required this.createdAt,
    this.retryCount = 0,
  });
  
  Map<String, dynamic> toJson() => {
    'id': id,
    'type': type,
    'endpoint': endpoint,
    'method': method,
    'data': data,
    'createdAt': createdAt.toIso8601String(),
    'retryCount': retryCount,
  };
  
  factory PendingAction.fromJson(Map<String, dynamic> json) => PendingAction(
    id: json['id'],
    type: json['type'],
    endpoint: json['endpoint'],
    method: json['method'],
    data: Map<String, dynamic>.from(json['data']),
    createdAt: DateTime.parse(json['createdAt']),
    retryCount: json['retryCount'] ?? 0,
  );
}

/// Offline mode service
class OfflineModeService extends StateNotifier<OfflineState> {
  static const String _cacheBoxName = 'offline_cache';
  static const String _actionsBoxName = 'pending_actions';
  static const String _dashboardKey = 'cached_dashboard';
  static const String _deliveriesKey = 'cached_deliveries';
  static const int _maxRetries = 3;
  
  Box<String>? _cacheBox;
  Box<String>? _actionsBox;
  StreamSubscription? _connectivitySubscription;
  final Ref _ref;
  
  OfflineModeService(this._ref) : super(const OfflineState()) {
    _init();
  }
  
  Future<void> _init() async {
    await Hive.initFlutter();
    _cacheBox = await Hive.openBox<String>(_cacheBoxName);
    _actionsBox = await Hive.openBox<String>(_actionsBoxName);
    
    // Update pending count
    _updatePendingCount();
    
    // Listen to connectivity changes
    _connectivitySubscription = Connectivity().onConnectivityChanged.listen((result) {
      final isOnline = result.any((r) => r != ConnectivityResult.none);
      state = state.copyWith(isOnline: isOnline);
      
      if (isOnline) {
        _syncPendingActions();
      }
    });
    
    // Check initial connectivity
    final result = await Connectivity().checkConnectivity();
    final isOnline = result.any((r) => r != ConnectivityResult.none);
    state = state.copyWith(isOnline: isOnline);
  }
  
  void _updatePendingCount() {
    final count = _actionsBox?.length ?? 0;
    state = state.copyWith(pendingActionsCount: count);
  }
  
  /// Cache dashboard data
  Future<void> cacheDashboard(Map<String, dynamic> data) async {
    try {
      await _cacheBox?.put(_dashboardKey, jsonEncode(data));
      debugPrint('📦 Dashboard cached');
    } catch (e) {
      debugPrint('❌ Error caching dashboard: $e');
    }
  }
  
  /// Get cached dashboard data
  Map<String, dynamic>? getCachedDashboard() {
    try {
      final json = _cacheBox?.get(_dashboardKey);
      if (json != null) {
        return jsonDecode(json) as Map<String, dynamic>;
      }
    } catch (e) {
      debugPrint('❌ Error reading cached dashboard: $e');
    }
    return null;
  }
  
  /// Cache deliveries list
  Future<void> cacheDeliveries(List<Map<String, dynamic>> data) async {
    try {
      await _cacheBox?.put(_deliveriesKey, jsonEncode(data));
      debugPrint('📦 Deliveries cached');
    } catch (e) {
      debugPrint('❌ Error caching deliveries: $e');
    }
  }
  
  /// Get cached deliveries
  List<Map<String, dynamic>>? getCachedDeliveries() {
    try {
      final json = _cacheBox?.get(_deliveriesKey);
      if (json != null) {
        final list = jsonDecode(json) as List;
        return list.map((e) => Map<String, dynamic>.from(e)).toList();
      }
    } catch (e) {
      debugPrint('❌ Error reading cached deliveries: $e');
    }
    return null;
  }
  
  /// Queue an action to be synced when online
  Future<void> queueAction({
    required String type,
    required String endpoint,
    required String method,
    required Map<String, dynamic> data,
  }) async {
    final action = PendingAction(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      type: type,
      endpoint: endpoint,
      method: method,
      data: data,
      createdAt: DateTime.now(),
    );
    
    try {
      await _actionsBox?.put(action.id, jsonEncode(action.toJson()));
      _updatePendingCount();
      debugPrint('📝 Action queued: $type');
      
      // Try to sync immediately if online
      if (state.isOnline) {
        _syncPendingActions();
      }
    } catch (e) {
      debugPrint('❌ Error queueing action: $e');
    }
  }
  
  /// Sync all pending actions
  Future<void> _syncPendingActions() async {
    if (state.isSyncing || !state.isOnline) return;
    
    final actions = _actionsBox?.values.toList() ?? [];
    if (actions.isEmpty) return;
    
    state = state.copyWith(isSyncing: true);
    debugPrint('🔄 Syncing ${actions.length} pending actions...');
    
    for (final actionJson in actions) {
      try {
        final action = PendingAction.fromJson(jsonDecode(actionJson));
        final success = await _executeAction(action);
        
        if (success) {
          await _actionsBox?.delete(action.id);
          debugPrint('✅ Action synced: ${action.type}');
        } else {
          action.retryCount++;
          if (action.retryCount >= _maxRetries) {
            await _actionsBox?.delete(action.id);
            debugPrint('❌ Action failed after $_maxRetries retries: ${action.type}');
          } else {
            await _actionsBox?.put(action.id, jsonEncode(action.toJson()));
          }
        }
      } catch (e) {
        debugPrint('❌ Error syncing action: $e');
      }
    }
    
    _updatePendingCount();
    state = state.copyWith(
      isSyncing: false,
      lastSyncTime: DateTime.now(),
    );
    debugPrint('✅ Sync complete');
  }
  
  Future<bool> _executeAction(PendingAction action) async {
    // Implement actual API call here using dio
    // For now, just simulate success
    await Future.delayed(const Duration(milliseconds: 500));
    return true;
  }
  
  /// Force manual sync
  Future<void> forceSync() async {
    if (!state.isOnline) {
      debugPrint('⚠️ Cannot sync: offline');
      return;
    }
    await _syncPendingActions();
  }
  
  /// Clear all cached data
  Future<void> clearCache() async {
    await _cacheBox?.clear();
    debugPrint('🗑️ Cache cleared');
  }
  
  /// Clear all pending actions
  Future<void> clearPendingActions() async {
    await _actionsBox?.clear();
    _updatePendingCount();
    debugPrint('🗑️ Pending actions cleared');
  }
  
  @override
  void dispose() {
    _connectivitySubscription?.cancel();
    super.dispose();
  }
}

/// Offline mode provider
final offlineModeProvider = StateNotifierProvider<OfflineModeService, OfflineState>((ref) {
  return OfflineModeService(ref);
});

/// Connection indicator widget
class ConnectionIndicator extends ConsumerWidget {
  final bool showLabel;
  
  const ConnectionIndicator({super.key, this.showLabel = true});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final offlineState = ref.watch(offlineModeProvider);
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: offlineState.isOnline 
            ? Colors.green.withOpacity(0.1) 
            : Colors.red.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: offlineState.isOnline ? Colors.green : Colors.red,
            ),
          ),
          if (showLabel) ...[
            const SizedBox(width: 6),
            Text(
              offlineState.isOnline ? 'En ligne' : 'Hors ligne',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w500,
                color: offlineState.isOnline ? Colors.green : Colors.red,
              ),
            ),
          ],
          if (offlineState.pendingActionsCount > 0) ...[
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.orange,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                '${offlineState.pendingActionsCount}',
                style: const TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
            ),
          ],
          if (offlineState.isSyncing) ...[
            const SizedBox(width: 8),
            const SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(Colors.blue),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Offline banner widget
class OfflineBanner extends ConsumerWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final offlineState = ref.watch(offlineModeProvider);
    
    if (offlineState.isOnline) return const SizedBox.shrink();
    
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      color: Colors.orange.shade800,
      child: Row(
        children: [
          const Icon(Icons.wifi_off, color: Colors.white, size: 18),
          const SizedBox(width: 12),
          const Expanded(
            child: Text(
              'Vous êtes hors ligne. Les données affichées peuvent être obsolètes.',
              style: TextStyle(color: Colors.white, fontSize: 13),
            ),
          ),
          if (offlineState.pendingActionsCount > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                '${offlineState.pendingActionsCount} en attente',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
