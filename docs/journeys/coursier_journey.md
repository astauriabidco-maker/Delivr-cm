# 🏍️ Parcours Coursier — "La journée type d'un coursier RELAY237"

> *Suivez Jean, coursier moto à Douala, dans sa journée avec RELAY237.*

---

## 📖 L'histoire de Jean

Jean a 23 ans. Il a une moto et cherchait un job flexible. Un ami lui a parlé de RELAY237. En 48h, il était coursier. Aujourd'hui, il fait entre 8 et 15 courses par jour et gagne plus qu'un emploi salarié classique.

---

## 🌅 Jour 0 — L'onboarding (une seule fois !)

### Le parcours d'inscription en 6 étapes

```
┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐
│ 📱  │──▶│ 📄  │──▶│ 👥  │──▶│ 💰  │──▶│ 📜  │──▶│ ⏳  │
│Phone│   │Docs │   │Urgen│   │Caut.│   │Cont.│   │Wait │
│+OTP │   │CNI+ │   │Contact│  │     │   │Sign │   │Admin│
│     │   │Moto │   │     │   │     │   │     │   │     │
└─────┘   └─────┘   └─────┘   └─────┘   └─────┘   └─────┘
  1/6       2/6       3/6       4/6       5/6       6/6
```

| Étape | URL | Ce que fait Jean |
|---|---|---|
| 1. Téléphone | `/courier/onboarding/phone/` | Entre son numéro +237, reçoit un OTP WhatsApp |
| 2. Documents | `/courier/onboarding/documents/` | Upload sa CNI + photo de sa moto |
| 3. Contact urgence | `/courier/onboarding/emergency/` | Nom + téléphone d'un proche |
| 4. Caution | `/courier/onboarding/caution/` | Paie une caution (Mobile Money) |
| 5. Contrat | `/courier/onboarding/contract/` | Accepte les conditions, signe numériquement |
| 6. En attente | `/courier/onboarding/status/` | L'admin vérifie et approuve |

### La période de probation

```
                 PROBATION (7 jours)
    ┌─────────────────────────────────────────┐
    │  📦 Max 10 livraisons/jour              │
    │  📊 Score de confiance calculé           │
    │  🔍 Admin surveille les performances     │
    │                                          │
    │  Score ≥ 0.5 → ✅ APPROUVÉ              │
    │  Score < 0.5 → ❌ REJETÉ                │
    │                                          │
    │  Le score compte :                       │
    │  - Taux de livraison réussie             │
    │  - Temps de réponse                      │
    │  - Notes des clients                     │
    │  - Nombre d'annulations                  │
    └─────────────────────────────────────────┘
```

---

## ☀️ 7h30 — Jean se met en ligne

Jean ouvre l'app RELAY237 sur son téléphone et active sa disponibilité :

```
┌──────────────────────────────────────┐
│  🏍️ Dashboard Coursier              │
│                                      │
│  ┌──────────────────────────────┐   │
│  │  🟢 EN LIGNE                 │   │
│  │  [══════════════] Toggle     │   │
│  └──────────────────────────────┘   │
│                                      │
│  📊 Aujourd'hui                      │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐       │
│  │ 0  │ │ 0  │ │5.0 │ │800 │       │
│  │crs.│ │XAF │ │ ⭐ │ │XAF │       │
│  │    │ │rev.│ │note│ │wal.│       │
│  └────┘ └────┘ └────┘ └────┘       │
└──────────────────────────────────────┘
```

> **En coulisses** : Quand Jean active le toggle, son `is_online` passe à `True` et sa position GPS commence à être envoyée toutes les 10 secondes via l'API mobile.

---

## 🔔 7h45 — Première course !

### Notification de nouvelle course

Jean reçoit une notification push + WhatsApp :

```
📦 NOUVELLE COURSE !

🏠 Pickup : Bonamoussadi (Marie Fashion)
📍 Dropoff : Akwa (Paul Nkwi)
📏 Distance : 5.2 km
💰 Gain estimé : 1 200 XAF

⏱️ Vous avez 60 secondes pour accepter !

[✅ Accepter]  [❌ Refuser]
```

Jean accepte la course. Son `acceptance_rate` est mis à jour.

> **Si Jean refuse trop souvent** : Son `acceptance_rate` baisse → moins de courses proposées → affecte son niveau.

---

## 🏠 8h00 — Le pickup

Jean arrive chez Marie (la vendeuse). Le processus :

```
┌─────────────────────────────────────────┐
│  📸 Étape 1 : Prendre une photo         │
│                                          │
│  Photographiez le colis pour preuve.     │
│  [📷 Prendre la photo]                  │
│                                          │
├──────────────────────────────────────────┤
│  🔐 Étape 2 : Entrer le code OTP        │
│                                          │
│  Demandez le code au vendeur.            │
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐              │
│  │ 4 │ │ 7 │ │ 2 │ │ 1 │              │
│  └───┘ └───┘ └───┘ └───┘              │
│                                          │
│  [✅ Confirmer le retrait]              │
└─────────────────────────────────────────┘
```

> **Sécurité** : L'OTP garantit que le bon colis est récupéré par le bon coursier. Le vendeur reçoit un code unique par WhatsApp qu'il donne à Jean.

---

## 🚀 8h15 — En transit

Jean roule vers Akwa. L'app lui montre :

```
┌──────────────────────────────────────┐
│  🗺️ Navigation active                │
│                                      │
│  📍 Paul Nkwi — Akwa                │
│  📏 3.8 km restants                  │
│  ⏱️ ETA : 12 min                    │
│                                      │
│  ═══════════════▶────── (60%)        │
│                                      │
│  [📱 Ouvrir dans Google Maps]        │
│  [⚠️ Signaler un événement]         │
└──────────────────────────────────────┘
```

### Signalement d'événements (type Waze)

En route, Jean croise un contrôle de police. Il signale :

```
⚠️ Signaler un événement

[🚗 Accident]  [👮 Police]  [🚧 Route barrée]
[🌊 Inondation] [🚦 Embouteillage] [🏗️ Travaux]
[⚠️ Danger]  [⛽ Station essence] [📍 Autre]

→ Jean sélectionne "👮 Police"
→ Sa position GPS est enregistrée
→ Les autres coursiers sont avertis !
```

---

## ✅ 8h30 — Livraison au destinataire

Jean arrive chez Paul. Il demande le code OTP :

```
┌─────────────────────────────────────────┐
│  📦 Livraison — Paul Nkwi              │
│                                          │
│  🔐 Entrez le code du destinataire      │
│                                          │
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐              │
│  │ 8 │ │ 3 │ │ 5 │ │ 6 │              │
│  └───┘ └───┘ └───┘ └───┘              │
│                                          │
│  [✅ Confirmer la livraison]            │
└─────────────────────────────────────────┘
```

Code OK → ✅ **LIVRAISON CONFIRMÉE !**

```
🎉 Livraison réussie !

💰 +1 600 XAF (après commission)
🔥 Streak : 16 livraisons consécutives !
⭐ Note : 4.8/5 (moyenne)

[📦 Course suivante]  [🏠 Retour]
```

---

## 💰 Le wallet du coursier

### Comment ça marche (CASH P2P)

```
1. Paul (client) donne 2 000 XAF en cash à Jean
2. Jean garde les 2 000 XAF physiquement
3. La plateforme DÉBITE 400 XAF (20%) du wallet de Jean
4. Le wallet de Jean : avant → après

   Wallet: 800 XAF → 400 XAF
   (800 - 400 commission = 400 XAF)
   
   ⚠️ Le wallet peut devenir NÉGATIF !
```

### Comment ça marche (PRÉPAYÉ)

```
1. Le vendeur avait déjà payé 2 000 XAF
2. La plateforme CRÉDITE 1 600 XAF (80%) au wallet de Jean
3. Le wallet de Jean : avant → après

   Wallet: 400 XAF → 2 000 XAF
```

### Retirer son argent

Jean veut retirer via MTN Mobile Money :

```
┌──────────────────────────────────────┐
│  💳 Retrait Mobile Money              │
│                                      │
│  Solde disponible : 12 500 XAF       │
│                                      │
│  Montant : [10 000] XAF             │
│  Envoyé vers : MTN MoMo             │
│  Numéro : +237 691 234 567          │
│                                      │
│  Min: 1 000 XAF | Max: 500 000 XAF  │
│                                      │
│  [💸 Demander le retrait]            │
│                                      │
│  ⏳ Délai : 24-48h (validation admin)│
└──────────────────────────────────────┘
```

### Le piège de la dette 💀

```
   Wallet: +500 XAF   → 🟢 Tout va bien
   
   3 courses cash d'affilée sans rembourser :
   
   Wallet: +500
           -400 (commission course 1)
           = +100 XAF  → 🟢 OK

   Wallet: +100
           -350 (commission course 2)
           = -250 XAF  → 🟡 Attention !
           
   WhatsApp : "⚠️ Votre solde est négatif (-250 XAF)..."
   
   Wallet: -250
           -400 (commission course 3)
           = -650 XAF  → 🟡 Danger
           
   ...
   
   Wallet: -2 500 XAF → 🔴 BLOQUÉ !!
   ═══════════════════════════════════
   "Votre compte est bloqué. 
    Déposez de l'argent pour continuer."
```

---

## 🏆 Gamification — Les niveaux

### Progression de Jean

```
    🥉 BRONZE         🥈 SILVER          🥇 GOLD          💎 PLATINUM
    ──────────────────────────────────────────────────────────────────
    [████████████████] Jean est ici !
    
    ✅ 247 livraisons     (besoin: 200+ pour GOLD)
    ⭐ 4.7/5 note         (besoin: 4.0+)
    🔥 Best streak: 42    (besoin: 25+)
    
    → Jean est presque GOLD ! 🎯
```

### Badges débloqués

```
🏅 Premier Pas        — 1ère livraison complétée
🌅 Lève-tôt           — Livraison avant 8h
🌙 Noctambule          — Livraison après 22h  
🔥 En Feu             — 10 livraisons consécutives
⭐ 5 Étoiles          — Première note parfaite
📏 Marathon            — 500 km parcourus
💯 Centurion           — 100 livraisons
🏆 Légende             — 500 livraisons
```

---

## 📊 18h00 — Bilan de la journée

Jean ouvre **📊 Performances** :

```
┌──────────────────────────────────────────┐
│  📊 Performances — Aujourd'hui           │
│                                          │
│  📦 12 courses    💰 14 400 XAF gagné    │
│  ✅ 100% succès   ⏱️ 38 sec rép. moyen  │
│  📏 47.3 km       🔥 Streak: 12         │
│                                          │
│  📈 Évolution de la semaine              │
│  L  M  M  J  V  S  D                    │
│  8  10 12 9  12 -  -                     │
│  ▓  ▓▓ ▓▓ ▓  ▓▓                         │
│                                          │
│  🏆 Classement : #4 / 52 coursiers      │
│  ↑ +2 places cette semaine              │
└──────────────────────────────────────────┘
```

### Classement (Leaderboard)

```
┌──────────────────────────────────────────┐
│  🏆 Classement Global                    │
│                                          │
│  🥇 #1  Pierre K.   ⭐4.9  📦312  💎    │
│  🥈 #2  André M.    ⭐4.8  📦287  🥇    │
│  🥉 #3  Samuel T.   ⭐4.8  📦265  🥇    │
│  🏅 #4  Jean M. ← vous   ⭐4.7  📦247  🥈│
│     #5  Paul N.      ⭐4.6  📦231  🥈    │
│     ...                                  │
└──────────────────────────────────────────┘
```

---

## 📅 Planning de disponibilité

Jean configure ses créneaux dans **📅 Disponibilité** :

```
┌──────────────────────────────────────────┐
│  📅 Ma Disponibilité                      │
│                                          │
│  🟢 Actuellement EN LIGNE                │
│                                          │
│  Créneaux récurrents :                   │
│  ┌────────────────────────────────────┐  │
│  │ Lun-Ven  07:00 — 12:00            │  │
│  │ Lun-Ven  14:00 — 20:00            │  │
│  │ Sam      08:00 — 18:00            │  │
│  └────────────────────────────────────┘  │
│                                          │
│  [+ Ajouter un créneau]                 │
└──────────────────────────────────────────┘
```

---

## 💡 Résumé — Ce que RELAY237 apporte à Jean

| Avant | Avec RELAY237 |
|---|---|
| Attendre les appels | Courses automatiques push |
| Négocier chaque prix | Tarification fixe et transparente |
| Pas de suivi client | GPS + OTP = confiance |
| Revenus incertains | Dashboard avec KPIs clairs |
| Pas de progression | Gamification (niveaux, badges, streak) |
| Cash à gérer manuellement | Wallet + retrait MoMo/OM |
| Isolé | Communauté + classement motivant |

---

## 📦 Modules impliqués dans ce parcours

| Étape | Module(s) | Fichiers clés |
|---|---|---|
| Onboarding | `courier/` | `onboarding_views.py` |
| Dashboard | `courier/` | `dashboard.html`, `views.py` |
| Notification de course | `bot/`, `logistics/` | `tasks.py`, `dispatch.py` |
| Navigation | `logistics/` | Smart routing, OSRM |
| OTP (pickup & dropoff) | `core/`, `bot/` | OTP gen + WhatsApp |
| GPS temps réel | `courier/`, `logistics/` | API mobile + Channels |
| Signalements trafic | `logistics/` | `TrafficEvent` model |
| Wallet | `finance/` | `WalletService` |
| Retraits | `finance/` | `WithdrawalService` |
| Gamification | `core/`, `courier/` | `CourierLevel`, `badges.html` |
| Performances | `courier/` | `performance.html`, `views.py` |
| Leaderboard | `courier/` | `leaderboard.html` |

---

*📖 Retour au [README principal](../README.md) | Voir aussi : [🛍️ Parcours Vendeur](./vendeur_journey.md)*
