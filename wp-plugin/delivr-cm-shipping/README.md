# RELAY237 Shipping Plugin for WooCommerce

Plugin WordPress/WooCommerce pour intégrer la livraison express RELAY237 à votre boutique en ligne.

## 🚀 Fonctionnalités

- **Calcul automatique des tarifs** : Interroge l'API RELAY237 pour afficher le prix exact selon le quartier
- **Création automatique des commandes** : Envoie les détails à l'API après paiement
- **Notifications WhatsApp** : Le bot RELAY237 contacte automatiquement le client
- **Prix de secours** : Tarif de fallback si l'API est indisponible
- **Logs détaillés** : Suivi des appels API dans WooCommerce > Status > Logs

## 📦 Installation

1. **Télécharger** le dossier `relay237-shipping`
2. **Uploader** dans `/wp-content/plugins/`
3. **Activer** le plugin dans WordPress > Extensions
4. **Configurer** dans WooCommerce > Paramètres > Livraison

## ⚙️ Configuration

### Ajouter une zone de livraison

1. Allez dans **WooCommerce > Paramètres > Livraison**
2. Créez une zone (ex: "Douala" ou "Yaoundé")
3. Ajoutez la méthode **"RELAY237 Express"**
4. Configurez les paramètres :

| Paramètre | Description | Exemple |
|-----------|-------------|---------|
| **Titre** | Nom affiché au client | Livraison Express RELAY237 |
| **URL de l'API** | Endpoint RELAY237 | `https://api.relay237.com` |
| **Clé API** | Clé API partenaire envoyée avec `Authorization: Api-Key ...` | `dlv_xxxxxxxxxxxx` |
| **ID boutique RELAY237** | UUID du compte BUSINESS lié à la clé API | `00000000-0000-0000-0000-000000000000` |
| **Prix de secours** | Tarif si API indisponible | 1500 XAF |
| **Latitude boutique** | Position GPS | 4.0511 |
| **Longitude boutique** | Position GPS | 9.7679 |

### Obtenir votre clé API et votre ID boutique

1. Connectez-vous à votre dashboard RELAY237
2. Créez un compte de type "BUSINESS"
3. Générez une clé API partenaire depuis le portail
4. Renseignez aussi l'UUID de la boutique BUSINESS (`shop_id`) dans la méthode de livraison WooCommerce

## 🔄 Flux de fonctionnement

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   WooCommerce   │────▶│   API RELAY237    │────▶│   Bot WhatsApp  │
│     Panier      │     │ /api/public/quote │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        ▼                                               ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Checkout     │────▶│  /api/orders    │────▶│  Client notifié │
│    Paiement     │     │                 │     │  📲 WhatsApp    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## 📋 Champs d'adresse recommandés

Pour une meilleure précision, configurez votre checkout ainsi :

- **Adresse 1** : Numéro et rue (ex: "BP 123")
- **Adresse 2** : **Quartier** (ex: "Akwa", "Bonanjo", "Bastos")
- **Ville** : Douala ou Yaoundé

Le plugin utilise le champ **Adresse 2** comme quartier pour le calcul du tarif.
Lorsqu'un quartier RELAY237 est sélectionné, son identifiant technique est également enregistré sur la commande pour créer la livraison via `/api/orders/`.

## 🐛 Dépannage

### Les tarifs ne s'affichent pas
- Vérifiez que l'API est accessible depuis votre serveur
- Consultez les logs dans **WooCommerce > Status > Logs** (fichier `relay237-shipping`)

### Erreur 402 (Solde insuffisant)
- Rechargez votre wallet RELAY237 depuis le dashboard
- Le plugin affiche une note sur la commande avec le détail

### Erreur 401 (Non autorisé)
- Vérifiez votre clé API dans les paramètres
- Vérifiez que l'ID boutique correspond au compte BUSINESS propriétaire de cette clé
- Régénérez une nouvelle clé API si nécessaire

## 📄 Licence

MIT License - RELAY237 © 2024
