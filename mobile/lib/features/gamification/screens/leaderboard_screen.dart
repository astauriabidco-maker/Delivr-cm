import 'package:flutter/material.dart';

import '../../../app/theme.dart';

class LeaderboardScreen extends StatelessWidget {
  const LeaderboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Classement'),
        backgroundColor: DelivrColors.surface,
      ),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.leaderboard,
              size: 64,
              color: DelivrColors.primary,
            ),
            SizedBox(height: 16),
            Text(
              'Classement des coursiers',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            SizedBox(height: 8),
            Text(
              'Top performers\nPhase 18.3 - À venir',
              textAlign: TextAlign.center,
              style: TextStyle(color: DelivrColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}
