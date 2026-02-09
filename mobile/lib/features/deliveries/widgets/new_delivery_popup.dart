import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme.dart';
import '../../../core/demo/mock_data_provider.dart';

/// Popup widget for new delivery offers
/// Shows pickup/dropoff info with a countdown timer
class NewDeliveryPopup extends ConsumerStatefulWidget {
  final MockDelivery delivery;
  final VoidCallback onAccept;
  final VoidCallback onReject;
  final int timeoutSeconds;

  const NewDeliveryPopup({
    super.key,
    required this.delivery,
    required this.onAccept,
    required this.onReject,
    this.timeoutSeconds = 30,
  });

  @override
  ConsumerState<NewDeliveryPopup> createState() => _NewDeliveryPopupState();
}

class _NewDeliveryPopupState extends ConsumerState<NewDeliveryPopup>
    with SingleTickerProviderStateMixin {
  late int _remainingSeconds;
  Timer? _timer;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _remainingSeconds = widget.timeoutSeconds;
    _startTimer();
    
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat(reverse: true);
    
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.05).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  void _startTimer() {
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (mounted) {
        setState(() {
          _remainingSeconds--;
        });
        if (_remainingSeconds <= 0) {
          timer.cancel();
          widget.onReject();
        }
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.delivery;
    final progressValue = _remainingSeconds / widget.timeoutSeconds;
    final isUrgent = _remainingSeconds <= 10;

    return Container(
      margin: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: DelivrColors.primary.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header with timer
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: isUrgent 
                    ? [Colors.red.shade600, Colors.red.shade800]
                    : [DelivrColors.primary, DelivrColors.primaryDark],
              ),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
            ),
            child: Column(
              children: [
                Row(
                  children: [
                    ScaleTransition(
                      scale: _pulseAnimation,
                      child: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.2),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.local_shipping,
                          color: Colors.white,
                          size: 24,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Text(
                        '🚀 Nouvelle course !',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    // Timer circle
                    Stack(
                      alignment: Alignment.center,
                      children: [
                        SizedBox(
                          width: 50,
                          height: 50,
                          child: CircularProgressIndicator(
                            value: progressValue,
                            strokeWidth: 4,
                            backgroundColor: Colors.white24,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              isUrgent ? Colors.amber : Colors.white,
                            ),
                          ),
                        ),
                        Text(
                          '$_remainingSeconds',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Earnings highlight
          Container(
            padding: const EdgeInsets.symmetric(vertical: 12),
            color: Colors.green.shade50,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.monetization_on, color: Colors.green, size: 28),
                const SizedBox(width: 8),
                Text(
                  '${d.courierEarning.toStringAsFixed(0)} XAF',
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: Colors.green,
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.green.shade100,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '${d.estimatedDistanceKm.toStringAsFixed(1)} km • ${d.estimatedTimeMinutes} min',
                    style: TextStyle(
                      color: Colors.green.shade800,
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
          ),

          // Route details
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                // Pickup
                _buildLocationRow(
                  icon: Icons.store,
                  iconColor: Colors.blue,
                  title: 'Récupérer chez',
                  name: d.senderName,
                  address: '${d.pickupLocation.name} • ${d.pickupAddress}',
                ),
                
                // Line connector
                Padding(
                  padding: const EdgeInsets.only(left: 15),
                  child: Row(
                    children: [
                      Container(
                        width: 2,
                        height: 30,
                        color: Colors.grey.shade300,
                      ),
                      const Spacer(),
                    ],
                  ),
                ),
                
                // Dropoff
                _buildLocationRow(
                  icon: Icons.location_on,
                  iconColor: Colors.red,
                  title: 'Livrer à',
                  name: d.recipientName,
                  address: '${d.dropoffLocation.name} • ${d.dropoffAddress}',
                ),
              ],
            ),
          ),

          // Package info
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 16),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                Icon(_getPackageIcon(d.packageType), color: DelivrColors.primary),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _getPackageLabel(d.packageType),
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 12,
                        ),
                      ),
                      Text(
                        d.packageDescription,
                        style: TextStyle(
                          color: Colors.grey.shade600,
                          fontSize: 12,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Action buttons
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Row(
              children: [
                // Reject button
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: widget.onReject,
                    icon: const Icon(Icons.close),
                    label: const Text('Refuser'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.grey.shade700,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      side: BorderSide(color: Colors.grey.shade400),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                // Accept button
                Expanded(
                  flex: 2,
                  child: ElevatedButton.icon(
                    onPressed: widget.onAccept,
                    icon: const Icon(Icons.check),
                    label: const Text('Accepter'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLocationRow({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String name,
    required String address,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: iconColor.withValues(alpha: 0.1),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: iconColor, size: 16),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: TextStyle(
                  color: Colors.grey.shade600,
                  fontSize: 11,
                ),
              ),
              Text(
                name,
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
              ),
              Text(
                address,
                style: TextStyle(
                  color: Colors.grey.shade600,
                  fontSize: 12,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ],
    );
  }

  IconData _getPackageIcon(String type) {
    switch (type) {
      case 'food':
        return Icons.restaurant;
      case 'medical':
        return Icons.medical_services;
      case 'documents':
        return Icons.description;
      case 'clothing':
        return Icons.checkroom;
      case 'groceries':
        return Icons.shopping_bag;
      case 'fragile':
        return Icons.warning_amber;
      default:
        return Icons.inventory_2;
    }
  }

  String _getPackageLabel(String type) {
    switch (type) {
      case 'food':
        return '🍽️ Nourriture';
      case 'medical':
        return '💊 Médical';
      case 'documents':
        return '📄 Documents';
      case 'clothing':
        return '👕 Vêtements';
      case 'groceries':
        return '🛒 Courses';
      case 'fragile':
        return '⚠️ Fragile';
      default:
        return '📦 Colis';
    }
  }
}

/// Show the new delivery popup as a modal
Future<bool> showNewDeliveryPopup(
  BuildContext context, {
  required MockDelivery delivery,
  int timeoutSeconds = 30,
}) async {
  bool accepted = false;
  
  await showDialog(
    context: context,
    barrierDismissible: false,
    barrierColor: Colors.black54,
    builder: (context) => Center(
      child: NewDeliveryPopup(
        delivery: delivery,
        timeoutSeconds: timeoutSeconds,
        onAccept: () {
          accepted = true;
          Navigator.of(context).pop();
        },
        onReject: () {
          accepted = false;
          Navigator.of(context).pop();
        },
      ),
    ),
  );

  return accepted;
}
