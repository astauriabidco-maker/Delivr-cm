import 'package:flutter_test/flutter_test.dart';
import 'package:delivr_courier/features/deliveries/providers/delivery_provider.dart';

void main() {
  group('Delivery Model', () {
    test('fromJson parses all fields correctly', () {
      final json = {
        'id': '123e4567-e89b-12d3-a456-426614174000',
        'status': 'ASSIGNED',
        'pickup_address': 'Akwa, Douala',
        'dropoff_address': 'Bonapriso, Douala',
        'pickup_lat': 4.0511,
        'pickup_lng': 9.7679,
        'dropoff_lat': 4.0411,
        'dropoff_lng': 9.6879,
        'sender_phone': '+237612345678',
        'sender_name': 'Jean Dupont',
        'recipient_phone': '+237687654321',
        'recipient_name': 'Marie Claire',
        'distance_km': 5.2,
        'total_price': 1500.0,
        'courier_earning': 1200.0,
        'pickup_otp': '1234',
        'dropoff_otp': '5678',
        'notes': 'Colis fragile',
        'created_at': '2026-02-06T10:00:00Z',
      };

      final delivery = Delivery.fromJson(json);

      expect(delivery.id, '123e4567-e89b-12d3-a456-426614174000');
      expect(delivery.status, DeliveryStatus.assigned);
      expect(delivery.pickupAddress, 'Akwa, Douala');
      expect(delivery.dropoffAddress, 'Bonapriso, Douala');
      expect(delivery.senderPhone, '+237612345678');
      expect(delivery.recipientPhone, '+237687654321');
      expect(delivery.distanceKm, 5.2);
      expect(delivery.totalPrice, 1500.0);
      expect(delivery.courierEarning, 1200.0);
      expect(delivery.pickupOtp, '1234');
      expect(delivery.dropoffOtp, '5678');
    });

    test('fromJson handles missing optional fields', () {
      final json = {
        'id': 'test-id',
        'status': 'PENDING',
        'pickup_address': 'Test Address',
        'dropoff_address': 'Test Dropoff',
        'sender_phone': '+237600000000',
        'recipient_phone': '+237611111111',
        'distance_km': 0,
        'total_price': 0,
        'courier_earning': 0,
        'created_at': '2026-02-06T10:00:00Z',
      };

      final delivery = Delivery.fromJson(json);

      expect(delivery.senderName, isNull);
      expect(delivery.recipientName, isNull);
      expect(delivery.pickupLat, isNull);
      expect(delivery.pickupLng, isNull);
      expect(delivery.notes, isNull);
    });

    test('parseStatus handles all status values', () {
      expect(Delivery.fromJson({'status': 'PENDING', 'id': '', 'pickup_address': '', 'dropoff_address': '', 'sender_phone': '', 'recipient_phone': '', 'distance_km': 0, 'total_price': 0, 'courier_earning': 0, 'created_at': ''}).status, DeliveryStatus.pending);
      expect(Delivery.fromJson({'status': 'ASSIGNED', 'id': '', 'pickup_address': '', 'dropoff_address': '', 'sender_phone': '', 'recipient_phone': '', 'distance_km': 0, 'total_price': 0, 'courier_earning': 0, 'created_at': ''}).status, DeliveryStatus.assigned);
      expect(Delivery.fromJson({'status': 'EN_ROUTE_PICKUP', 'id': '', 'pickup_address': '', 'dropoff_address': '', 'sender_phone': '', 'recipient_phone': '', 'distance_km': 0, 'total_price': 0, 'courier_earning': 0, 'created_at': ''}).status, DeliveryStatus.enRoutePickup);
      expect(Delivery.fromJson({'status': 'PICKED_UP', 'id': '', 'pickup_address': '', 'dropoff_address': '', 'sender_phone': '', 'recipient_phone': '', 'distance_km': 0, 'total_price': 0, 'courier_earning': 0, 'created_at': ''}).status, DeliveryStatus.pickedUp);
      expect(Delivery.fromJson({'status': 'IN_TRANSIT', 'id': '', 'pickup_address': '', 'dropoff_address': '', 'sender_phone': '', 'recipient_phone': '', 'distance_km': 0, 'total_price': 0, 'courier_earning': 0, 'created_at': ''}).status, DeliveryStatus.inTransit);
      expect(Delivery.fromJson({'status': 'COMPLETED', 'id': '', 'pickup_address': '', 'dropoff_address': '', 'sender_phone': '', 'recipient_phone': '', 'distance_km': 0, 'total_price': 0, 'courier_earning': 0, 'created_at': ''}).status, DeliveryStatus.completed);
      expect(Delivery.fromJson({'status': 'CANCELLED', 'id': '', 'pickup_address': '', 'dropoff_address': '', 'sender_phone': '', 'recipient_phone': '', 'distance_km': 0, 'total_price': 0, 'courier_earning': 0, 'created_at': ''}).status, DeliveryStatus.cancelled);
    });

    test('copyWith updates only specified fields', () {
      final original = Delivery(
        id: 'test-id',
        status: DeliveryStatus.assigned,
        pickupAddress: 'Pickup',
        dropoffAddress: 'Dropoff',
        senderPhone: '+237600000000',
        recipientPhone: '+237611111111',
        distanceKm: 5.0,
        totalPrice: 1000,
        courierEarning: 800,
        createdAt: DateTime.now(),
      );

      final updated = original.copyWith(
        status: DeliveryStatus.pickedUp,
        pickedUpAt: DateTime.now(),
      );

      expect(updated.id, original.id);
      expect(updated.status, DeliveryStatus.pickedUp);
      expect(updated.pickupAddress, original.pickupAddress);
      expect(updated.pickedUpAt, isNotNull);
    });
  });

  group('ActiveDeliveryState', () {
    test('initial state has correct defaults', () {
      const state = ActiveDeliveryState();

      expect(state.delivery, isNull);
      expect(state.isLoading, false);
      expect(state.error, isNull);
      expect(state.pendingPhoto, isNull);
      expect(state.isSubmitting, false);
    });

    test('copyWith clears error when clearError is true', () {
      final state = const ActiveDeliveryState(error: 'Some error');
      final updated = state.copyWith(clearError: true);

      expect(updated.error, isNull);
    });

    test('copyWith clears photo when clearPhoto is true', () {
      // Note: Can't test with real File in unit test
      final state = const ActiveDeliveryState();
      final updated = state.copyWith(clearPhoto: true);

      expect(updated.pendingPhoto, isNull);
    });
  });
}
