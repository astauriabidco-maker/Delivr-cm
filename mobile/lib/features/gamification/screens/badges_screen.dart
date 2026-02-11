import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme.dart';

/// Badge model
class Badge {
  final String id;
  final String name;
  final String description;
  final String icon;
  final bool unlocked;
  final double progress; // 0.0 to 1.0
  final String? unlockedAt;
  final String category;

  const Badge({
    required this.id,
    required this.name,
    required this.description,
    required this.icon,
    required this.unlocked,
    required this.progress,
    this.unlockedAt,
    required this.category,
  });
}

/// Courier level data
class CourierLevel {
  final String name;
  final String icon;
  final Color color;
  final int currentXp;
  final int nextLevelXp;
  final int deliveriesCompleted;

  const CourierLevel({
    required this.name,
    required this.icon,
    required this.color,
    required this.currentXp,
    required this.nextLevelXp,
    required this.deliveriesCompleted,
  });

  double get progress => currentXp / nextLevelXp;
}

/// Mock badge data provider
final badgesProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  await Future.delayed(const Duration(milliseconds: 600));

  return {
    'level': const CourierLevel(
      name: 'Bronze',
      icon: '🥉',
      color: DelivrColors.bronze,
      currentXp: 1250,
      nextLevelXp: 2500,
      deliveriesCompleted: 47,
    ),
    'badges': const [
      // Speed badges
      Badge(
        id: 'first_delivery',
        name: 'Première course',
        description: 'Compléter votre première livraison',
        icon: '🎯',
        unlocked: true,
        progress: 1.0,
        unlockedAt: '15 Jan 2026',
        category: 'Débuts',
      ),
      Badge(
        id: 'speed_demon',
        name: 'Express',
        description: 'Livrer en moins de 15 minutes',
        icon: '⚡',
        unlocked: true,
        progress: 1.0,
        unlockedAt: '18 Jan 2026',
        category: 'Vitesse',
      ),
      Badge(
        id: 'ten_deliveries',
        name: '10 courses',
        description: 'Compléter 10 livraisons',
        icon: '🔟',
        unlocked: true,
        progress: 1.0,
        unlockedAt: '20 Jan 2026',
        category: 'Volume',
      ),
      Badge(
        id: 'fifty_deliveries',
        name: 'Semi-pro',
        description: 'Compléter 50 livraisons',
        icon: '🏅',
        unlocked: false,
        progress: 0.94,
        category: 'Volume',
      ),
      Badge(
        id: 'night_owl',
        name: 'Couche-tard',
        description: 'Livrer après 22h',
        icon: '🦉',
        unlocked: true,
        progress: 1.0,
        unlockedAt: '25 Jan 2026',
        category: 'Spécial',
      ),
      Badge(
        id: 'five_star',
        name: '5 étoiles',
        description: 'Obtenir une note parfaite de 5.0',
        icon: '⭐',
        unlocked: true,
        progress: 1.0,
        unlockedAt: '28 Jan 2026',
        category: 'Qualité',
      ),
      Badge(
        id: 'rain_warrior',
        name: 'Guerrier de la pluie',
        description: 'Livrer sous forte pluie',
        icon: '🌧️',
        unlocked: false,
        progress: 0.0,
        category: 'Spécial',
      ),
      Badge(
        id: 'hundred_deliveries',
        name: 'Centurion',
        description: 'Compléter 100 livraisons',
        icon: '💯',
        unlocked: false,
        progress: 0.47,
        category: 'Volume',
      ),
      Badge(
        id: 'marathon',
        name: 'Marathon',
        description: 'Parcourir 100 km total',
        icon: '🏃',
        unlocked: false,
        progress: 0.72,
        category: 'Distance',
      ),
      Badge(
        id: 'streak_7',
        name: 'Série de 7',
        description: 'Livrer 7 jours consécutifs',
        icon: '🔥',
        unlocked: false,
        progress: 0.57,
        category: 'Régularité',
      ),
      Badge(
        id: 'loyal_customer',
        name: 'Fidélité',
        description: 'Livrer 5 fois pour le même client',
        icon: '💎',
        unlocked: false,
        progress: 0.4,
        category: 'Qualité',
      ),
      Badge(
        id: 'thousand_deliveries',
        name: 'Légende',
        description: 'Compléter 1000 livraisons',
        icon: '👑',
        unlocked: false,
        progress: 0.047,
        category: 'Volume',
      ),
    ],
  };
});

class BadgesScreen extends ConsumerWidget {
  const BadgesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final badgesAsync = ref.watch(badgesProvider);

    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Badges & Niveau'),
        backgroundColor: DelivrColors.surface,
        elevation: 0,
      ),
      body: badgesAsync.when(
        loading: () => const Center(
          child: CircularProgressIndicator(color: DelivrColors.primary),
        ),
        error: (error, _) => Center(child: Text('Erreur: $error')),
        data: (data) {
          final level = data['level'] as CourierLevel;
          final badges = data['badges'] as List<Badge>;
          final unlocked = badges.where((b) => b.unlocked).length;

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Level card
                _buildLevelCard(level),
                const SizedBox(height: 20),

                // Stats row
                _buildStatsRow(unlocked, badges.length, level.deliveriesCompleted),
                const SizedBox(height: 24),

                // Unlocked badges
                _buildSection('🏆 Badges obtenus', badges.where((b) => b.unlocked).toList()),
                const SizedBox(height: 24),

                // In progress
                _buildSection('🔓 En cours', badges.where((b) => !b.unlocked && b.progress > 0).toList()),
                const SizedBox(height: 24),

                // Locked
                _buildSection('🔒 À découvrir', badges.where((b) => !b.unlocked && b.progress == 0).toList()),
                const SizedBox(height: 24),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildLevelCard(CourierLevel level) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            level.color.withValues(alpha: 0.9),
            level.color.withValues(alpha: 0.6),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: level.color.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        children: [
          Text(
            level.icon,
            style: const TextStyle(fontSize: 48),
          ),
          const SizedBox(height: 8),
          Text(
            'Niveau ${level.name}',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16),

          // XP Progress bar
          Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${level.currentXp} XP',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.9),
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    '${level.nextLevelXp} XP',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.7),
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: LinearProgressIndicator(
                  value: level.progress,
                  minHeight: 12,
                  backgroundColor: Colors.white.withValues(alpha: 0.2),
                  valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                '${(level.progress * 100).toInt()}% vers Silver',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.8),
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatsRow(int unlocked, int total, int deliveries) {
    return Row(
      children: [
        _buildStatChip('🏆', '$unlocked/$total', 'Badges'),
        const SizedBox(width: 10),
        _buildStatChip('📦', '$deliveries', 'Courses'),
        const SizedBox(width: 10),
        _buildStatChip('🔥', '4j', 'Série'),
      ],
    );
  }

  Widget _buildStatChip(String emoji, String value, String label) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
        decoration: BoxDecoration(
          color: DelivrColors.surface,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          children: [
            Text(emoji, style: const TextStyle(fontSize: 22)),
            const SizedBox(height: 6),
            Text(
              value,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            Text(
              label,
              style: const TextStyle(
                fontSize: 12,
                color: DelivrColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSection(String title, List<Badge> badges) {
    if (badges.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Text(
            title,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 0.75,
          ),
          itemCount: badges.length,
          itemBuilder: (context, index) => _buildBadgeCard(badges[index]),
        ),
      ],
    );
  }

  Widget _buildBadgeCard(Badge badge) {
    return GestureDetector(
      onTap: () {},
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: DelivrColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: badge.unlocked
              ? Border.all(color: DelivrColors.gold.withValues(alpha: 0.5), width: 2)
              : null,
          boxShadow: badge.unlocked
              ? [
                  BoxShadow(
                    color: DelivrColors.gold.withValues(alpha: 0.1),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ]
              : null,
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Icon
            Text(
              badge.icon,
              style: TextStyle(
                fontSize: 32,
                color: badge.unlocked ? null : const Color(0xFF9E9E9E),
              ),
            ),
            const SizedBox(height: 8),

            // Name
            Text(
              badge.name,
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: badge.unlocked ? null : DelivrColors.textSecondary,
              ),
            ),
            const SizedBox(height: 6),

            // Progress or checkmark
            if (badge.unlocked)
              const Icon(Icons.check_circle, color: DelivrColors.success, size: 18)
            else if (badge.progress > 0)
              Column(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: badge.progress,
                      minHeight: 5,
                      backgroundColor: DelivrColors.divider,
                      valueColor: const AlwaysStoppedAnimation<Color>(DelivrColors.primary),
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    '${(badge.progress * 100).toInt()}%',
                    style: const TextStyle(
                      fontSize: 10,
                      color: DelivrColors.textSecondary,
                    ),
                  ),
                ],
              )
            else
              const Icon(Icons.lock_outline, color: DelivrColors.textHint, size: 16),
          ],
        ),
      ),
    );
  }
}
