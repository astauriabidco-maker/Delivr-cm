import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'app/app.dart';
import 'core/config/app_config.dart';
import 'features/notifications/notification_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  AppConfig.init(_resolveAppConfig());

  debugPrint('RELAY237 starting with ${AppConfig.current}');

  // Initialize Hive for local storage
  await Hive.initFlutter();

  // Initialize notification service
  final notificationService = NotificationService();
  await notificationService.initialize();
  await notificationService.requestPermissions();

  runApp(const ProviderScope(child: DelivrCourierApp()));
}

AppConfig _resolveAppConfig() {
  const environment = String.fromEnvironment(
    'APP_ENV',
    defaultValue: 'development',
  );
  const localIp = String.fromEnvironment('LOCAL_API_IP');

  switch (environment) {
    case 'emulator':
      return AppConfig.emulator();
    case 'local_network':
      if (localIp.isEmpty) {
        throw StateError('LOCAL_API_IP is required when APP_ENV=local_network');
      }
      return AppConfig.localNetwork(localIp);
    case 'staging':
      return AppConfig.staging();
    case 'production':
      return AppConfig.production();
    case 'development':
      return AppConfig.development();
    default:
      throw StateError('Unsupported APP_ENV: $environment');
  }
}
