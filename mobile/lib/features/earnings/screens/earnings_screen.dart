import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';

import '../../../app/theme.dart';

/// Mock earnings data — will be replaced by API data
class EarningsData {
  final double todayEarnings;
  final double weekEarnings;
  final double monthEarnings;
  final int todayDeliveries;
  final int weekDeliveries;
  final int monthDeliveries;
  final double avgPerDelivery;
  final List<DailyEarning> weeklyChart;
  final List<EarningEntry> recentEntries;

  const EarningsData({
    required this.todayEarnings,
    required this.weekEarnings,
    required this.monthEarnings,
    required this.todayDeliveries,
    required this.weekDeliveries,
    required this.monthDeliveries,
    required this.avgPerDelivery,
    required this.weeklyChart,
    required this.recentEntries,
  });
}

class DailyEarning {
  final String day;
  final double amount;
  const DailyEarning(this.day, this.amount);
}

class EarningEntry {
  final String id;
  final String description;
  final double amount;
  final DateTime date;
  final String type; // 'delivery', 'bonus', 'tip', 'penalty'
  const EarningEntry({
    required this.id,
    required this.description,
    required this.amount,
    required this.date,
    required this.type,
  });
}

/// Provider for earnings data (mock for now)
final earningsProvider = FutureProvider<EarningsData>((ref) async {
  // Simulate API call
  await Future.delayed(const Duration(milliseconds: 800));

  return EarningsData(
    todayEarnings: 12500,
    weekEarnings: 67800,
    monthEarnings: 245000,
    todayDeliveries: 8,
    weekDeliveries: 42,
    monthDeliveries: 156,
    avgPerDelivery: 1562,
    weeklyChart: const [
      DailyEarning('Lun', 8500),
      DailyEarning('Mar', 12300),
      DailyEarning('Mer', 9800),
      DailyEarning('Jeu', 11200),
      DailyEarning('Ven', 14500),
      DailyEarning('Sam', 7200),
      DailyEarning('Dim', 4300),
    ],
    recentEntries: [
      EarningEntry(
        id: '1',
        description: 'Livraison Akwa → Bonapriso',
        amount: 1800,
        date: DateTime.now().subtract(const Duration(hours: 1)),
        type: 'delivery',
      ),
      EarningEntry(
        id: '2',
        description: 'Bonus vitesse ⚡',
        amount: 500,
        date: DateTime.now().subtract(const Duration(hours: 2)),
        type: 'bonus',
      ),
      EarningEntry(
        id: '3',
        description: 'Livraison Deïdo → Bonanjo',
        amount: 2200,
        date: DateTime.now().subtract(const Duration(hours: 3)),
        type: 'delivery',
      ),
      EarningEntry(
        id: '4',
        description: 'Pourboire client 🎉',
        amount: 300,
        date: DateTime.now().subtract(const Duration(hours: 4)),
        type: 'tip',
      ),
      EarningEntry(
        id: '5',
        description: 'Livraison Bali → Akwa',
        amount: 1500,
        date: DateTime.now().subtract(const Duration(hours: 5)),
        type: 'delivery',
      ),
      EarningEntry(
        id: '6',
        description: 'Livraison Ndokotti → Makepe',
        amount: 2800,
        date: DateTime.now().subtract(const Duration(hours: 7)),
        type: 'delivery',
      ),
      EarningEntry(
        id: '7',
        description: 'Livraison Logpom → PK14',
        amount: 3200,
        date: DateTime.now().subtract(const Duration(hours: 9)),
        type: 'delivery',
      ),
    ],
  );
});

class EarningsScreen extends ConsumerStatefulWidget {
  const EarningsScreen({super.key});

  @override
  ConsumerState<EarningsScreen> createState() => _EarningsScreenState();
}

class _EarningsScreenState extends ConsumerState<EarningsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _numberFormat = NumberFormat('#,###', 'fr_FR');

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final earningsAsync = ref.watch(earningsProvider);

    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Mes gains'),
        backgroundColor: DelivrColors.surface,
        elevation: 0,
      ),
      body: earningsAsync.when(
        loading: () => const Center(
          child: CircularProgressIndicator(color: DelivrColors.primary),
        ),
        error: (error, _) => Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 48, color: DelivrColors.error),
              const SizedBox(height: 16),
              Text('Erreur: $error'),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => ref.invalidate(earningsProvider),
                child: const Text('Réessayer'),
              ),
            ],
          ),
        ),
        data: (data) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(earningsProvider),
          color: DelivrColors.primary,
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Main balance card
                _buildMainCard(data),
                const SizedBox(height: 20),

                // Period tabs
                _buildPeriodTabs(data),
                const SizedBox(height: 20),

                // Weekly chart
                _buildWeeklyChart(data),
                const SizedBox(height: 20),

                // Recent earnings list
                _buildRecentEarnings(data),
                const SizedBox(height: 20),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildMainCard(EarningsData data) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [DelivrColors.primary, DelivrColors.primaryDark],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: DelivrColors.primary.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.account_balance_wallet, color: Colors.white70, size: 20),
              const SizedBox(width: 8),
              Text(
                "Gains aujourd'hui",
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.85),
                  fontSize: 14,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            '${_numberFormat.format(data.todayEarnings)} XAF',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 36,
              fontWeight: FontWeight.bold,
              letterSpacing: -1,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.delivery_dining, color: Colors.white, size: 16),
                const SizedBox(width: 4),
                Text(
                  '${data.todayDeliveries} livraisons',
                  style: const TextStyle(color: Colors.white, fontSize: 13),
                ),
                const SizedBox(width: 12),
                const Icon(Icons.trending_up, color: Colors.white, size: 16),
                const SizedBox(width: 4),
                Text(
                  'Moy. ${_numberFormat.format(data.avgPerDelivery)} XAF',
                  style: const TextStyle(color: Colors.white, fontSize: 13),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPeriodTabs(EarningsData data) {
    return Row(
      children: [
        _buildPeriodCard(
          'Semaine',
          '${_numberFormat.format(data.weekEarnings)} XAF',
          '${data.weekDeliveries} courses',
          Icons.date_range,
          DelivrColors.info,
        ),
        const SizedBox(width: 12),
        _buildPeriodCard(
          'Mois',
          '${_numberFormat.format(data.monthEarnings)} XAF',
          '${data.monthDeliveries} courses',
          Icons.calendar_month,
          DelivrColors.success,
        ),
      ],
    );
  }

  Widget _buildPeriodCard(
    String label,
    String amount,
    String subtitle,
    IconData icon,
    Color color,
  ) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: DelivrColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: color.withValues(alpha: 0.2)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(icon, size: 16, color: color),
                ),
                const SizedBox(width: 8),
                Text(
                  label,
                  style: const TextStyle(
                    fontSize: 13,
                    color: DelivrColors.textSecondary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              amount,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              subtitle,
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

  Widget _buildWeeklyChart(EarningsData data) {
    final maxEarning = data.weeklyChart.map((e) => e.amount).reduce(
          (a, b) => a > b ? a : b,
        );

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: DelivrColors.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.bar_chart, size: 20, color: DelivrColors.primary),
              SizedBox(width: 8),
              Text(
                'Cette semaine',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          SizedBox(
            height: 180,
            child: BarChart(
              BarChartData(
                alignment: BarChartAlignment.spaceAround,
                maxY: maxEarning * 1.2,
                barTouchData: BarTouchData(
                  enabled: true,
                  touchTooltipData: BarTouchTooltipData(
                    getTooltipItem: (group, groupIndex, rod, rodIndex) {
                      return BarTooltipItem(
                        '${_numberFormat.format(rod.toY.toInt())} XAF',
                        const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      );
                    },
                  ),
                ),
                titlesData: FlTitlesData(
                  show: true,
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      getTitlesWidget: (value, meta) {
                        final idx = value.toInt();
                        if (idx >= 0 && idx < data.weeklyChart.length) {
                          return Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              data.weeklyChart[idx].day,
                              style: const TextStyle(
                                color: DelivrColors.textSecondary,
                                fontSize: 12,
                              ),
                            ),
                          );
                        }
                        return const SizedBox.shrink();
                      },
                    ),
                  ),
                  leftTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                  topTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                  rightTitles: const AxisTitles(
                    sideTitles: SideTitles(showTitles: false),
                  ),
                ),
                borderData: FlBorderData(show: false),
                gridData: const FlGridData(show: false),
                barGroups: data.weeklyChart.asMap().entries.map((entry) {
                  final isToday = entry.key == DateTime.now().weekday - 1;
                  return BarChartGroupData(
                    x: entry.key,
                    barRods: [
                      BarChartRodData(
                        toY: entry.value.amount,
                        color: isToday
                            ? DelivrColors.primary
                            : DelivrColors.primary.withValues(alpha: 0.3),
                        width: 28,
                        borderRadius: const BorderRadius.vertical(
                          top: Radius.circular(8),
                        ),
                      ),
                    ],
                  );
                }).toList(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecentEarnings(EarningsData data) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            Icon(Icons.receipt_long, size: 20, color: DelivrColors.textSecondary),
            SizedBox(width: 8),
            Text(
              "Gains récents",
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            color: DelivrColors.surface,
            borderRadius: BorderRadius.circular(16),
          ),
          child: ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: data.recentEntries.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final entry = data.recentEntries[index];
              return _buildEarningRow(entry);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildEarningRow(EarningEntry entry) {
    final icon = switch (entry.type) {
      'delivery' => Icons.delivery_dining,
      'bonus' => Icons.bolt,
      'tip' => Icons.favorite,
      'penalty' => Icons.warning,
      _ => Icons.monetization_on,
    };
    final color = switch (entry.type) {
      'delivery' => DelivrColors.primary,
      'bonus' => DelivrColors.gold,
      'tip' => DelivrColors.success,
      'penalty' => DelivrColors.error,
      _ => DelivrColors.textSecondary,
    };
    final timeAgo = _formatTimeAgo(entry.date);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, size: 20, color: color),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.description,
                  style: const TextStyle(
                    fontWeight: FontWeight.w500,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  timeAgo,
                  style: const TextStyle(
                    fontSize: 12,
                    color: DelivrColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Text(
            '+${_numberFormat.format(entry.amount)} XAF',
            style: TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 15,
              color: entry.type == 'penalty' ? DelivrColors.error : DelivrColors.success,
            ),
          ),
        ],
      ),
    );
  }

  String _formatTimeAgo(DateTime date) {
    final diff = DateTime.now().difference(date);
    if (diff.inMinutes < 60) return 'Il y a ${diff.inMinutes} min';
    if (diff.inHours < 24) return 'Il y a ${diff.inHours}h';
    return 'Il y a ${diff.inDays}j';
  }
}
