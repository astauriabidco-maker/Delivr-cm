import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../app/theme.dart';
import '../widgets/transaction_dialogs.dart';

/// Wallet balance state
class WalletState {
  final double balance;
  final double debt;
  final List<WalletTransaction> transactions;
  final bool isLoading;
  
  const WalletState({
    this.balance = 0,
    this.debt = 0,
    this.transactions = const [],
    this.isLoading = false,
  });
  
  /// Net balance (balance - debt)
  double get netBalance => balance - debt;
  
  /// Whether the courier has debt
  bool get hasDebt => debt > 0;
  
  /// Whether net balance is negative
  bool get isNegative => netBalance < 0;
}

/// Wallet transaction
class WalletTransaction {
  final String id;
  final String type; // 'earning', 'withdrawal', 'debt', 'debt_payment'
  final double amount;
  final String description;
  final DateTime date;
  
  const WalletTransaction({
    required this.id,
    required this.type,
    required this.amount,
    required this.description,
    required this.date,
  });
}

/// Mock wallet provider
final walletProvider = StateProvider<WalletState>((ref) {
  // Mock data - would be from API
  return WalletState(
    balance: 15000,
    debt: 18500, // Example: courier has debt
    transactions: [
      WalletTransaction(
        id: '1',
        type: 'earning',
        amount: 1500,
        description: 'Course #A2F4',
        date: DateTime.now().subtract(const Duration(hours: 1)),
      ),
      WalletTransaction(
        id: '2',
        type: 'debt',
        amount: -5000,
        description: 'Remboursement colis perdu',
        date: DateTime.now().subtract(const Duration(days: 1)),
      ),
      WalletTransaction(
        id: '3',
        type: 'earning',
        amount: 2000,
        description: 'Course #B3G6',
        date: DateTime.now().subtract(const Duration(days: 1)),
      ),
      WalletTransaction(
        id: '4',
        type: 'withdrawal',
        amount: -10000,
        description: 'Retrait OM',
        date: DateTime.now().subtract(const Duration(days: 2)),
      ),
      WalletTransaction(
        id: '5',
        type: 'debt_payment',
        amount: -2500,
        description: 'Remboursement dette',
        date: DateTime.now().subtract(const Duration(days: 3)),
      ),
    ],
  );
});

class WalletScreen extends ConsumerWidget {
  const WalletScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wallet = ref.watch(walletProvider);
    final currencyFormat = NumberFormat('#,###', 'fr_FR');

    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Portefeuille'),
        backgroundColor: DelivrColors.surface,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            // Balance card
            Container(
              margin: const EdgeInsets.all(16),
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: wallet.isNegative
                      ? [const Color(0xFFD32F2F), const Color(0xFFB71C1C)]
                      : [DelivrColors.primary, DelivrColors.primary.withOpacity(0.8)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: (wallet.isNegative ? Colors.red : DelivrColors.primary)
                        .withOpacity(0.3),
                    blurRadius: 15,
                    offset: const Offset(0, 5),
                  ),
                ],
              ),
              child: Column(
                children: [
                  Text(
                    wallet.isNegative ? 'Solde à rembourser' : 'Solde disponible',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.9),
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (wallet.isNegative)
                        const Text(
                          '-',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 36,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      Text(
                        currencyFormat.format(wallet.netBalance.abs()),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 36,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const Padding(
                        padding: EdgeInsets.only(top: 8, left: 4),
                        child: Text(
                          'XAF',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 16,
                          ),
                        ),
                      ),
                    ],
                  ),
                  
                  // Debt warning
                  if (wallet.hasDebt) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(
                            Icons.warning_amber_rounded,
                            color: Colors.amber,
                            size: 20,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Dette: ${currencyFormat.format(wallet.debt)} XAF',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  
                  const SizedBox(height: 20),
                  
                  // Top-up button (always visible)
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () => _showTopUpDialog(context, ref),
                      icon: const Icon(Icons.add_circle_outline),
                      label: const Text('Recharger'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: Colors.blue,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 12),
                  
                  // Action buttons
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: wallet.isNegative ? null : () {
                            _showWithdrawDialog(context, ref, wallet);
                          },
                          icon: const Icon(Icons.arrow_upward),
                          label: const Text('Retirer'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.white,
                            foregroundColor: wallet.isNegative 
                                ? Colors.grey 
                                : DelivrColors.primary,
                            disabledBackgroundColor: Colors.white54,
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                        ),
                      ),
                      if (wallet.hasDebt) ...[
                        const SizedBox(width: 12),
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: () {
                              _showPayDebtDialog(context, ref, wallet);
                            },
                            icon: const Icon(Icons.payment),
                            label: const Text('Rembourser'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.amber,
                              foregroundColor: Colors.black87,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),

            // Balance breakdown
            if (wallet.hasDebt)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.orange.shade50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.orange.shade200),
                  ),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          Icon(Icons.info_outline, color: Colors.orange.shade700),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'Détail de votre solde',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: Colors.orange.shade900,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      _buildBreakdownRow(
                        'Gains cumulés',
                        '${currencyFormat.format(wallet.balance)} XAF',
                        Colors.green,
                      ),
                      const SizedBox(height: 8),
                      _buildBreakdownRow(
                        'Dette à rembourser',
                        '-${currencyFormat.format(wallet.debt)} XAF',
                        Colors.red,
                      ),
                      const Divider(height: 20),
                      _buildBreakdownRow(
                        'Solde net',
                        '${wallet.isNegative ? "-" : ""}${currencyFormat.format(wallet.netBalance.abs())} XAF',
                        wallet.isNegative ? Colors.red : Colors.green,
                        isBold: true,
                      ),
                    ],
                  ),
                ),
              ),

            const SizedBox(height: 24),

            // Transaction history
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Historique',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  TextButton(
                    onPressed: () {},
                    child: const Text('Voir tout'),
                  ),
                ],
              ),
            ),

            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: wallet.transactions.length,
              itemBuilder: (context, index) {
                final tx = wallet.transactions[index];
                return _buildTransactionItem(tx, currencyFormat);
              },
            ),

            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildBreakdownRow(String label, String value, Color color, {bool isBold = false}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(
            fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
          ),
        ),
        Text(
          value,
          style: TextStyle(
            color: color,
            fontWeight: isBold ? FontWeight.bold : FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _buildTransactionItem(WalletTransaction tx, NumberFormat format) {
    IconData icon;
    Color color;
    
    switch (tx.type) {
      case 'earning':
        icon = Icons.add_circle;
        color = Colors.green;
        break;
      case 'withdrawal':
        icon = Icons.arrow_upward;
        color = Colors.blue;
        break;
      case 'debt':
        icon = Icons.remove_circle;
        color = Colors.red;
        break;
      case 'debt_payment':
        icon = Icons.payment;
        color = Colors.orange;
        break;
      default:
        icon = Icons.swap_horiz;
        color = Colors.grey;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  tx.description,
                  style: const TextStyle(fontWeight: FontWeight.w500),
                ),
                Text(
                  _formatDate(tx.date),
                  style: TextStyle(
                    fontSize: 12,
                    color: DelivrColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Text(
            '${tx.amount >= 0 ? '+' : ''}${format.format(tx.amount)} XAF',
            style: TextStyle(
              fontWeight: FontWeight.bold,
              color: tx.amount >= 0 ? Colors.green : Colors.red,
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);
    
    if (diff.inHours < 1) {
      return 'Il y a ${diff.inMinutes} min';
    } else if (diff.inHours < 24) {
      return 'Il y a ${diff.inHours}h';
    } else if (diff.inDays == 1) {
      return 'Hier';
    } else {
      return DateFormat('dd/MM/yyyy').format(date);
    }
  }

  void _showWithdrawDialog(BuildContext context, WidgetRef ref, WalletState wallet) {
    showWithdrawalDialog(
      context,
      maxAmount: wallet.balance,
      onSuccess: () {
        // Refresh wallet data
        // ref.invalidate(walletProvider);
      },
    );
  }

  void _showPayDebtDialog(BuildContext context, WidgetRef ref, WalletState wallet) {
    showDebtPaymentDialog(
      context,
      debt: wallet.debt,
      availableBalance: wallet.balance,
      onSuccess: () {
        // Refresh wallet data
        // ref.invalidate(walletProvider);
      },
    );
  }

  void _showTopUpDialog(BuildContext context, WidgetRef ref) {
    showTopUpDialog(
      context,
      onSuccess: () {
        // Refresh wallet data
        // ref.invalidate(walletProvider);
      },
    );
  }
}
