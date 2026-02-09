import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme.dart';
import '../../../core/api/api_client.dart';


/// Deliveries list screen with active and completed tabs
class DeliveriesScreen extends ConsumerStatefulWidget {
  const DeliveriesScreen({super.key});

  @override
  ConsumerState<DeliveriesScreen> createState() => _DeliveriesScreenState();
}

class _DeliveriesScreenState extends ConsumerState<DeliveriesScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Mes courses'),
        backgroundColor: DelivrColors.surface,
        elevation: 0,
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: DelivrColors.primary,
          labelColor: DelivrColors.primary,
          unselectedLabelColor: DelivrColors.textSecondary,
          tabs: const [
            Tab(text: 'En cours'),
            Tab(text: 'Terminées'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          _ActiveDeliveriesTab(),
          _CompletedDeliveriesTab(),
        ],
      ),
    );
  }
}

/// Tab showing active deliveries
class _ActiveDeliveriesTab extends ConsumerWidget {
  const _ActiveDeliveriesTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final deliveriesAsync = ref.watch(activeDeliveriesProvider);

    return deliveriesAsync.when(
      data: (deliveries) {
        if (deliveries.isEmpty) {
          return _buildEmptyState(
            icon: Icons.local_shipping_outlined,
            title: 'Aucune course en cours',
            subtitle: 'Les nouvelles courses apparaîtront ici',
          );
        }
        return RefreshIndicator(
          onRefresh: () => ref.refresh(activeDeliveriesProvider.future),
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: deliveries.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) => _DeliveryCard(
              delivery: deliveries[index],
              isActive: true,
            ),
          ),
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, _) => _buildErrorState(
        error.toString(),
        () => ref.refresh(activeDeliveriesProvider),
      ),
    );
  }
}

/// Tab showing completed deliveries
class _CompletedDeliveriesTab extends ConsumerWidget {
  const _CompletedDeliveriesTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final deliveriesAsync = ref.watch(completedDeliveriesProvider);

    return deliveriesAsync.when(
      data: (deliveries) {
        if (deliveries.isEmpty) {
          return _buildEmptyState(
            icon: Icons.check_circle_outline,
            title: 'Aucune course terminée',
            subtitle: 'Votre historique sera affiché ici',
          );
        }
        return RefreshIndicator(
          onRefresh: () => ref.refresh(completedDeliveriesProvider.future),
          child: ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: deliveries.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) => _DeliveryCard(
              delivery: deliveries[index],
              isActive: false,
            ),
          ),
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, _) => _buildErrorState(
        error.toString(),
        () => ref.refresh(completedDeliveriesProvider),
      ),
    );
  }
}

/// Delivery card widget
class _DeliveryCard extends StatelessWidget {
  final DeliveryListItem delivery;
  final bool isActive;

  const _DeliveryCard({
    required this.delivery,
    required this.isActive,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: InkWell(
        onTap: () => context.push('/deliveries/${delivery.id}'),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header with status
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: _getStatusColor(delivery.status).withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          _getStatusIcon(delivery.status),
                          size: 14,
                          color: _getStatusColor(delivery.status),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          _getStatusLabel(delivery.status),
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                            color: _getStatusColor(delivery.status),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Spacer(),
                  Text(
                    delivery.createdAt,
                    style: TextStyle(
                      fontSize: 12,
                      color: DelivrColors.textSecondary,
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 12),

              // Pickup address
              Row(
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: const BoxDecoration(
                      color: DelivrColors.success,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      delivery.pickupAddress,
                      style: const TextStyle(fontSize: 14),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),

              // Connector line
              Container(
                margin: const EdgeInsets.only(left: 4),
                height: 16,
                child: const VerticalDivider(
                  color: DelivrColors.divider,
                  thickness: 2,
                ),
              ),

              // Dropoff address
              Row(
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: const BoxDecoration(
                      color: DelivrColors.primary,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      delivery.dropoffAddress,
                      style: const TextStyle(fontSize: 14),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 12),

              // Footer with distance and earnings
              Row(
                children: [
                  Icon(
                    Icons.straighten,
                    size: 16,
                    color: DelivrColors.textSecondary,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    '${delivery.distanceKm.toStringAsFixed(1)} km',
                    style: TextStyle(
                      fontSize: 13,
                      color: DelivrColors.textSecondary,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    '${delivery.courierEarning.toStringAsFixed(0)} XAF',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: DelivrColors.success,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'ASSIGNED':
        return DelivrColors.primary;
      case 'EN_ROUTE_PICKUP':
      case 'ARRIVED_PICKUP':
        return Colors.orange;
      case 'PICKED_UP':
      case 'IN_TRANSIT':
        return Colors.blue;
      case 'ARRIVED_DROPOFF':
        return Colors.purple;
      case 'COMPLETED':
        return DelivrColors.success;
      case 'CANCELLED':
      case 'FAILED':
        return DelivrColors.error;
      default:
        return DelivrColors.textSecondary;
    }
  }

  IconData _getStatusIcon(String status) {
    switch (status) {
      case 'ASSIGNED':
        return Icons.person_pin;
      case 'EN_ROUTE_PICKUP':
        return Icons.directions_bike;
      case 'ARRIVED_PICKUP':
        return Icons.location_on;
      case 'PICKED_UP':
        return Icons.inventory_2;
      case 'IN_TRANSIT':
        return Icons.local_shipping;
      case 'ARRIVED_DROPOFF':
        return Icons.pin_drop;
      case 'COMPLETED':
        return Icons.check_circle;
      case 'CANCELLED':
      case 'FAILED':
        return Icons.cancel;
      default:
        return Icons.hourglass_empty;
    }
  }

  String _getStatusLabel(String status) {
    switch (status) {
      case 'ASSIGNED':
        return 'Assignée';
      case 'EN_ROUTE_PICKUP':
        return 'En route vers retrait';
      case 'ARRIVED_PICKUP':
        return 'Arrivé au retrait';
      case 'PICKED_UP':
        return 'Colis récupéré';
      case 'IN_TRANSIT':
        return 'En transit';
      case 'ARRIVED_DROPOFF':
        return 'Arrivé destination';
      case 'COMPLETED':
        return 'Livrée';
      case 'CANCELLED':
        return 'Annulée';
      case 'FAILED':
        return 'Échec';
      default:
        return 'En attente';
    }
  }
}

Widget _buildEmptyState({
  required IconData icon,
  required String title,
  required String subtitle,
}) {
  return Center(
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, size: 64, color: DelivrColors.primary.withValues(alpha: 0.5)),
        const SizedBox(height: 16),
        Text(
          title,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          subtitle,
          style: TextStyle(color: DelivrColors.textSecondary),
        ),
      ],
    ),
  );
}

Widget _buildErrorState(String error, VoidCallback onRetry) {
  return Center(
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.error_outline, size: 48, color: DelivrColors.error),
        const SizedBox(height: 16),
        Text(error, textAlign: TextAlign.center),
        const SizedBox(height: 16),
        ElevatedButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('Réessayer'),
        ),
      ],
    ),
  );
}

/// Model for delivery list item
class DeliveryListItem {
  final String id;
  final String status;
  final String pickupAddress;
  final String dropoffAddress;
  final double distanceKm;
  final double courierEarning;
  final String createdAt;

  DeliveryListItem({
    required this.id,
    required this.status,
    required this.pickupAddress,
    required this.dropoffAddress,
    required this.distanceKm,
    required this.courierEarning,
    required this.createdAt,
  });

  factory DeliveryListItem.fromJson(Map<String, dynamic> json) {
    return DeliveryListItem(
      id: json['id'] ?? '',
      status: json['status'] ?? 'PENDING',
      pickupAddress: json['pickup_address'] ?? 'N/A',
      dropoffAddress: json['dropoff_address'] ?? 'N/A',
      distanceKm: (json['distance_km'] as num?)?.toDouble() ?? 0,
      courierEarning: (json['courier_earning'] as num?)?.toDouble() ?? 0,
      createdAt: _formatDate(json['created_at']),
    );
  }

  static String _formatDate(String? isoDate) {
    if (isoDate == null) return '';
    try {
      final date = DateTime.parse(isoDate);
      final now = DateTime.now();
      if (date.day == now.day && date.month == now.month && date.year == now.year) {
        return 'Aujourd\'hui ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
      }
      return '${date.day}/${date.month} ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return '';
    }
  }
}

/// Providers for deliveries list
final activeDeliveriesProvider = FutureProvider<List<DeliveryListItem>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final response = await api.get('/api/mobile/deliveries/', queryParameters: {'status': 'active'});
  
  if (response.success && response.data != null) {
    final list = response.data!['deliveries'] as List<dynamic>?;
    return list?.map((e) => DeliveryListItem.fromJson(e as Map<String, dynamic>)).toList() ?? [];
  }
  return [];
});

final completedDeliveriesProvider = FutureProvider<List<DeliveryListItem>>((ref) async {
  final api = ref.watch(apiClientProvider);
  final response = await api.get('/api/mobile/deliveries/', queryParameters: {'status': 'completed'});
  
  if (response.success && response.data != null) {
    final list = response.data!['deliveries'] as List<dynamic>?;
    return list?.map((e) => DeliveryListItem.fromJson(e as Map<String, dynamic>)).toList() ?? [];
  }
  return [];
});
