import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme.dart';
import '../providers/smart_route_provider.dart';
import '../services/navigation_launcher.dart';

/// === SMART NAVIGATION BUTTON ===
///
/// A premium button that:
/// 1. Calculates the smart route (with traffic awareness)
/// 2. Shows ETA, distance, and traffic warnings
/// 3. Lets the courier choose Google Maps, Waze, or Apple Maps
/// 4. Opens the nav app with optimized waypoints
///
/// Usage:
/// ```dart
/// SmartNavigateButton(
///   originLat: courierLat,
///   originLng: courierLng,
///   destLat: delivery.dropoffGeo.latitude,
///   destLng: delivery.dropoffGeo.longitude,
///   label: 'Naviguer vers le client',
/// )
/// ```
class SmartNavigateButton extends ConsumerStatefulWidget {
  final double originLat;
  final double originLng;
  final double destLat;
  final double destLng;
  final String label;
  final bool compact;

  const SmartNavigateButton({
    super.key,
    required this.originLat,
    required this.originLng,
    required this.destLat,
    required this.destLng,
    this.label = 'Naviguer',
    this.compact = false,
  });

  @override
  ConsumerState<SmartNavigateButton> createState() =>
      _SmartNavigateButtonState();
}

class _SmartNavigateButtonState extends ConsumerState<SmartNavigateButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    // Auto-calculate route on init
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _calculateRoute();
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _calculateRoute() async {
    await ref.read(smartRouteProvider.notifier).calculateRoute(
          originLat: widget.originLat,
          originLng: widget.originLng,
          destLat: widget.destLat,
          destLng: widget.destLng,
        );
  }

  @override
  Widget build(BuildContext context) {
    final routeState = ref.watch(smartRouteProvider);

    if (widget.compact) {
      return _buildCompactButton(routeState);
    }
    return _buildFullButton(routeState);
  }

  /// Compact: just an icon button with ETA badge
  Widget _buildCompactButton(SmartRouteState state) {
    return GestureDetector(
      onTap: () => _onNavigate(state),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF1A73E8), Color(0xFF4285F4)],
          ),
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF1A73E8).withValues(alpha: 0.3),
              blurRadius: 8,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.navigation_rounded, color: Colors.white, size: 18),
            const SizedBox(width: 6),
            if (state.isLoading)
              const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            else if (state.route != null) ...[
              Text(
                state.route!.etaText,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 13,
                ),
              ),
              if (state.route!.hasTrafficImpact) ...[
                const SizedBox(width: 4),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                  decoration: BoxDecoration(
                    color: Colors.orange.withValues(alpha: 0.3),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '+${state.route!.trafficDelay.round()}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ] else
              Text(
                widget.label,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
              ),
          ],
        ),
      ),
    );
  }

  /// Full: detailed card with route info, warnings, and nav app picker
  Widget _buildFullButton(SmartRouteState state) {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        final route = state.route;
        
        return GestureDetector(
          onTap: () => _onNavigate(state),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF1A73E8).withValues(
                    alpha: 0.1 + (_pulseController.value * 0.1),
                  ),
                  blurRadius: 16 + (_pulseController.value * 8),
                  offset: const Offset(0, 4),
                ),
              ],
              border: Border.all(
                color: const Color(0xFF1A73E8).withValues(alpha: 0.15),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                // Header row
                Row(
                  children: [
                    // Navigate icon with gradient background
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF1A73E8), Color(0xFF4285F4)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(
                        Icons.navigation_rounded,
                        color: Colors.white,
                        size: 22,
                      ),
                    ),
                    const SizedBox(width: 12),

                    // Route info
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            widget.label,
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 15,
                              color: DelivrColors.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 2),
                          if (state.isLoading)
                            Text(
                              'Calcul de l\'itinéraire...',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey.shade500,
                              ),
                            )
                          else if (route != null)
                            Row(
                              children: [
                                // Distance
                                Icon(Icons.straighten,
                                    size: 13, color: Colors.grey.shade500),
                                const SizedBox(width: 3),
                                Text(
                                  route.distanceText,
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.grey.shade600,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                const SizedBox(width: 10),
                                // ETA
                                Icon(Icons.schedule,
                                    size: 13, color: Colors.grey.shade500),
                                const SizedBox(width: 3),
                                Text(
                                  route.etaText,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: Color(0xFF1A73E8),
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                                // Traffic delay
                                if (route.hasTrafficImpact) ...[
                                  const SizedBox(width: 4),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 5,
                                      vertical: 1,
                                    ),
                                    decoration: BoxDecoration(
                                      color:
                                          Colors.orange.withValues(alpha: 0.15),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Text(
                                      '+${route.trafficDelay.round()} min trafic',
                                      style: const TextStyle(
                                        fontSize: 10,
                                        color: Colors.deepOrange,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                  ),
                                ],
                              ],
                            )
                          else if (state.error != null)
                            Text(
                              state.error!,
                              style: const TextStyle(
                                fontSize: 12,
                                color: Colors.redAccent,
                              ),
                            ),
                        ],
                      ),
                    ),

                    // GO button
                    if (!state.isLoading)
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 8,
                        ),
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFF34A853), Color(0xFF0D652D)],
                          ),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: const Text(
                          'GO',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w900,
                            fontSize: 16,
                            letterSpacing: 1,
                          ),
                        ),
                      )
                    else
                      const SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                  ],
                ),

                // Warnings (if any)
                if (route != null && route.warnings.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  ...route.warnings.take(3).map(
                        (w) => Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: Row(
                            children: [
                              Icon(
                                w.isDanger
                                    ? Icons.error
                                    : (w.isWarning
                                        ? Icons.warning_amber_rounded
                                        : Icons.info_outline),
                                size: 14,
                                color: w.isDanger
                                    ? Colors.red
                                    : (w.isWarning
                                        ? Colors.orange
                                        : Colors.blue),
                              ),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  w.message,
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: Colors.grey.shade600,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              if (w.penaltyMinutes > 0)
                                Text(
                                  '+${w.penaltyMinutes.round()} min',
                                  style: TextStyle(
                                    fontSize: 10,
                                    color: Colors.grey.shade500,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  /// Handle navigate tap — show app picker
  void _onNavigate(SmartRouteState state) {
    if (state.isLoading) return;

    final route = state.route;
    if (route != null) {
      _showNavAppPicker(route);
    } else {
      // No smart route — launch simple navigation
      NavigationLauncher.launchSimpleNavigation(
        destLat: widget.destLat,
        destLng: widget.destLng,
        originLat: widget.originLat,
        originLng: widget.originLng,
      );
    }
  }

  /// Show bottom sheet to pick navigation app
  void _showNavAppPicker(SmartRouteData route) {
    final apps = NavigationLauncher.getAvailableApps();

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
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

            // Title
            const Text(
              'Ouvrir avec',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.bold,
                color: DelivrColors.textPrimary,
              ),
            ),
            const SizedBox(height: 4),

            // Route summary
            Text(
              '${route.distanceText} • ${route.etaText}'
              '${route.hasTrafficImpact ? " (+${route.trafficDelay.round()} min trafic)" : ""}',
              style: TextStyle(
                fontSize: 13,
                color: Colors.grey.shade500,
              ),
            ),
            const SizedBox(height: 16),

            // App buttons
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: apps.map((app) {
                final colors = {
                  NavApp.googleMaps: const Color(0xFF4285F4),
                  NavApp.waze: const Color(0xFF33CCFF),
                  NavApp.appleMaps: const Color(0xFF000000),
                };
                final icons = {
                  NavApp.googleMaps: Icons.map_rounded,
                  NavApp.waze: Icons.explore_rounded,
                  NavApp.appleMaps: Icons.apple_rounded,
                };

                return GestureDetector(
                  onTap: () {
                    Navigator.of(ctx).pop();
                    NavigationLauncher.launchNavigation(
                      route: route,
                      preferredApp: app,
                    );
                  },
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(
                          color: colors[app]!.withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: colors[app]!.withValues(alpha: 0.2),
                          ),
                        ),
                        child: Icon(
                          icons[app],
                          color: colors[app],
                          size: 28,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        app.label,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),

            // Waypoints info
            if (route.waypoints.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 14),
                child: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A73E8).withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.route_rounded,
                        size: 16,
                        color: Color(0xFF1A73E8),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '${route.waypoints.length} points optimisés pour éviter le trafic',
                        style: const TextStyle(
                          fontSize: 11,
                          color: Color(0xFF1A73E8),
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
