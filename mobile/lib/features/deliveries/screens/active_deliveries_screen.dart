import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../app/theme.dart';
import '../../../core/demo/mock_data_provider.dart';
import '../../../core/services/navigation_service.dart';
import '../services/route_optimizer_service.dart';

class ActiveDeliveriesScreen extends ConsumerStatefulWidget {
  const ActiveDeliveriesScreen({super.key});

  @override
  ConsumerState<ActiveDeliveriesScreen> createState() => _ActiveDeliveriesScreenState();
}

class _ActiveDeliveriesScreenState extends ConsumerState<ActiveDeliveriesScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isOptimized = false;
  List<MockDelivery> _displayedDeliveries = [];

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
    final acceptedDeliveries = ref.watch(acceptedDeliveriesProvider);
    
    // Initialize displayed deliveries
    if (_displayedDeliveries.isEmpty || !_isOptimized) {
      _displayedDeliveries = List.from(acceptedDeliveries);
    }

    final totalEarnings = acceptedDeliveries.fold<double>(
      0, (sum, d) => sum + d.courierEarning,
    );

    final originalDistance = RouteOptimizerService.calculateTotalDistance(acceptedDeliveries);
    final optimizedDistance = _isOptimized
        ? RouteOptimizerService.calculateTotalDistance(_displayedDeliveries)
        : originalDistance;

    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        backgroundColor: DelivrColors.surface,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Mes courses actives'),
            Text(
              '${acceptedDeliveries.length} course${acceptedDeliveries.length > 1 ? 's' : ''} • ${totalEarnings.toStringAsFixed(0)} XAF',
              style: TextStyle(
                fontSize: 12,
                color: DelivrColors.textSecondary,
                fontWeight: FontWeight.normal,
              ),
            ),
          ],
        ),
        actions: [
          // Optimize button
          if (acceptedDeliveries.length > 1)
            TextButton.icon(
              onPressed: () => _optimizeRoute(acceptedDeliveries),
              icon: Icon(
                _isOptimized ? Icons.check_circle : Icons.route,
                size: 18,
                color: _isOptimized ? DelivrColors.success : DelivrColors.primary,
              ),
              label: Text(
                _isOptimized ? 'Optimisé' : 'Optimiser',
                style: TextStyle(
                  color: _isOptimized ? DelivrColors.success : DelivrColors.primary,
                ),
              ),
            ),
        ],
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: DelivrColors.primary,
          labelColor: DelivrColors.primary,
          unselectedLabelColor: DelivrColors.textSecondary,
          tabs: const [
            Tab(icon: Icon(Icons.list), text: 'Liste'),
            Tab(icon: Icon(Icons.map), text: 'Carte'),
          ],
        ),
      ),
      body: Column(
        children: [
          // Stats bar
          _buildStatsBar(acceptedDeliveries, originalDistance, optimizedDistance),
          
          // Tab content
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                // List view
                _buildListView(_displayedDeliveries),
                // Map view
                _buildMapView(_displayedDeliveries),
              ],
            ),
          ),
        ],
      ),
      // FAB for next navigation
      floatingActionButton: acceptedDeliveries.isNotEmpty
          ? FloatingActionButton.extended(
              onPressed: () => _navigateToNext(_displayedDeliveries),
              backgroundColor: DelivrColors.primary,
              icon: const Icon(Icons.navigation),
              label: const Text('Prochain point'),
            )
          : null,
    );
  }

  Widget _buildStatsBar(
    List<MockDelivery> deliveries,
    double originalDistance,
    double optimizedDistance,
  ) {
    final savings = originalDistance - optimizedDistance;
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      color: DelivrColors.surface,
      child: Row(
        children: [
          _buildStatChip(
            Icons.local_shipping,
            '${deliveries.length}',
            'Courses',
            DelivrColors.primary,
          ),
          const SizedBox(width: 12),
          _buildStatChip(
            Icons.route,
            '${optimizedDistance.toStringAsFixed(1)} km',
            'Distance',
            DelivrColors.info,
          ),
          if (_isOptimized && savings > 0.1) ...[
            const SizedBox(width: 12),
            _buildStatChip(
              Icons.savings,
              '-${savings.toStringAsFixed(1)} km',
              'Économie',
              DelivrColors.success,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStatChip(IconData icon, String value, String label, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            Icon(icon, size: 20, color: color),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    value,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 10,
                      color: DelivrColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildListView(List<MockDelivery> deliveries) {
    if (deliveries.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.inbox_outlined,
              size: 64,
              color: DelivrColors.textHint,
            ),
            const SizedBox(height: 16),
            Text(
              'Aucune course active',
              style: TextStyle(
                fontSize: 18,
                color: DelivrColors.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Acceptez des courses depuis le dashboard',
              style: TextStyle(
                fontSize: 14,
                color: DelivrColors.textHint,
              ),
            ),
          ],
        ),
      );
    }

    return ReorderableListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: deliveries.length,
      onReorder: (oldIndex, newIndex) {
        setState(() {
          if (newIndex > oldIndex) newIndex--;
          final item = _displayedDeliveries.removeAt(oldIndex);
          _displayedDeliveries.insert(newIndex, item);
          _isOptimized = false; // Manual reorder cancels optimization
        });
      },
      itemBuilder: (context, index) {
        final delivery = deliveries[index];
        return _buildDeliveryCard(delivery, index, key: ValueKey(delivery.id));
      },
    );
  }

  Widget _buildDeliveryCard(MockDelivery delivery, int index, {Key? key}) {
    final statusColor = _getStatusColor(delivery.status);
    final statusLabel = _getStatusLabel(delivery.status);
    final isPickup = ['pending', 'en_route_pickup', 'arrived_pickup'].contains(delivery.status);

    return Card(
      key: key,
      margin: const EdgeInsets.only(bottom: 12),
      color: DelivrColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: statusColor.withOpacity(0.3),
          width: 1,
        ),
      ),
      child: InkWell(
        onTap: () => context.push('/deliveries/${delivery.id}'),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                children: [
                  // Order number
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: DelivrColors.primary,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Center(
                      child: Text(
                        '${index + 1}',
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  
                  // Tracking code
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          delivery.trackingCode,
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),
                        Text(
                          delivery.packageType,
                          style: TextStyle(
                            fontSize: 12,
                            color: DelivrColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  
                  // Status badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      statusLabel,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: statusColor,
                      ),
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 12),
              const Divider(height: 1),
              const SizedBox(height: 12),
              
              // Current destination
              Row(
                children: [
                  Icon(
                    isPickup ? Icons.store : Icons.home,
                    size: 20,
                    color: isPickup ? DelivrColors.info : DelivrColors.success,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isPickup ? 'Pickup: ${delivery.pickupLocation.name}' : 'Livraison: ${delivery.dropoffLocation.name}',
                          style: const TextStyle(fontWeight: FontWeight.w500),
                        ),
                        Text(
                          isPickup ? delivery.senderName : delivery.recipientName,
                          style: TextStyle(
                            fontSize: 12,
                            color: DelivrColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  
                  // Earning
                  Text(
                    '${delivery.courierEarning.toStringAsFixed(0)} XAF',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      color: DelivrColors.success,
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 12),
              
              // Quick actions
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _callContact(
                        isPickup ? delivery.senderPhone : delivery.recipientPhone,
                      ),
                      icon: const Icon(Icons.phone, size: 16),
                      label: const Text('Appeler'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: DelivrColors.primary,
                        side: BorderSide(color: DelivrColors.primary.withOpacity(0.3)),
                        padding: const EdgeInsets.symmetric(vertical: 8),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: () => _navigateToDelivery(delivery, isPickup),
                      icon: const Icon(Icons.navigation, size: 16),
                      label: const Text('GPS'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: DelivrColors.primary,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 8),
                      ),
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

  Widget _buildMapView(List<MockDelivery> deliveries) {
    if (deliveries.isEmpty) {
      return const Center(child: Text('Aucune course à afficher'));
    }

    final points = RouteOptimizerService.getAllPoints(deliveries);
    if (points.isEmpty) {
      return const Center(child: Text('Toutes les courses sont terminées'));
    }

    // Calculate bounds
    double minLat = points.first.lat;
    double maxLat = points.first.lat;
    double minLng = points.first.lng;
    double maxLng = points.first.lng;

    for (final point in points) {
      if (point.lat < minLat) minLat = point.lat;
      if (point.lat > maxLat) maxLat = point.lat;
      if (point.lng < minLng) minLng = point.lng;
      if (point.lng > maxLng) maxLng = point.lng;
    }

    final center = LatLng((minLat + maxLat) / 2, (minLng + maxLng) / 2);

    return FlutterMap(
      options: MapOptions(
        initialCenter: center,
        initialZoom: 13,
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.delivr.cm',
        ),
        
        // Route polyline
        PolylineLayer(
          polylines: [
            Polyline(
              points: points.map((p) => LatLng(p.lat, p.lng)).toList(),
              strokeWidth: 3,
              color: DelivrColors.primary.withOpacity(0.7),
            ),
          ],
        ),
        
        // Markers
        MarkerLayer(
          markers: points.asMap().entries.map((entry) {
            final index = entry.key;
            final point = entry.value;
            
            return Marker(
              point: LatLng(point.lat, point.lng),
              width: 40,
              height: 40,
              child: GestureDetector(
                onTap: () => _showPointInfo(point),
                child: Container(
                  decoration: BoxDecoration(
                    color: point.isPickup ? DelivrColors.info : DelivrColors.success,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 2),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.2),
                        blurRadius: 4,
                      ),
                    ],
                  ),
                  child: Center(
                    child: Text(
                      '${index + 1}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  void _optimizeRoute(List<MockDelivery> deliveries) {
    setState(() {
      _displayedDeliveries = RouteOptimizerService.optimizeRoute(deliveries);
      _isOptimized = true;
    });

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('✓ Tournée optimisée !'),
        backgroundColor: Colors.green,
      ),
    );
  }

  void _navigateToNext(List<MockDelivery> deliveries) {
    final nextPoint = RouteOptimizerService.getNextPoint(deliveries);
    if (nextPoint != null) {
      NavigationService.navigateTo(
        latitude: nextPoint.lat,
        longitude: nextPoint.lng,
        label: nextPoint.address,
      );
    }
  }

  void _navigateToDelivery(MockDelivery delivery, bool isPickup) {
    if (isPickup) {
      NavigationService.navigateTo(
        latitude: delivery.pickupLocation.lat,
        longitude: delivery.pickupLocation.lng,
        label: delivery.pickupAddress,
      );
    } else {
      NavigationService.navigateTo(
        latitude: delivery.dropoffLocation.lat,
        longitude: delivery.dropoffLocation.lng,
        label: delivery.dropoffAddress,
      );
    }
  }

  void _callContact(String phone) async {
    final uri = Uri.parse('tel:$phone');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  void _showPointInfo(RoutePoint point) {
    showModalBottomSheet(
      context: context,
      backgroundColor: DelivrColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: point.isPickup 
                        ? DelivrColors.info.withOpacity(0.1)
                        : DelivrColors.success.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    point.label,
                    style: TextStyle(
                      color: point.isPickup ? DelivrColors.info : DelivrColors.success,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const Spacer(),
                Text(
                  point.trackingCode,
                  style: TextStyle(
                    color: DelivrColors.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              point.address,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.person_outline, size: 16),
                const SizedBox(width: 4),
                Text(point.contactName),
                const SizedBox(width: 16),
                const Icon(Icons.phone_outlined, size: 16),
                const SizedBox(width: 4),
                Text(point.contactPhone),
              ],
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () {
                      Navigator.pop(context);
                      _callContact(point.contactPhone);
                    },
                    icon: const Icon(Icons.phone),
                    label: const Text('Appeler'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () {
                      Navigator.pop(context);
                      NavigationService.navigateTo(
                        latitude: point.lat,
                        longitude: point.lng,
                        label: point.address,
                      );
                    },
                    icon: const Icon(Icons.navigation),
                    label: const Text('Y aller'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: DelivrColors.primary,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Color _getStatusColor(String status) {
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

  String _getStatusLabel(String status) {
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
        return 'Vers pickup';
      case 'arrived_pickup':
        return 'Arrivé pickup';
      default:
        return 'En attente';
    }
  }
}
