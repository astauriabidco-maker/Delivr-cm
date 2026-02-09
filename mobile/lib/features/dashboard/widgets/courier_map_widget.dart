import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../../../app/theme.dart';
import '../providers/traffic_provider.dart';
import '../providers/events_provider.dart';
import 'traffic_events_layer.dart';
import 'report_event_sheet.dart';

/// Map widget showing courier's current location and nearby deliveries
class CourierMapWidget extends ConsumerStatefulWidget {
  final double? latitude;
  final double? longitude;
  final List<MapDeliveryMarker> deliveryMarkers;
  final double height;
  final bool showTraffic;
  
  const CourierMapWidget({
    super.key,
    this.latitude,
    this.longitude,
    this.deliveryMarkers = const [],
    this.height = 200,
    this.showTraffic = true,
  });

  @override
  ConsumerState<CourierMapWidget> createState() => _CourierMapWidgetState();
}

class _CourierMapWidgetState extends ConsumerState<CourierMapWidget> {
  late MapController _mapController;
  bool _trafficVisible = true;
  // Default to Douala city center
  static const LatLng _defaultLocation = LatLng(4.0511, 9.7679);
  static const double _cellSize = 0.0018;
  
  @override
  void initState() {
    super.initState();
    _mapController = MapController();
    if (widget.showTraffic) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        ref.read(trafficHeatmapProvider.notifier).startAutoRefresh();
        ref.read(trafficHeatmapProvider.notifier).fetchStats();
        ref.read(trafficEventsProvider.notifier).startAutoRefresh();
      });
    }
  }

  @override
  void dispose() {
    _mapController.dispose();
    super.dispose();
  }

  LatLng get _currentLocation {
    if (widget.latitude != null && widget.longitude != null) {
      return LatLng(widget.latitude!, widget.longitude!);
    }
    return _defaultLocation;
  }

  @override
  Widget build(BuildContext context) {
    final trafficState = widget.showTraffic ? ref.watch(trafficHeatmapProvider) : null;

    return Container(
      height: widget.height,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 20,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Stack(
          children: [
            // Map
            FlutterMap(
              mapController: _mapController,
              options: MapOptions(
                initialCenter: _currentLocation,
                initialZoom: 14.0,
                minZoom: 10.0,
                maxZoom: 18.0,
              ),
              children: [
                // OpenStreetMap tiles (free, no API key needed)
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'cm.delivr.courier',
                  tileProvider: kIsWeb 
                    ? NetworkTileProvider() 
                    : NetworkTileProvider(),
                ),
                
                // Traffic heatmap layer (colored grid cells)
                if (widget.showTraffic && _trafficVisible && trafficState != null && trafficState.cells.isNotEmpty)
                  PolygonLayer(
                    polygons: trafficState.cells.map((cell) {
                      final half = _cellSize / 2;
                      return Polygon(
                        points: [
                          LatLng(cell.lat - half, cell.lng - half),
                          LatLng(cell.lat - half, cell.lng + half),
                          LatLng(cell.lat + half, cell.lng + half),
                          LatLng(cell.lat + half, cell.lng - half),
                        ],
                        color: Color(cell.level.colorValue)
                            .withValues(alpha: cell.level.opacity),
                        borderColor: Color(cell.level.colorValue).withValues(alpha: 0.3),
                        borderStrokeWidth: 0.5,
                      );
                    }).toList(),
                  ),
                
                // Delivery markers
                MarkerLayer(
                  markers: [
                    // Current location marker (courier)
                    Marker(
                      point: _currentLocation,
                      width: 60,
                      height: 60,
                      child: _buildCourierMarker(),
                    ),
                    
                    // Delivery point markers
                    ...widget.deliveryMarkers.map((dm) => Marker(
                      point: LatLng(dm.latitude, dm.longitude),
                      width: 40,
                      height: 50,
                      child: _buildDeliveryMarker(dm),
                    )),
                  ],
                ),
                
                // Traffic events markers
                if (widget.showTraffic && _trafficVisible)
                  const TrafficEventsLayer(),
              ],
            ),
            
            // Gradient overlay at top
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: Container(
                height: 40,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Colors.black.withValues(alpha: 0.3),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),
            
            // Map label
            Positioned(
              top: 12,
              left: 12,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.95),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.1),
                      blurRadius: 4,
                    ),
                  ],
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: DelivrColors.success,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'En ligne',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: DelivrColors.textPrimary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            
            // Traffic toggle + stats (top right)
            if (widget.showTraffic)
              Positioned(
                top: 12,
                right: 12,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    _buildTrafficToggle(trafficState),
                    if (_trafficVisible && trafficState?.stats != null)
                      _buildTrafficStats(trafficState!.stats!),
                  ],
                ),
              ),
            
            // Recenter button
            Positioned(
              bottom: 12,
              right: 12,
              child: GestureDetector(
                onTap: () {
                  _mapController.move(_currentLocation, 14.0);
                },
                child: Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.15),
                        blurRadius: 8,
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.my_location,
                    color: DelivrColors.primary,
                    size: 20,
                  ),
                ),
              ),
            ),
            
            // Traffic legend (bottom left)
            if (widget.showTraffic && _trafficVisible && trafficState != null && trafficState.cells.isNotEmpty)
              Positioned(
                bottom: 12,
                left: 12,
                child: _buildTrafficLegend(),
              ),
            
            // Report event FAB (bottom center)
            if (widget.showTraffic)
              Positioned(
                bottom: 12,
                left: 0,
                right: 0,
                child: Center(
                  child: GestureDetector(
                    onTap: () => showQuickReportSheet(
                      context,
                      latitude: _currentLocation.latitude,
                      longitude: _currentLocation.longitude,
                      // TODO: pass real speed from GPS provider
                      currentSpeedKmh: null,
                    ),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [DelivrColors.primary, DelivrColors.primaryLight],
                        ),
                        borderRadius: BorderRadius.circular(24),
                        boxShadow: [
                          BoxShadow(
                            color: DelivrColors.primary.withValues(alpha: 0.3),
                            blurRadius: 12,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.flash_on, color: Colors.white, size: 18),
                          SizedBox(width: 6),
                          Text(
                            'Signaler ⚡',
                            style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildCourierMarker() {
    return Stack(
      alignment: Alignment.center,
      children: [
        // Pulsing circle
        Container(
          width: 60,
          height: 60,
          decoration: BoxDecoration(
            color: DelivrColors.primary.withValues(alpha: 0.2),
            shape: BoxShape.circle,
          ),
        ),
        // Inner circle
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: DelivrColors.primary,
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 3),
            boxShadow: [
              BoxShadow(
                color: DelivrColors.primary.withValues(alpha: 0.4),
                blurRadius: 10,
                spreadRadius: 2,
              ),
            ],
          ),
          child: const Icon(
            Icons.delivery_dining,
            color: Colors.white,
            size: 22,
          ),
        ),
      ],
    );
  }
  
  Widget _buildDeliveryMarker(MapDeliveryMarker dm) {
    // Get marker color based on status
    Color markerColor;
    switch (dm.status.toUpperCase()) {
      case 'ASSIGNED':
        markerColor = DelivrColors.warning;
        break;
      case 'PICKED_UP':
      case 'IN_TRANSIT':
        markerColor = DelivrColors.info;
        break;
      case 'COMPLETED':
        markerColor = DelivrColors.success;
        break;
      default:
        markerColor = DelivrColors.textSecondary;
    }
    
    return Column(
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: markerColor,
            shape: BoxShape.circle,
            border: Border.all(color: Colors.white, width: 2),
            boxShadow: [
              BoxShadow(
                color: markerColor.withValues(alpha: 0.4),
                blurRadius: 6,
              ),
            ],
          ),
          child: Icon(
            dm.isPickup ? Icons.inventory_2 : Icons.location_on,
            color: Colors.white,
            size: 16,
          ),
        ),
        // Pin pointer
        Container(
          width: 0,
          height: 0,
          decoration: BoxDecoration(
            border: Border(
              left: BorderSide(color: Colors.transparent, width: 6),
              right: BorderSide(color: Colors.transparent, width: 6),
              top: BorderSide(color: markerColor, width: 8),
            ),
          ),
        ),
      ],
    );
  }
  // ==========================
  // Traffic UI components
  // ==========================
  
  Widget _buildTrafficToggle(TrafficHeatmapState? state) {
    return GestureDetector(
      onTap: () => setState(() => _trafficVisible = !_trafficVisible),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
        decoration: BoxDecoration(
          color: _trafficVisible ? Colors.blue.shade700 : Colors.white.withValues(alpha: 0.95),
          borderRadius: BorderRadius.circular(8),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.15),
              blurRadius: 4,
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.traffic,
              size: 14,
              color: _trafficVisible ? Colors.white : Colors.grey.shade600,
            ),
            const SizedBox(width: 3),
            Text(
              'Trafic',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: _trafficVisible ? Colors.white : Colors.grey.shade600,
              ),
            ),
            if (state?.isLoading == true) ...[
              const SizedBox(width: 4),
              SizedBox(
                width: 8,
                height: 8,
                child: CircularProgressIndicator(
                  strokeWidth: 1.5,
                  color: _trafficVisible ? Colors.white : Colors.grey,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
  
  Widget _buildTrafficStats(TrafficStats stats) {
    return Container(
      margin: const EdgeInsets.only(top: 4),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 4,
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(stats.overallLevel.emoji, style: const TextStyle(fontSize: 12)),
          const SizedBox(width: 3),
          Text(
            '${stats.avgCitySpeed.toStringAsFixed(0)} km/h',
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.bold,
              color: Color(stats.overallLevel.colorValue),
            ),
          ),
          const SizedBox(width: 6),
          Icon(Icons.people, size: 10, color: Colors.grey.shade600),
          const SizedBox(width: 2),
          Text(
            '${stats.onlineCouriers}',
            style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
          ),
        ],
      ),
    );
  }
  
  Widget _buildTrafficLegend() {
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 4,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          _legendRow(TrafficLevel.fluide),
          _legendRow(TrafficLevel.modere),
          _legendRow(TrafficLevel.dense),
          _legendRow(TrafficLevel.bloque),
        ],
      ),
    );
  }
  
  Widget _legendRow(TrafficLevel level) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(
              color: Color(level.colorValue).withValues(alpha: level.opacity),
              border: Border.all(color: Color(level.colorValue), width: 0.5),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 4),
          Text(
            level.label,
            style: TextStyle(fontSize: 9, color: Colors.grey.shade700),
          ),
        ],
      ),
    );
  }
}

/// Data class for delivery markers on the map
class MapDeliveryMarker {
  final String id;
  final double latitude;
  final double longitude;
  final String status;
  final String recipientName;
  final bool isPickup;
  
  const MapDeliveryMarker({
    required this.id,
    required this.latitude,
    required this.longitude,
    required this.status,
    required this.recipientName,
    this.isPickup = false,
  });
}
