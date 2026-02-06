import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme.dart';

/// Mobile Money operator
enum MobileMoneyOperator {
  mtnMomo('MTN MoMo', 'MTN Mobile Money', Colors.amber, '6'),
  orangeMoney('Orange Money', 'Orange Money', Colors.deepOrange, '69');

  const MobileMoneyOperator(this.name, this.fullName, this.color, this.prefix);

  final String name;
  final String fullName;
  final Color color;
  final String prefix;
}

/// Transaction type
enum TransactionType { withdrawal, debtPayment }

/// Withdrawal dialog
class WithdrawalDialog extends ConsumerStatefulWidget {
  final double maxAmount;
  final VoidCallback? onSuccess;

  const WithdrawalDialog({
    super.key,
    required this.maxAmount,
    this.onSuccess,
  });

  @override
  ConsumerState<WithdrawalDialog> createState() => _WithdrawalDialogState();
}

class _WithdrawalDialogState extends ConsumerState<WithdrawalDialog> {
  final _formKey = GlobalKey<FormState>();
  final _amountController = TextEditingController();
  final _phoneController = TextEditingController();
  MobileMoneyOperator _selectedOperator = MobileMoneyOperator.mtnMomo;
  bool _isLoading = false;
  int _step = 1; // 1: form, 2: confirm, 3: success

  @override
  void dispose() {
    _amountController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: _buildContent(),
    );
  }

  Widget _buildContent() {
    switch (_step) {
      case 1:
        return _buildForm();
      case 2:
        return _buildConfirmation();
      case 3:
        return _buildSuccess();
      default:
        return _buildForm();
    }
  }

  Widget _buildForm() {
    return SingleChildScrollView(
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: DelivrColors.success.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.arrow_upward, color: DelivrColors.success),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Text(
                    'Retirer des fonds',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),

            const SizedBox(height: 8),
            Text(
              'Solde disponible: ${widget.maxAmount.toStringAsFixed(0)} XAF',
              style: TextStyle(color: DelivrColors.textSecondary),
            ),

            const SizedBox(height: 24),

            // Operator selection
            const Text(
              'Opérateur Mobile Money',
              style: TextStyle(fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 8),
            Row(
              children: MobileMoneyOperator.values.map((op) {
                final isSelected = _selectedOperator == op;
                return Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _selectedOperator = op),
                    child: Container(
                      margin: EdgeInsets.only(
                        right: op == MobileMoneyOperator.mtnMomo ? 8 : 0,
                        left: op == MobileMoneyOperator.orangeMoney ? 8 : 0,
                      ),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      decoration: BoxDecoration(
                        color: isSelected ? op.color.withOpacity(0.1) : Colors.grey.shade100,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isSelected ? op.color : Colors.transparent,
                          width: 2,
                        ),
                      ),
                      child: Column(
                        children: [
                          Icon(
                            Icons.smartphone,
                            color: isSelected ? op.color : Colors.grey,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            op.name,
                            style: TextStyle(
                              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                              color: isSelected ? op.color : Colors.grey,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),

            const SizedBox(height: 20),

            // Amount
            const Text('Montant à retirer', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            TextFormField(
              controller: _amountController,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: InputDecoration(
                hintText: 'Ex: 5000',
                suffixText: 'XAF',
                filled: true,
                fillColor: Colors.grey.shade100,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Veuillez entrer un montant';
                }
                final amount = double.tryParse(value) ?? 0;
                if (amount < 500) {
                  return 'Minimum 500 XAF';
                }
                if (amount > widget.maxAmount) {
                  return 'Montant supérieur à votre solde';
                }
                return null;
              },
            ),

            const SizedBox(height: 16),

            // Phone number
            const Text('Numéro de téléphone', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            TextFormField(
              controller: _phoneController,
              keyboardType: TextInputType.phone,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: InputDecoration(
                hintText: _selectedOperator == MobileMoneyOperator.mtnMomo
                    ? '6XXXXXXXX'
                    : '69XXXXXXX',
                prefixText: '+237 ',
                filled: true,
                fillColor: Colors.grey.shade100,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Veuillez entrer un numéro';
                }
                if (value.length != 9) {
                  return 'Numéro invalide (9 chiffres)';
                }
                return null;
              },
            ),

            const SizedBox(height: 24),

            // Submit button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _isLoading
                    ? null
                    : () {
                        if (_formKey.currentState!.validate()) {
                          setState(() => _step = 2);
                        }
                      },
                style: ElevatedButton.styleFrom(
                  backgroundColor: _selectedOperator.color,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Continuer',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConfirmation() {
    final amount = double.tryParse(_amountController.text) ?? 0;
    final fee = amount * 0.02; // 2% frais
    final total = amount - fee;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.info_outline, size: 48, color: DelivrColors.primary),
        const SizedBox(height: 16),
        const Text(
          'Confirmer le retrait',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 24),

        // Summary card
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.grey.shade100,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            children: [
              _buildSummaryRow('Montant', '${amount.toStringAsFixed(0)} XAF'),
              const Divider(),
              _buildSummaryRow('Frais (2%)', '-${fee.toStringAsFixed(0)} XAF', isRed: true),
              const Divider(),
              _buildSummaryRow('Vous recevrez', '${total.toStringAsFixed(0)} XAF', isBold: true),
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(Icons.smartphone, color: _selectedOperator.color, size: 20),
                  const SizedBox(width: 8),
                  Text(
                    '+237 ${_phoneController.text}',
                    style: const TextStyle(fontWeight: FontWeight.w500),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: _selectedOperator.color.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      _selectedOperator.name,
                      style: TextStyle(
                        fontSize: 12,
                        color: _selectedOperator.color,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),

        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => setState(() => _step = 1),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text('Modifier'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton(
                onPressed: _isLoading ? null : _processWithdrawal,
                style: ElevatedButton.styleFrom(
                  backgroundColor: DelivrColors.success,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: _isLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Text('Confirmer'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildSuccess() {
    final amount = double.tryParse(_amountController.text) ?? 0;
    final fee = amount * 0.02;
    final total = amount - fee;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: DelivrColors.success.withOpacity(0.1),
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.check, size: 48, color: DelivrColors.success),
        ),
        const SizedBox(height: 16),
        const Text(
          'Retrait initié !',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        Text(
          '${total.toStringAsFixed(0)} XAF envoyés sur\n+237 ${_phoneController.text}',
          textAlign: TextAlign.center,
          style: TextStyle(color: DelivrColors.textSecondary),
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: Colors.amber.shade100,
            borderRadius: BorderRadius.circular(20),
          ),
          child: const Text(
            'Vous recevrez un SMS de confirmation',
            style: TextStyle(fontSize: 12, color: Colors.brown),
          ),
        ),
        const SizedBox(height: 24),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              widget.onSuccess?.call();
            },
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: const Text('Fermer'),
          ),
        ),
      ],
    );
  }

  Widget _buildSummaryRow(String label, String value, {bool isBold = false, bool isRed = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label),
          Text(
            value,
            style: TextStyle(
              fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
              color: isRed ? Colors.red : null,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _processWithdrawal() async {
    setState(() => _isLoading = true);

    // Simulate API call
    await Future.delayed(const Duration(seconds: 2));

    // TODO: Call actual API
    // final success = await ref.read(walletServiceProvider).withdraw(
    //   amount: double.parse(_amountController.text),
    //   phone: _phoneController.text,
    //   operator: _selectedOperator,
    // );

    setState(() {
      _isLoading = false;
      _step = 3;
    });
  }
}

/// Debt payment dialog
class DebtPaymentDialog extends ConsumerStatefulWidget {
  final double debt;
  final double availableBalance;
  final VoidCallback? onSuccess;

  const DebtPaymentDialog({
    super.key,
    required this.debt,
    required this.availableBalance,
    this.onSuccess,
  });

  @override
  ConsumerState<DebtPaymentDialog> createState() => _DebtPaymentDialogState();
}

class _DebtPaymentDialogState extends ConsumerState<DebtPaymentDialog> {
  int _selectedOption = 0; // 0: auto, 1: partial, 2: full
  final _amountController = TextEditingController();
  final _phoneController = TextEditingController();
  MobileMoneyOperator _selectedOperator = MobileMoneyOperator.mtnMomo;
  bool _isLoading = false;
  int _step = 1;

  @override
  void dispose() {
    _amountController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: _buildContent(),
    );
  }

  Widget _buildContent() {
    if (_step == 2) return _buildPaymentForm();
    if (_step == 3) return _buildSuccess();
    return _buildOptions();
  }

  Widget _buildOptions() {
    return SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.orange.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.payment, color: Colors.orange),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Rembourser la dette',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    Text(
                      'Total dû: ${widget.debt.toStringAsFixed(0)} XAF',
                      style: const TextStyle(color: Colors.red, fontWeight: FontWeight.w500),
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.pop(context),
              ),
            ],
          ),

          const SizedBox(height: 24),

          // Option 1: Auto deduction
          _buildOption(
            index: 0,
            icon: Icons.autorenew,
            title: 'Déduction automatique',
            subtitle: 'La dette sera déduite de vos prochains gains',
            isRecommended: true,
          ),

          const SizedBox(height: 12),

          // Option 2: Partial payment
          _buildOption(
            index: 1,
            icon: Icons.pie_chart,
            title: 'Paiement partiel',
            subtitle: 'Payez maintenant une partie de la dette',
          ),

          const SizedBox(height: 12),

          // Option 3: Full payment
          _buildOption(
            index: 2,
            icon: Icons.check_circle,
            title: 'Paiement total',
            subtitle: 'Réglez la totalité maintenant (${widget.debt.toStringAsFixed(0)} XAF)',
          ),

          const SizedBox(height: 24),

          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () {
                if (_selectedOption == 0) {
                  // Auto deduction - just show confirmation
                  _showAutoDeductionConfirmation();
                } else {
                  // Go to payment form
                  if (_selectedOption == 2) {
                    _amountController.text = widget.debt.toStringAsFixed(0);
                  }
                  setState(() => _step = 2);
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.orange,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text('Continuer', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildOption({
    required int index,
    required IconData icon,
    required String title,
    required String subtitle,
    bool isRecommended = false,
  }) {
    final isSelected = _selectedOption == index;
    return GestureDetector(
      onTap: () => setState(() => _selectedOption = index),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isSelected ? Colors.orange.withOpacity(0.1) : Colors.grey.shade100,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? Colors.orange : Colors.transparent,
            width: 2,
          ),
        ),
        child: Row(
          children: [
            Icon(icon, color: isSelected ? Colors.orange : Colors.grey),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        title,
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          color: isSelected ? Colors.orange.shade800 : null,
                        ),
                      ),
                      if (isRecommended) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.green,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text(
                            'Recommandé',
                            style: TextStyle(fontSize: 10, color: Colors.white),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                  ),
                ],
              ),
            ),
            Radio<int>(
              value: index,
              groupValue: _selectedOption,
              onChanged: (v) => setState(() => _selectedOption = v ?? 0),
              activeColor: Colors.orange,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPaymentForm() {
    return SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Back button
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => setState(() => _step = 1),
              ),
              Text(
                _selectedOption == 1 ? 'Paiement partiel' : 'Paiement total',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Amount (editable for partial)
          if (_selectedOption == 1) ...[
            const Text('Montant à payer', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            TextFormField(
              controller: _amountController,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: InputDecoration(
                hintText: 'Ex: 5000',
                suffixText: 'XAF',
                filled: true,
                fillColor: Colors.grey.shade100,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
            const SizedBox(height: 16),
          ] else ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.orange.shade50,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Montant total'),
                  Text(
                    '${widget.debt.toStringAsFixed(0)} XAF',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],

          // Operator selection
          const Text('Payer via', style: TextStyle(fontWeight: FontWeight.w500)),
          const SizedBox(height: 8),
          Row(
            children: MobileMoneyOperator.values.map((op) {
              final isSelected = _selectedOperator == op;
              return Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _selectedOperator = op),
                  child: Container(
                    margin: EdgeInsets.only(
                      right: op == MobileMoneyOperator.mtnMomo ? 8 : 0,
                      left: op == MobileMoneyOperator.orangeMoney ? 8 : 0,
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: isSelected ? op.color.withOpacity(0.1) : Colors.grey.shade100,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: isSelected ? op.color : Colors.transparent,
                        width: 2,
                      ),
                    ),
                    child: Column(
                      children: [
                        Icon(Icons.smartphone, color: isSelected ? op.color : Colors.grey),
                        const SizedBox(height: 4),
                        Text(
                          op.name,
                          style: TextStyle(
                            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                            color: isSelected ? op.color : Colors.grey,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }).toList(),
          ),

          const SizedBox(height: 16),

          // Phone number
          const Text('Numéro de téléphone', style: TextStyle(fontWeight: FontWeight.w500)),
          const SizedBox(height: 8),
          TextFormField(
            controller: _phoneController,
            keyboardType: TextInputType.phone,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            decoration: InputDecoration(
              hintText: '6XXXXXXXX',
              prefixText: '+237 ',
              filled: true,
              fillColor: Colors.grey.shade100,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
            ),
          ),

          const SizedBox(height: 8),
          Text(
            'Un code USSD vous sera envoyé pour confirmer le paiement',
            style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
          ),

          const SizedBox(height: 24),

          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _isLoading ? null : _processPayment,
              style: ElevatedButton.styleFrom(
                backgroundColor: _selectedOperator.color,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: _isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Text('Payer maintenant', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSuccess() {
    final amount = _selectedOption == 0
        ? widget.debt
        : (double.tryParse(_amountController.text) ?? widget.debt);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.green.withOpacity(0.1),
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.check, size: 48, color: Colors.green),
        ),
        const SizedBox(height: 16),
        Text(
          _selectedOption == 0 ? 'Déduction activée !' : 'Paiement initié !',
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        Text(
          _selectedOption == 0
              ? 'La dette sera automatiquement déduite de vos prochains gains.'
              : '${amount.toStringAsFixed(0)} XAF\nConfirmez le paiement sur votre téléphone.',
          textAlign: TextAlign.center,
          style: TextStyle(color: DelivrColors.textSecondary),
        ),
        const SizedBox(height: 24),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              widget.onSuccess?.call();
            },
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: const Text('Fermer'),
          ),
        ),
      ],
    );
  }

  void _showAutoDeductionConfirmation() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Confirmer'),
        content: const Text(
          'Vos prochains gains seront automatiquement utilisés pour rembourser la dette jusqu\'à ce qu\'elle soit entièrement payée.\n\nVoulez-vous continuer ?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Annuler'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              setState(() => _step = 3);
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.orange),
            child: const Text('Confirmer'),
          ),
        ],
      ),
    );
  }

  Future<void> _processPayment() async {
    if (_phoneController.text.length != 9) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Numéro de téléphone invalide')),
      );
      return;
    }

    setState(() => _isLoading = true);

    // Simulate API call
    await Future.delayed(const Duration(seconds: 2));

    // TODO: Call actual payment API

    setState(() {
      _isLoading = false;
      _step = 3;
    });
  }
}

/// Show withdrawal dialog
void showWithdrawalDialog(BuildContext context, {
  required double maxAmount,
  VoidCallback? onSuccess,
}) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => WithdrawalDialog(
      maxAmount: maxAmount,
      onSuccess: onSuccess,
    ),
  );
}

/// Show debt payment dialog
void showDebtPaymentDialog(BuildContext context, {
  required double debt,
  required double availableBalance,
  VoidCallback? onSuccess,
}) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => DebtPaymentDialog(
      debt: debt,
      availableBalance: availableBalance,
      onSuccess: onSuccess,
    ),
  );
}

/// Top-up (Recharge) dialog
class TopUpDialog extends ConsumerStatefulWidget {
  final VoidCallback? onSuccess;

  const TopUpDialog({
    super.key,
    this.onSuccess,
  });

  @override
  ConsumerState<TopUpDialog> createState() => _TopUpDialogState();
}

class _TopUpDialogState extends ConsumerState<TopUpDialog> {
  final _formKey = GlobalKey<FormState>();
  final _amountController = TextEditingController();
  final _phoneController = TextEditingController();
  MobileMoneyOperator _selectedOperator = MobileMoneyOperator.mtnMomo;
  bool _isLoading = false;
  int _step = 1; // 1: form, 2: confirm, 3: pending, 4: success

  // Preset amounts for quick selection
  final List<int> _presetAmounts = [1000, 2000, 5000, 10000, 20000];

  @override
  void dispose() {
    _amountController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: _buildContent(),
    );
  }

  Widget _buildContent() {
    switch (_step) {
      case 1:
        return _buildForm();
      case 2:
        return _buildConfirmation();
      case 3:
        return _buildPending();
      case 4:
        return _buildSuccess();
      default:
        return _buildForm();
    }
  }

  Widget _buildForm() {
    return SingleChildScrollView(
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.blue.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.add_circle, color: Colors.blue),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Text(
                    'Recharger mon wallet',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),

            const SizedBox(height: 8),
            Text(
              'Ajoutez des fonds à votre compte DELIVR',
              style: TextStyle(color: DelivrColors.textSecondary),
            ),

            const SizedBox(height: 24),

            // Preset amounts
            const Text('Montant rapide', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _presetAmounts.map((amount) {
                final isSelected = _amountController.text == amount.toString();
                return GestureDetector(
                  onTap: () {
                    setState(() {
                      _amountController.text = amount.toString();
                    });
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    decoration: BoxDecoration(
                      color: isSelected ? Colors.blue.withOpacity(0.1) : Colors.grey.shade100,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: isSelected ? Colors.blue : Colors.transparent,
                        width: 2,
                      ),
                    ),
                    child: Text(
                      '$amount XAF',
                      style: TextStyle(
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                        color: isSelected ? Colors.blue : Colors.grey.shade700,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),

            const SizedBox(height: 16),

            // Custom amount
            const Text('Ou entrez un montant', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            TextFormField(
              controller: _amountController,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: InputDecoration(
                hintText: 'Ex: 5000',
                suffixText: 'XAF',
                filled: true,
                fillColor: Colors.grey.shade100,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Veuillez entrer un montant';
                }
                final amount = double.tryParse(value) ?? 0;
                if (amount < 500) {
                  return 'Minimum 500 XAF';
                }
                if (amount > 500000) {
                  return 'Maximum 500 000 XAF';
                }
                return null;
              },
              onChanged: (_) => setState(() {}),
            ),

            const SizedBox(height: 20),

            // Operator selection
            const Text(
              'Payer via',
              style: TextStyle(fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 8),
            Row(
              children: MobileMoneyOperator.values.map((op) {
                final isSelected = _selectedOperator == op;
                return Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _selectedOperator = op),
                    child: Container(
                      margin: EdgeInsets.only(
                        right: op == MobileMoneyOperator.mtnMomo ? 8 : 0,
                        left: op == MobileMoneyOperator.orangeMoney ? 8 : 0,
                      ),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      decoration: BoxDecoration(
                        color: isSelected ? op.color.withOpacity(0.1) : Colors.grey.shade100,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isSelected ? op.color : Colors.transparent,
                          width: 2,
                        ),
                      ),
                      child: Column(
                        children: [
                          Icon(
                            Icons.smartphone,
                            color: isSelected ? op.color : Colors.grey,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            op.name,
                            style: TextStyle(
                              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                              color: isSelected ? op.color : Colors.grey,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),

            const SizedBox(height: 16),

            // Phone number
            const Text('Numéro de téléphone', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            TextFormField(
              controller: _phoneController,
              keyboardType: TextInputType.phone,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              decoration: InputDecoration(
                hintText: _selectedOperator == MobileMoneyOperator.mtnMomo
                    ? '6XXXXXXXX'
                    : '69XXXXXXX',
                prefixText: '+237 ',
                filled: true,
                fillColor: Colors.grey.shade100,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Veuillez entrer un numéro';
                }
                if (value.length != 9) {
                  return 'Numéro invalide (9 chiffres)';
                }
                return null;
              },
            ),

            const SizedBox(height: 24),

            // Submit button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _isLoading
                    ? null
                    : () {
                        if (_formKey.currentState!.validate()) {
                          setState(() => _step = 2);
                        }
                      },
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Continuer',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConfirmation() {
    final amount = double.tryParse(_amountController.text) ?? 0;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.account_balance_wallet, size: 48, color: Colors.blue),
        const SizedBox(height: 16),
        const Text(
          'Confirmer la recharge',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 24),

        // Summary card
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.blue.shade50,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Montant'),
                  Text(
                    '${amount.toStringAsFixed(0)} XAF',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              const Divider(height: 24),
              Row(
                children: [
                  Icon(Icons.smartphone, color: _selectedOperator.color, size: 20),
                  const SizedBox(width: 8),
                  Text(
                    '+237 ${_phoneController.text}',
                    style: const TextStyle(fontWeight: FontWeight.w500),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: _selectedOperator.color.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      _selectedOperator.name,
                      style: TextStyle(
                        fontSize: 12,
                        color: _selectedOperator.color,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),

        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.amber.shade50,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.amber.shade200),
          ),
          child: Row(
            children: [
              Icon(Icons.info_outline, color: Colors.amber.shade800, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Vous recevrez une demande de paiement USSD sur votre téléphone.',
                  style: TextStyle(fontSize: 12, color: Colors.amber.shade900),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),

        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => setState(() => _step = 1),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text('Modifier'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton(
                onPressed: _isLoading ? null : _processTopUp,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: _isLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Text('Payer'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildPending() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const SizedBox(
          width: 60,
          height: 60,
          child: CircularProgressIndicator(
            strokeWidth: 4,
            valueColor: AlwaysStoppedAnimation<Color>(Colors.blue),
          ),
        ),
        const SizedBox(height: 24),
        const Text(
          'Paiement en attente',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 12),
        Text(
          'Veuillez confirmer le paiement\nsur votre téléphone',
          textAlign: TextAlign.center,
          style: TextStyle(color: DelivrColors.textSecondary),
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: _selectedOperator.color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.phone_android, size: 16, color: _selectedOperator.color),
              const SizedBox(width: 8),
              Text(
                '+237 ${_phoneController.text}',
                style: TextStyle(
                  fontWeight: FontWeight.w500,
                  color: _selectedOperator.color,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        TextButton(
          onPressed: () {
            // Simulate success for demo
            setState(() => _step = 4);
          },
          child: const Text('Simuler la confirmation'),
        ),
      ],
    );
  }

  Widget _buildSuccess() {
    final amount = double.tryParse(_amountController.text) ?? 0;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.green.withOpacity(0.1),
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.check, size: 48, color: Colors.green),
        ),
        const SizedBox(height: 16),
        const Text(
          'Recharge réussie !',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        Text(
          '${amount.toStringAsFixed(0)} XAF ajoutés à votre wallet',
          style: TextStyle(color: DelivrColors.textSecondary, fontSize: 16),
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: Colors.blue.shade50,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: const [
              Icon(Icons.account_balance_wallet, color: Colors.blue, size: 20),
              SizedBox(width: 8),
              Text(
                'Votre nouveau solde est disponible',
                style: TextStyle(color: Colors.blue, fontWeight: FontWeight.w500),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              widget.onSuccess?.call();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
            ),
            child: const Text('Fermer'),
          ),
        ),
      ],
    );
  }

  Future<void> _processTopUp() async {
    setState(() => _isLoading = true);

    // Simulate API call to initiate payment
    await Future.delayed(const Duration(seconds: 2));

    // Move to pending state (waiting for user to confirm on phone)
    setState(() {
      _isLoading = false;
      _step = 3;
    });

    // TODO: In real implementation:
    // 1. Call API to initiate Mobile Money payment
    // 2. Start polling for payment status
    // 3. Update UI based on status (pending -> success/failed)
  }
}

/// Show top-up dialog
void showTopUpDialog(BuildContext context, {
  VoidCallback? onSuccess,
}) {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => TopUpDialog(
      onSuccess: onSuccess,
    ),
  );
}

