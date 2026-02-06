import 'dart:math';
import '../../../core/demo/mock_data_provider.dart';

/// Service for optimizing delivery routes
class RouteOptimizerService {
  /// Optimize the order of deliveries using Nearest Neighbor algorithm
  /// Returns deliveries sorted in optimal order
  static List<MockDelivery> optimizeRoute(
    List<MockDelivery> deliveries, {
    double? startLat,
    double? startLng,
  }) {
    if (deliveries.length <= 1) return deliveries;

    // Start from courier's current position or first pickup
    double currentLat = startLat ?? deliveries.first.pickupLocation.lat;
    double currentLng = startLng ?? deliveries.first.pickupLocation.lng;

    final remaining = List<MockDelivery>.from(deliveries);
    final optimized = <MockDelivery>[];

    // Build the route using nearest neighbor
    while (remaining.isNotEmpty) {
      // Find nearest delivery point
      MockDelivery? nearest;
      double minDistance = double.infinity;
      bool isPickup = true;

      for (final delivery in remaining) {
        // Check pickup point
        final pickupDist = _calculateDistance(
          currentLat, currentLng,
          delivery.pickupLocation.lat, delivery.pickupLocation.lng,
        );
        
        // Only consider dropoff if already picked up
        final isAlreadyPickedUp = ['picked_up', 'in_transit', 'arrived_dropoff']
            .contains(delivery.status);
        
        if (!isAlreadyPickedUp && pickupDist < minDistance) {
          minDistance = pickupDist;
          nearest = delivery;
          isPickup = true;
        }
        
        // Check dropoff point (only if pickup done)
        if (isAlreadyPickedUp) {
          final dropoffDist = _calculateDistance(
            currentLat, currentLng,
            delivery.dropoffLocation.lat, delivery.dropoffLocation.lng,
          );
          if (dropoffDist < minDistance) {
            minDistance = dropoffDist;
            nearest = delivery;
            isPickup = false;
          }
        }
      }

      if (nearest != null) {
        optimized.add(nearest);
        remaining.remove(nearest);
        
        // Update current position
        if (isPickup) {
          currentLat = nearest.pickupLocation.lat;
          currentLng = nearest.pickupLocation.lng;
        } else {
          currentLat = nearest.dropoffLocation.lat;
          currentLng = nearest.dropoffLocation.lng;
        }
      } else {
        break;
      }
    }

    return optimized;
  }

  /// Calculate total route distance in km
  static double calculateTotalDistance(
    List<MockDelivery> deliveries, {
    double? startLat,
    double? startLng,
  }) {
    if (deliveries.isEmpty) return 0;

    double totalDistance = 0;
    double currentLat = startLat ?? deliveries.first.pickupLocation.lat;
    double currentLng = startLng ?? deliveries.first.pickupLocation.lng;

    for (final delivery in deliveries) {
      final isAlreadyPickedUp = ['picked_up', 'in_transit', 'arrived_dropoff']
          .contains(delivery.status);

      if (!isAlreadyPickedUp) {
        // Distance to pickup
        totalDistance += _calculateDistance(
          currentLat, currentLng,
          delivery.pickupLocation.lat, delivery.pickupLocation.lng,
        );
        currentLat = delivery.pickupLocation.lat;
        currentLng = delivery.pickupLocation.lng;
      }

      // Distance to dropoff
      totalDistance += _calculateDistance(
        currentLat, currentLng,
        delivery.dropoffLocation.lat, delivery.dropoffLocation.lng,
      );
      currentLat = delivery.dropoffLocation.lat;
      currentLng = delivery.dropoffLocation.lng;
    }

    return totalDistance;
  }

  /// Get the next point to navigate to
  static RoutePoint? getNextPoint(List<MockDelivery> deliveries) {
    for (final delivery in deliveries) {
      final status = delivery.status;
      
      // Needs pickup
      if (['pending', 'en_route_pickup', 'arrived_pickup'].contains(status)) {
        return RoutePoint(
          delivery: delivery,
          isPickup: true,
          lat: delivery.pickupLocation.lat,
          lng: delivery.pickupLocation.lng,
          address: delivery.pickupAddress,
          contactName: delivery.senderName,
          contactPhone: delivery.senderPhone,
        );
      }
      
      // Needs dropoff
      if (['picked_up', 'in_transit', 'arrived_dropoff'].contains(status)) {
        return RoutePoint(
          delivery: delivery,
          isPickup: false,
          lat: delivery.dropoffLocation.lat,
          lng: delivery.dropoffLocation.lng,
          address: delivery.dropoffAddress,
          contactName: delivery.recipientName,
          contactPhone: delivery.recipientPhone,
        );
      }
    }
    return null;
  }

  /// Get all route points for map display
  static List<RoutePoint> getAllPoints(List<MockDelivery> deliveries) {
    final points = <RoutePoint>[];
    
    for (final delivery in deliveries) {
      // Always add both pickup and dropoff points for visualization
      points.add(RoutePoint(
        delivery: delivery,
        isPickup: true,
        lat: delivery.pickupLocation.lat,
        lng: delivery.pickupLocation.lng,
        address: delivery.pickupAddress,
        contactName: delivery.senderName,
        contactPhone: delivery.senderPhone,
      ));

      points.add(RoutePoint(
        delivery: delivery,
        isPickup: false,
        lat: delivery.dropoffLocation.lat,
        lng: delivery.dropoffLocation.lng,
        address: delivery.dropoffAddress,
        contactName: delivery.recipientName,
        contactPhone: delivery.recipientPhone,
      ));
    }

    return points;
  }

  /// Calculate distance using Haversine formula
  static double _calculateDistance(
    double lat1, double lng1,
    double lat2, double lng2,
  ) {
    const double earthRadius = 6371; // km
    
    final dLat = _toRadians(lat2 - lat1);
    final dLng = _toRadians(lng2 - lng1);
    
    final a = sin(dLat / 2) * sin(dLat / 2) +
        cos(_toRadians(lat1)) * cos(_toRadians(lat2)) *
        sin(dLng / 2) * sin(dLng / 2);
    
    final c = 2 * atan2(sqrt(a), sqrt(1 - a));
    
    return earthRadius * c;
  }

  static double _toRadians(double degrees) => degrees * pi / 180;
}

/// Represents a point on the route
class RoutePoint {
  final MockDelivery delivery;
  final bool isPickup;
  final double lat;
  final double lng;
  final String address;
  final String contactName;
  final String contactPhone;

  RoutePoint({
    required this.delivery,
    required this.isPickup,
    required this.lat,
    required this.lng,
    required this.address,
    required this.contactName,
    required this.contactPhone,
  });

  String get label => isPickup ? 'Pickup' : 'Livraison';
  String get trackingCode => delivery.trackingCode;
}
