# DELIVR-CM Shipping Plugin for WooCommerce

Plugin WordPress/WooCommerce pour intégrer la livraison express DELIVR-CM à votre boutique en ligne.

## 🚀 Fonctionnalités

- **Calcul automatique des tarifs** : Interroge l'API DELIVR-CM pour afficher le prix exact selon le quartier
- **Création automatique des commandes** : Envoie les détails à l'API après paiement
- **Notifications WhatsApp** : Le bot DELIVR-CM contacte automatiquement le client
- **Prix de secours** : Tarif de fallback si l'API est indisponible
- **Logs détaillés** : Suivi des appels API dans WooCommerce > Status > Logs

## 📦 Installation

1. **Télécharger** le dossier `delivr-cm-shipping`
2. **Uploader** dans `/wp-content/plugins/`
3. **Activer** le plugin dans WordPress > Extensions
4. **Configurer** dans WooCommerce > Paramètres > Livraison

## ⚙️ Configuration

### Ajouter une zone de livraison

1. Allez dans **WooCommerce > Paramètres > Livraison**
2. Créez une zone (ex: "Douala" ou "Yaoundé")
3. Ajoutez la méthode **"DELIVR-CM Express"**
4. Configurez les paramètres :

| Paramètre | Description | Exemple |
|-----------|-------------|---------|
| **Titre** | Nom affiché au client | Livraison Express DELIVR-CM |
| **URL de l'API** | Endpoint DELIVR-CM | `https://api.delivr.cm` |
| **Clé API** | Token JWT de votre boutique | `eyJhbGciOiJIUzI1...` |
| **Prix de secours** | Tarif si API indisponible | 1500 XAF |
| **Latitude boutique** | Position GPS | 4.0511 |
| **Longitude boutique** | Position GPS | 9.7679 |

### Obtenir votre clé API

1. Connectez-vous à votre dashboard DELIVR-CM
2. Créez un compte de type "BUSINESS"
3. Générez un token JWT depuis l'API `/api/auth/token/`

## 🔄 Flux de fonctionnement

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   WooCommerce   │────▶│   API DELIVR    │────▶│   Bot WhatsApp  │
│     Panier      │     │   /api/quote    │     │                 │
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

## 🐛 Dépannage

### Les tarifs ne s'affichent pas
- Vérifiez que l'API est accessible depuis votre serveur
- Consultez les logs dans **WooCommerce > Status > Logs** (fichier `delivr-cm-shipping`)

### Erreur 402 (Solde insuffisant)
- Rechargez votre wallet DELIVR-CM depuis le dashboard
- Le plugin affiche une note sur la commande avec le détail

### Erreur 401 (Non autorisé)
- Vérifiez votre clé API dans les paramètres
- Régénérez un nouveau token JWT si nécessaire

## 📄 Licence

MIT License - DELIVR-CM © 2024
