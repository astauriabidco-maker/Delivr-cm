import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../app/theme.dart';

/// Contact button with call and WhatsApp functionality
class ContactButton extends StatelessWidget {
  final String name;
  final String phone;
  final VoidCallback? onCall;

  const ContactButton({
    super.key,
    required this.name,
    required this.phone,
    this.onCall,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: DelivrColors.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          // Avatar
          CircleAvatar(
            radius: 20,
            backgroundColor: DelivrColors.primaryLight,
            child: Text(
              name.isNotEmpty ? name[0].toUpperCase() : '?',
              style: const TextStyle(
                fontWeight: FontWeight.bold,
                color: DelivrColors.primary,
              ),
            ),
          ),
          const SizedBox(width: 12),
          
          // Name & Phone
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: const TextStyle(
                    fontWeight: FontWeight.w500,
                    fontSize: 14,
                  ),
                ),
                Text(
                  _formatPhone(phone),
                  style: TextStyle(
                    fontSize: 13,
                    color: DelivrColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          
          // WhatsApp button
          IconButton(
            onPressed: () => _openWhatsApp(context, phone),
            icon: const Icon(Icons.message),
            color: DelivrColors.success,
            tooltip: 'WhatsApp',
          ),
          
          // Call button
          Container(
            decoration: BoxDecoration(
              color: DelivrColors.success,
              borderRadius: BorderRadius.circular(10),
            ),
            child: IconButton(
              onPressed: onCall ?? () => _makeCall(context, phone),
              icon: const Icon(Icons.call),
              color: Colors.white,
              tooltip: 'Appeler',
            ),
          ),
        ],
      ),
    );
  }

  String _formatPhone(String phone) {
    // Format as +237 6XX XX XX XX
    if (phone.startsWith('+237') && phone.length == 13) {
      return '${phone.substring(0, 4)} ${phone.substring(4, 5)} ${phone.substring(5, 7)} ${phone.substring(7, 9)} ${phone.substring(9, 11)} ${phone.substring(11)}';
    }
    return phone;
  }

  Future<void> _makeCall(BuildContext context, String phone) async {
    final uri = Uri.parse('tel:$phone');
    try {
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri);
      } else {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Impossible d\'ouvrir le téléphone')),
          );
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur: $e')),
        );
      }
    }
  }

  Future<void> _openWhatsApp(BuildContext context, String phone) async {
    // Remove + and spaces for WhatsApp URL
    final cleanPhone = phone.replaceAll(RegExp(r'[^\d]'), '');
    final uri = Uri.parse('https://wa.me/$cleanPhone');
    
    try {
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('WhatsApp non disponible')),
          );
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur: $e')),
        );
      }
    }
  }
}
