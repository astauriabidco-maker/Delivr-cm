import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_client.dart';

/// Dashboard data model
class DashboardData {
  final int todayDeliveries;
  final double todayEarnings;
  final double todayDistance;
  final double rating;
  final int successStreak;
  final String level;
  final ActiveDelivery? activeDelivery;
  final List<RecentDelivery> recentDeliveries;

  const DashboardData({
    required this.todayDeliveries,
    required this.todayEarnings,
    required this.todayDistance,
    required this.rating,
    required this.successStreak,
    required this.level,
    this.activeDelivery,
    required this.recentDeliveries,
  });

  factory DashboardData.fromJson(Map<String, dynamic> json) {
    return DashboardData(
      todayDeliveries: json['today_deliveries'] ?? 0,
      todayEarnings: (json['today_earnings'] ?? 0).toDouble(),
      todayDistance: (json['today_distance'] ?? 0).toDouble(),
      rating: (json['rating'] ?? 0).toDouble(),
      successStreak: json['success_streak'] ?? 0,
      level: json['level'] ?? 'BRONZE',
      activeDelivery: json['active_delivery'] != null
          ? ActiveDelivery.fromJson(json['active_delivery'])
          : null,
      recentDeliveries: (json['recent_deliveries'] as List? ?? [])
          .map((e) => RecentDelivery.fromJson(e))
          .toList(),
    );
  }
}

/// Active delivery model
class ActiveDelivery {
  final String id;
  final String status;
  final String pickupAddress;
  final String dropoffAddress;
  final double pickupLat;
  final double pickupLng;
  final double dropoffLat;
  final double dropoffLng;
  final double earning;
  final String recipientPhone;

  const ActiveDelivery({
    required this.id,
    required this.status,
    required this.pickupAddress,
    required this.dropoffAddress,
    required this.pickupLat,
    required this.pickupLng,
    required this.dropoffLat,
    required this.dropoffLng,
    required this.earning,
    required this.recipientPhone,
  });

  factory ActiveDelivery.fromJson(Map<String, dynamic> json) {
    return ActiveDelivery(
      id: json['id'] ?? '',
      status: json['status'] ?? 'ASSIGNED',
      pickupAddress: json['pickup_address'] ?? 'Adresse de retrait',
      dropoffAddress: json['dropoff_address'] ?? 'Adresse de livraison',
      pickupLat: (json['pickup_lat'] ?? 0).toDouble(),
      pickupLng: (json['pickup_lng'] ?? 0).toDouble(),
      dropoffLat: (json['dropoff_lat'] ?? 0).toDouble(),
      dropoffLng: (json['dropoff_lng'] ?? 0).toDouble(),
      earning: (json['courier_earning'] ?? 0).toDouble(),
      recipientPhone: json['recipient_phone'] ?? '',
    );
  }
}

/// Recent delivery model
class RecentDelivery {
  final String id;
  final String status;
  final String dropoffAddress;
  final double earning;
  final DateTime completedAt;
  
  const RecentDelivery({
    required this.id,
    required this.status,
    required this.dropoffAddress,
    required this.earning,
    required this.completedAt,
  });

  factory RecentDelivery.fromJson(Map<String, dynamic> json) {
    return RecentDelivery(
      id: json['id'] ?? '',
      status: json['status'] ?? '',
      dropoffAddress: json['dropoff_address'] ?? '',
      earning: (json['courier_earning'] ?? 0).toDouble(),
      completedAt: DateTime.tryParse(json['completed_at'] ?? '') ?? DateTime.now(),
    );
  }

  String get timeAgo {
    final diff = DateTime.now().difference(completedAt);
    if (diff.inMinutes < 60) {
      return 'Il y a ${diff.inMinutes} min';
    } else if (diff.inHours < 24) {
      return 'Il y a ${diff.inHours}h';
    } else {
      return 'Il y a ${diff.inDays}j';
    }
  }
}

/// Dashboard provider
final dashboardProvider = FutureProvider.autoDispose<DashboardData>((ref) async {
  final dio = ref.watch(dioProvider);
  
  try {
    final response = await dio.get('/api/mobile/dashboard/');
    return DashboardData.fromJson(response.data);
  } on DioException catch (e) {
    throw Exception(e.response?.data?['detail'] ?? 'Erreur de chargement');
  }
});

/// Online status provider
final onlineStatusProvider = StateNotifierProvider<OnlineStatusNotifier, bool>((ref) {
  return OnlineStatusNotifier(ref);
});

class OnlineStatusNotifier extends StateNotifier<bool> {
  final Ref _ref;
  
  OnlineStatusNotifier(this._ref) : super(false) {
    _loadStatus();
  }
  
  Future<void> _loadStatus() async {
    // Status is already loaded from dashboard data
    // No separate endpoint needed - init with false,
    // will be updated from dashboard response
    state = false;
  }
  
  Future<void> toggle() async {
    final dio = _ref.read(dioProvider);
    
    try {
      final response = await dio.post('/api/mobile/toggle-online/');
      state = response.data['is_online'] ?? !state;
      
      // Refresh dashboard
      _ref.invalidate(dashboardProvider);
    } catch (e) {
      // Revert on error
    }
  }
}
