import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../../../app/theme.dart';
import '../providers/events_provider.dart';

/// Couche de marqueurs pour les événements trafic sur la carte
class TrafficEventsLayer extends ConsumerWidget {
  const TrafficEventsLayer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final eventsState = ref.watch(trafficEventsProvider);

    if (eventsState.events.isEmpty) {
      return const SizedBox.shrink();
    }

    return MarkerLayer(
      markers: eventsState.events.map((event) {
        return Marker(
          point: LatLng(event.latitude, event.longitude),
          width: 44,
          height: 44,
          child: GestureDetector(
            onTap: () => _showEventDetail(context, event, ref),
            child: _EventMarker(event: event),
          ),
        );
      }).toList(),
    );
  }

  void _showEventDetail(
    BuildContext context,
    TrafficEventData event,
    WidgetRef ref,
  ) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _EventDetailSheet(event: event, ref: ref),
    );
  }
}

/// Marqueur animé pour un événement
class _EventMarker extends StatefulWidget {
  final TrafficEventData event;

  const _EventMarker({required this.event});

  @override
  State<_EventMarker> createState() => _EventMarkerState();
}

class _EventMarkerState extends State<_EventMarker>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.2).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isCritical = widget.event.severity == 'CRITICAL' ||
        widget.event.severity == 'HIGH';

    return AnimatedBuilder(
      animation: _pulseAnimation,
      builder: (context, child) {
        return Transform.scale(
          scale: isCritical ? _pulseAnimation.value : 1.0,
          child: child,
        );
      },
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: Colors.white,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: Color(widget.event.eventType.colorValue)
                  .withValues(alpha: 0.4),
              blurRadius: 8,
              spreadRadius: 2,
            ),
          ],
          border: Border.all(
            color: Color(widget.event.eventType.colorValue),
            width: 2.5,
          ),
        ),
        child: Center(
          child: Text(
            widget.event.eventType.emoji,
            style: const TextStyle(fontSize: 20),
          ),
        ),
      ),
    );
  }
}

/// Détail d'un événement
class _EventDetailSheet extends StatelessWidget {
  final TrafficEventData event;
  final WidgetRef ref;

  const _EventDetailSheet({required this.event, required this.ref});

  @override
  Widget build(BuildContext context) {
    final eventColor = Color(event.eventType.colorValue);

    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: const EdgeInsets.all(20),
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
          const SizedBox(height: 16),

          // Header
          Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: eventColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Center(
                  child: Text(
                    event.eventType.emoji,
                    style: const TextStyle(fontSize: 28),
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      event.eventType.label,
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: eventColor,
                      ),
                    ),
                    if (event.address.isNotEmpty)
                      Text(
                        event.address,
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    Text(
                      '${event.timeAgo} • ${event.timeRemaining}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: DelivrColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              _buildConfidenceBadge(),
            ],
          ),
          const SizedBox(height: 12),

          // Description
          if (event.description.isNotEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.grey.shade50,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                event.description,
                style: const TextStyle(
                  fontSize: 14,
                  color: DelivrColors.textPrimary,
                ),
              ),
            ),
          const SizedBox(height: 16),

          // Reporter info
          Row(
            children: [
              Icon(Icons.person_outline, size: 16, color: Colors.grey.shade500),
              const SizedBox(width: 6),
              Text(
                'Signalé par ${event.reporterName}',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey.shade500,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Vote buttons
          if (!event.isOwn) _buildVoteButtons(context),

          // Delete button for own events
          if (event.isOwn) _buildDeleteButton(context),
        ],
      ),
    );
  }

  Widget _buildConfidenceBadge() {
    final score = event.confidenceScore;
    Color color;
    if (score >= 70) {
      color = Colors.green;
    } else if (score >= 40) {
      color = Colors.orange;
    } else {
      color = Colors.red;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        '$score%',
        style: TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.bold,
          color: color,
        ),
      ),
    );
  }

  Widget _buildVoteButtons(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: event.userVote == 'up'
                ? null
                : () async {
                    final ok = await ref
                        .read(trafficEventsProvider.notifier)
                        .voteEvent(event.id, true);
                    if (ok && context.mounted) {
                      Navigator.pop(context);
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('👍 Confirmé !'),
                          behavior: SnackBarBehavior.floating,
                        ),
                      );
                    }
                  },
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.green,
              side: BorderSide(
                color: event.userVote == 'up'
                    ? Colors.green
                    : Colors.grey.shade300,
              ),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            icon: const Icon(Icons.thumb_up_outlined),
            label: Text('Confirmer (${event.upvotes})'),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: event.userVote == 'down'
                ? null
                : () async {
                    final ok = await ref
                        .read(trafficEventsProvider.notifier)
                        .voteEvent(event.id, false);
                    if (ok && context.mounted) {
                      Navigator.pop(context);
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('👎 Infirmé'),
                          behavior: SnackBarBehavior.floating,
                        ),
                      );
                    }
                  },
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.red,
              side: BorderSide(
                color: event.userVote == 'down'
                    ? Colors.red
                    : Colors.grey.shade300,
              ),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            icon: const Icon(Icons.thumb_down_outlined),
            label: Text('Infirmer (${event.downvotes})'),
          ),
        ),
      ],
    );
  }

  Widget _buildDeleteButton(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: () async {
          final confirmed = await showDialog<bool>(
            context: context,
            builder: (ctx) => AlertDialog(
              title: const Text('Supprimer le signalement ?'),
              content: const Text(
                'Cette action est irréversible.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx, false),
                  child: const Text('Annuler'),
                ),
                TextButton(
                  onPressed: () => Navigator.pop(ctx, true),
                  child: const Text(
                    'Supprimer',
                    style: TextStyle(color: Colors.red),
                  ),
                ),
              ],
            ),
          );

          if (confirmed == true) {
            final ok = await ref
                .read(trafficEventsProvider.notifier)
                .deleteEvent(event.id);
            if (ok && context.mounted) {
              Navigator.pop(context);
            }
          }
        },
        style: OutlinedButton.styleFrom(
          foregroundColor: Colors.red,
          side: const BorderSide(color: Colors.red),
          padding: const EdgeInsets.symmetric(vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        icon: const Icon(Icons.delete_outline),
        label: const Text('Supprimer mon signalement'),
      ),
    );
  }
}
