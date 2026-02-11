# 👨‍💼 Module `fleet/` — Gestion de Flotte

> Le centre de contrôle pour les administrateurs. Live map, alertes, finances, onboarding des coursiers.

---

## 🎯 Rôle en une phrase

> Ce module permet à l'équipe DELIVR-CM de **superviser** tous les coursiers, **approuver** les inscriptions, **gérer** les finances et **monitorer** les opérations en temps réel.

---

## 🖥️ Pages

| Page | URL | Description |
|---|---|---|
| 🏠 Dashboard | `/fleet/` | Vue synthétique : coursiers en ligne, courses actives, alertes |
| 👥 Coursiers | `/fleet/couriers/` | Liste avec filtres (statut, niveau, en ligne) |
| 👤 Détail coursier | `/fleet/couriers/<id>/` | Profil complet, actions admin |
| 🗺️ Carte en direct | `/fleet/live-map/` | Position GPS de tous les coursiers |
| ⚠️ Alertes | `/fleet/alerts/` | Anomalies détectées automatiquement |
| 📊 Analytics | `/fleet/analytics/` | Statistiques globales de la flotte |
| 📊 Analytics avancées | `/fleet/analytics/advanced/` | Métriques détaillées |
| 🗺️ Couverture | `/fleet/coverage/` | Carte de couverture par quartier |
| 💳 Retraits | `/fleet/withdrawals/` | Gérer les demandes de retrait MoMo/OM |
| 📋 Onboarding | `/fleet/onboarding/` | Valider/rejeter les nouveaux coursiers |
| 💰 Finance | `/fleet/finance/` | Dashboard financier global |
| 📄 Rapports | `/fleet/reports/` | Exports et rapports PDF |

---

## 🔧 Actions admin

| Action | URL | Effet |
|---|---|---|
| Vérifier un coursier | `/fleet/couriers/<id>/verify/` | `is_verified = True` |
| Bloquer/débloquer | `/fleet/couriers/<id>/block/` | Toggle `is_active` |
| Ajuster la dette | `/fleet/couriers/<id>/adjust-debt/` | Modifier `debt_ceiling` |
| Approuver onboarding | `/fleet/onboarding/<id>/approve/` | `onboarding_status = PROBATION` |
| Rejeter onboarding | `/fleet/onboarding/<id>/reject/` | `onboarding_status = REJECTED` |
| Approuver retrait | `/fleet/withdrawals/<id>/approve/` | Débit wallet + envoi MoMo |
| Rejeter retrait | `/fleet/withdrawals/<id>/reject/` | Refusé avec raison |
| Compléter retrait | `/fleet/withdrawals/<id>/complete/` | Confirmer la réception MoMo |

---

## 📡 API Temps réel

| Endpoint | Description |
|---|---|
| `/fleet/api/stats/` | Stats globales (AJAX) |
| `/fleet/api/couriers/online/` | Coursiers en ligne |
| `/fleet/api/courier-positions/` | Positions GPS (pour la map) |
| `/fleet/api/alerts/` | Nouvelles alertes |

---

*📖 Retour au [README principal](../README.md)*
