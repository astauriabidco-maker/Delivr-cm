import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../app/theme.dart';
import '../../../core/demo/mock_data_provider.dart';
import '../providers/dashboard_provider.dart';
import '../widgets/stats_card.dart';
import '../widgets/online_toggle.dart';
import '../widgets/active_delivery_banner.dart';
import '../widgets/quick_actions.dart';
import '../widgets/courier_map_widget.dart';
import '../../deliveries/widgets/new_delivery_popup.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  @override
  Widget build(BuildContext context) {
    final dashboardAsync = ref.watch(dashboardProvider);
    final demoMode = ref.watch(demoModeProvider);
    // Watch accepted deliveries to trigger rebuilds
    final acceptedDeliveries = ref.watch(acceptedDeliveriesProvider);

    return Scaffold(
      backgroundColor: DelivrColors.background,
      // Demo FAB - only visible in demo mode
      floatingActionButton: demoMode ? FloatingActionButton.extended(
        onPressed: () => _simulateNewDelivery(),
        backgroundColor: DelivrColors.primary,
        icon: const Icon(Icons.add_alert),
        label: const Text('Simuler course'),
      ) : null,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(dashboardProvider);
          },
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                _buildHeader(context),
                const SizedBox(height: 24),

                // Online Toggle
                const OnlineToggle(),
                const SizedBox(height: 16),
                
                // Interactive Map
                _buildMapSection(context, dashboardAsync),
                const SizedBox(height: 16),

                // Active Delivery Banner (if any)
                dashboardAsync.when(
                  data: (data) {
                    if (data.activeDelivery != null) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: ActiveDeliveryBanner(
                          delivery: data.activeDelivery!,
                          onTap: () => context.push(
                            '/deliveries/${data.activeDelivery!.id}',
                          ),
                        ),
                      );
                    }
                    return const SizedBox.shrink();
                  },
                  loading: () => const SizedBox.shrink(),
                  error: (_, __) => const SizedBox.shrink(),
                ),

                // Stats Cards
                dashboardAsync.when(
                  data: (data) => _buildStatsGrid(data),
                  loading: () => _buildStatsLoading(),
                  error: (error, _) => _buildError(error.toString()),
                ),
                
                const SizedBox(height: 24),

                // Quick Actions
                const QuickActions(),
                
                const SizedBox(height: 24),

                // Recent Deliveries - pass accepted deliveries directly
                _buildRecentDeliveries(context, dashboardAsync, acceptedDeliveries),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Simulate a new delivery notification
  void _simulateNewDelivery() async {
    final newDelivery = MockDataProvider.generateNewDelivery();
    
    final accepted = await showNewDeliveryPopup(
      context,
      delivery: newDelivery,
      timeoutSeconds: 30,
    );
    
    if (!mounted) return;
    
    if (accepted) {
      // Add to accepted deliveries provider
      ref.read(acceptedDeliveriesProvider.notifier).acceptDelivery(newDelivery);
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('✓ Course ${newDelivery.trackingCode} acceptée !'),
          backgroundColor: Colors.green,
          duration: const Duration(seconds: 3),
        ),
      );
      
      // Force a rebuild
      setState(() {});
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Course refusée'),
          backgroundColor: Colors.grey,
        ),
      );
    }
  }


  Widget _buildHeader(BuildContext context) {
    return Row(
      children: [
        // Avatar
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: DelivrColors.primary.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(
            Icons.person,
            color: DelivrColors.primary,
          ),
        ),
        const SizedBox(width: 12),
        
        // Greeting
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _getGreeting(),
                style: TextStyle(
                  fontSize: 14,
                  color: DelivrColors.textSecondary,
                ),
              ),
              const Text(
                'Coursier',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: DelivrColors.textPrimary,
                ),
              ),
            ],
          ),
        ),
        
        // Notifications
        IconButton(
          onPressed: () {
            // TODO: Open notifications
          },
          icon: Stack(
            children: [
              const Icon(Icons.notifications_outlined),
              Positioned(
                right: 0,
                top: 0,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: DelivrColors.error,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  String _getGreeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Bonjour 👋';
    if (hour < 18) return 'Bon après-midi 👋';
    return 'Bonsoir 👋';
  }
  
  Widget _buildMapSection(BuildContext context, AsyncValue<DashboardData> dashboardAsync) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Section title
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              'Ma position',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: DelivrColors.textPrimary,
              ),
            ),
            TextButton.icon(
              onPressed: () {
                // TODO: Navigate to full map view
              },
              icon: const Icon(Icons.open_in_full, size: 16),
              label: const Text('Agrandir'),
              style: TextButton.styleFrom(
                foregroundColor: DelivrColors.primary,
                padding: EdgeInsets.zero,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        
        // Map widget
        dashboardAsync.when(
          data: (data) {
            // Collect delivery markers from recent deliveries
            final markers = <MapDeliveryMarker>[];
            for (final delivery in data.recentDeliveries.take(5)) {
              // Add markers for active deliveries
              if (delivery.status != 'COMPLETED' && delivery.status != 'CANCELLED') {
                markers.add(MapDeliveryMarker(
                  id: delivery.id,
                  latitude: 4.051 + (markers.length * 0.005), // Sample coords
                  longitude: 9.768 + (markers.length * 0.003),
                  status: delivery.status,
                  recipientName: delivery.dropoffAddress,
                  isPickup: delivery.status == 'ASSIGNED',
                ));
              }
            }
            
            return CourierMapWidget(
              // Default to Douala center
              latitude: 4.0511,
              longitude: 9.7679,
              deliveryMarkers: markers,
              height: 200,
            );
          },
          loading: () => Container(
            height: 200,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Center(
              child: CircularProgressIndicator(),
            ),
          ),
          error: (_, __) => Container(
            height: 200,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.map_outlined, size: 48, color: DelivrColors.textSecondary),
                  const SizedBox(height: 8),
                  Text(
                    'Carte indisponible',
                    style: TextStyle(color: DelivrColors.textSecondary),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildStatsGrid(DashboardData data) {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: StatsCard(
                icon: Icons.delivery_dining,
                label: 'Courses aujourd\'hui',
                value: data.todayDeliveries.toString(),
                color: DelivrColors.primary,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: StatsCard(
                icon: Icons.attach_money,
                label: 'Gains du jour',
                value: '${data.todayEarnings.toStringAsFixed(0)} XAF',
                color: DelivrColors.success,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: StatsCard(
                icon: Icons.route,
                label: 'Distance',
                value: '${data.todayDistance.toStringAsFixed(1)} km',
                color: DelivrColors.info,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: StatsCard(
                icon: Icons.star,
                label: 'Note',
                value: data.rating.toStringAsFixed(1),
                color: DelivrColors.warning,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildStatsLoading() {
    return Column(
      children: [
        Row(
          children: [
            Expanded(child: _shimmerCard()),
            const SizedBox(width: 12),
            Expanded(child: _shimmerCard()),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _shimmerCard()),
            const SizedBox(width: 12),
            Expanded(child: _shimmerCard()),
          ],
        ),
      ],
    );
  }

  Widget _shimmerCard() {
    return Container(
      height: 100,
      decoration: BoxDecoration(
        color: Colors.grey[200],
        borderRadius: BorderRadius.circular(16),
      ),
    );
  }

  Widget _buildError(String error) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: DelivrColors.errorLight,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: DelivrColors.error),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'Erreur: $error',
              style: const TextStyle(color: DelivrColors.error),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecentDeliveries(
    BuildContext context,
    AsyncValue<DashboardData> dashboardAsync,
    List<MockDelivery> acceptedDeliveries,
  ) {
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                const Text(
                  'Courses récentes',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: DelivrColors.textPrimary,
                  ),
                ),
                if (acceptedDeliveries.isNotEmpty) ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: DelivrColors.primary,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      '${acceptedDeliveries.length}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ],
            ),
            TextButton(
              onPressed: () => context.go(AppRoutes.deliveries),
              child: const Text('Voir tout'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        
        // Show accepted mock deliveries first
        if (acceptedDeliveries.isNotEmpty)
          Column(
            children: acceptedDeliveries.take(5).map((delivery) {
              return _buildMockDeliveryItem(context, delivery);
            }).toList(),
          )
        else
          dashboardAsync.when(
            data: (data) {
              if (data.recentDeliveries.isEmpty) {
                return Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: DelivrColors.surface,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    children: [
                      Icon(
                        Icons.inbox_outlined,
                        size: 48,
                        color: DelivrColors.textHint,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Aucune course récente',
                        style: TextStyle(
                          color: DelivrColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                );
              }
              
              return Column(
                children: data.recentDeliveries.map((delivery) {
                  return _buildDeliveryItem(context, delivery);
                }).toList(),
              );
            },
            loading: () => _shimmerCard(),
            error: (_, __) => const SizedBox.shrink(),
          ),
      ],
    );
  }

  /// Build delivery item from mock data
  Widget _buildMockDeliveryItem(BuildContext context, MockDelivery delivery) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: DelivrColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: _getMockStatusColor(delivery.status).withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: ListTile(
        onTap: () => context.push('/deliveries/${delivery.id}'),
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: _getMockStatusColor(delivery.status).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(
            _getMockStatusIcon(delivery.status),
            color: _getMockStatusColor(delivery.status),
            size: 20,
          ),
        ),
        title: Text(
          '${delivery.dropoffLocation.name} • ${delivery.recipientName}',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w500),
        ),
        subtitle: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: _getMockStatusColor(delivery.status).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                _getMockStatusLabel(delivery.status),
                style: TextStyle(
                  fontSize: 10,
                  color: _getMockStatusColor(delivery.status),
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              '${delivery.estimatedDistanceKm.toStringAsFixed(1)} km',
              style: TextStyle(
                fontSize: 12,
                color: DelivrColors.textSecondary,
              ),
            ),
          ],
        ),
        trailing: Text(
          '${delivery.courierEarning.toStringAsFixed(0)} XAF',
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: DelivrColors.success,
          ),
        ),
      ),
    );
  }

  Color _getMockStatusColor(String status) {
    switch (status) {
      case 'completed':
        return DelivrColors.success;
      case 'cancelled':
        return DelivrColors.error;
      case 'in_transit':
      case 'picked_up':
        return DelivrColors.info;
      case 'en_route_pickup':
      case 'arrived_pickup':
        return DelivrColors.warning;
      default:
        return DelivrColors.textSecondary;
    }
  }

  IconData _getMockStatusIcon(String status) {
    switch (status) {
      case 'completed':
        return Icons.check_circle;
      case 'cancelled':
        return Icons.cancel;
      case 'in_transit':
        return Icons.local_shipping;
      case 'picked_up':
        return Icons.inventory;
      case 'en_route_pickup':
        return Icons.directions_bike;
      case 'arrived_pickup':
        return Icons.store;
      default:
        return Icons.pending;
    }
  }

  String _getMockStatusLabel(String status) {
    switch (status) {
      case 'completed':
        return 'Livré';
      case 'cancelled':
        return 'Annulé';
      case 'in_transit':
        return 'En transit';
      case 'picked_up':
        return 'Récupéré';
      case 'en_route_pickup':
        return 'En route pickup';
      case 'arrived_pickup':
        return 'Arrivé pickup';
      default:
        return 'En attente';
    }
  }

  Widget _buildDeliveryItem(BuildContext context, RecentDelivery delivery) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: DelivrColors.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: ListTile(
        onTap: () => context.push('/deliveries/${delivery.id}'),
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: _getStatusColor(delivery.status).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(
            _getStatusIcon(delivery.status),
            color: _getStatusColor(delivery.status),
            size: 20,
          ),
        ),
        title: Text(
          delivery.dropoffAddress,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w500),
        ),
        subtitle: Text(
          delivery.timeAgo,
          style: TextStyle(
            fontSize: 12,
            color: DelivrColors.textSecondary,
          ),
        ),
        trailing: Text(
          '${delivery.earning.toStringAsFixed(0)} XAF',
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: DelivrColors.success,
          ),
        ),
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'COMPLETED':
        return DelivrColors.success;
      case 'CANCELLED':
        return DelivrColors.error;
      case 'PICKED_UP':
        return DelivrColors.info;
      default:
        return DelivrColors.warning;
    }
  }

  IconData _getStatusIcon(String status) {
    switch (status) {
      case 'COMPLETED':
        return Icons.check_circle;
      case 'CANCELLED':
        return Icons.cancel;
      case 'PICKED_UP':
        return Icons.local_shipping;
      default:
        return Icons.pending;
    }
  }
}
