import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme.dart';

/// Leaderboard entry model
class LeaderboardEntry {
  final int rank;
  final String name;
  final String avatar;
  final int deliveries;
  final double rating;
  final String level;
  final bool isCurrentUser;

  const LeaderboardEntry({
    required this.rank,
    required this.name,
    required this.avatar,
    required this.deliveries,
    required this.rating,
    required this.level,
    this.isCurrentUser = false,
  });
}

/// Mock leaderboard data
final leaderboardProvider = FutureProvider<List<LeaderboardEntry>>((ref) async {
  await Future.delayed(const Duration(milliseconds: 600));

  return const [
    LeaderboardEntry(rank: 1, name: 'Jean-Pierre M.', avatar: '👨🏾', deliveries: 312, rating: 4.9, level: 'Gold'),
    LeaderboardEntry(rank: 2, name: 'Fatima A.', avatar: '👩🏾', deliveries: 287, rating: 4.95, level: 'Gold'),
    LeaderboardEntry(rank: 3, name: 'Emmanuel K.', avatar: '👨🏾‍🦱', deliveries: 253, rating: 4.8, level: 'Silver'),
    LeaderboardEntry(rank: 4, name: 'Clarisse N.', avatar: '👩🏾‍🦱', deliveries: 198, rating: 4.85, level: 'Silver'),
    LeaderboardEntry(rank: 5, name: 'Paul B.', avatar: '👨🏾‍🦲', deliveries: 176, rating: 4.7, level: 'Silver'),
    LeaderboardEntry(rank: 6, name: 'Alice T.', avatar: '👩🏾‍🦰', deliveries: 165, rating: 4.75, level: 'Bronze'),
    LeaderboardEntry(rank: 7, name: 'Daniel O.', avatar: '👨🏾', deliveries: 148, rating: 4.6, level: 'Bronze'),
    LeaderboardEntry(rank: 8, name: 'Grace M.', avatar: '👩🏾', deliveries: 132, rating: 4.65, level: 'Bronze'),
    LeaderboardEntry(rank: 12, name: 'Vous', avatar: '🧑🏾', deliveries: 47, rating: 4.5, level: 'Bronze', isCurrentUser: true),
  ];
});

class LeaderboardScreen extends ConsumerWidget {
  const LeaderboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final leaderboardAsync = ref.watch(leaderboardProvider);

    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Classement'),
        backgroundColor: DelivrColors.surface,
        elevation: 0,
      ),
      body: leaderboardAsync.when(
        loading: () => const Center(
          child: CircularProgressIndicator(color: DelivrColors.primary),
        ),
        error: (error, _) => Center(child: Text('Erreur: $error')),
        data: (entries) {
          final top3 = entries.where((e) => e.rank <= 3).toList();
          final rest = entries.where((e) => e.rank > 3).toList();

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                // Period selector
                _buildPeriodSelector(),
                const SizedBox(height: 20),

                // Top 3 podium
                _buildPodium(top3),
                const SizedBox(height: 24),

                // Rest of leaderboard
                Container(
                  decoration: BoxDecoration(
                    color: DelivrColors.surface,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: rest.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) => _buildRow(rest[index]),
                  ),
                ),
                const SizedBox(height: 20),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildPeriodSelector() {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: DelivrColors.surface,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          _buildPeriodTab('Semaine', true),
          _buildPeriodTab('Mois', false),
          _buildPeriodTab('Tout', false),
        ],
      ),
    );
  }

  Widget _buildPeriodTab(String label, bool active) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: active ? DelivrColors.primary : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(
          label,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: active ? Colors.white : DelivrColors.textSecondary,
            fontWeight: active ? FontWeight.w600 : FontWeight.normal,
            fontSize: 14,
          ),
        ),
      ),
    );
  }

  Widget _buildPodium(List<LeaderboardEntry> top3) {
    if (top3.length < 3) return const SizedBox.shrink();

    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        // 2nd place
        Expanded(child: _buildPodiumCard(top3[1], 100, DelivrColors.silver)),
        const SizedBox(width: 8),
        // 1st place
        Expanded(child: _buildPodiumCard(top3[0], 130, DelivrColors.gold)),
        const SizedBox(width: 8),
        // 3rd place
        Expanded(child: _buildPodiumCard(top3[2], 80, DelivrColors.bronze)),
      ],
    );
  }

  Widget _buildPodiumCard(LeaderboardEntry entry, double height, Color color) {
    final medal = switch (entry.rank) {
      1 => '🥇',
      2 => '🥈',
      3 => '🥉',
      _ => '',
    };

    return Column(
      children: [
        // Avatar
        Text(entry.avatar, style: const TextStyle(fontSize: 36)),
        const SizedBox(height: 4),
        Text(
          entry.name.split(' ').first,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
          overflow: TextOverflow.ellipsis,
        ),
        Text(
          '${entry.deliveries} courses',
          style: const TextStyle(fontSize: 11, color: DelivrColors.textSecondary),
        ),
        const SizedBox(height: 8),

        // Podium pillar
        Container(
          height: height,
          width: double.infinity,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [color, color.withValues(alpha: 0.6)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(medal, style: const TextStyle(fontSize: 28)),
              const SizedBox(height: 4),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.star, color: Colors.white, size: 14),
                  const SizedBox(width: 2),
                  Text(
                    '${entry.rating}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildRow(LeaderboardEntry entry) {
    return Container(
      color: entry.isCurrentUser
          ? DelivrColors.primary.withValues(alpha: 0.08)
          : null,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          // Rank
          SizedBox(
            width: 32,
            child: Text(
              '#${entry.rank}',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 15,
                color: entry.isCurrentUser
                    ? DelivrColors.primary
                    : DelivrColors.textSecondary,
              ),
            ),
          ),
          const SizedBox(width: 12),

          // Avatar
          Text(entry.avatar, style: const TextStyle(fontSize: 28)),
          const SizedBox(width: 12),

          // Name + level
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.name,
                  style: TextStyle(
                    fontWeight: entry.isCurrentUser
                        ? FontWeight.bold
                        : FontWeight.w500,
                    fontSize: 14,
                    color: entry.isCurrentUser
                        ? DelivrColors.primary
                        : null,
                  ),
                ),
                Text(
                  entry.level,
                  style: const TextStyle(
                    fontSize: 12,
                    color: DelivrColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),

          // Stats
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                '${entry.deliveries} courses',
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.star, color: DelivrColors.gold, size: 14),
                  const SizedBox(width: 2),
                  Text(
                    '${entry.rating}',
                    style: const TextStyle(
                      fontSize: 12,
                      color: DelivrColors.textSecondary,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}
