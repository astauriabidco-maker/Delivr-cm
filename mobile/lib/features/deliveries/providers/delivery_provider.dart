import 'dart:io';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/api/api_client.dart';

/// Delivery status enum
enum DeliveryStatus {
  pending,
  assigned,
  enRoutePickup,
  arrivedPickup,
  pickedUp,
  inTransit,
  arrivedDropoff,
  completed,
  cancelled,
}

const String _mobileDeliveriesPath = '/api/mobile/deliveries';
const String _mobileDeliveryPhotoUploadPath =
    '/api/mobile/uploads/delivery-photo/';

/// Delivery model
class Delivery {
  final String id;
  final DeliveryStatus status;
  final String pickupAddress;
  final String dropoffAddress;
  final double? pickupLat;
  final double? pickupLng;
  final double? dropoffLat;
  final double? dropoffLng;
  final String senderPhone;
  final String? senderName;
  final String recipientPhone;
  final String? recipientName;
  final double distanceKm;
  final double totalPrice;
  final double courierEarning;
  final String? pickupOtp;
  final String? dropoffOtp;
  final String? pickupPhotoUrl;
  final String? dropoffPhotoUrl;
  final String? notes;
  final DateTime createdAt;
  final DateTime? pickedUpAt;
  final DateTime? completedAt;

  Delivery({
    required this.id,
    required this.status,
    required this.pickupAddress,
    required this.dropoffAddress,
    this.pickupLat,
    this.pickupLng,
    this.dropoffLat,
    this.dropoffLng,
    required this.senderPhone,
    this.senderName,
    required this.recipientPhone,
    this.recipientName,
    required this.distanceKm,
    required this.totalPrice,
    required this.courierEarning,
    this.pickupOtp,
    this.dropoffOtp,
    this.pickupPhotoUrl,
    this.dropoffPhotoUrl,
    this.notes,
    required this.createdAt,
    this.pickedUpAt,
    this.completedAt,
  });

  factory Delivery.fromJson(Map<String, dynamic> json) {
    return Delivery(
      id: json['id'] ?? '',
      status: _parseStatus(json['status']),
      pickupAddress: json['pickup_address'] ?? '',
      dropoffAddress: json['dropoff_address'] ?? '',
      pickupLat: (json['pickup_lat'] as num?)?.toDouble(),
      pickupLng: (json['pickup_lng'] as num?)?.toDouble(),
      dropoffLat: (json['dropoff_lat'] as num?)?.toDouble(),
      dropoffLng: (json['dropoff_lng'] as num?)?.toDouble(),
      senderPhone: json['sender_phone'] ?? '',
      senderName: json['sender_name'],
      recipientPhone: json['recipient_phone'] ?? '',
      recipientName: json['recipient_name'],
      distanceKm: (json['distance_km'] as num?)?.toDouble() ?? 0,
      totalPrice: (json['total_price'] as num?)?.toDouble() ?? 0,
      courierEarning: (json['courier_earning'] as num?)?.toDouble() ?? 0,
      pickupOtp: json['pickup_otp'],
      dropoffOtp: json['dropoff_otp'],
      pickupPhotoUrl: json['pickup_photo_url'],
      dropoffPhotoUrl: json['proof_photo_url'] ?? json['dropoff_photo_url'],
      notes: json['notes'],
      createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
      pickedUpAt: json['picked_up_at'] != null
          ? DateTime.tryParse(json['picked_up_at'])
          : null,
      completedAt: json['completed_at'] != null
          ? DateTime.tryParse(json['completed_at'])
          : null,
    );
  }

  static DeliveryStatus _parseStatus(String? status) {
    switch (status?.toUpperCase()) {
      case 'PENDING':
        return DeliveryStatus.pending;
      case 'ASSIGNED':
        return DeliveryStatus.assigned;
      case 'EN_ROUTE_PICKUP':
        return DeliveryStatus.enRoutePickup;
      case 'ARRIVED_PICKUP':
        return DeliveryStatus.arrivedPickup;
      case 'PICKED_UP':
        return DeliveryStatus.pickedUp;
      case 'IN_TRANSIT':
        return DeliveryStatus.inTransit;
      case 'ARRIVED_DROPOFF':
        return DeliveryStatus.arrivedDropoff;
      case 'COMPLETED':
        return DeliveryStatus.completed;
      case 'CANCELLED':
        return DeliveryStatus.cancelled;
      default:
        return DeliveryStatus.pending;
    }
  }

  static String statusToApiValue(DeliveryStatus status) {
    switch (status) {
      case DeliveryStatus.pending:
        return 'PENDING';
      case DeliveryStatus.assigned:
        return 'ASSIGNED';
      case DeliveryStatus.enRoutePickup:
        return 'EN_ROUTE_PICKUP';
      case DeliveryStatus.arrivedPickup:
        return 'ARRIVED_PICKUP';
      case DeliveryStatus.pickedUp:
        return 'PICKED_UP';
      case DeliveryStatus.inTransit:
        return 'IN_TRANSIT';
      case DeliveryStatus.arrivedDropoff:
        return 'ARRIVED_DROPOFF';
      case DeliveryStatus.completed:
        return 'COMPLETED';
      case DeliveryStatus.cancelled:
        return 'CANCELLED';
    }
  }

  Delivery copyWith({
    DeliveryStatus? status,
    String? pickupPhotoUrl,
    String? dropoffPhotoUrl,
    DateTime? pickedUpAt,
    DateTime? completedAt,
  }) {
    return Delivery(
      id: id,
      status: status ?? this.status,
      pickupAddress: pickupAddress,
      dropoffAddress: dropoffAddress,
      pickupLat: pickupLat,
      pickupLng: pickupLng,
      dropoffLat: dropoffLat,
      dropoffLng: dropoffLng,
      senderPhone: senderPhone,
      senderName: senderName,
      recipientPhone: recipientPhone,
      recipientName: recipientName,
      distanceKm: distanceKm,
      totalPrice: totalPrice,
      courierEarning: courierEarning,
      pickupOtp: pickupOtp,
      dropoffOtp: dropoffOtp,
      pickupPhotoUrl: pickupPhotoUrl ?? this.pickupPhotoUrl,
      dropoffPhotoUrl: dropoffPhotoUrl ?? this.dropoffPhotoUrl,
      notes: notes,
      createdAt: createdAt,
      pickedUpAt: pickedUpAt ?? this.pickedUpAt,
      completedAt: completedAt ?? this.completedAt,
    );
  }
}

/// Active delivery state
class ActiveDeliveryState {
  final Delivery? delivery;
  final bool isLoading;
  final String? error;
  final File? pendingPhoto;
  final bool isSubmitting;
  final double? lastWalletDelta;
  final double? lastWalletBalance;

  const ActiveDeliveryState({
    this.delivery,
    this.isLoading = false,
    this.error,
    this.pendingPhoto,
    this.isSubmitting = false,
    this.lastWalletDelta,
    this.lastWalletBalance,
  });

  ActiveDeliveryState copyWith({
    Delivery? delivery,
    bool? isLoading,
    String? error,
    File? pendingPhoto,
    bool? isSubmitting,
    double? lastWalletDelta,
    double? lastWalletBalance,
    bool clearPhoto = false,
    bool clearError = false,
    bool clearWalletResult = false,
  }) {
    return ActiveDeliveryState(
      delivery: delivery ?? this.delivery,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      pendingPhoto: clearPhoto ? null : (pendingPhoto ?? this.pendingPhoto),
      isSubmitting: isSubmitting ?? this.isSubmitting,
      lastWalletDelta: clearWalletResult
          ? null
          : (lastWalletDelta ?? this.lastWalletDelta),
      lastWalletBalance: clearWalletResult
          ? null
          : (lastWalletBalance ?? this.lastWalletBalance),
    );
  }
}

/// Active delivery provider
final activeDeliveryProvider =
    StateNotifierProvider<ActiveDeliveryNotifier, ActiveDeliveryState>((ref) {
      return ActiveDeliveryNotifier(ref);
    });

class ActiveDeliveryNotifier extends StateNotifier<ActiveDeliveryState> {
  final Ref _ref;
  final ImagePicker _imagePicker = ImagePicker();

  ActiveDeliveryNotifier(this._ref) : super(const ActiveDeliveryState());

  /// Load active delivery details
  Future<void> loadDelivery(String deliveryId) async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      final api = _ref.read(apiClientProvider);
      final response = await api.get('$_mobileDeliveriesPath/$deliveryId/');

      if (response.success && response.data != null) {
        state = state.copyWith(
          delivery: Delivery.fromJson(response.data!),
          isLoading: false,
        );
      } else {
        state = state.copyWith(
          isLoading: false,
          error: response.error ?? 'Erreur de chargement',
        );
      }
    } catch (e) {
      state = state.copyWith(isLoading: false, error: 'Erreur: $e');
    }
  }

  /// Update delivery status
  Future<bool> updateStatus(DeliveryStatus newStatus) async {
    state = state.copyWith(isSubmitting: true, clearError: true);

    try {
      final api = _ref.read(apiClientProvider);
      final response = await api.patch(
        '$_mobileDeliveriesPath/${state.delivery!.id}/status/',
        data: {'status': Delivery.statusToApiValue(newStatus)},
      );

      if (response.success) {
        state = state.copyWith(
          delivery: state.delivery!.copyWith(status: newStatus),
          isSubmitting: false,
        );
        return true;
      } else {
        state = state.copyWith(
          isSubmitting: false,
          error: response.error ?? 'Erreur de mise à jour',
        );
        return false;
      }
    } catch (e) {
      state = state.copyWith(isSubmitting: false, error: 'Erreur: $e');
      return false;
    }
  }

  /// Take photo for pickup/dropoff
  Future<void> takePhoto() async {
    try {
      final XFile? image = await _imagePicker.pickImage(
        source: ImageSource.camera,
        maxWidth: 1280,
        maxHeight: 1280,
        imageQuality: 80,
      );

      if (image != null) {
        state = state.copyWith(pendingPhoto: File(image.path));
      }
    } catch (e) {
      state = state.copyWith(error: 'Erreur caméra: $e');
    }
  }

  /// Clear pending photo
  void clearPhoto() {
    state = state.copyWith(clearPhoto: true);
  }

  /// Confirm pickup with OTP and photo
  Future<bool> confirmPickup(String otp) async {
    if (state.delivery == null) return false;

    state = state.copyWith(isSubmitting: true, clearError: true);

    try {
      final api = _ref.read(apiClientProvider);

      // Upload photo if available
      String? photoUrl;
      if (state.pendingPhoto != null) {
        photoUrl = await _uploadPhoto(state.pendingPhoto!, 'pickup');
      }

      // Confirm pickup
      final response = await api.post(
        '$_mobileDeliveriesPath/${state.delivery!.id}/confirm-pickup/',
        data: {'otp': otp, if (photoUrl != null) 'photo_url': photoUrl},
      );

      if (response.success) {
        state = state.copyWith(
          delivery: state.delivery!.copyWith(
            status: DeliveryStatus.pickedUp,
            pickupPhotoUrl: photoUrl,
            pickedUpAt: DateTime.now(),
          ),
          isSubmitting: false,
          clearPhoto: true,
        );
        return true;
      } else {
        state = state.copyWith(
          isSubmitting: false,
          error: response.error ?? 'Code OTP invalide',
        );
        return false;
      }
    } catch (e) {
      state = state.copyWith(isSubmitting: false, error: 'Erreur: $e');
      return false;
    }
  }

  /// Confirm dropoff with OTP and proof of delivery
  Future<bool> confirmDropoff(String otp) async {
    if (state.delivery == null) return false;

    state = state.copyWith(isSubmitting: true, clearError: true);

    try {
      final api = _ref.read(apiClientProvider);

      // Upload photo if available
      String? photoUrl;
      if (state.pendingPhoto != null) {
        photoUrl = await _uploadPhoto(state.pendingPhoto!, 'dropoff');
      }

      // Confirm dropoff
      final response = await api.post(
        '$_mobileDeliveriesPath/${state.delivery!.id}/confirm-dropoff/',
        data: {'otp': otp, if (photoUrl != null) 'photo_url': photoUrl},
      );

      if (response.success) {
        final responseData = response.data;
        state = state.copyWith(
          delivery: state.delivery!.copyWith(
            status: DeliveryStatus.completed,
            dropoffPhotoUrl: photoUrl,
            completedAt: DateTime.now(),
          ),
          isSubmitting: false,
          clearPhoto: true,
          lastWalletDelta:
              (responseData?['wallet_delta'] as num?)?.toDouble(),
          lastWalletBalance:
              (responseData?['wallet_balance'] as num?)?.toDouble(),
        );
        return true;
      } else {
        state = state.copyWith(
          isSubmitting: false,
          error: response.error ?? 'Code OTP invalide',
        );
        return false;
      }
    } catch (e) {
      state = state.copyWith(isSubmitting: false, error: 'Erreur: $e');
      return false;
    }
  }

  /// Upload photo to server
  Future<String?> _uploadPhoto(File photo, String type) async {
    try {
      final api = _ref.read(apiClientProvider);
      final response = await api.uploadFile(
        _mobileDeliveryPhotoUploadPath,
        photo,
        fieldName: 'photo',
        extraData: {'delivery_id': state.delivery!.id, 'type': type},
      );

      if (response.success && response.data != null) {
        return response.data!['url'];
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  /// Call sender
  void callSender() {
    // Will be implemented with url_launcher
  }

  /// Call recipient
  void callRecipient() {
    // Will be implemented with url_launcher
  }

  /// Clear state
  void clear() {
    state = const ActiveDeliveryState();
  }
}
