# 🛍️ Parcours Vendeur — "La journée type d'un vendeur Instagram"

> *Suivez Marie, vendeuse de bijoux artisanaux sur Instagram à Douala, dans sa journée avec RELAY237.*

---

## 📖 L'histoire de Marie

Marie a 26 ans. Elle fabrique et vend des bijoux sur Instagram depuis 2 ans. Avant RELAY237, elle passait 2h par jour à organiser les livraisons : appeler des coursiers au hasard, négocier les prix, perdre des colis... Un cauchemar.

Depuis qu'elle utilise RELAY237, tout a changé ✨

---

## ☀️ 8h00 — L'inscription (une seule fois !)

### Étape 1 : Créer son compte

Marie va sur `relay237.com` et clique **"Commencer à livrer"**.

```
📱 Numéro WhatsApp : +237 677 123 456
👤 Nom : Marie Fashion Bijoux
🔒 Mot de passe : ********
📦 Type de commerce : Réseaux Sociaux (Instagram, FB, WA)
```

### Étape 2 : En attente de validation

```
┌─────────────────────────────────────────┐
│  ⏳ Compte en attente de validation     │
│                                         │
│  Notre équipe vérifie votre compte.     │
│  Vous recevrez un WhatsApp dès que      │
│  votre compte sera activé.              │
└─────────────────────────────────────────┘
```

> **En coulisses** : Un admin RELAY237 voit la demande dans le Fleet Manager, vérifie le profil Instagram de Marie, et clique "Approuver". Marie reçoit un WhatsApp : *"🎉 Votre compte RELAY237 est activé !"*

### Étape 3 : Personnaliser sa boutique

Marie accède à **🎨 Personnalisation** et configure :

| Champ | Valeur |
|---|---|
| Logo | *son logo Instagram* |
| Couleur | `#E91E63` (rose fuchsia) |
| Message d'accueil | *"✨ Merci de commander chez Marie Fashion ! Livraison express à Douala."* |

Son **lien magique** est généré automatiquement :
```
🔗 relay237.com/book/marie-fashion-bijoux/
```

---

## 🌅 9h00 — Première commande du jour

### Le flux concret

```
1️⃣  Un client DM Marie sur Instagram : "Je veux le collier doré !"
    
2️⃣  Marie lui envoie son lien RELAY237 via WhatsApp :
    "Passez votre commande ici 👉 relay237.com/book/marie-fashion-bijoux/"
    
3️⃣  Le client ouvre le lien et voit la page PERSONNALISÉE de Marie
    (logo rose, message d'accueil...)
    
4️⃣  Le client remplit :
    ┌──────────────────────────────────┐
    │  📦 Commande chez Marie Fashion  │
    │                                  │
    │  Destinataire : Paul Nkwi       │
    │  Téléphone : 677 987 654        │
    │  Quartier : Akwa                │
    │  Adresse : Rue de l'Hôpital     │
    │  Notes : "2ème étage, sonner"   │
    │                                  │
    │  💰 Prix livraison : 1 500 XAF  │
    │                                  │
    │  [✅ Commander]                  │
    └──────────────────────────────────┘
    
5️⃣  La commande apparaît INSTANTANÉMENT dans le dashboard de Marie !
```

### Ce que Marie voit sur son dashboard

```
┌──────────────────────────────────────────────────┐
│  📊 Dashboard — Vue d'ensemble                    │
│                                                    │
│  📦 Commandes aujourd'hui    💰 Revenus            │
│     3                           4 500 XAF          │
│  📈 +2 cette semaine         📈 13 200 XAF/sem     │
│                                                    │
│  ✅ Taux de livraison        💳 Solde Wallet        │
│     96.2%                       23 400 XAF         │
└──────────────────────────────────────────────────┘
```

---

## 🏍️ 9h15 — Le coursier est assigné

### Ce qui se passe automatiquement

```mermaid
graph LR
    A[📦 Commande créée] --> B{🔍 Dispatch automatique}
    B --> C[Trouve le coursier<br/>le plus proche dispo]
    C --> D[📱 Notification coursier]
    D --> E[✅ Coursier accepte]
    E --> F[📱 WhatsApp à Marie :<br/>"Coursier Jean assigné 🏍️"]
```

Marie reçoit un WhatsApp :
```
🏍️ RELAY237 — Coursier Assigné

Commande #a7f3 pour Paul Nkwi
Coursier : Jean Mbarga ⭐ 4.8
Tél : 691 234 567

Le coursier est en route pour récupérer votre colis !
```

### Suivi temps réel

Marie ouvre **🗺️ Suivi en direct** et voit la position GPS de Jean en temps réel sur une carte :

```
  🏠 Marie (Bonamoussadi)          📍 Paul (Akwa)
     ↓                                ↑
     🏍️ ←── Jean en route ──────────→
         Distance : 5.2 km
         ETA : 18 min
```

---

## 📸 9h30 — Le pickup

Jean arrive chez Marie. Il doit :

1. **📷 Prendre une photo** du colis
2. **🔐 Entrer le code OTP** que Marie a reçu par WhatsApp

```
WhatsApp → Marie :
"🔐 Code de retrait : 4 7 2 1
Donnez ce code au coursier Jean pour confirmer le retrait."
```

Marie donne le code `4721` → Jean le saisit → ✅ **Colis récupéré !**

Marie reçoit la notification :
```
📦 Colis récupéré par Jean Mbarga
En transit vers Paul Nkwi (Akwa)
```

---

## 🚀 9h45 — En transit

Marie peut suivre Jean en temps réel. Elle voit :
- 🏍️ Position GPS du coursier
- ⏱️ ETA estimé
- 📍 L'itinéraire optimisé

Si Marie a configuré des **Webhooks**, son site reçoit un callback :
```json
POST https://marie-fashion.com/webhook
{
    "event": "order.in_transit",
    "order_id": "a7f3...",
    "courier": {
        "name": "Jean Mbarga",
        "phone": "+237691234567"
    },
    "eta_minutes": 12
}
```

---

## ✅ 10h00 — Livraison confirmée !

Jean arrive chez Paul. Il demande le **code OTP** envoyé au destinataire :

```
WhatsApp → Paul :
"📦 Votre colis de Marie Fashion arrive !
🔐 Code de livraison : 8 3 5 6
Donnez ce code au coursier pour confirmer."
```

Paul donne `8356` → Jean confirme → ✅ **LIVRÉ !**

### Ce que Marie reçoit

```
✅ RELAY237 — Livraison Confirmée

Commande #a7f3 livrée avec succès !
Destinataire : Paul Nkwi (Akwa)
Coursier : Jean Mbarga

💰 Votre wallet a été crédité de 1 200 XAF
   (1 500 XAF - 300 XAF commission 20%)
```

---

## 📊 18h00 — Fin de journée

Marie ouvre ses **📈 Analytiques Avancées** :

```
┌──────────────────────────────────────────────┐
│  📈 Analytiques — 7 derniers jours           │
│                                              │
│  📦 12 commandes  ✅ 11 succès  ❌ 1 annulée │
│  💰 18 000 XAF    📊 91.7% taux  ⚖️ 0 litige │
│                                              │
│  📈 Évolution:    🎯 Statuts:    ⏰ Pointe:  │
│  ╭──╮            [███ 92%  ✅]   14h-16h     │
│  │  ╰──╮         [█   8%  ❌]               │
│  ╰─────╯                                    │
│                                              │
│  🏆 Top Quartiers :                          │
│  1. Akwa (5 livraisons)                      │
│  2. Bonapriso (3 livraisons)                 │
│  3. Bonamoussadi (2 livraisons)              │
└──────────────────────────────────────────────┘
```

### 🧾 Factures automatiques

Chaque livraison génère une facture PDF téléchargeable depuis **🧾 Factures** :

```
┌──────────────────────────────────┐
│  FACTURE DLV-2026-000142        │
│  Date : 11/02/2026              │
│                                  │
│  De : Marie Fashion Bijoux      │
│  À : Paul Nkwi — Akwa           │
│                                  │
│  Livraison : 1 500 XAF          │
│  Commission (20%) : -300 XAF    │
│  ─────────────────────          │
│  Net vendeur : 1 200 XAF        │
│                                  │
│  💰 Crédité sur wallet           │
└──────────────────────────────────┘
```

---

## 🔧 Les outils avancés de Marie

### 🔑 API REST (pour les pros)

Si Marie a aussi un site WooCommerce, elle peut automatiser les commandes :

```bash
# Créer une livraison via l'API
curl -X POST https://relay237.com/api/v1/deliveries/ \
  -H "Authorization: Api-Key dlv_xxxxxxxxxxxx" \
  -d '{
    "recipient_name": "Paul Nkwi",
    "recipient_phone": "+237677987654",
    "dropoff_address": "Akwa, Rue de l hôpital",
    "item_description": "Collier doré",
    "payment_method": "CASH_P2P"
  }'
```

### 🪝 Webhooks

Marie peut configurer des callbacks HTTP pour son site :

| Événement | Description |
|---|---|
| `order.created` | Commande créée |
| `order.assigned` | Coursier assigné |
| `order.picked_up` | Colis récupéré |
| `order.in_transit` | En transit |
| `order.completed` | Livré ✅ |
| `order.cancelled` | Annulé ❌ |

### ⚖️ Litiges

Si un client signale un problème, Marie peut créer un litige avec :
- 📝 Description détaillée
- 📸 Preuves photos
- L'équipe RELAY237 enquête et résout

---

## 💡 Résumé — Ce que RELAY237 apporte à Marie

| Avant RELAY237 | Avec RELAY237 |
|---|---|
| 2h/jour à organiser les livraisons | 2 minutes par commande |
| Appeler des coursiers au hasard | Dispatch automatique |
| Pas de suivi après pickup | GPS temps réel |
| Négocier les prix à chaque fois | Tarification transparente |
| Pas de preuve de livraison | OTP + Photo |
| Compter le cash manuellement | Wallet automatique |
| Aucune donnée de performance | Analytics avec graphiques |
| Pas d'intégration site web | API REST + Webhooks |

---

## 📦 Modules impliqués dans ce parcours

| Étape | Module(s) | Fichiers clés |
|---|---|---|
| Inscription | `partners/`, `core/` | `views.py` (PartnerSignupView) |
| Dashboard | `partners/` | `dashboard.html`, `views.py` |
| Commande publique | `home/`, `logistics/` | `views.py` (PublicShopView) |
| Dispatch coursier | `logistics/` | `services/dispatch.py` |
| Notifications | `bot/` | `tasks.py`, WhatsApp API |
| OTP | `core/`, `bot/` | OTP generation + WhatsApp |
| Suivi GPS | `logistics/`, `courier/` | WebSocket Channels |
| Finances | `finance/` | `WalletService`, `Transaction` |
| Factures | `finance/`, `reports/` | `Invoice`, PDF generation |
| Webhooks | `partners/` | `WebhookConfig`, HTTP callbacks |
| Litiges | `support/` | `Dispute`, `Refund` |

---

*📖 Retour au [README principal](../README.md) | Voir aussi : [🏍️ Parcours Coursier](./coursier_journey.md)*
