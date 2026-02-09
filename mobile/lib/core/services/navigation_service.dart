import 'dart:io';

import 'package:url_launcher/url_launcher.dart';

/// Service for external map navigation
class NavigationService {
  /// Opens external maps app with directions to destination
  static Future<bool> navigateTo({
    required double latitude,
    required double longitude,
    String? label,
  }) async {
    final encodedLabel = Uri.encodeComponent(label ?? 'Destination');
    Uri uri;
    
    if (Platform.isIOS) {
      // Apple Maps
      uri = Uri.parse(
        'https://maps.apple.com/?daddr=$latitude,$longitude&dirflg=d&q=$encodedLabel'
      );
    } else {
      // Google Maps
      uri = Uri.parse(
        'https://www.google.com/maps/dir/?api=1&destination=$latitude,$longitude&travelmode=driving&destination_place_id=$encodedLabel'
      );
    }
    
    // Fallback to Google Maps web
    final googleMapsUri = Uri.parse(
      'https://www.google.com/maps/search/?api=1&query=$latitude,$longitude'
    );
    
    try {
      if (await canLaunchUrl(uri)) {
        return await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else if (await canLaunchUrl(googleMapsUri)) {
        return await launchUrl(googleMapsUri, mode: LaunchMode.externalApplication);
      }
    } catch (e) {
      // Fallback: open in browser
      return await launchUrl(googleMapsUri, mode: LaunchMode.platformDefault);
    }
    return false;
  }
  
  /// Opens WhatsApp with a pre-filled message
  static Future<bool> openWhatsApp({
    required String phoneNumber,
    String? message,
  }) async {
    // Normalize phone number
    String phone = phoneNumber.replaceAll(RegExp(r'[^\d+]'), '');
    if (!phone.startsWith('+')) {
      phone = '+237$phone';
    }
    phone = phone.replaceAll('+', '');
    
    final encodedMessage = Uri.encodeComponent(message ?? '');
    final uri = Uri.parse('https://wa.me/$phone?text=$encodedMessage');
    
    try {
      return await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (e) {
      return false;
    }
  }
  
  /// Opens phone dialer
  static Future<bool> callPhone(String phoneNumber) async {
    final uri = Uri.parse('tel:$phoneNumber');
    try {
      return await launchUrl(uri);
    } catch (e) {
      return false;
    }
  }
}
