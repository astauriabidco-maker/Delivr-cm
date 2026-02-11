# 🤖 Module `bot/` — WhatsApp & Notifications

> Le système nerveux de communication. Envoie des messages WhatsApp à chaque étape clé.

---

## 🎯 Rôle en une phrase

> Ce module **notifie** chaque acteur (vendeur, coursier, client) par **WhatsApp** à chaque étape de la livraison, gère les **OTP**, et envoie des **rappels automatiques**.

---

## 📱 Fournisseurs supportés

| Fournisseur | Variable | Usage |
|---|---|---|
| **Twilio** | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | WhatsApp via Twilio |
| **Meta (direct)** | `META_API_TOKEN`, `META_PHONE_NUMBER_ID` | WhatsApp Business API |
| **Orange SMS** | `ORANGE_SMS_CLIENT_ID`, `ORANGE_SMS_CLIENT_SECRET` | SMS fallback |

Le fournisseur actif est défini par `ACTIVE_WHATSAPP_PROVIDER` dans `settings.py`.

---

## 📬 Notifications envoyées

| Événement | Destinataire | Message |
|---|---|---|
| Commande créée | 🛍️ Vendeur | "Nouvelle commande #XXX de Paul Nkwi" |
| Coursier assigné | 🛍️ Vendeur + 👤 Client | "Coursier Jean Mbarga assigné ⭐4.8" |
| OTP pickup | 🛍️ Vendeur | "Code de retrait : 4721" |
| Colis récupéré | 🛍️ Vendeur + 👤 Client | "Colis récupéré, en transit" |
| Coursier en approche | 👤 Client | "Jean arrive dans ~3 min" |
| OTP livraison | 👤 Client | "Code de livraison : 8356" |
| Livraison confirmée | 🛍️ Vendeur | "Livré ✅ — Wallet crédité +1200 XAF" |
| Commande annulée | 🛍️ Vendeur + 👤 Client | "Commande annulée" |
| Alerte dette | 🏍️ Coursier | "⚠️ Wallet négatif : -500 XAF" |
| Résumé quotidien | 🏍️ Coursier | "Bilan : 12 courses, 14 400 XAF" |

---

## ⏰ Tâches Celery programmées

| Tâche | Fréquence | Description |
|---|---|---|
| `check_debt_warnings` | Toutes les heures | Alerter les coursiers en dette |
| `check_pending_reminders` | Toutes les 15 min | Rappeler les commandes en attente |
| `send_all_daily_summaries` | 21h chaque jour | Résumé quotidien aux coursiers |
| `cleanup_traffic_data` | Toutes les 5 min | Nettoyer les événements trafic expirés |
| `aggregate_traffic_heatmap` | Toutes les 2 min | Rafraîchir la heatmap |

---

*📖 Retour au [README principal](../README.md)*
