import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../../../app/theme.dart';

/// Map widget showing courier's current location and nearby deliveries
class CourierMapWidget extends ConsumerStatefulWidget {
  final double? latitude;
  final double? longitude;
  final List<MapDeliveryMarker> deliveryMarkers;
  final double height;
  
  const CourierMapWidget({
    super.key,
    this.latitude,
    this.longitude,
    this.deliveryMarkers = const [],
    this.height = 200,
  });

  @override
  ConsumerState<CourierMapWidget> createState() => _CourierMapWidgetState();
}

class _CourierMapWidgetState extends ConsumerState<CourierMapWidget> {
  late MapController _mapController;
  // Default to Douala city center
  static const LatLng _defaultLocation = LatLng(4.0511, 9.7679);
  
  @override
  void initState() {
    super.initState();
    _mapController = MapController();
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
    return Container(
      height: widget.height,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
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
                      Colors.black.withOpacity(0.3),
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
                  color: Colors.white.withOpacity(0.95),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.1),
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
                        color: Colors.black.withOpacity(0.15),
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
            color: DelivrColors.primary.withOpacity(0.2),
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
                color: DelivrColors.primary.withOpacity(0.4),
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
                color: markerColor.withOpacity(0.4),
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
