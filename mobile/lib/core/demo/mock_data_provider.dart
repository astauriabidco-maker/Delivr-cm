import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Douala neighborhood data with real GPS coordinates
class Neighborhood {
  final String name;
  final double lat;
  final double lng;
  final String zone; // Douala I, II, III, etc.

  const Neighborhood({
    required this.name,
    required this.lat,
    required this.lng,
    required this.zone,
  });
}

/// Predefined neighborhoods in Douala
class DoualaNeeighborhoods {
  static const List<Neighborhood> all = [
    // Douala I
    Neighborhood(name: 'Bonanjo', lat: 4.0511, lng: 9.6945, zone: 'Douala I'),
    Neighborhood(name: 'Akwa', lat: 4.0555, lng: 9.7034, zone: 'Douala I'),
    Neighborhood(name: 'Bali', lat: 4.0489, lng: 9.7112, zone: 'Douala I'),
    Neighborhood(name: 'Bonapriso', lat: 4.0267, lng: 9.6878, zone: 'Douala I'),
    
    // Douala II
    Neighborhood(name: 'New Bell', lat: 4.0345, lng: 9.7234, zone: 'Douala II'),
    Neighborhood(name: 'Nkongmondo', lat: 4.0312, lng: 9.7189, zone: 'Douala II'),
    
    // Douala III
    Neighborhood(name: 'Makepe', lat: 4.0678, lng: 9.7456, zone: 'Douala III'),
    Neighborhood(name: 'Logbessou', lat: 4.0756, lng: 9.7623, zone: 'Douala III'),
    Neighborhood(name: 'Bonamoussadi', lat: 4.0823, lng: 9.7345, zone: 'Douala III'),
    Neighborhood(name: 'Kotto', lat: 4.0934, lng: 9.7512, zone: 'Douala III'),
    
    // Douala IV
    Neighborhood(name: 'Bonaberi', lat: 4.0645, lng: 9.6678, zone: 'Douala IV'),
    Neighborhood(name: 'Sodiko', lat: 4.0756, lng: 9.6534, zone: 'Douala IV'),
    
    // Douala V
    Neighborhood(name: 'Ndokotti', lat: 4.0456, lng: 9.7389, zone: 'Douala V'),
    Neighborhood(name: 'Bepanda', lat: 4.0512, lng: 9.7445, zone: 'Douala V'),
    Neighborhood(name: 'Yassa', lat: 4.0234, lng: 9.7678, zone: 'Douala V'),
  ];

  static Neighborhood random() {
    final index = DateTime.now().millisecondsSinceEpoch % all.length;
    return all[index];
  }

  static Neighborhood getByName(String name) {
    return all.firstWhere(
      (n) => n.name.toLowerCase() == name.toLowerCase(),
      orElse: () => all.first,
    );
  }
}

/// Mock delivery data for testing
class MockDelivery {
  final String id;
  final String trackingCode;
  final String senderName;
  final String senderPhone;
  final Neighborhood pickupLocation;
  final String pickupAddress;
  final String recipientName;
  final String recipientPhone;
  final Neighborhood dropoffLocation;
  final String dropoffAddress;
  final String packageType;
  final String packageDescription;
  final double price;
  final double courierEarning;
  final String status;
  final DateTime createdAt;
  final DateTime? acceptedAt;
  final double estimatedDistanceKm;
  final int estimatedTimeMinutes;

  const MockDelivery({
    required this.id,
    required this.trackingCode,
    required this.senderName,
    required this.senderPhone,
    required this.pickupLocation,
    required this.pickupAddress,
    required this.recipientName,
    required this.recipientPhone,
    required this.dropoffLocation,
    required this.dropoffAddress,
    required this.packageType,
    required this.packageDescription,
    required this.price,
    required this.courierEarning,
    required this.status,
    required this.createdAt,
    this.acceptedAt,
    required this.estimatedDistanceKm,
    required this.estimatedTimeMinutes,
  });

  Map<String, dynamic> toJson() => {
    'id': id,
    'tracking_code': trackingCode,
    'sender_name': senderName,
    'sender_phone': senderPhone,
    'pickup_lat': pickupLocation.lat,
    'pickup_lng': pickupLocation.lng,
    'pickup_address': pickupAddress,
    'pickup_neighborhood': pickupLocation.name,
    'recipient_name': recipientName,
    'recipient_phone': recipientPhone,
    'dropoff_lat': dropoffLocation.lat,
    'dropoff_lng': dropoffLocation.lng,
    'dropoff_address': dropoffAddress,
    'dropoff_neighborhood': dropoffLocation.name,
    'package_type': packageType,
    'package_description': packageDescription,
    'price': price,
    'courier_earning': courierEarning,
    'status': status,
    'created_at': createdAt.toIso8601String(),
    'accepted_at': acceptedAt?.toIso8601String(),
    'estimated_distance_km': estimatedDistanceKm,
    'estimated_time_minutes': estimatedTimeMinutes,
  };
}

/// Mock data provider with realistic test deliveries
class MockDataProvider {
  static final List<MockDelivery> _deliveries = [
    // 1. Course active - en route vers pickup
    MockDelivery(
      id: 'DEL-001',
      trackingCode: 'DLR-2026-A1B2C3',
      senderName: 'Restaurant Le Gourmet',
      senderPhone: '+237699001122',
      pickupLocation: DoualaNeeighborhoods.getByName('Akwa'),
      pickupAddress: 'Rue Joss, Face Hôtel Sawa',
      recipientName: 'Marie Ngono',
      recipientPhone: '+237677889900',
      dropoffLocation: DoualaNeeighborhoods.getByName('Makepe'),
      dropoffAddress: 'Carrefour Andem, 2ème entrée à droite',
      packageType: 'food',
      packageDescription: 'Commande repas - Ndolè + Miondo',
      price: 2500,
      courierEarning: 1250,
      status: 'en_route_pickup',
      createdAt: DateTime.now().subtract(const Duration(minutes: 15)),
      acceptedAt: DateTime.now().subtract(const Duration(minutes: 10)),
      estimatedDistanceKm: 4.2,
      estimatedTimeMinutes: 18,
    ),

    // 2. Course active - arrivé au pickup
    MockDelivery(
      id: 'DEL-002',
      trackingCode: 'DLR-2026-D4E5F6',
      senderName: 'Boutique Mode Express',
      senderPhone: '+237699112233',
      pickupLocation: DoualaNeeighborhoods.getByName('Bonapriso'),
      pickupAddress: 'Avenue De Gaulle, Immeuble Rose',
      recipientName: 'Jean-Paul Mbarga',
      recipientPhone: '+237655443322',
      dropoffLocation: DoualaNeeighborhoods.getByName('Bonamoussadi'),
      dropoffAddress: 'Santa Barbara, près du stade',
      packageType: 'clothing',
      packageDescription: 'Vêtements - 2 chemises + 1 pantalon',
      price: 3000,
      courierEarning: 1500,
      status: 'arrived_pickup',
      createdAt: DateTime.now().subtract(const Duration(minutes: 25)),
      acceptedAt: DateTime.now().subtract(const Duration(minutes: 20)),
      estimatedDistanceKm: 5.8,
      estimatedTimeMinutes: 22,
    ),

    // 3. Course active - en transit
    MockDelivery(
      id: 'DEL-003',
      trackingCode: 'DLR-2026-G7H8I9',
      senderName: 'Pharmacie Centrale',
      senderPhone: '+237699223344',
      pickupLocation: DoualaNeeighborhoods.getByName('Bonanjo'),
      pickupAddress: 'Boulevard de la Liberté',
      recipientName: 'Dr. Aimée Fotso',
      recipientPhone: '+237677112233',
      dropoffLocation: DoualaNeeighborhoods.getByName('Bepanda'),
      dropoffAddress: 'Rue des Manguiers, Maison bleue',
      packageType: 'medical',
      packageDescription: 'Médicaments urgents',
      price: 3500,
      courierEarning: 1750,
      status: 'in_transit',
      createdAt: DateTime.now().subtract(const Duration(minutes: 35)),
      acceptedAt: DateTime.now().subtract(const Duration(minutes: 30)),
      estimatedDistanceKm: 6.1,
      estimatedTimeMinutes: 25,
    ),

    // 4. Course en attente d'acceptation
    MockDelivery(
      id: 'DEL-004',
      trackingCode: 'DLR-2026-J1K2L3',
      senderName: 'Supermarché Casino',
      senderPhone: '+237699334455',
      pickupLocation: DoualaNeeighborhoods.getByName('Akwa'),
      pickupAddress: 'Boulevard Ahidjo, près Total',
      recipientName: 'Famille Tchatchouang',
      recipientPhone: '+237655667788',
      dropoffLocation: DoualaNeeighborhoods.getByName('Logbessou'),
      dropoffAddress: 'Entrée Cité des Palmiers',
      packageType: 'groceries',
      packageDescription: 'Courses alimentaires - 3 sacs',
      price: 3000,
      courierEarning: 1500,
      status: 'pending',
      createdAt: DateTime.now().subtract(const Duration(minutes: 2)),
      estimatedDistanceKm: 7.3,
      estimatedTimeMinutes: 28,
    ),

    // 5. Course en attente d'acceptation
    MockDelivery(
      id: 'DEL-005',
      trackingCode: 'DLR-2026-M4N5O6',
      senderName: 'Librairie du Savoir',
      senderPhone: '+237699445566',
      pickupLocation: DoualaNeeighborhoods.getByName('Bali'),
      pickupAddress: 'Rue de la Joie, 3ème étage',
      recipientName: 'Étudiant Eric Kenfack',
      recipientPhone: '+237699887766',
      dropoffLocation: DoualaNeeighborhoods.getByName('Ndokotti'),
      dropoffAddress: 'Cité universitaire, bloc C',
      packageType: 'documents',
      packageDescription: 'Livres scolaires - 5 manuels',
      price: 2000,
      courierEarning: 1000,
      status: 'pending',
      createdAt: DateTime.now().subtract(const Duration(minutes: 1)),
      estimatedDistanceKm: 3.8,
      estimatedTimeMinutes: 15,
    ),

    // 6. Course terminée aujourd'hui
    MockDelivery(
      id: 'DEL-006',
      trackingCode: 'DLR-2026-P7Q8R9',
      senderName: 'Boulangerie La Mie',
      senderPhone: '+237699556677',
      pickupLocation: DoualaNeeighborhoods.getByName('Bonapriso'),
      pickupAddress: 'Rue Franqueville',
      recipientName: 'Bureau SABC',
      recipientPhone: '+237233445566',
      dropoffLocation: DoualaNeeighborhoods.getByName('Bonanjo'),
      dropoffAddress: 'Immeuble BICEC, RDC',
      packageType: 'food',
      packageDescription: 'Plateaux sandwichs - Réunion',
      price: 4000,
      courierEarning: 2000,
      status: 'completed',
      createdAt: DateTime.now().subtract(const Duration(hours: 3)),
      acceptedAt: DateTime.now().subtract(const Duration(hours: 3)),
      estimatedDistanceKm: 2.1,
      estimatedTimeMinutes: 10,
    ),

    // 7. Course terminée hier
    MockDelivery(
      id: 'DEL-007',
      trackingCode: 'DLR-2026-S1T2U3',
      senderName: 'Bijouterie Prestige',
      senderPhone: '+237699667788',
      pickupLocation: DoualaNeeighborhoods.getByName('Akwa'),
      pickupAddress: 'Galerie Akwa Palace',
      recipientName: 'Mme Essono Christine',
      recipientPhone: '+237677554433',
      dropoffLocation: DoualaNeeighborhoods.getByName('Bonapriso'),
      dropoffAddress: 'Résidence Les Cocotiers',
      packageType: 'fragile',
      packageDescription: 'Coffret bijoux - FRAGILE',
      price: 5000,
      courierEarning: 2500,
      status: 'completed',
      createdAt: DateTime.now().subtract(const Duration(days: 1)),
      acceptedAt: DateTime.now().subtract(const Duration(days: 1)),
      estimatedDistanceKm: 1.8,
      estimatedTimeMinutes: 8,
    ),

    // 8. Course express premium
    MockDelivery(
      id: 'DEL-008',
      trackingCode: 'DLR-2026-V4W5X6',
      senderName: 'Notaire Maître Atangana',
      senderPhone: '+237699778899',
      pickupLocation: DoualaNeeighborhoods.getByName('Bonanjo'),
      pickupAddress: 'Avenue des Cocotiers, Cabinet notarial',
      recipientName: 'Tribunal de Grande Instance',
      recipientPhone: '+237233112233',
      dropoffLocation: DoualaNeeighborhoods.getByName('Bonanjo'),
      dropoffAddress: 'Palais de Justice',
      packageType: 'documents',
      packageDescription: 'Actes notariés URGENT',
      price: 2500,
      courierEarning: 1500,
      status: 'pending',
      createdAt: DateTime.now(),
      estimatedDistanceKm: 0.8,
      estimatedTimeMinutes: 5,
    ),
  ];

  /// Get active deliveries (assigned to courier)
  static List<MockDelivery> getActiveDeliveries() {
    return _deliveries.where((d) => 
      ['en_route_pickup', 'arrived_pickup', 'picked_up', 'in_transit', 'arrived_dropoff']
        .contains(d.status)
    ).toList();
  }

  /// Get pending deliveries (available to accept)
  static List<MockDelivery> getPendingDeliveries() {
    return _deliveries.where((d) => d.status == 'pending').toList();
  }

  /// Get completed deliveries
  static List<MockDelivery> getCompletedDeliveries() {
    return _deliveries.where((d) => d.status == 'completed').toList();
  }

  /// Get all deliveries
  static List<MockDelivery> getAllDeliveries() => _deliveries;

  /// Get a random pending delivery for simulation
  static MockDelivery? getRandomPendingDelivery() {
    final pending = getPendingDeliveries();
    if (pending.isEmpty) return null;
    final index = DateTime.now().millisecondsSinceEpoch % pending.length;
    return pending[index];
  }

  /// Generate a new random delivery for simulation
  static MockDelivery generateNewDelivery() {
    final pickup = DoualaNeeighborhoods.all[
      DateTime.now().millisecondsSinceEpoch % DoualaNeeighborhoods.all.length
    ];
    final dropoff = DoualaNeeighborhoods.all[
      (DateTime.now().millisecondsSinceEpoch + 5) % DoualaNeeighborhoods.all.length
    ];

    final senders = [
      ('Restaurant Chez Mama', '+237699111111', 'food', 'Commande repas'),
      ('Pharmacie du Port', '+237699222222', 'medical', 'Médicaments'),
      ('Boutique Tendance', '+237699333333', 'clothing', 'Vêtements'),
      ('Express Docs', '+237699444444', 'documents', 'Documents importants'),
      ('Marché Central', '+237699555555', 'groceries', 'Courses diverses'),
    ];

    final recipients = [
      ('Client VIP', '+237677111111'),
      ('Bureau CAMTEL', '+237677222222'),
      ('Mme Dupont', '+237677333333'),
      ('Famille Mbarga', '+237677444444'),
      ('Résidence Palm', '+237677555555'),
    ];

    final senderIndex = DateTime.now().second % senders.length;
    final recipientIndex = DateTime.now().millisecond % recipients.length;
    final sender = senders[senderIndex];
    final recipient = recipients[recipientIndex];

    // Calculate simple distance (Haversine approximation)
    final distKm = _calculateDistance(
      pickup.lat, pickup.lng,
      dropoff.lat, dropoff.lng,
    );
    final timeMin = (distKm / 0.5).round(); // ~30km/h average

    final basePrice = 1500 + (distKm * 200).round();
    final earning = (basePrice * 0.5).round();

    return MockDelivery(
      id: 'DEL-NEW-${DateTime.now().millisecondsSinceEpoch}',
      trackingCode: 'DLR-${DateTime.now().year}-${DateTime.now().millisecondsSinceEpoch.toString().substring(8)}',
      senderName: sender.$1,
      senderPhone: sender.$2,
      pickupLocation: pickup,
      pickupAddress: 'Près de ${pickup.name} centre',
      recipientName: recipient.$1,
      recipientPhone: recipient.$2,
      dropoffLocation: dropoff,
      dropoffAddress: 'Quartier ${dropoff.name}',
      packageType: sender.$3,
      packageDescription: sender.$4,
      price: basePrice.toDouble(),
      courierEarning: earning.toDouble(),
      status: 'pending',
      createdAt: DateTime.now(),
      estimatedDistanceKm: distKm,
      estimatedTimeMinutes: timeMin,
    );
  }

  /// Haversine formula for distance calculation
  static double _calculateDistance(double lat1, double lng1, double lat2, double lng2) {
    const double earthRadius = 6371; // km
    final dLat = _toRadians(lat2 - lat1);
    final dLng = _toRadians(lng2 - lng1);
    final a = _sin(dLat / 2) * _sin(dLat / 2) +
        _cos(_toRadians(lat1)) * _cos(_toRadians(lat2)) *
        _sin(dLng / 2) * _sin(dLng / 2);
    final c = 2 * _atan2(_sqrt(a), _sqrt(1 - a));
    return earthRadius * c;
  }

  static double _toRadians(double deg) => deg * 3.14159 / 180;
  static double _sin(double x) => _taylorSin(x);
  static double _cos(double x) => _taylorCos(x);
  static double _sqrt(double x) => x > 0 ? _babylonianSqrt(x) : 0;
  static double _atan2(double y, double x) => _simpleAtan2(y, x);

  // Simple implementations to avoid dart:math on web
  static double _taylorSin(double x) {
    x = x % (2 * 3.14159);
    double result = x;
    double term = x;
    for (int n = 1; n <= 7; n++) {
      term *= -x * x / ((2 * n) * (2 * n + 1));
      result += term;
    }
    return result;
  }

  static double _taylorCos(double x) {
    x = x % (2 * 3.14159);
    double result = 1;
    double term = 1;
    for (int n = 1; n <= 7; n++) {
      term *= -x * x / ((2 * n - 1) * (2 * n));
      result += term;
    }
    return result;
  }

  static double _babylonianSqrt(double x) {
    double guess = x / 2;
    for (int i = 0; i < 10; i++) {
      guess = (guess + x / guess) / 2;
    }
    return guess;
  }

  static double _simpleAtan2(double y, double x) {
    if (x > 0) return _taylorAtan(y / x);
    if (x < 0 && y >= 0) return _taylorAtan(y / x) + 3.14159;
    if (x < 0 && y < 0) return _taylorAtan(y / x) - 3.14159;
    if (x == 0 && y > 0) return 3.14159 / 2;
    if (x == 0 && y < 0) return -3.14159 / 2;
    return 0;
  }

  static double _taylorAtan(double x) {
    if (x.abs() > 1) {
      return (x > 0 ? 1 : -1) * 3.14159 / 2 - _taylorAtan(1 / x);
    }
    double result = x;
    double term = x;
    for (int n = 1; n <= 15; n++) {
      term *= -x * x;
      result += term / (2 * n + 1);
    }
    return result;
  }
}

/// Provider for pending deliveries (available to accept)
final pendingDeliveriesProvider = StateProvider<List<MockDelivery>>((ref) {
  return MockDataProvider.getPendingDeliveries();
});

/// Provider for demo mode toggle
final demoModeProvider = StateProvider<bool>((ref) => true);

/// Provider for simulating new delivery arrival
final newDeliveryNotificationProvider = StateProvider<MockDelivery?>((ref) => null);

/// Provider for accepted deliveries (active courses)
final acceptedDeliveriesProvider = StateNotifierProvider<AcceptedDeliveriesNotifier, List<MockDelivery>>((ref) {
  return AcceptedDeliveriesNotifier();
});

/// Notifier for managing accepted deliveries
class AcceptedDeliveriesNotifier extends StateNotifier<List<MockDelivery>> {
  AcceptedDeliveriesNotifier() : super(MockDataProvider.getActiveDeliveries());

  /// Accept a new delivery
  void acceptDelivery(MockDelivery delivery) {
    // Create an "accepted" version with updated status
    final acceptedDelivery = MockDelivery(
      id: delivery.id,
      trackingCode: delivery.trackingCode,
      senderName: delivery.senderName,
      senderPhone: delivery.senderPhone,
      pickupLocation: delivery.pickupLocation,
      pickupAddress: delivery.pickupAddress,
      recipientName: delivery.recipientName,
      recipientPhone: delivery.recipientPhone,
      dropoffLocation: delivery.dropoffLocation,
      dropoffAddress: delivery.dropoffAddress,
      packageType: delivery.packageType,
      packageDescription: delivery.packageDescription,
      price: delivery.price,
      courierEarning: delivery.courierEarning,
      status: 'en_route_pickup', // Now active
      createdAt: delivery.createdAt,
      acceptedAt: DateTime.now(),
      estimatedDistanceKm: delivery.estimatedDistanceKm,
      estimatedTimeMinutes: delivery.estimatedTimeMinutes,
    );
    
    state = [acceptedDelivery, ...state];
  }

  /// Update delivery status
  void updateStatus(String deliveryId, String newStatus) {
    state = state.map((d) {
      if (d.id == deliveryId) {
        return MockDelivery(
          id: d.id,
          trackingCode: d.trackingCode,
          senderName: d.senderName,
          senderPhone: d.senderPhone,
          pickupLocation: d.pickupLocation,
          pickupAddress: d.pickupAddress,
          recipientName: d.recipientName,
          recipientPhone: d.recipientPhone,
          dropoffLocation: d.dropoffLocation,
          dropoffAddress: d.dropoffAddress,
          packageType: d.packageType,
          packageDescription: d.packageDescription,
          price: d.price,
          courierEarning: d.courierEarning,
          status: newStatus,
          createdAt: d.createdAt,
          acceptedAt: d.acceptedAt,
          estimatedDistanceKm: d.estimatedDistanceKm,
          estimatedTimeMinutes: d.estimatedTimeMinutes,
        );
      }
      return d;
    }).toList();
  }

  /// Get active deliveries count (for stats)
  int get activeCount => state.where((d) => 
    ['en_route_pickup', 'arrived_pickup', 'picked_up', 'in_transit', 'arrived_dropoff']
      .contains(d.status)
  ).length;

  /// Get total earnings for today
  double get todayEarnings => state
    .where((d) => d.status == 'completed' && 
      d.acceptedAt != null && 
      d.acceptedAt!.day == DateTime.now().day)
    .fold(0.0, (sum, d) => sum + d.courierEarning);
}

