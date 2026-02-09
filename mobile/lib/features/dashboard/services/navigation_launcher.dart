import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:url_launcher/url_launcher.dart';

import '../providers/smart_route_provider.dart';

/// Navigation app preferences
enum NavApp {
  googleMaps('Google Maps', '🗺️'),
  waze('Waze', '📍'),
  appleMaps('Apple Maps', '🍎');

  final String label;
  final String emoji;
  const NavApp(this.label, this.emoji);
}

/// Service to launch external navigation apps with smart route waypoints.
///
/// The key innovation: instead of just sending the destination,
/// we inject strategic waypoints that FORCE the navigation app
/// to follow DELIVR-CM's traffic-optimized route.
class NavigationLauncher {
  /// Launch navigation to a destination using smart route data.
  ///
  /// Opens the user's preferred navigation app with waypoints
  /// from our smart routing engine.
  static Future<bool> launchNavigation({
    required SmartRouteData route,
    NavApp? preferredApp,
  }) async {
    final app = preferredApp ?? _detectDefaultApp();

    String url;
    switch (app) {
      case NavApp.googleMaps:
        url = route.navigation.googleMaps;
        break;
      case NavApp.waze:
        url = route.navigation.waze;
        break;
      case NavApp.appleMaps:
        url = route.navigation.appleMaps;
        break;
    }

    if (url.isEmpty) {
      // Fallback: try Google Maps web URL
      url = route.navigation.googleMaps;
    }

    if (url.isEmpty) {
      debugPrint('[NavigationLauncher] No navigation URL available');
      return false;
    }

    return _launchUrl(url);
  }

  /// Launch navigation with just coordinates (no smart route needed).
  ///
  /// Used when we don't have a smart route yet or as a fallback.
  static Future<bool> launchSimpleNavigation({
    required double destLat,
    required double destLng,
    double? originLat,
    double? originLng,
    NavApp? preferredApp,
  }) async {
    final app = preferredApp ?? _detectDefaultApp();

    String url;
    switch (app) {
      case NavApp.googleMaps:
        if (originLat != null && originLng != null) {
          url = 'https://www.google.com/maps/dir/'
              '$originLat,$originLng/$destLat,$destLng'
              '/@$destLat,$destLng,14z/data=!4m2!4m1!3e0';
        } else {
          url =
              'https://www.google.com/maps/dir/?api=1&destination=$destLat,$destLng&travelmode=driving';
        }
        break;
      case NavApp.waze:
        url = 'https://waze.com/ul?ll=$destLat,$destLng&navigate=yes';
        break;
      case NavApp.appleMaps:
        url = 'https://maps.apple.com/?daddr=$destLat,$destLng&dirflg=d';
        break;
    }

    return _launchUrl(url);
  }

  /// Launch navigation with custom waypoints (for advanced usage).
  static Future<bool> launchWithWaypoints({
    required double originLat,
    required double originLng,
    required double destLat,
    required double destLng,
    required List<List<double>> waypoints,
    NavApp? preferredApp,
  }) async {
    final app = preferredApp ?? _detectDefaultApp();

    String url;
    switch (app) {
      case NavApp.googleMaps:
        final parts = <String>['$originLat,$originLng'];
        for (final wp in waypoints) {
          parts.add('${wp[0]},${wp[1]}');
        }
        parts.add('$destLat,$destLng');
        final path = parts.join('/');
        url =
            'https://www.google.com/maps/dir/$path/@$destLat,$destLng,14z/data=!4m2!4m1!3e0';
        break;
      case NavApp.waze:
        // Waze doesn't support waypoints, just navigate to destination
        url = 'https://waze.com/ul?ll=$destLat,$destLng&navigate=yes';
        break;
      case NavApp.appleMaps:
        url =
            'https://maps.apple.com/?saddr=$originLat,$originLng&daddr=$destLat,$destLng&dirflg=d';
        break;
    }

    return _launchUrl(url);
  }

  /// Detect what navigation apps are available.
  static List<NavApp> getAvailableApps() {
    if (kIsWeb) {
      return [NavApp.googleMaps, NavApp.waze];
    }

    final apps = <NavApp>[NavApp.googleMaps, NavApp.waze];

    if (!kIsWeb && Platform.isIOS) {
      apps.add(NavApp.appleMaps);
    }

    return apps;
  }

  /// Detect the best default navigation app.
  static NavApp _detectDefaultApp() {
    if (kIsWeb) return NavApp.googleMaps;

    try {
      if (Platform.isIOS) {
        return NavApp.appleMaps; // Most iPhone users prefer Apple Maps
      }
    } catch (_) {}

    return NavApp.googleMaps;
  }

  /// Launch a URL.
  static Future<bool> _launchUrl(String url) async {
    try {
      final uri = Uri.parse(url);

      if (await canLaunchUrl(uri)) {
        return await launchUrl(
          uri,
          mode: LaunchMode.externalApplication,
        );
      } else {
        // Fallback: try launching as web URL
        return await launchUrl(
          uri,
          mode: LaunchMode.platformDefault,
        );
      }
    } catch (e) {
      debugPrint('[NavigationLauncher] Failed to launch URL: $e');
      return false;
    }
  }
}
