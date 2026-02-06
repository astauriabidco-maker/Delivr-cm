import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme.dart';
import '../../../core/location/location_service.dart';

/// Widget showing GPS tracking status and battery level
class GpsStatusWidget extends ConsumerWidget {
  const GpsStatusWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final locationState = ref.watch(locationStateProvider);
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: DelivrColors.surface,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(13),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // GPS Status Icon
          _buildGpsIcon(locationState),
          const SizedBox(width: 8),
          
          // Status Text
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _getModeLabel(locationState.mode),
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: DelivrColors.textPrimary,
                ),
              ),
              if (locationState.lastUpdate != null)
                Text(
                  _getLastUpdateText(locationState.lastUpdate!),
                  style: TextStyle(
                    fontSize: 10,
                    color: DelivrColors.textSecondary,
                  ),
                ),
            ],
          ),
          
          const SizedBox(width: 12),
          
          // Battery Indicator
          _buildBatteryIndicator(locationState.batteryLevel),
        ],
      ),
    );
  }

  Widget _buildGpsIcon(LocationState state) {
    Color iconColor;
    IconData icon;
    
    if (state.error != null) {
      iconColor = DelivrColors.error;
      icon = Icons.gps_off;
    } else if (!state.isTracking) {
      iconColor = DelivrColors.textSecondary;
      icon = Icons.gps_off;
    } else {
      switch (state.mode) {
        case LocationTrackingMode.active:
          iconColor = DelivrColors.success;
          icon = Icons.gps_fixed;
          break;
        case LocationTrackingMode.idle:
          iconColor = DelivrColors.info;
          icon = Icons.gps_fixed;
          break;
        case LocationTrackingMode.batterySaving:
          iconColor = DelivrColors.warning;
          icon = Icons.gps_not_fixed;
          break;
        case LocationTrackingMode.stopped:
          iconColor = DelivrColors.textSecondary;
          icon = Icons.gps_off;
          break;
      }
    }
    
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: iconColor.withAlpha(25),
        shape: BoxShape.circle,
      ),
      child: Icon(
        icon,
        size: 18,
        color: iconColor,
      ),
    );
  }

  Widget _buildBatteryIndicator(int level) {
    Color batteryColor;
    IconData batteryIcon;
    
    if (level > 60) {
      batteryColor = DelivrColors.success;
      batteryIcon = Icons.battery_full;
    } else if (level > 20) {
      batteryColor = DelivrColors.warning;
      batteryIcon = Icons.battery_3_bar;
    } else {
      batteryColor = DelivrColors.error;
      batteryIcon = Icons.battery_1_bar;
    }
    
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          batteryIcon,
          size: 16,
          color: batteryColor,
        ),
        const SizedBox(width: 2),
        Text(
          '$level%',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w500,
            color: batteryColor,
          ),
        ),
      ],
    );
  }

  String _getModeLabel(LocationTrackingMode mode) {
    switch (mode) {
      case LocationTrackingMode.active:
        return 'GPS Actif';
      case LocationTrackingMode.idle:
        return 'GPS Standard';
      case LocationTrackingMode.batterySaving:
        return 'Économie batterie';
      case LocationTrackingMode.stopped:
        return 'GPS Inactif';
    }
  }

  String _getLastUpdateText(DateTime lastUpdate) {
    final now = DateTime.now();
    final diff = now.difference(lastUpdate);
    
    if (diff.inSeconds < 10) {
      return 'À l\'instant';
    } else if (diff.inSeconds < 60) {
      return 'Il y a ${diff.inSeconds}s';
    } else if (diff.inMinutes < 5) {
      return 'Il y a ${diff.inMinutes}min';
    } else {
      return 'Mise à jour en cours...';
    }
  }
}

/// Compact GPS indicator for header
class GpsIndicatorCompact extends ConsumerWidget {
  const GpsIndicatorCompact({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final locationState = ref.watch(locationStateProvider);
    
    Color color;
    IconData icon;
    
    if (locationState.error != null || !locationState.isTracking) {
      color = DelivrColors.textSecondary;
      icon = Icons.gps_off;
    } else {
      switch (locationState.mode) {
        case LocationTrackingMode.active:
          color = DelivrColors.success;
          icon = Icons.gps_fixed;
          break;
        case LocationTrackingMode.idle:
          color = DelivrColors.info;
          icon = Icons.gps_fixed;
          break;
        case LocationTrackingMode.batterySaving:
          color = DelivrColors.warning;
          icon = Icons.gps_not_fixed;
          break;
        case LocationTrackingMode.stopped:
          color = DelivrColors.textSecondary;
          icon = Icons.gps_off;
          break;
      }
    }
    
    return Tooltip(
      message: _getTooltipMessage(locationState),
      child: Icon(icon, size: 20, color: color),
    );
  }

  String _getTooltipMessage(LocationState state) {
    if (state.error != null) return 'Erreur GPS';
    if (!state.isTracking) return 'GPS inactif';
    
    switch (state.mode) {
      case LocationTrackingMode.active:
        return 'GPS haute précision (batterie: ${state.batteryLevel}%)';
      case LocationTrackingMode.idle:
        return 'GPS standard (batterie: ${state.batteryLevel}%)';
      case LocationTrackingMode.batterySaving:
        return 'Mode économie batterie (${state.batteryLevel}%)';
      case LocationTrackingMode.stopped:
        return 'GPS inactif';
    }
  }
}
