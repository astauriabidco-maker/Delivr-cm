import 'dart:io';
import 'package:flutter/material.dart';

import '../../../app/theme.dart';

/// Photo preview widget with retake/remove options
class PhotoPreview extends StatelessWidget {
  final File photo;
  final VoidCallback onRetake;
  final VoidCallback onRemove;

  const PhotoPreview({
    super.key,
    required this.photo,
    required this.onRetake,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        // Photo
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: Image.file(
            photo,
            width: double.infinity,
            height: 200,
            fit: BoxFit.cover,
          ),
        ),
        
        // Actions overlay
        Positioned(
          bottom: 8,
          right: 8,
          child: Row(
            children: [
              // Retake button
              _ActionButton(
                icon: Icons.camera_alt,
                label: 'Reprendre',
                onTap: onRetake,
                color: DelivrColors.primary,
              ),
              const SizedBox(width: 8),
              // Remove button
              _ActionButton(
                icon: Icons.close,
                label: 'Supprimer',
                onTap: onRemove,
                color: DelivrColors.error,
              ),
            ],
          ),
        ),
        
        // Success badge
        Positioned(
          top: 8,
          left: 8,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: DelivrColors.success,
              borderRadius: BorderRadius.circular(4),
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.check, size: 14, color: Colors.white),
                SizedBox(width: 4),
                Text(
                  'Photo prise',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color color;

  const _ActionButton({
    required this.icon,
    required this.label,
    required this.onTap,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: color,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 16, color: Colors.white),
              const SizedBox(width: 4),
              Text(
                label,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
