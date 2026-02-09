import 'package:flutter/material.dart';

import '../../../app/theme.dart';
import '../../../core/services/navigation_service.dart';

class SupportScreen extends StatelessWidget {
  const SupportScreen({super.key});
  
  // Support phone number
  static const String supportPhone = '+237691000000';
  
  // FAQ items
  static const List<Map<String, String>> faqItems = [
    {
      'question': 'Comment accepter une livraison ?',
      'answer': 'Lorsqu\'une nouvelle livraison est disponible, vous recevrez une notification. Appuyez sur "Accepter" pour prendre en charge la livraison.',
    },
    {
      'question': 'Comment annuler une livraison ?',
      'answer': 'Vous pouvez annuler uniquement avant le pickup. Allez dans les détails de la livraison et appuyez sur "Annuler". Note : trop d\'annulations affectent votre notation.',
    },
    {
      'question': 'Quand est-ce que je reçois mes gains ?',
      'answer': 'Vos gains sont crédités automatiquement sur votre portefeuille dès que la livraison est confirmée par le destinataire.',
    },
    {
      'question': 'Comment retirer mon argent ?',
      'answer': 'Dans l\'onglet Portefeuille, appuyez sur "Retirer". Vous pouvez transférer vers Mobile Money (OM, MTN MoMo) ou votre compte bancaire.',
    },
    {
      'question': 'Mon client ne répond pas, que faire ?',
      'answer': 'Appelez d\'abord le client via l\'application. Si pas de réponse après 5 minutes, contactez le support pour assistance.',
    },
    {
      'question': 'Comment améliorer ma notation ?',
      'answer': 'Livrez rapidement, soyez courtois, et respectez les instructions de livraison. Les 5 étoiles sont à portée !',
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DelivrColors.background,
      appBar: AppBar(
        title: const Text('Aide & Support'),
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: DelivrColors.textPrimary,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Contact Card
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [DelivrColors.primary, DelivrColors.primary.withValues(alpha: 0.8)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: DelivrColors.primary.withValues(alpha: 0.3),
                    blurRadius: 15,
                    offset: const Offset(0, 5),
                  ),
                ],
              ),
              child: Column(
                children: [
                  const Icon(Icons.headset_mic, color: Colors.white, size: 48),
                  const SizedBox(height: 12),
                  const Text(
                    'Besoin d\'aide ?',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Notre équipe support est disponible 7j/7 de 6h à 22h',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.9),
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () => NavigationService.openWhatsApp(
                            phoneNumber: supportPhone,
                            message: 'Bonjour, j\'ai besoin d\'aide concernant...',
                          ),
                          icon: const Icon(Icons.chat),
                          label: const Text('WhatsApp'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF25D366),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () => NavigationService.callPhone(supportPhone),
                          icon: const Icon(Icons.phone),
                          label: const Text('Appeler'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.white,
                            foregroundColor: DelivrColors.primary,
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 32),
            
            // FAQ Section
            const Text(
              'Questions fréquentes',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            
            ...faqItems.map((faq) => _buildFaqItem(faq)),
            
            const SizedBox(height: 24),
            
            // Quick Links
            const Text(
              'Liens rapides',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            
            _buildQuickLink(
              icon: Icons.description,
              title: 'Conditions d\'utilisation',
              onTap: () {},
            ),
            _buildQuickLink(
              icon: Icons.privacy_tip,
              title: 'Politique de confidentialité',
              onTap: () {},
            ),
            _buildQuickLink(
              icon: Icons.info_outline,
              title: 'À propos de DELIVR',
              onTap: () {},
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildFaqItem(Map<String, String> faq) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: ExpansionTile(
        title: Text(
          faq['question']!,
          style: const TextStyle(
            fontWeight: FontWeight.w500,
            fontSize: 14,
          ),
        ),
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        shape: const RoundedRectangleBorder(side: BorderSide.none),
        children: [
          Text(
            faq['answer']!,
            style: TextStyle(
              color: DelivrColors.textSecondary,
              fontSize: 14,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildQuickLink({
    required IconData icon,
    required String title,
    required VoidCallback onTap,
  }) {
    return ListTile(
      leading: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: DelivrColors.primary.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Icon(icon, color: DelivrColors.primary, size: 20),
      ),
      title: Text(title),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: 0, vertical: 4),
    );
  }
}
