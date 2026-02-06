import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../app/theme.dart';

/// Provider for delivery history with filters
final historyFilterProvider = StateProvider<HistoryFilter>((ref) => HistoryFilter());

class HistoryFilter {
  final DateTime? startDate;
  final DateTime? endDate;
  final String? status;
  
  HistoryFilter({this.startDate, this.endDate, this.status});
  
  HistoryFilter copyWith({
    DateTime? startDate,
    DateTime? endDate,
    String? status,
  }) {
    return HistoryFilter(
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
      status: status ?? this.status,
    );
  }
}

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  final _dateFormat = DateFormat('dd/MM/yyyy');
  
  // Mock data - would be replaced with API call
  final List<Map<String, dynamic>> _deliveries = [
    {
      'id': '1',
      'status': 'COMPLETED',
      'pickup_address': 'Akwa, Douala',
      'dropoff_address': 'Bonapriso, Douala',
      'earning': 1500.0,
      'date': DateTime.now().subtract(const Duration(days: 1)),
    },
    {
      'id': '2',
      'status': 'COMPLETED',
      'pickup_address': 'Bonamoussadi, Douala',
      'dropoff_address': 'Makepe, Douala',
      'earning': 2000.0,
      'date': DateTime.now().subtract(const Duration(days: 2)),
    },
    {
      'id': '3',
      'status': 'CANCELLED',
      'pickup_address': 'Deido, Douala',
      'dropoff_address': 'Bali, Douala',
      'earning': 0.0,
      'date': DateTime.now().subtract(const Duration(days: 3)),
    },
    {
      'id': '4',
      'status': 'COMPLETED',
      'pickup_address': 'Logpom, Douala',
      'dropoff_address': 'Kotto, Douala',
      'earning': 2500.0,
      'date': DateTime.now().subtract(const Duration(days: 5)),
    },
  ];

  @override
  Widget build(BuildContext context) {
    final filter = ref.watch(historyFilterProvider);
    
    // Apply filters
    final filteredDeliveries = _deliveries.where((d) {
      if (filter.status != null && d['status'] != filter.status) {
        return false;
      }
      if (filter.startDate != null && d['date'].isBefore(filter.startDate!)) {
        return false;
      }
      if (filter.endDate != null && d['date'].isAfter(filter.endDate!)) {
        return false;
      }
      return true;
    }).toList();
    
    // Calculate stats
    final totalEarnings = filteredDeliveries
        .where((d) => d['status'] == 'COMPLETED')
        .fold<double>(0, (sum, d) => sum + (d['earning'] as double));
    final completedCount = filteredDeliveries.where((d) => d['status'] == 'COMPLETED').length;
    final cancelledCount = filteredDeliveries.where((d) => d['status'] == 'CANCELLED').length;

    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Historique'),
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: DelivrColors.textPrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.filter_list),
            onPressed: () => _showFilterDialog(context),
          ),
        ],
      ),
      body: Column(
        children: [
          // Stats Summary
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [DelivrColors.primary, DelivrColors.primary.withOpacity(0.8)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: DelivrColors.primary.withOpacity(0.3),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStatItem('Gains', '${totalEarnings.toStringAsFixed(0)} XAF', Icons.payments),
                _buildStatItem('Complétées', '$completedCount', Icons.check_circle),
                _buildStatItem('Annulées', '$cancelledCount', Icons.cancel),
              ],
            ),
          ),
          
          // Active filters
          if (filter.status != null || filter.startDate != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  const Text('Filtres: ', style: TextStyle(fontWeight: FontWeight.w500)),
                  if (filter.status != null)
                    Chip(
                      label: Text(filter.status!),
                      deleteIcon: const Icon(Icons.close, size: 16),
                      onDeleted: () {
                        ref.read(historyFilterProvider.notifier).state = 
                            filter.copyWith(status: null);
                      },
                    ),
                  if (filter.startDate != null)
                    Padding(
                      padding: const EdgeInsets.only(left: 8),
                      child: Chip(
                        label: Text('Depuis ${_dateFormat.format(filter.startDate!)}'),
                        deleteIcon: const Icon(Icons.close, size: 16),
                        onDeleted: () {
                          ref.read(historyFilterProvider.notifier).state = 
                              filter.copyWith(startDate: null);
                        },
                      ),
                    ),
                ],
              ),
            ),
          
          // Delivery List
          Expanded(
            child: filteredDeliveries.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.history, size: 64, color: DelivrColors.textSecondary),
                        const SizedBox(height: 16),
                        Text(
                          'Aucune course trouvée',
                          style: TextStyle(color: DelivrColors.textSecondary),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: filteredDeliveries.length,
                    itemBuilder: (context, index) {
                      final delivery = filteredDeliveries[index];
                      return _buildDeliveryCard(delivery);
                    },
                  ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildStatItem(String label, String value, IconData icon) {
    return Column(
      children: [
        Icon(icon, color: Colors.white, size: 28),
        const SizedBox(height: 8),
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            color: Colors.white.withOpacity(0.8),
            fontSize: 12,
          ),
        ),
      ],
    );
  }
  
  Widget _buildDeliveryCard(Map<String, dynamic> delivery) {
    final isCompleted = delivery['status'] == 'COMPLETED';
    
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _dateFormat.format(delivery['date']),
                style: TextStyle(
                  color: DelivrColors.textSecondary,
                  fontSize: 12,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: isCompleted 
                      ? DelivrColors.success.withOpacity(0.1) 
                      : DelivrColors.error.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  isCompleted ? 'Complétée' : 'Annulée',
                  style: TextStyle(
                    color: isCompleted ? DelivrColors.success : DelivrColors.error,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Icon(Icons.radio_button_checked, size: 16, color: DelivrColors.primary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  delivery['pickup_address'],
                  style: const TextStyle(fontSize: 14),
                ),
              ),
            ],
          ),
          Container(
            margin: const EdgeInsets.only(left: 7),
            height: 16,
            width: 2,
            color: DelivrColors.textSecondary.withOpacity(0.3),
          ),
          Row(
            children: [
              Icon(Icons.location_on, size: 16, color: DelivrColors.secondary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  delivery['dropoff_address'],
                  style: const TextStyle(fontSize: 14),
                ),
              ),
            ],
          ),
          if (isCompleted) ...[
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Text(
                  '+${(delivery['earning'] as double).toStringAsFixed(0)} XAF',
                  style: TextStyle(
                    color: DelivrColors.success,
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
  
  void _showFilterDialog(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        padding: const EdgeInsets.all(24),
        decoration: const BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Filtrer les courses',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const Text('Statut', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                _buildFilterChip('COMPLETED', 'Complétées'),
                _buildFilterChip('CANCELLED', 'Annulées'),
              ],
            ),
            const SizedBox(height: 16),
            const Text('Période', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                ActionChip(
                  label: const Text('7 derniers jours'),
                  onPressed: () {
                    ref.read(historyFilterProvider.notifier).state = 
                        HistoryFilter(startDate: DateTime.now().subtract(const Duration(days: 7)));
                    Navigator.pop(context);
                  },
                ),
                ActionChip(
                  label: const Text('30 derniers jours'),
                  onPressed: () {
                    ref.read(historyFilterProvider.notifier).state = 
                        HistoryFilter(startDate: DateTime.now().subtract(const Duration(days: 30)));
                    Navigator.pop(context);
                  },
                ),
              ],
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  ref.read(historyFilterProvider.notifier).state = HistoryFilter();
                  Navigator.pop(context);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: DelivrColors.textSecondary,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
                child: const Text('Réinitialiser les filtres'),
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildFilterChip(String status, String label) {
    final filter = ref.watch(historyFilterProvider);
    final isSelected = filter.status == status;
    
    return FilterChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (selected) {
        ref.read(historyFilterProvider.notifier).state = 
            filter.copyWith(status: selected ? status : null);
        Navigator.pop(context);
      },
      selectedColor: DelivrColors.primary.withOpacity(0.2),
      checkmarkColor: DelivrColors.primary,
    );
  }
}
