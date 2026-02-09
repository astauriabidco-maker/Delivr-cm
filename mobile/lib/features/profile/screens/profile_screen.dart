import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router.dart';
import '../../../app/theme.dart';
import '../../../core/auth/auth_provider.dart';
import '../../../core/theme/theme_provider.dart';
import '../../../core/services/profile_photo_service.dart';
import '../../../core/i18n/translations.dart';
import '../../../core/offline/offline_mode_service.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authStateProvider);
    final isDarkMode = ref.watch(themeModeProvider) == ThemeMode.dark;
    final tr = ref.watch(translationsProvider);

    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: Text(tr.myProfile),
        backgroundColor: DelivrColors.surface,
        actions: [
          // Connection indicator
          const Padding(
            padding: EdgeInsets.only(right: 8),
            child: ConnectionIndicator(showLabel: false),
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () {
              // TODO: Settings screen
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            // Offline banner
            const OfflineBanner(),
            
            // Profile header with photo
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: DelivrColors.surface,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                children: [
                  // Profile photo picker
                  const ProfilePhotoPicker(size: 100),
                  const SizedBox(height: 16),
                  Text(
                    authState.courierPhone ?? 'Coursier',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: DelivrColors.gold.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Text(
                      'BRONZE',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: DelivrColors.bronze,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // Dark mode toggle
            Container(
              margin: const EdgeInsets.only(bottom: 8),
              decoration: BoxDecoration(
                color: DelivrColors.surface,
                borderRadius: BorderRadius.circular(12),
              ),
              child: SwitchListTile(
                secondary: Icon(
                  isDarkMode ? Icons.dark_mode : Icons.light_mode,
                  color: DelivrColors.primary,
                ),
                title: Text(tr.darkMode),
                value: isDarkMode,
                onChanged: (value) {
                  ref.read(themeModeProvider.notifier).toggleDarkMode();
                },
              ),
            ),

            // Language selector
            Container(
              margin: const EdgeInsets.only(bottom: 8),
              decoration: BoxDecoration(
                color: DelivrColors.surface,
                borderRadius: BorderRadius.circular(12),
              ),
              child: const LanguageSelector(),
            ),

            // Menu items
            _buildMenuItem(
              icon: Icons.trending_up,
              title: tr.myPerformance,
              onTap: () => context.push(AppRoutes.earnings),
            ),
            _buildMenuItem(
              icon: Icons.emoji_events,
              title: tr.badgesAndRewards,
              onTap: () => context.push(AppRoutes.badges),
            ),
            _buildMenuItem(
              icon: Icons.history,
              title: tr.historyOfDeliveries,
              onTap: () => context.push(AppRoutes.history),
            ),
            _buildMenuItem(
              icon: Icons.help_outline,
              title: tr.helpAndSupport,
              onTap: () => context.push(AppRoutes.support),
            ),
            _buildMenuItem(
              icon: Icons.privacy_tip_outlined,
              title: tr.privacy,
              onTap: () {},
            ),

            const SizedBox(height: 24),

            // Logout button
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () async {
                  final confirm = await showDialog<bool>(
                    context: context,
                    builder: (context) => AlertDialog(
                      title: const Text('Déconnexion'),
                      content: const Text(
                        'Voulez-vous vraiment vous déconnecter ?',
                      ),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(context, false),
                          child: const Text('Annuler'),
                        ),
                        ElevatedButton(
                          onPressed: () => Navigator.pop(context, true),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: DelivrColors.error,
                          ),
                          child: const Text('Déconnexion'),
                        ),
                      ],
                    ),
                  );

                  if (confirm == true) {
                    await ref.read(authServiceProvider).logout();
                    if (context.mounted) {
                      context.go(AppRoutes.login);
                    }
                  }
                },
                icon: const Icon(Icons.logout, color: DelivrColors.error),
                label: const Text(
                  'Se déconnecter',
                  style: TextStyle(color: DelivrColors.error),
                ),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: DelivrColors.error),
                  padding: const EdgeInsets.all(16),
                ),
              ),
            ),

            const SizedBox(height: 24),

            // Version
            Text(
              'Version 1.0.0',
              style: TextStyle(
                fontSize: 12,
                color: DelivrColors.textHint,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMenuItem({
    required IconData icon,
    required String title,
    required VoidCallback onTap,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: DelivrColors.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: ListTile(
        onTap: onTap,
        leading: Icon(icon, color: DelivrColors.primary),
        title: Text(title),
        trailing: const Icon(
          Icons.chevron_right,
          color: DelivrColors.textSecondary,
        ),
      ),
    );
  }
}
