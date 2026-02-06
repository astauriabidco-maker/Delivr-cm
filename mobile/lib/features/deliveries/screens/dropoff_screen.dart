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

/// Dropoff confirmation screen
class DropoffScreen extends ConsumerStatefulWidget {
  final String deliveryId;

  const DropoffScreen({
    super.key,
    required this.deliveryId,
  });

  @override
  ConsumerState<DropoffScreen> createState() => _DropoffScreenState();
}

class _DropoffScreenState extends ConsumerState<DropoffScreen> {
  final _otpController = TextEditingController();
  bool _isOtpValid = false;

  @override
  void initState() {
    super.initState();
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
        title: const Text('Confirmation Livraison'),
        backgroundColor: DelivrColors.success,
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
          _buildStatusBanner(delivery),
          const SizedBox(height: 16),

          // Dropoff Address
          AddressCard(
            icon: Icons.flag,
            label: 'Adresse de livraison',
            address: delivery.dropoffAddress,
            iconColor: DelivrColors.success,
          ),
          const SizedBox(height: 16),

          // Recipient Contact
          ContactButton(
            name: delivery.recipientName ?? 'Destinataire',
            phone: delivery.recipientPhone,
            onCall: () => ref.read(activeDeliveryProvider.notifier).callRecipient(),
          ),
          const SizedBox(height: 24),

          // Earning Summary
          _buildEarningSummary(delivery),
          const SizedBox(height: 24),

          // OTP Section
          _buildOtpSection(delivery),
          const SizedBox(height: 24),

          // Photo Section (Proof of Delivery)
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
              onPressed: _canConfirm(state) ? () => _confirmDropoff() : null,
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
                  : Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.done_all, color: Colors.white),
                        const SizedBox(width: 8),
                        Text(
                          'CONFIRMER LA LIVRAISON',
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

  Widget _buildStatusBanner(Delivery delivery) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            DelivrColors.success,
            DelivrColors.success.withAlpha(200),
          ],
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Row(
        children: [
          Icon(Icons.local_shipping, size: 32, color: Colors.white),
          SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Livraison du colis',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                Text(
                  'Demandez le code OTP au destinataire',
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

  Widget _buildEarningSummary(Delivery delivery) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: DelivrColors.successLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: DelivrColors.success.withAlpha(100)),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: DelivrColors.success,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.attach_money,
              color: Colors.white,
              size: 28,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Votre gain pour cette course',
                  style: TextStyle(
                    color: DelivrColors.success,
                    fontSize: 13,
                  ),
                ),
                Text(
                  '${delivery.courierEarning.toStringAsFixed(0)} XAF',
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: DelivrColors.success,
                  ),
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
              Icon(Icons.pin, color: DelivrColors.success),
              SizedBox(width: 8),
              Text(
                'Code OTP de livraison',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Entrez le code à 4 chiffres fourni par le destinataire',
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
                  Icon(Icons.verified_user, color: DelivrColors.success),
                  SizedBox(width: 8),
                  Text(
                    'Preuve de livraison',
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
                  color: DelivrColors.warningLight,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  'Recommandé',
                  style: TextStyle(
                    fontSize: 11,
                    color: DelivrColors.warning,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'Prenez une photo du colis remis au destinataire',
            style: TextStyle(
              fontSize: 13,
              color: DelivrColors.textSecondary,
            ),
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
                    color: DelivrColors.success.withAlpha(100),
                    style: BorderStyle.solid,
                  ),
                  borderRadius: BorderRadius.circular(12),
                  color: DelivrColors.successLight.withAlpha(100),
                ),
                child: const Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.add_a_photo,
                        size: 36,
                        color: DelivrColors.success,
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Prendre une photo',
                        style: TextStyle(
                          color: DelivrColors.success,
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

  Future<void> _confirmDropoff() async {
    HapticFeedback.heavyImpact();
    
    final success = await ref
        .read(activeDeliveryProvider.notifier)
        .confirmDropoff(_otpController.text);
    
    if (success && mounted) {
      // Show success dialog
      await _showSuccessDialog();
    }
  }

  Future<void> _showSuccessDialog() async {
    final delivery = ref.read(activeDeliveryProvider).delivery!;
    
    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: const BoxDecoration(
                color: DelivrColors.successLight,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.check_circle,
                size: 48,
                color: DelivrColors.success,
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              '🎉 Livraison Terminée!',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '+${delivery.courierEarning.toStringAsFixed(0)} XAF',
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
                color: DelivrColors.success,
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              'ajoutés à votre wallet',
              style: TextStyle(
                color: DelivrColors.textSecondary,
              ),
            ),
          ],
        ),
        actions: [
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () {
                Navigator.of(context).pop();
                context.go('/dashboard');
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: DelivrColors.success,
              ),
              child: const Text('Retour au tableau de bord'),
            ),
          ),
        ],
      ),
    );
  }
}
