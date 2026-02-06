import 'package:flutter/material.dart';

import '../../../app/theme.dart';

/// Card showing an address with icon
class AddressCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String address;
  final Color iconColor;
  final VoidCallback? onNavigate;

  const AddressCard({
    super.key,
    required this.icon,
    required this.label,
    required this.address,
    required this.iconColor,
    this.onNavigate,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: DelivrColors.surface,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(10),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          // Icon
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: iconColor.withAlpha(25),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: iconColor),
          ),
          const SizedBox(width: 12),
          
          // Address info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 12,
                    color: DelivrColors.textSecondary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  address,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w500,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          
          // Navigate button
          if (onNavigate != null)
            IconButton(
              onPressed: onNavigate,
              icon: const Icon(Icons.navigation),
              color: iconColor,
              tooltip: 'Naviguer',
            ),
        ],
      ),
    );
  }
}
