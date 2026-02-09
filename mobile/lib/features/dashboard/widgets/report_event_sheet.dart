import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme.dart';
import '../providers/events_provider.dart';
import '../services/speed_anomaly_detector.dart';

/// ============================================================
/// QUICK-TAP REPORT — Signalement en 1 tap
/// ============================================================
/// 
/// Flow simplifié :
/// 1. GPS → AUTO (coordonnées actuelles)
/// 2. Sévérité → AUTO (calculée depuis la vitesse GPS)
/// 3. Adresse → AUTO (reverse geocoding Nominatim)
/// 4. Type → 1 TAP sur un emoji (seule action manuelle)
/// 5. Description → OPTIONNEL (accessible après coup)
///
/// Le coursier voit une rangée d'emojis et tape UNE fois → terminé.
/// ============================================================

/// Bottom sheet ultra-simplifié : 1 tap = signalement envoyé
class QuickReportSheet extends ConsumerStatefulWidget {
  final double latitude;
  final double longitude;
  final double? currentSpeedKmh;

  const QuickReportSheet({
    super.key,
    required this.latitude,
    required this.longitude,
    this.currentSpeedKmh,
  });

  @override
  ConsumerState<QuickReportSheet> createState() => _QuickReportSheetState();
}

class _QuickReportSheetState extends ConsumerState<QuickReportSheet> {
  bool _isSending = false;
  String? _sendingType;
  String _autoAddress = '';
  bool _loadingAddress = true;

  @override
  void initState() {
    super.initState();
    _fetchAddress();
  }

  Future<void> _fetchAddress() async {
    final addr = await ReverseGeocoder.getAddress(
      widget.latitude,
      widget.longitude,
    );
    if (mounted) {
      setState(() {
        _autoAddress = addr;
        _loadingAddress = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final autoSeverity = widget.currentSpeedKmh != null
        ? SpeedAnomalyDetector.computeSeverityValue(widget.currentSpeedKmh!)
        : 'MEDIUM';

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Handle
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: Colors.grey.shade300,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 14),

          // Header compact
          Row(
            children: [
              const Icon(Icons.flash_on, color: DelivrColors.warning, size: 22),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  'Signalement rapide',
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.bold,
                    color: DelivrColors.textPrimary,
                  ),
                ),
              ),
              // Auto-info badges
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: DelivrColors.success.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.gps_fixed, size: 12, color: DelivrColors.success),
                    const SizedBox(width: 4),
                    Text(
                      'GPS auto',
                      style: TextStyle(
                        fontSize: 11,
                        color: DelivrColors.success,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),

          // Location auto-detected
          Row(
            children: [
              Icon(Icons.place, size: 14, color: Colors.grey.shade500),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  _loadingAddress ? 'Localisation...' : _autoAddress,
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (widget.currentSpeedKmh != null) ...[
                const SizedBox(width: 8),
                Icon(Icons.speed, size: 14, color: Colors.grey.shade500),
                const SizedBox(width: 2),
                Text(
                  '${widget.currentSpeedKmh!.toStringAsFixed(0)} km/h',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
                ),
              ],
            ],
          ),
          const SizedBox(height: 16),

          // "Tapez pour signaler" subtitle
          Text(
            'Appuyez pour signaler 👇',
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey.shade600,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 12),

          // === QUICK-TAP GRID (2 rows of 5) ===
          _buildQuickTapGrid(autoSeverity),
        ],
      ),
    );
  }

  Widget _buildQuickTapGrid(String autoSeverity) {
    // Types prioritaires pour coursiers à Douala
    final quickTypes = [
      TrafficEventType.trafficJam,
      TrafficEventType.accident,
      TrafficEventType.police,
      TrafficEventType.roadClosed,
      TrafficEventType.flooding,
      TrafficEventType.pothole,
      TrafficEventType.roadwork,
      TrafficEventType.hazard,
      TrafficEventType.fuelStation,
      TrafficEventType.other,
    ];

    return GridView.count(
      crossAxisCount: 5,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 8,
      crossAxisSpacing: 8,
      childAspectRatio: 0.82,
      children: quickTypes.map((type) {
        final isSending = _sendingType == type.value;
        return GestureDetector(
          onTap: _isSending ? null : () => _quickReport(type, autoSeverity),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            decoration: BoxDecoration(
              color: isSending
                  ? Color(type.colorValue).withValues(alpha: 0.2)
                  : Colors.grey.shade50,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: isSending
                    ? Color(type.colorValue)
                    : Colors.grey.shade200,
                width: isSending ? 2 : 1,
              ),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (isSending)
                  SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Color(type.colorValue),
                    ),
                  )
                else
                  Text(type.emoji, style: const TextStyle(fontSize: 26)),
                const SizedBox(height: 4),
                Text(
                  type.label,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 9.5,
                    fontWeight: FontWeight.w600,
                    color: isSending
                        ? Color(type.colorValue)
                        : DelivrColors.textSecondary,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  /// 1-TAP REPORT : envoyer immédiatement
  Future<void> _quickReport(TrafficEventType type, String severity) async {
    setState(() {
      _isSending = true;
      _sendingType = type.value;
    });

    // Auto-fill address en background si pas encore chargé
    if (_autoAddress.isEmpty) {
      _autoAddress = await ReverseGeocoder.getAddress(
        widget.latitude,
        widget.longitude,
      );
    }

    final event = await ref.read(trafficEventsProvider.notifier).reportEvent(
          type: type,
          latitude: widget.latitude,
          longitude: widget.longitude,
          severity: severity,
          address: _autoAddress,
          description: '', // Pas demandé en mode quick
        );

    if (!mounted) return;

    if (event != null) {
      Navigator.of(context).pop(true);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              Text(type.emoji, style: const TextStyle(fontSize: 18)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${type.label} signalé — Merci !',
                  style: const TextStyle(fontWeight: FontWeight.w500),
                ),
              ),
            ],
          ),
          backgroundColor: DelivrColors.success,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          duration: const Duration(seconds: 2),
        ),
      );
    } else {
      setState(() {
        _isSending = false;
        _sendingType = null;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Connectez-vous pour signaler'),
          backgroundColor: DelivrColors.warning,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      );
    }
  }
}

/// ============================================================
/// PROACTIVE ALERT — Notification quand ralentissement détecté
/// ============================================================
/// 
/// Apparaît en haut de la carte quand le GPS détecte un
/// ralentissement. Le coursier tape 1 emoji pour confirmer.

class ProactiveSlowdownAlert extends ConsumerWidget {
  final SlowdownAlert alert;
  final VoidCallback onDismiss;

  const ProactiveSlowdownAlert({
    super.key,
    required this.alert,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      margin: const EdgeInsets.symmetric(horizontal: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: DelivrColors.warning.withValues(alpha: 0.3),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
        border: Border.all(
          color: DelivrColors.warning.withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: DelivrColors.warning.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.speed,
                  size: 18,
                  color: DelivrColors.warning,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      alert.message,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                        color: DelivrColors.textPrimary,
                      ),
                    ),
                    Text(
                      'Que se passe-t-il ? Tapez un icône',
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.grey.shade500,
                      ),
                    ),
                  ],
                ),
              ),
              // Close button
              GestureDetector(
                onTap: onDismiss,
                child: Icon(Icons.close, size: 18, color: Colors.grey.shade400),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Quick emoji row (most common causes)
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _quickAlertButton(context, ref, TrafficEventType.trafficJam),
              _quickAlertButton(context, ref, TrafficEventType.accident),
              _quickAlertButton(context, ref, TrafficEventType.police),
              _quickAlertButton(context, ref, TrafficEventType.roadClosed),
              _quickAlertButton(context, ref, TrafficEventType.flooding),
              // "Rien" button (just dismiss)
              _nothingButton(context),
            ],
          ),
        ],
      ),
    );
  }

  Widget _quickAlertButton(
    BuildContext context,
    WidgetRef ref,
    TrafficEventType type,
  ) {
    return GestureDetector(
      onTap: () async {
        final severity = SpeedAnomalyDetector.computeSeverityValue(
          alert.analysis.currentSpeed,
        );
        final address = await ReverseGeocoder.getAddress(
          alert.analysis.latitude,
          alert.analysis.longitude,
        );

        await ref.read(trafficEventsProvider.notifier).reportEvent(
              type: type,
              latitude: alert.analysis.latitude,
              longitude: alert.analysis.longitude,
              severity: severity,
              address: address,
            );

        onDismiss();
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('${type.emoji} Signalé automatiquement — Merci !'),
              backgroundColor: DelivrColors.success,
              behavior: SnackBarBehavior.floating,
              duration: const Duration(seconds: 2),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          );
        }
      },
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: Color(type.colorValue).withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: Color(type.colorValue).withValues(alpha: 0.3),
              ),
            ),
            child: Center(
              child: Text(type.emoji, style: const TextStyle(fontSize: 22)),
            ),
          ),
          const SizedBox(height: 3),
          Text(
            type.label,
            style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w500),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _nothingButton(BuildContext context) {
    return GestureDetector(
      onTap: onDismiss,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: const Center(
              child: Text('✓', style: TextStyle(fontSize: 22)),
            ),
          ),
          const SizedBox(height: 3),
          const Text(
            'RAS',
            style: TextStyle(fontSize: 9, fontWeight: FontWeight.w500),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

/// Fonction utilitaire pour ouvrir le sheet quick-report
Future<bool?> showQuickReportSheet(
  BuildContext context, {
  required double latitude,
  required double longitude,
  double? currentSpeedKmh,
}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => QuickReportSheet(
      latitude: latitude,
      longitude: longitude,
      currentSpeedKmh: currentSpeedKmh,
    ),
  );
}
