# 📦 Module `logistics/` — Livraisons, Quartiers & Routing

> Le moteur opérationnel de RELAY237. Gère tout le cycle de vie d'une livraison, du calcul de prix à la confirmation GPS.

---

## 🎯 Rôle en une phrase

> Ce module sait **combien coûte** une livraison, **quel coursier** l'assigner, **où il est** en temps réel, et **quand c'est livré**.

---

## 👥 Qui l'utilise ?

| Profil | Utilisation |
|---|---|
| 🛍️ BUSINESS | Crée des livraisons, suit en temps réel |
| 🏍️ COURIER | Reçoit, accepte et confirme les livraisons |
| 👤 CLIENT | Destinataire — donne l'OTP |
| 👑 ADMIN | Supervision globale, live map |

---

## 📦 Modèles de données

### `Delivery` — Cœur du système

```python
class Delivery:
    id                # UUID
    tracking_number   # "DLV-XXXXXX" (auto-généré)
    
    # Acteurs
    sender            # FK → User (le vendeur qui envoie)
    courier           # FK → User (le coursier assigné)
    client_name       # Nom du destinataire
    client_phone      # Téléphone du destinataire
    
    # Adresses
    pickup_address        # Texte libre
    pickup_neighborhood   # FK → Neighborhood (optionnel)
    pickup_geo            # PointField (GPS)
    dropoff_address       # Texte libre
    dropoff_neighborhood  # FK → Neighborhood (optionnel)
    dropoff_geo           # PointField (GPS)
    
    # Statut
    status  # PENDING → ASSIGNED → EN_ROUTE_PICKUP → ARRIVED_PICKUP 
            # → IN_TRANSIT → ARRIVED_DROPOFF → COMPLETED | CANCELLED | FAILED
    
    # Tarification (FIGÉE à la création)
    distance_km       # Distance calculée
    total_price       # Prix total (XAF)
    platform_fee      # Commission plateforme (20%)
    courier_earning   # Gain coursier (80%)
    payment_method    # CASH_P2P | PREPAID_WALLET | MOBILE_MONEY
    
    # Sécurité
    otp_code          # Code 4 chiffres pour le pickup
    delivery_otp_code # Code 4 chiffres pour la livraison
    pickup_photo      # Photo du colis au pickup
    
    # Timestamps
    created_at         # Création
    assigned_at        # Coursier assigné
    picked_up_at       # Colis récupéré
    completed_at       # Livraison confirmée
    estimated_duration # Durée estimée (minutes)
    
    # E-commerce
    item_description   # Description du colis
    shop               # FK → User (boutique B2B)
```

### `Neighborhood` — Quartiers de Douala/Yaoundé

```python
class Neighborhood:
    name        # Ex: "Akwa", "Bonapriso", "Bonamoussadi"
    city        # DOUALA | YAOUNDE
    center_geo  # PointField (barycentre du quartier)
    radius_km   # Rayon approximatif (défaut: 1.5 km)
    is_active   # Bool
```

### `Rating` — Évaluations post-livraison

```python
class Rating:
    delivery    # FK → Delivery
    rater       # FK → User (celui qui note)
    rated       # FK → User (celui qui est noté)
    rating_type # COURIER (client→coursier) | SENDER (coursier→client)
    score       # 1 à 5 ⭐
    comment     # Texte libre (optionnel)
```

### `TrafficEvent` — Signalements trafic (style Waze)

```python
class TrafficEvent:
    reporter     # FK → User (coursier)
    event_type   # ACCIDENT | POLICE | ROAD_CLOSED | FLOOD | TRAFFIC_JAM | ...
    severity     # LOW | MEDIUM | HIGH | CRITICAL
    location     # PointField (GPS)
    description  # Texte libre
    is_active    # Bool
    upvotes      # Int (confirmé par d'autres coursiers)
    expires_at   # Auto-expiration
```

---

## 🔄 Cycle de vie d'une livraison

```
   PENDING ──→ ASSIGNED ──→ EN_ROUTE_PICKUP ──→ ARRIVED_PICKUP
                                                       │
                                                       ▼
                                               📸 Photo + OTP
                                                       │
                                                       ▼
                                                  IN_TRANSIT
                                                       │
                                                       ▼
                                               ARRIVED_DROPOFF
                                                       │
                                                       ▼
                                               🔐 OTP livraison
                                                       │
                                            ┌──────────┴──────────┐
                                            ▼                     ▼
                                       COMPLETED              FAILED
                                     💰 Finances            ⚠️ Litige
                                        traitées
```

---

## 💰 Tarification

```python
# Configuration dans settings.py
PRICING_BASE_FARE    = 500   # Prise en charge (XAF)
PRICING_COST_PER_KM  = 150   # Par kilomètre
PRICING_MINIMUM_FARE = 1000  # Prix minimum
PLATFORM_FEE_PERCENT = 20    # Commission plateforme (%)

# Calcul
prix = max(BASE_FARE + (distance_km × COST_PER_KM), MINIMUM_FARE)
platform_fee = prix × 20%
courier_earning = prix × 80%
```

### Exemples

| Distance | Calcul | Prix | Commission | Gain coursier |
|---|---|---|---|---|
| 1 km | max(500+150, 1000) | **1 000 XAF** | 200 | 800 |
| 3 km | max(500+450, 1000) | **1 000 XAF** | 200 | 800 |
| 5 km | 500+750 | **1 250 XAF** | 250 | 1 000 |
| 10 km | 500+1500 | **2 000 XAF** | 400 | 1 600 |
| 20 km | 500+3000 | **3 500 XAF** | 700 | 2 800 |

---

## 🗺️ Services

### Dispatch automatique (`services/dispatch.py`)
- Trouve le coursier **le plus proche** et **en ligne**
- Vérifie qu'il n'est pas bloqué (dette)
- Envoie une notification push + WhatsApp
- Timeout de 60 secondes pour accepter

### Pricing (`services/pricing.py`)
- Calcule la distance (GPS ou quartier → quartier)
- Applique la formule de tarification
- Applique les promos si code valide

### Routing intelligent
- Utilise **OSRM** (self-hosted) pour les itinéraires optimaux
- Intègre les **événements trafic** signalés par les coursiers
- Génère des waypoints pour Google Maps / Waze

---

## 🌐 URLs & Endpoints

### Portail partenaire (HTML)
| URL | Vue | Description |
|---|---|---|
| `/partners/orders/` | `PartnerOrdersView` | Liste des commandes |
| `/partners/orders/<id>/` | `PartnerOrderDetailView` | Détail d'une commande |
| `/partners/tracking/` | `PartnerTrackingView` | Carte temps réel |

### API REST
| Endpoint | Méthode | Description |
|---|---|---|
| `/api/v1/deliveries/` | POST | Créer une livraison |
| `/api/v1/deliveries/<id>/` | GET | Détail livraison |
| `/api/v1/deliveries/<id>/status/` | PATCH | Mettre à jour le statut |
| `/api/v1/pricing/estimate/` | POST | Estimer le prix |

### API Mobile (coursier)
| Endpoint | Méthode | Description |
|---|---|---|
| `/api/mobile/deliveries/available/` | GET | Courses disponibles |
| `/api/mobile/deliveries/<id>/accept/` | POST | Accepter une course |
| `/api/mobile/deliveries/<id>/pickup/` | POST | Confirmer le pickup |
| `/api/mobile/deliveries/<id>/complete/` | POST | Confirmer la livraison |
| `/api/mobile/location/update/` | POST | Mettre à jour la position GPS |

---

## 🔗 Dépendances

```
logistics/
  │
  ├──→ core/      (User: sender, courier, client)
  ├──→ finance/   (déclenche les transactions à la complétion)
  ├──→ bot/       (notifications WhatsApp à chaque changement)
  ├──→ partners/  (notifications partenaire + webhooks)
  └──→ support/   (création de litiges liés aux livraisons)
```

---

## ⚠️ Points d'attention

| Règle | Détail |
|---|---|
| **Prix figé** | Le prix est calculé et stocké à la CRÉATION de la livraison |
| **OTP obligatoires** | Un OTP pour le pickup (vendeur) + un OTP pour la livraison (destinataire) |
| **Double GPS** | Pickup ET dropoff peuvent être en GPS exact OU par quartier |
| **Photo pickup** | Le coursier DOIT prendre une photo du colis au retrait |
| **Rating bidirectionnel** | Le client note le coursier ET le coursier note le client |
| **Événements trafic** | Auto-expirent après un délai configurable |

---

*📖 Retour au [README principal](../README.md)*
