import 'package:flutter/material.dart';

import '../../../app/theme.dart';

class BadgesScreen extends StatelessWidget {
  const BadgesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Mes badges'),
        backgroundColor: DelivrColors.surface,
      ),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.emoji_events,
              size: 64,
              color: DelivrColors.gold,
            ),
            SizedBox(height: 16),
            Text(
              'Collection de badges',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            SizedBox(height: 8),
            Text(
              'Gamification & Récompenses\nPhase 18.3 - À venir',
              textAlign: TextAlign.center,
              style: TextStyle(color: DelivrColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}
