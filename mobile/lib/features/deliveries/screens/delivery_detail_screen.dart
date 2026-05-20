import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../app/theme.dart';
import '../../../core/services/navigation_service.dart';
import '../providers/delivery_provider.dart';

class DeliveryDetailScreen extends ConsumerStatefulWidget {
  final String deliveryId;

  const DeliveryDetailScreen({super.key, required this.deliveryId});

  @override
  ConsumerState<DeliveryDetailScreen> createState() =>
      _DeliveryDetailScreenState();
}

class _DeliveryDetailScreenState extends ConsumerState<DeliveryDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(activeDeliveryProvider.notifier).loadDelivery(widget.deliveryId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(activeDeliveryProvider);
    final delivery = state.delivery;

    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Détails de la course'),
        backgroundColor: DelivrColors.surface,
        elevation: 0,
      ),
      body:
          state.isLoading
              ? const Center(child: CircularProgressIndicator())
              : delivery == null
              ? _buildErrorState(state.error ?? 'Livraison non trouvée')
              : _buildContent(delivery),
      bottomNavigationBar:
          delivery == null
              ? null
              : _buildBottomActions(context, delivery, state),
    );
  }

  Widget _buildContent(Delivery delivery) {
    return RefreshIndicator(
      onRefresh:
          () => ref
              .read(activeDeliveryProvider.notifier)
              .loadDelivery(widget.deliveryId),
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildStatusCard(delivery),
            const SizedBox(height: 24),
            const Text(
              'Itinéraire',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            _buildAddressCard(
              icon: Icons.radio_button_checked,
              iconColor: DelivrColors.primary,
              label: 'PICKUP',
              address: delivery.pickupAddress,
              lat: delivery.pickupLat,
              lng: delivery.pickupLng,
              contactName: delivery.senderName ?? 'Expéditeur',
              contactPhone: delivery.senderPhone,
            ),
            Container(
              margin: const EdgeInsets.only(left: 15),
              height: 24,
              width: 2,
              color: DelivrColors.textSecondary.withValues(alpha: 0.3),
            ),
            _buildAddressCard(
              icon: Icons.location_on,
              iconColor: DelivrColors.secondary,
              label: 'LIVRAISON',
              address: delivery.dropoffAddress,
              lat: delivery.dropoffLat,
              lng: delivery.dropoffLng,
              contactName: delivery.recipientName ?? 'Destinataire',
              contactPhone: delivery.recipientPhone,
            ),
            const SizedBox(height: 24),
            _buildPackageCard(delivery),
            const SizedBox(height: 24),
            if (delivery.notes != null && delivery.notes!.isNotEmpty)
              _buildNotesCard(delivery.notes!),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusCard(Delivery delivery) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            _statusColor(delivery.status),
            _statusColor(delivery.status).withValues(alpha: 0.8),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(_statusIcon(delivery.status), color: Colors.white),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _statusLabel(delivery.status),
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Gain: ${delivery.courierEarning.toStringAsFixed(0)} XAF',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.9),
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAddressCard({
    required IconData icon,
    required Color iconColor,
    required String label,
    required String address,
    required double? lat,
    required double? lng,
    required String contactName,
    required String contactPhone,
  }) {
    final hasCoordinates = lat != null && lng != null;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: iconColor, size: 20),
              const SizedBox(width: 8),
              Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: iconColor,
                ),
              ),
              const Spacer(),
              PopupMenuButton<String>(
                enabled: hasCoordinates,
                icon: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.navigation,
                      size: 16,
                      color:
                          hasCoordinates
                              ? DelivrColors.primary
                              : DelivrColors.textSecondary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'GPS',
                      style: TextStyle(
                        fontSize: 12,
                        color:
                            hasCoordinates
                                ? DelivrColors.primary
                                : DelivrColors.textSecondary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
                onSelected: (value) {
                  if (lat == null || lng == null) return;

                  if (value == 'google') {
                    NavigationService.navigateTo(
                      latitude: lat,
                      longitude: lng,
                      label: address,
                    );
                  } else if (value == 'waze') {
                    final uri = Uri.parse(
                      'https://waze.com/ul?ll=$lat,$lng&navigate=yes',
                    );
                    launchUrl(uri, mode: LaunchMode.externalApplication);
                  }
                },
                itemBuilder:
                    (context) => const [
                      PopupMenuItem(
                        value: 'google',
                        child: Row(
                          children: [
                            Icon(Icons.map, size: 20),
                            SizedBox(width: 12),
                            Text('Google Maps'),
                          ],
                        ),
                      ),
                      PopupMenuItem(
                        value: 'waze',
                        child: Row(
                          children: [
                            Icon(Icons.directions_car, size: 20),
                            SizedBox(width: 12),
                            Text('Waze'),
                          ],
                        ),
                      ),
                    ],
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            address,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 8),
          const Divider(height: 1),
          const SizedBox(height: 8),
          Row(
            children: [
              const Icon(Icons.person_outline, size: 16, color: Colors.grey),
              const SizedBox(width: 8),
              Expanded(
                child: Text(contactName, style: const TextStyle(fontSize: 13)),
              ),
              IconButton(
                visualDensity: VisualDensity.compact,
                onPressed:
                    contactPhone.isEmpty
                        ? null
                        : () => NavigationService.callPhone(contactPhone),
                icon: const Icon(Icons.phone, size: 18),
                color: DelivrColors.success,
              ),
              IconButton(
                visualDensity: VisualDensity.compact,
                onPressed:
                    contactPhone.isEmpty
                        ? null
                        : () => NavigationService.openWhatsApp(
                          phoneNumber: contactPhone,
                          message: 'Bonjour, je suis votre coursier RELAY237.',
                        ),
                icon: const Icon(Icons.chat, size: 18),
                color: const Color(0xFF25D366),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPackageCard(Delivery delivery) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Colis',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.05),
                blurRadius: 8,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: DelivrColors.info.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.inventory_2, color: DelivrColors.info),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      delivery.notes?.isNotEmpty == true
                          ? delivery.notes!
                          : 'Colis RELAY237',
                      style: const TextStyle(fontWeight: FontWeight.w500),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${delivery.distanceKm.toStringAsFixed(1)} km',
                      style: TextStyle(
                        color: DelivrColors.textSecondary,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildNotesCard(String notes) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: DelivrColors.warningLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: DelivrColors.warning.withValues(alpha: 0.3)),
      ),
      child: Text(notes, style: const TextStyle(fontSize: 13)),
    );
  }

  Widget _buildBottomActions(
    BuildContext context,
    Delivery delivery,
    ActiveDeliveryState state,
  ) {
    final action = _nextAction(delivery.status);

    if (action == null) {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, -5),
          ),
        ],
      ),
      child: SafeArea(
        child: Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed:
                    delivery.pickupLat == null || delivery.pickupLng == null
                        ? null
                        : () => NavigationService.navigateTo(
                          latitude: delivery.pickupLat!,
                          longitude: delivery.pickupLng!,
                          label: 'Pickup - ${delivery.pickupAddress}',
                        ),
                icon: const Icon(Icons.navigation),
                label: const Text('Naviguer'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: DelivrColors.primary,
                  side: const BorderSide(color: DelivrColors.primary),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton(
                onPressed: state.isSubmitting ? null : () => _runAction(action),
                style: ElevatedButton.styleFrom(
                  backgroundColor: DelivrColors.primary,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                child:
                    state.isSubmitting
                        ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            color: Colors.white,
                            strokeWidth: 2,
                          ),
                        )
                        : Text(action.label, textAlign: TextAlign.center),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState(String error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.error_outline,
              size: 56,
              color: DelivrColors.error,
            ),
            const SizedBox(height: 16),
            Text(error, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed:
                  () => ref
                      .read(activeDeliveryProvider.notifier)
                      .loadDelivery(widget.deliveryId),
              icon: const Icon(Icons.refresh),
              label: const Text('Réessayer'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _runAction(_DeliveryAction action) async {
    switch (action.type) {
      case _DeliveryActionType.status:
        final ok = await ref
            .read(activeDeliveryProvider.notifier)
            .updateStatus(action.status!);
        if (!mounted || ok) return;
        final error = ref.read(activeDeliveryProvider).error;
        if (error != null) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(error), backgroundColor: DelivrColors.error),
          );
        }
        return;
      case _DeliveryActionType.pickup:
        context.push('/deliveries/${widget.deliveryId}/pickup');
        return;
      case _DeliveryActionType.dropoff:
        context.push('/deliveries/${widget.deliveryId}/dropoff');
        return;
    }
  }

  _DeliveryAction? _nextAction(DeliveryStatus status) {
    switch (status) {
      case DeliveryStatus.assigned:
        return const _DeliveryAction.status(
          'Démarrer vers pickup',
          DeliveryStatus.enRoutePickup,
        );
      case DeliveryStatus.enRoutePickup:
        return const _DeliveryAction.status(
          'Je suis au pickup',
          DeliveryStatus.arrivedPickup,
        );
      case DeliveryStatus.arrivedPickup:
        return const _DeliveryAction.pickup('Confirmer retrait');
      case DeliveryStatus.pickedUp:
        return const _DeliveryAction.status(
          'Démarrer livraison',
          DeliveryStatus.inTransit,
        );
      case DeliveryStatus.inTransit:
        return const _DeliveryAction.status(
          'Je suis arrivé',
          DeliveryStatus.arrivedDropoff,
        );
      case DeliveryStatus.arrivedDropoff:
        return const _DeliveryAction.dropoff('Confirmer livraison');
      case DeliveryStatus.completed:
      case DeliveryStatus.cancelled:
      case DeliveryStatus.pending:
        return null;
    }
  }

  Color _statusColor(DeliveryStatus status) {
    switch (status) {
      case DeliveryStatus.assigned:
      case DeliveryStatus.enRoutePickup:
      case DeliveryStatus.arrivedPickup:
        return DelivrColors.primary;
      case DeliveryStatus.pickedUp:
      case DeliveryStatus.inTransit:
        return DelivrColors.info;
      case DeliveryStatus.arrivedDropoff:
      case DeliveryStatus.completed:
        return DelivrColors.success;
      case DeliveryStatus.cancelled:
        return DelivrColors.error;
      case DeliveryStatus.pending:
        return DelivrColors.textSecondary;
    }
  }

  IconData _statusIcon(DeliveryStatus status) {
    switch (status) {
      case DeliveryStatus.assigned:
        return Icons.assignment_ind;
      case DeliveryStatus.enRoutePickup:
        return Icons.directions_bike;
      case DeliveryStatus.arrivedPickup:
        return Icons.location_on;
      case DeliveryStatus.pickedUp:
        return Icons.inventory_2;
      case DeliveryStatus.inTransit:
        return Icons.local_shipping;
      case DeliveryStatus.arrivedDropoff:
        return Icons.pin_drop;
      case DeliveryStatus.completed:
        return Icons.check_circle;
      case DeliveryStatus.cancelled:
        return Icons.cancel;
      case DeliveryStatus.pending:
        return Icons.hourglass_empty;
    }
  }

  String _statusLabel(DeliveryStatus status) {
    switch (status) {
      case DeliveryStatus.assigned:
        return 'Course assignée';
      case DeliveryStatus.enRoutePickup:
        return 'En route vers le pickup';
      case DeliveryStatus.arrivedPickup:
        return 'Arrivé au pickup';
      case DeliveryStatus.pickedUp:
        return 'Colis récupéré';
      case DeliveryStatus.inTransit:
        return 'En livraison';
      case DeliveryStatus.arrivedDropoff:
        return 'Arrivé chez le client';
      case DeliveryStatus.completed:
        return 'Livraison terminée';
      case DeliveryStatus.cancelled:
        return 'Course annulée';
      case DeliveryStatus.pending:
        return 'En attente';
    }
  }
}

enum _DeliveryActionType { status, pickup, dropoff }

class _DeliveryAction {
  final String label;
  final _DeliveryActionType type;
  final DeliveryStatus? status;

  const _DeliveryAction.status(this.label, this.status)
    : type = _DeliveryActionType.status;

  const _DeliveryAction.pickup(this.label)
    : type = _DeliveryActionType.pickup,
      status = null;

  const _DeliveryAction.dropoff(this.label)
    : type = _DeliveryActionType.dropoff,
      status = null;
}
