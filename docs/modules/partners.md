# 🛍️ Module `partners/` — Portail Vendeur

> L'interface métier des e-commerçants. Dashboard, commandes, analytics, API, webhooks — tout ce dont un vendeur a besoin.

---

## 🎯 Rôle en une phrase

> Ce module donne aux vendeurs un **cockpit complet** pour gérer leurs livraisons, suivre leurs revenus, et intégrer DELIVR-CM à leur site e-commerce.

---

## 👥 Qui l'utilise ?

| Profil | Utilisation |
|---|---|
| 🛍️ BUSINESS | Portail complet (dashboard → litiges) |
| 👑 ADMIN | Approbation des partenaires |

---

## 📦 Modèles de données

### `PartnerAPIKey` — Clés API sécurisées
```python
class PartnerAPIKey(AbstractAPIKey):
    partner  # FK → User (le propriétaire de la clé)
    # Hérite : name, prefix, hashed_key, created, revoked
```

### `WebhookConfig` — Configuration des callbacks HTTP
```python
class WebhookConfig:
    user         # FK → User (one-to-one)
    url          # URL de callback
    secret       # HMAC secret (pour signature)
    events       # JSON list ["order.created", "order.completed", ...]
    is_active    # Bool
    last_triggered    # DateTime
    last_status_code  # Int (200, 500, ...)
    failure_count     # Compteur d'échecs
```

### `PartnerNotification` — Notifications in-app
```python
class PartnerNotification:
    user               # FK → User
    notification_type  # order_created | order_assigned | order_picked_up | 
                       # order_completed | order_cancelled | payment_received |
                       # invoice_generated | system
    title             # Titre
    message           # Corps du message
    delivery          # FK → Delivery (optionnel)
    is_read           # Bool
```

---

## 🖥️ Pages du portail

| Page | URL | Vue | Fonctionnalité |
|---|---|---|---|
| 🏠 Dashboard | `/partners/dashboard/` | `PartnerDashboardView` | KPIs, stats rapides, clés API |
| 📋 Commandes | `/partners/orders/` | `PartnerOrdersView` | Liste avec filtres + pagination |
| 📋 Détail commande | `/partners/orders/<id>/` | `PartnerOrderDetailView` | Timeline, statut, infos |
| 📥 Export CSV | `/partners/orders/export/` | `PartnerOrderExportView` | Export des commandes |
| 💰 Wallet | `/partners/wallet/` | `PartnerWalletView` | Solde + transactions |
| 👤 Profil | `/partners/profile/` | `PartnerProfileView` | Modifier nom, tel, etc. |
| 🪝 Webhooks | `/partners/webhooks/` | `PartnerWebhooksView` | Configurer les callbacks |
| 🎨 Branding | `/partners/branding/` | `PartnerBrandingView` | Logo, couleur, message |
| 🧾 Factures | `/partners/invoices/` | `PartnerInvoicesView` | Télécharger les factures |
| 🗺️ Suivi | `/partners/tracking/` | `PartnerTrackingView` | Carte temps réel |
| 📈 Analytics | `/partners/analytics/` | `PartnerAnalyticsView` | Graphiques avancés |
| 🔔 Notifs | `/partners/notifications/` | `PartnerNotificationsView` | Fil de notifications |
| ⚖️ Litiges | `/partners/disputes/` | `PartnerDisputeListView` | Liste des litiges |
| ⚖️ Nouveau litige | `/partners/disputes/new/<id>/` | `PartnerDisputeCreateView` | Créer un litige |
| ⚖️ Détail litige | `/partners/disputes/<id>/` | `PartnerDisputeDetailView` | Suivi du litige |
| 📖 API Docs | `/partners/docs/` | Swagger UI | Documentation interactive API |

---

## 🔑 Système d'API Keys

### Flux d'activation

```
1. Vendeur s'inscrit → is_business_approved = False
2. Admin approuve → is_business_approved = True
3. Vendeur génère une clé API depuis le dashboard
4. La clé est affichée UNE SEULE FOIS (stockée hashée)
5. Le vendeur l'utilise dans ses appels API
```

### Sécurité des clés
```
- Chaque clé est liée à UN partenaire spécifique
- Un partenaire ne peut agir que sur SES propres données
- Clé révoquée = accès coupé immédiatement
- Le prefix de la clé permet l'identification sans exposer la clé
```

---

## 🪝 Système de Webhooks

### Événements disponibles

| Événement | Déclenché quand... |
|---|---|
| `order.created` | Nouvelle commande créée |
| `order.assigned` | Coursier assigné |
| `order.picked_up` | Colis récupéré |
| `order.in_transit` | En transit |
| `order.completed` | Livraison terminée ✅ |
| `order.cancelled` | Commande annulée ❌ |
| `payment.received` | Paiement reçu |

### Payload de webhook
```json
{
    "event": "order.completed",
    "timestamp": "2026-02-11T10:30:00Z",
    "data": {
        "order_id": "a7f3...",
        "tracking_number": "DLV-A7F3X2",
        "status": "COMPLETED",
        "courier": {
            "name": "Jean Mbarga",
            "phone": "+237691234567"
        },
        "recipient": {
            "name": "Paul Nkwi",
            "phone": "+237677987654"
        },
        "pricing": {
            "total": 1500,
            "commission": 300,
            "net": 1200
        }
    },
    "signature": "sha256=abc123..."
}
```

### Vérification HMAC
```python
import hmac, hashlib

expected_sig = hmac.new(
    webhook_secret.encode(),
    request.body,
    hashlib.sha256
).hexdigest()

is_valid = hmac.compare_digest(
    f"sha256={expected_sig}",
    request.headers['X-Delivr-Signature']
)
```

---

## 📊 Analytics – Données disponibles

| Métrique | Description |
|---|---|
| Commandes par jour/semaine/mois | Évolution temporelle |
| Revenus cumulés | Wallet + tendance |
| Taux de livraison | % de commandes complétées |
| Taux de litiges | % de commandes avec litige |
| Heures de pointe | Distribution horaire |
| Top quartiers | Quartiers avec le plus de livraisons |
| Répartition par statut | COMPLETED vs CANCELLED vs FAILED |

---

## ⚠️ Points d'attention

| Règle | Détail |
|---|---|
| **Approbation requise** | `is_business_approved = True` nécessaire pour les clés API |
| **Slug unique** | Auto-généré, utilisé pour `/book/<slug>/` |
| **Webhook retry** | Les webhooks échoués sont comptabilisés (failure_count) |
| **HMAC obligatoire** | Le secret HMAC est généré automatiquement, régénérable |
| **Export CSV** | Disponible avec filtres (date, statut) |

---

*📖 Retour au [README principal](../README.md)*
