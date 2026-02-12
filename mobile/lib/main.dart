import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'app/app.dart';
import 'core/config/app_config.dart';
import 'features/notifications/notification_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // =============================================
  // ENVIRONMENT CONFIGURATION
  // =============================================
  // Switch between environments by changing this line:
  //
  // AppConfig.init(AppConfig.development());       // Web browser
  // AppConfig.init(AppConfig.emulator());           // Android emulator
  // AppConfig.init(AppConfig.localNetwork('192.168.1.X'));  // Physical device (WiFi)
  // AppConfig.init(AppConfig.staging());            // Staging server
  // AppConfig.init(AppConfig.production());         // Production
  //
  AppConfig.init(AppConfig.development());
  
  debugPrint('🚀 DELIVR starting with ${AppConfig.current}');
  
  // Initialize Hive for local storage
  await Hive.initFlutter();
  
  // Initialize notification service
  final notificationService = NotificationService();
  await notificationService.initialize();
  await notificationService.requestPermissions();
  
  runApp(
    const ProviderScope(
      child: DelivrCourierApp(),
    ),
  );
}
