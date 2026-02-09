import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Supported locales
enum AppLocale {
  fr('fr', 'Français', '🇫🇷'),
  en('en', 'English', '🇬🇧');
  
  const AppLocale(this.code, this.name, this.flag);
  
  final String code;
  final String name;
  final String flag;
  
  Locale get locale => Locale(code);
  
  static AppLocale fromCode(String code) {
    return AppLocale.values.firstWhere(
      (l) => l.code == code,
      orElse: () => AppLocale.fr,
    );
  }
}

/// Locale notifier with persistence
class LocaleNotifier extends StateNotifier<AppLocale> {
  static const String _key = 'app_locale';
  
  LocaleNotifier() : super(AppLocale.fr) {
    _loadLocale();
  }
  
  Future<void> _loadLocale() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final code = prefs.getString(_key);
      if (code != null) {
        state = AppLocale.fromCode(code);
      }
    } catch (e) {
      state = AppLocale.fr;
    }
  }
  
  Future<void> setLocale(AppLocale locale) async {
    state = locale;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_key, locale.code);
    } catch (e) {
      // Ignore persistence errors
    }
  }
  
  void toggleLocale() {
    setLocale(state == AppLocale.fr ? AppLocale.en : AppLocale.fr);
  }
}

/// Locale provider
final localeProvider = StateNotifierProvider<LocaleNotifier, AppLocale>((ref) {
  return LocaleNotifier();
});

/// Translations class
class AppTranslations {
  final AppLocale locale;
  
  AppTranslations(this.locale);
  
  String get(String key) {
    return _translations[locale.code]?[key] ?? _translations['fr']?[key] ?? key;
  }
  
  // Common translations
  String get appName => get('app_name');
  String get dashboard => get('dashboard');
  String get deliveries => get('deliveries');
  String get wallet => get('wallet');
  String get profile => get('profile');
  String get settings => get('settings');
  String get logout => get('logout');
  String get cancel => get('cancel');
  String get confirm => get('confirm');
  String get save => get('save');
  String get error => get('error');
  String get success => get('success');
  String get loading => get('loading');
  String get retry => get('retry');
  String get online => get('online');
  String get offline => get('offline');
  
  // Dashboard
  String get todayDeliveries => get('today_deliveries');
  String get todayEarnings => get('today_earnings');
  String get todayDistance => get('today_distance');
  String get rating => get('rating');
  String get quickActions => get('quick_actions');
  String get history => get('history');
  String get badges => get('badges');
  String get leaderboard => get('leaderboard');
  String get support => get('support');
  
  // Deliveries
  String get activeDeliveries => get('active_deliveries');
  String get completedDeliveries => get('completed_deliveries');
  String get noDeliveries => get('no_deliveries');
  String get pickup => get('pickup');
  String get dropoff => get('dropoff');
  String get navigate => get('navigate');
  String get confirmPickup => get('confirm_pickup');
  String get confirmDropoff => get('confirm_dropoff');
  String get enterOtp => get('enter_otp');
  String get takePhoto => get('take_photo');
  
  // Profile
  String get myProfile => get('my_profile');
  String get myPerformance => get('my_performance');
  String get badgesAndRewards => get('badges_and_rewards');
  String get historyOfDeliveries => get('history_of_deliveries');
  String get helpAndSupport => get('help_and_support');
  String get privacy => get('privacy');
  String get darkMode => get('dark_mode');
  String get language => get('language');
  String get logoutConfirm => get('logout_confirm');
  
  // Support
  String get faq => get('faq');
  String get contactUs => get('contact_us');
  String get callSupport => get('call_support');
  String get whatsappSupport => get('whatsapp_support');
  
  // Wallet
  String get balance => get('balance');
  String get withdraw => get('withdraw');
  String get transactionHistory => get('transaction_history');
  
  // Auth
  String get login => get('login');
  String get phoneNumber => get('phone_number');
  String get pin => get('pin');
  String get loginButton => get('login_button');
  String get invalidCredentials => get('invalid_credentials');
  
  static const Map<String, Map<String, String>> _translations = {
    'fr': {
      'app_name': 'DELIVR Coursier',
      'dashboard': 'Tableau de bord',
      'deliveries': 'Courses',
      'wallet': 'Portefeuille',
      'profile': 'Profil',
      'settings': 'Paramètres',
      'logout': 'Déconnexion',
      'cancel': 'Annuler',
      'confirm': 'Confirmer',
      'save': 'Enregistrer',
      'error': 'Erreur',
      'success': 'Succès',
      'loading': 'Chargement...',
      'retry': 'Réessayer',
      'online': 'En ligne',
      'offline': 'Hors ligne',
      
      'today_deliveries': 'Courses',
      'today_earnings': 'Gains',
      'today_distance': 'Distance',
      'rating': 'Note',
      'quick_actions': 'Actions rapides',
      'history': 'Historique',
      'badges': 'Badges',
      'leaderboard': 'Classement',
      'support': 'Support',
      
      'active_deliveries': 'En cours',
      'completed_deliveries': 'Terminées',
      'no_deliveries': 'Aucune course',
      'pickup': 'Pickup',
      'dropoff': 'Livraison',
      'navigate': 'Naviguer',
      'confirm_pickup': 'Confirmer pickup',
      'confirm_dropoff': 'Confirmer livraison',
      'enter_otp': 'Entrez le code OTP',
      'take_photo': 'Prendre une photo',
      
      'my_profile': 'Mon profil',
      'my_performance': 'Mes performances',
      'badges_and_rewards': 'Badges et récompenses',
      'history_of_deliveries': 'Historique des courses',
      'help_and_support': 'Aide et support',
      'privacy': 'Confidentialité',
      'dark_mode': 'Mode sombre',
      'language': 'Langue',
      'logout_confirm': 'Voulez-vous vraiment vous déconnecter ?',
      
      'faq': 'Questions fréquentes',
      'contact_us': 'Nous contacter',
      'call_support': 'Appeler',
      'whatsapp_support': 'WhatsApp',
      
      'balance': 'Solde',
      'withdraw': 'Retirer',
      'transaction_history': 'Historique des transactions',
      
      'login': 'Connexion',
      'phone_number': 'Numéro de téléphone',
      'pin': 'Code PIN',
      'login_button': 'Se connecter',
      'invalid_credentials': 'Identifiants incorrects',
    },
    'en': {
      'app_name': 'DELIVR Courier',
      'dashboard': 'Dashboard',
      'deliveries': 'Deliveries',
      'wallet': 'Wallet',
      'profile': 'Profile',
      'settings': 'Settings',
      'logout': 'Logout',
      'cancel': 'Cancel',
      'confirm': 'Confirm',
      'save': 'Save',
      'error': 'Error',
      'success': 'Success',
      'loading': 'Loading...',
      'retry': 'Retry',
      'online': 'Online',
      'offline': 'Offline',
      
      'today_deliveries': 'Deliveries',
      'today_earnings': 'Earnings',
      'today_distance': 'Distance',
      'rating': 'Rating',
      'quick_actions': 'Quick Actions',
      'history': 'History',
      'badges': 'Badges',
      'leaderboard': 'Leaderboard',
      'support': 'Support',
      
      'active_deliveries': 'Active',
      'completed_deliveries': 'Completed',
      'no_deliveries': 'No deliveries',
      'pickup': 'Pickup',
      'dropoff': 'Dropoff',
      'navigate': 'Navigate',
      'confirm_pickup': 'Confirm Pickup',
      'confirm_dropoff': 'Confirm Dropoff',
      'enter_otp': 'Enter OTP code',
      'take_photo': 'Take a photo',
      
      'my_profile': 'My Profile',
      'my_performance': 'My Performance',
      'badges_and_rewards': 'Badges & Rewards',
      'history_of_deliveries': 'Delivery History',
      'help_and_support': 'Help & Support',
      'privacy': 'Privacy',
      'dark_mode': 'Dark Mode',
      'language': 'Language',
      'logout_confirm': 'Do you really want to logout?',
      
      'faq': 'FAQ',
      'contact_us': 'Contact Us',
      'call_support': 'Call',
      'whatsapp_support': 'WhatsApp',
      
      'balance': 'Balance',
      'withdraw': 'Withdraw',
      'transaction_history': 'Transaction History',
      
      'login': 'Login',
      'phone_number': 'Phone Number',
      'pin': 'PIN Code',
      'login_button': 'Sign In',
      'invalid_credentials': 'Invalid credentials',
    },
  };
}

/// Translations provider
final translationsProvider = Provider<AppTranslations>((ref) {
  final locale = ref.watch(localeProvider);
  return AppTranslations(locale);
});

/// Extension for easy access in widgets
extension TranslationsExtension on WidgetRef {
  AppTranslations get tr => read(translationsProvider);
}

/// Language selector widget
class LanguageSelector extends ConsumerWidget {
  const LanguageSelector({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentLocale = ref.watch(localeProvider);
    
    return ListTile(
      leading: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: Theme.of(context).primaryColor.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(currentLocale.flag, style: const TextStyle(fontSize: 20)),
      ),
      title: Text(ref.watch(translationsProvider).language),
      subtitle: Text(currentLocale.name),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => _showLanguageDialog(context, ref),
    );
  }
  
  void _showLanguageDialog(BuildContext context, WidgetRef ref) {
    final currentLocale = ref.read(localeProvider);
    
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(ref.read(translationsProvider).language),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: AppLocale.values.map((locale) {
            final isSelected = locale == currentLocale;
            return ListTile(
              leading: Text(locale.flag, style: const TextStyle(fontSize: 24)),
              title: Text(locale.name),
              trailing: isSelected ? const Icon(Icons.check, color: Colors.green) : null,
              selected: isSelected,
              onTap: () {
                ref.read(localeProvider.notifier).setLocale(locale);
                Navigator.pop(context);
              },
            );
          }).toList(),
        ),
      ),
    );
  }
}
