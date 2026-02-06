import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../app/router.dart';
import '../../../app/theme.dart';
import '../../../core/services/navigation_service.dart';

class DeliveryDetailScreen extends ConsumerWidget {
  final String deliveryId;

  const DeliveryDetailScreen({super.key, required this.deliveryId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Mock delivery data - would be loaded from API
    final delivery = {
      'id': deliveryId,
      'status': 'ASSIGNED',
      'pickup_address': 'Akwa, Rue Joss, Douala',
      'pickup_lat': 4.0510,
      'pickup_lng': 9.7679,
      'dropoff_address': 'Bonapriso, Avenue De Gaulle, Douala',
      'dropoff_lat': 4.0197,
      'dropoff_lng': 9.6863,
      'sender_name': 'Jean Dupont',
      'sender_phone': '+237699123456',
      'recipient_name': 'Marie Claire',
      'recipient_phone': '+237677654321',
      'package_description': 'Petit colis - Documents',
      'earning': 1500.0,
      'distance': 5.2,
    };

    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Détails de la course'),
        backgroundColor: DelivrColors.surface,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Status card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [DelivrColors.primary, DelivrColors.primary.withOpacity(0.8)],
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
                      color: Colors.white.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(Icons.local_shipping, color: Colors.white, size: 28),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'En attente de pickup',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Gain: ${(delivery['earning'] as double).toStringAsFixed(0)} XAF',
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.9),
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // Addresses section
            const Text(
              'Itinéraire',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),

            // Pickup card
            _buildAddressCard(
              context: context,
              icon: Icons.radio_button_checked,
              iconColor: DelivrColors.primary,
              label: 'PICKUP',
              address: delivery['pickup_address'] as String,
              lat: delivery['pickup_lat'] as double,
              lng: delivery['pickup_lng'] as double,
              contactName: delivery['sender_name'] as String,
              contactPhone: delivery['sender_phone'] as String,
            ),

            // Connector line
            Container(
              margin: const EdgeInsets.only(left: 15),
              height: 24,
              width: 2,
              color: DelivrColors.textSecondary.withOpacity(0.3),
            ),

            // Dropoff card
            _buildAddressCard(
              context: context,
              icon: Icons.location_on,
              iconColor: DelivrColors.secondary,
              label: 'LIVRAISON',
              address: delivery['dropoff_address'] as String,
              lat: delivery['dropoff_lat'] as double,
              lng: delivery['dropoff_lng'] as double,
              contactName: delivery['recipient_name'] as String,
              contactPhone: delivery['recipient_phone'] as String,
            ),

            const SizedBox(height: 24),

            // Package info
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
                    color: Colors.black.withOpacity(0.05),
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
                      color: DelivrColors.info.withOpacity(0.1),
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
                          delivery['package_description'] as String,
                          style: const TextStyle(fontWeight: FontWeight.w500),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${(delivery['distance'] as double).toStringAsFixed(1)} km',
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
        ),
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
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
                  onPressed: () {
                    // Navigate to pickup location
                    NavigationService.navigateTo(
                      latitude: delivery['pickup_lat'] as double,
                      longitude: delivery['pickup_lng'] as double,
                      label: 'Pickup - ${delivery['pickup_address']}',
                    );
                  },
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
                  onPressed: () {
                    context.push('/deliveries/$deliveryId/pickup');
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: DelivrColors.primary,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  child: const Text('Confirmer pickup'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAddressCard({
    required BuildContext context,
    required IconData icon,
    required Color iconColor,
    required String label,
    required String address,
    required double lat,
    required double lng,
    required String contactName,
    required String contactPhone,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
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
              // GPS Navigation button with options
              PopupMenuButton<String>(
                icon: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: DelivrColors.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.navigation, size: 14, color: DelivrColors.primary),
                      const SizedBox(width: 4),
                      Text(
                        'GPS',
                        style: TextStyle(
                          fontSize: 12,
                          color: DelivrColors.primary,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      Icon(Icons.arrow_drop_down, size: 14, color: DelivrColors.primary),
                    ],
                  ),
                ),
                onSelected: (value) {
                  if (value == 'google') {
                    NavigationService.navigateTo(
                      latitude: lat,
                      longitude: lng,
                      label: address,
                    );
                  } else if (value == 'waze') {
                    final wazeUrl = 'https://waze.com/ul?ll=$lat,$lng&navigate=yes';
                    launchUrl(Uri.parse(wazeUrl), mode: LaunchMode.externalApplication);
                  }
                },
                itemBuilder: (context) => [
                  PopupMenuItem(
                    value: 'google',
                    child: Row(
                      children: [
                        Image.network(
                          'https://upload.wikimedia.org/wikipedia/commons/thumb/a/aa/Google_Maps_icon_%282020%29.svg/32px-Google_Maps_icon_%282020%29.svg.png',
                          width: 20,
                          height: 20,
                          errorBuilder: (_, __, ___) => const Icon(Icons.map, size: 20),
                        ),
                        const SizedBox(width: 12),
                        const Text('Google Maps'),
                      ],
                    ),
                  ),
                  PopupMenuItem(
                    value: 'waze',
                    child: Row(
                      children: [
                        Image.network(
                          'https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/Waze_logo.svg/32px-Waze_logo.svg.png',
                          width: 20,
                          height: 20,
                          errorBuilder: (_, __, ___) => const Icon(Icons.directions_car, size: 20),
                        ),
                        const SizedBox(width: 12),
                        const Text('Waze'),
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
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 8),
          const Divider(height: 1),
          const SizedBox(height: 8),
          Row(
            children: [
              const Icon(Icons.person_outline, size: 16, color: Colors.grey),
              const SizedBox(width: 8),
              Expanded(child: Text(contactName, style: const TextStyle(fontSize: 13))),
              GestureDetector(
                onTap: () => NavigationService.callPhone(contactPhone),
                child: Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: DelivrColors.success.withOpacity(0.1),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(Icons.phone, size: 16, color: DelivrColors.success),
                ),
              ),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: () => NavigationService.openWhatsApp(
                  phoneNumber: contactPhone,
                  message: 'Bonjour, je suis votre coursier DELIVR...',
                ),
                child: Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: const Color(0xFF25D366).withOpacity(0.1),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.chat, size: 16, color: Color(0xFF25D366)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
