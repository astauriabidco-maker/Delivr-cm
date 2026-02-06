import 'package:flutter/material.dart';

import '../../../app/theme.dart';

class EarningsScreen extends StatelessWidget {
  const EarningsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Mes gains'),
        backgroundColor: DelivrColors.surface,
      ),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.trending_up,
              size: 64,
              color: DelivrColors.success,
            ),
            SizedBox(height: 16),
            Text(
              'Historique des gains',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            SizedBox(height: 8),
            Text(
              'Graphiques et statistiques\nPhase 18.3 - À venir',
              textAlign: TextAlign.center,
              style: TextStyle(color: DelivrColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}
