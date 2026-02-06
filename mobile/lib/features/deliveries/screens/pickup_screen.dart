import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme.dart';
import '../providers/delivery_provider.dart';
import '../widgets/otp_input.dart';
import '../widgets/photo_preview.dart';
import '../widgets/address_card.dart';
import '../widgets/contact_button.dart';

/// Pickup confirmation screen
class PickupScreen extends ConsumerStatefulWidget {
  final String deliveryId;

  const PickupScreen({
    super.key,
    required this.deliveryId,
  });

  @override
  ConsumerState<PickupScreen> createState() => _PickupScreenState();
}

class _PickupScreenState extends ConsumerState<PickupScreen> {
  final _otpController = TextEditingController();
  bool _isOtpValid = false;

  @override
  void initState() {
    super.initState();
    // Load delivery details
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(activeDeliveryProvider.notifier).loadDelivery(widget.deliveryId);
    });
  }

  @override
  void dispose() {
    _otpController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(activeDeliveryProvider);
    final delivery = state.delivery;

    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Confirmation Retrait'),
        backgroundColor: DelivrColors.primary,
        foregroundColor: Colors.white,
      ),
      body: state.isLoading
          ? const Center(child: CircularProgressIndicator())
          : delivery == null
              ? _buildError(state.error ?? 'Livraison non trouvée')
              : _buildContent(context, delivery, state),
    );
  }

  Widget _buildContent(
    BuildContext context,
    Delivery delivery,
    ActiveDeliveryState state,
  ) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Status Banner
          _buildStatusBanner(),
          const SizedBox(height: 16),

          // Pickup Address
          AddressCard(
            icon: Icons.location_on,
            label: 'Adresse de retrait',
            address: delivery.pickupAddress,
            iconColor: DelivrColors.primary,
          ),
          const SizedBox(height: 16),

          // Sender Contact
          ContactButton(
            name: delivery.senderName ?? 'Expéditeur',
            phone: delivery.senderPhone,
            onCall: () => ref.read(activeDeliveryProvider.notifier).callSender(),
          ),
          const SizedBox(height: 24),

          // Instructions
          if (delivery.notes != null && delivery.notes!.isNotEmpty) ...[
            _buildNotesSection(delivery.notes!),
            const SizedBox(height: 24),
          ],

          // OTP Section
          _buildOtpSection(delivery),
          const SizedBox(height: 24),

          // Photo Section
          _buildPhotoSection(state),
          const SizedBox(height: 24),

          // Error message
          if (state.error != null)
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: DelivrColors.errorLight,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, color: DelivrColors.error),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      state.error!,
                      style: const TextStyle(color: DelivrColors.error),
                    ),
                  ),
                ],
              ),
            ),

          // Confirm Button
          SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton(
              onPressed: _canConfirm(state) ? () => _confirmPickup() : null,
              style: ElevatedButton.styleFrom(
                backgroundColor: DelivrColors.success,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: state.isSubmitting
                  ? const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 2,
                      ),
                    )
                  : const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.check_circle, color: Colors.white),
                        SizedBox(width: 8),
                        Text(
                          'CONFIRMER LE RETRAIT',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ],
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusBanner() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            DelivrColors.primary,
            DelivrColors.primary.withAlpha(200),
          ],
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Row(
        children: [
          Icon(Icons.inventory_2, size: 32, color: Colors.white),
          SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Retrait du colis',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                Text(
                  'Demandez le code OTP à l\'expéditeur',
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.white70,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNotesSection(String notes) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: DelivrColors.warningLight,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: DelivrColors.warning.withAlpha(100)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, color: DelivrColors.warning, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Instructions',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: DelivrColors.warning,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  notes,
                  style: const TextStyle(fontSize: 13),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildOtpSection(Delivery delivery) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: DelivrColors.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.pin, color: DelivrColors.primary),
              SizedBox(width: 8),
              Text(
                'Code OTP de retrait',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Entrez le code à 4 chiffres fourni par l\'expéditeur',
            style: TextStyle(
              fontSize: 13,
              color: DelivrColors.textSecondary,
            ),
          ),
          const SizedBox(height: 16),
          OtpInput(
            controller: _otpController,
            length: 4,
            onCompleted: (otp) {
              setState(() => _isOtpValid = otp.length == 4);
            },
            onChanged: (value) {
              setState(() => _isOtpValid = value.length == 4);
            },
          ),
        ],
      ),
    );
  }

  Widget _buildPhotoSection(ActiveDeliveryState state) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: DelivrColors.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Row(
                children: [
                  Icon(Icons.camera_alt, color: DelivrColors.primary),
                  SizedBox(width: 8),
                  Text(
                    'Photo du colis',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: DelivrColors.primaryLight,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  'Optionnel',
                  style: TextStyle(
                    fontSize: 11,
                    color: DelivrColors.primary,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          
          if (state.pendingPhoto != null)
            PhotoPreview(
              photo: state.pendingPhoto!,
              onRetake: () => ref.read(activeDeliveryProvider.notifier).takePhoto(),
              onRemove: () => ref.read(activeDeliveryProvider.notifier).clearPhoto(),
            )
          else
            InkWell(
              onTap: () => ref.read(activeDeliveryProvider.notifier).takePhoto(),
              borderRadius: BorderRadius.circular(12),
              child: Container(
                height: 120,
                decoration: BoxDecoration(
                  border: Border.all(
                    color: DelivrColors.primary.withAlpha(100),
                    style: BorderStyle.solid,
                  ),
                  borderRadius: BorderRadius.circular(12),
                  color: DelivrColors.primaryLight.withAlpha(50),
                ),
                child: const Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.add_a_photo,
                        size: 36,
                        color: DelivrColors.primary,
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Prendre une photo',
                        style: TextStyle(
                          color: DelivrColors.primary,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildError(String error) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 64, color: DelivrColors.error),
          const SizedBox(height: 16),
          Text(error, style: const TextStyle(color: DelivrColors.error)),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () => context.pop(),
            child: const Text('Retour'),
          ),
        ],
      ),
    );
  }

  bool _canConfirm(ActiveDeliveryState state) {
    return _isOtpValid && !state.isSubmitting;
  }

  Future<void> _confirmPickup() async {
    HapticFeedback.mediumImpact();
    
    final success = await ref
        .read(activeDeliveryProvider.notifier)
        .confirmPickup(_otpController.text);
    
    if (success && mounted) {
      // Show success and navigate to in-transit
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('✅ Retrait confirmé! Dirigez-vous vers la destination.'),
          backgroundColor: DelivrColors.success,
        ),
      );
      context.pop();
    }
  }
}
