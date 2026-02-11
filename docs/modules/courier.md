# 🏍️ Module `courier/` — App Coursier

> L'interface mobile-first des coursiers. Dashboard, revenus, gamification, wallet, historique.

---

## 🎯 Rôle en une phrase

> Ce module donne au coursier un **tableau de bord complet** pour gérer sa disponibilité, suivre ses revenus, progresser en niveau, et retirer son argent.

---

## 🖥️ Pages

| Page | URL | Description |
|---|---|---|
| 🏠 Dashboard | `/courier/dashboard/` | Stats du jour, toggle en ligne, alertes |
| 💰 Revenus | `/courier/earnings/` | Gains détaillés, graphiques |
| 📊 Performances | `/courier/performance/` | Note, streak, acceptation, temps |
| 🏆 Classement | `/courier/leaderboard/` | Top coursiers, position |
| 📅 Disponibilité | `/courier/availability/` | Toggle + créneaux récurrents |
| 💳 Wallet | `/courier/wallet/` | Solde + demande de retrait MoMo/OM |
| 📜 Historique | `/courier/wallet/history/` | Transactions passées |
| 👤 Profil | `/courier/profile/` | Infos personnelles, documents |
| 🏅 Badges | `/courier/badges/` | Succès débloqués, progression |
| 📋 Historique livraisons | `/courier/history/` | Toutes les courses + export CSV |
| 📱 Onboarding | `/courier/onboarding/` | Parcours d'inscription (6 étapes) |

---

## 📱 API Mobile (Flutter)

| Endpoint | Méthode | Description |
|---|---|---|
| `/api/mobile/deliveries/available/` | GET | Courses disponibles à proximité |
| `/api/mobile/deliveries/<id>/accept/` | POST | Accepter une course |
| `/api/mobile/deliveries/<id>/pickup/` | POST | Confirmer pickup (photo + OTP) |
| `/api/mobile/deliveries/<id>/complete/` | POST | Confirmer livraison (OTP) |
| `/api/mobile/location/update/` | POST | Position GPS (toutes les 10s) |
| `/api/mobile/toggle-online/` | POST | Passer en ligne / hors ligne |
| `/api/mobile/stats/` | GET | Stats du jour |
| `/api/mobile/withdrawal/request/` | POST | Demander un retrait |
| `/api/mobile/withdrawal/status/` | GET | Statut du dernier retrait |

---

## 🏅 Système de badges

| Badge | Condition | Icône |
|---|---|---|
| Premier Pas | 1ère livraison | 🏅 |
| Lève-tôt | Livraison avant 8h | 🌅 |
| Noctambule | Livraison après 22h | 🌙 |
| En Feu | 10 livraisons consécutives | 🔥 |
| 5 Étoiles | Première note 5/5 | ⭐ |
| Marathon | 500 km parcourus | 📏 |
| Centurion | 100 livraisons | 💯 |
| Légende | 500 livraisons | 🏆 |

---

*📖 Retour au [README principal](../README.md)*
