import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Theme mode provider with persistence
final themeModeProvider = StateNotifierProvider<ThemeModeNotifier, ThemeMode>((ref) {
  return ThemeModeNotifier();
});

class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  static const String _key = 'theme_mode';
  
  ThemeModeNotifier() : super(ThemeMode.light) {
    _loadTheme();
  }
  
  Future<void> _loadTheme() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final mode = prefs.getString(_key);
      if (mode == 'dark') {
        state = ThemeMode.dark;
      } else if (mode == 'system') {
        state = ThemeMode.system;
      } else {
        state = ThemeMode.light;
      }
    } catch (e) {
      state = ThemeMode.light;
    }
  }
  
  Future<void> setTheme(ThemeMode mode) async {
    state = mode;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_key, mode.name);
    } catch (e) {
      // Ignore persistence errors
    }
  }
  
  void toggleDarkMode() {
    setTheme(state == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark);
  }
  
  bool get isDark => state == ThemeMode.dark;
}

/// Dark theme colors
class DelivrDarkColors {
  static const Color background = Color(0xFF121212);
  static const Color surface = Color(0xFF1E1E1E);
  static const Color card = Color(0xFF2C2C2C);
  static const Color primary = Color(0xFF6750A4);
  static const Color secondary = Color(0xFFFF9800);
  static const Color textPrimary = Color(0xFFE0E0E0);
  static const Color textSecondary = Color(0xFF9E9E9E);
  static const Color success = Color(0xFF4CAF50);
  static const Color error = Color(0xFFEF5350);
  static const Color warning = Color(0xFFFFA726);
}

/// Build dark theme data
ThemeData buildDarkTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: ColorScheme.dark(
      primary: DelivrDarkColors.primary,
      secondary: DelivrDarkColors.secondary,
      surface: DelivrDarkColors.surface,
      error: DelivrDarkColors.error,
    ),
    scaffoldBackgroundColor: DelivrDarkColors.background,
    cardColor: DelivrDarkColors.card,
    appBarTheme: const AppBarTheme(
      backgroundColor: DelivrDarkColors.surface,
      foregroundColor: DelivrDarkColors.textPrimary,
      elevation: 0,
    ),
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: DelivrDarkColors.surface,
      selectedItemColor: DelivrDarkColors.primary,
      unselectedItemColor: DelivrDarkColors.textSecondary,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: DelivrDarkColors.primary,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: DelivrDarkColors.card,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: DelivrDarkColors.card,
      selectedColor: DelivrDarkColors.primary.withOpacity(0.3),
      labelStyle: const TextStyle(color: DelivrDarkColors.textPrimary),
    ),
    dividerColor: Colors.white12,
  );
}
