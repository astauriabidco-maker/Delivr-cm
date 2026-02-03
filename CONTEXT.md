# PROJET : DELIVR-CM (Plateforme Logistique Décentralisée Cameroun)

## 1. RÔLE ET OBJECTIF
Tu agis en tant qu'Architecte et Lead Developer Backend pour le projet DELIVR-CM.
L'objectif est de construire une API Backend (Django) pour une plateforme de livraison urbaine opérant à Douala et Yaoundé.

**Contraintes Majeures :**
1.  **Absence d'adresses :** Le système repose sur la géolocalisation GPS (Latitude/Longitude) via WhatsApp.
2.  **Infrastructure Low-Cost :** Utilisation de services Open Source hébergés (OSRM, Nominatim) au lieu d'APIs payantes (Google Maps).
3.  **Connexion Lente :** Le code doit être optimisé pour la latence réseau.

---

## 2. STACK TECHNIQUE (Cibles)
* **Langage :** Python 3.11+
* **Framework :** Django 5.x + Django Rest Framework (DRF)
* **Base de Données :** PostgreSQL 15+ avec extension **PostGIS** (Obligatoire).
* **Async/Queue :** Redis + Celery (pour les webhooks WhatsApp).
* **Cartographie (Dockerisés) :**
    * Routing : OSRM (Open Source Routing Machine)
    * Geocoding : Nominatim
* **Authentification :** JWT pour l'API, Session pour l'Admin.

---

## 3. MODÈLE DE DONNÉES (Règles strictes)

### A. Users (Custom User Model)
* `id`: UUID (Primary Key)
* `role`: Enum ['ADMIN', 'CLIENT', 'COURIER', 'BUSINESS']
* `phone_number`: String (Unique, format international +237...)
* `wallet_balance`: Decimal (10, 2).
    * *Concept Clé :* Pour un coursier, un solde NÉGATIF signifie qu'il doit de l'argent à la plateforme (Dette).
* `debt_ceiling`: Decimal (Default: 2500.00). Si `wallet_balance < -debt_ceiling`, le coursier est bloqué.
* `is_verified`: Boolean (Documents validés).

### B. Deliveries (La Course)
* `id`: UUID
* `sender`: FK(User)
* `courier`: FK(User) (Nullable au début)
* `status`: Enum ['PENDING', 'ASSIGNED', 'PICKED_UP', 'COMPLETED', 'CANCELLED']
* `payment_method`: Enum ['CASH_P2P', 'PREPAID_WALLET']
* **Locations (PostGIS Points) :**
    * `pickup_geo`: Point(Lat, Lng)
    * `dropoff_geo`: Point(Lat, Lng)
* **Pricing (Figé à la création) :**
    * `distance_km`: Float (Calculé via OSRM)
    * `total_price`: Decimal (Prix payé par le client)
    * `platform_fee`: Decimal (Commission plateforme ~20%)
    * `courier_earning`: Decimal (Net pour le coursier)
* `otp_code`: String(4) (Généré pour sécuriser la livraison).

### C. Neighborhoods (Pour API E-commerce)
Utilisé pour estimer le prix quand le GPS exact n'est pas connu (Barycentre).
* `city`: String (ex: Douala)
* `name`: String (ex: Akwa)
* `center_geo`: Point(Lat, Lng) (Le centre du quartier)
* `radius_km`: Float.

---

## 4. LOGIQUE MÉTIER & ALGORITHMES

### A. Moteur de Prix (Pricing Engine)
Le calcul se fait sur la distance routière (OSRM), pas à vol d'oiseau.
* **Paramètres :**
    * Base Fare: 500 XAF
    * Cost per Km: 150 XAF
    * Minimum Fare: 1000 XAF
* **Formule :** `RawPrice = 500 + (DistanceKm * 150)`
* **Règle d'arrondi :** Toujours arrondir à la centaine supérieure (ex: 1320 -> 1400 XAF).
* **Règle Finale :** `FinalPrice = Max(MinimumFare, RoundedPrice)`
* **Split :** `PlatformFee = FinalPrice * 0.20` / `CourierEarning = FinalPrice * 0.80`

### B. Gestion Financière (Wallet & Dette)
Doit utiliser `transaction.atomic()` pour éviter les erreurs comptables.

**Scénario 1 : Paiement CASH (Client -> Coursier)**
1.  Le coursier garde 100% du Cash.
2.  La plateforme DÉDUIT la `platform_fee` du `wallet_balance` du coursier.
    * *Exemple :* Solde 0 -> Solde -300 (Dette).

**Scénario 2 : Paiement PREPAID (Business -> Plateforme)**
1.  Le Business est débité du `total_price` à la commande.
2.  Le Coursier est CRÉDITÉ du `courier_earning` à la livraison.
    * *Exemple :* Solde -300 -> Solde +1000 (La plateforme lui doit de l'argent).

---

## 5. SPÉCIFICATIONS API & INTERFACES

### A. API Hybride E-commerce
* `POST /api/quote` :
    * Input: `{"city": "Douala", "neighborhood": "Bastos"}`
    * Logic: Trouve le `center_geo` du quartier Bastos -> Calcule route depuis la boutique -> Ajoute 20% de marge de sécurité -> Retourne Prix.
* `POST /api/orders` :
    * Input: Détails commande + ID Quartier.
    * Action: Crée la livraison en statut 'PENDING' et déclenche le Bot WhatsApp.

### B. Bot WhatsApp (Logique Mockée pour V1)
Le Bot agit comme une machine à états (State Machine sur Redis).
* **State 1 :** Ask Pickup Location (User send GPS).
* **State 2 :** Ask Recipient Phone.
* **State 3 :** Compute Price & Confirm.
* **State 4 :** Dispatch to Couriers (Radius search).

---

## 6. INSTRUCTIONS DE DÉVELOPPEMENT
1.  Ne jamais utiliser de clés API Google Maps. Utiliser les mocks ou OSRM local.
2.  Séparer le code en apps Django logiques : `core` (Users), `logistics` (Deliveries, Routing), `finance` (Wallets).
3.  Pour les tests, mocker systématiquement les appels WhatsApp et OSRM.
