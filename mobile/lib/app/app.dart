import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'router.dart';
import 'theme.dart';

class DelivrCourierApp extends ConsumerWidget {
  const DelivrCourierApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    
    // Lock orientation to portrait for consistent UX
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);
    
    // Set system UI overlay style
    SystemChrome.setSystemUIOverlayStyle(
      const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        systemNavigationBarColor: DelivrColors.background,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
    );
    
    return MaterialApp.router(
      title: 'DELIVR Coursier',
      debugShowCheckedModeBanner: false,
      theme: DelivrTheme.light,
      darkTheme: DelivrTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
