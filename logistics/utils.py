"""
DELIVR-CM - Logistics Utilities
================================
Services utilitaires pour le calcul de distance et de prix.
"""

import math
from decimal import Decimal, ROUND_UP


# ============================================
# CONSTANTES DE CONFIGURATION
# ============================================

# Pricing Engine (cf. CONTEXT.md)
BASE_FARE = 500          # XAF - Frais de base
COST_PER_KM = 150        # XAF - Prix par kilomètre
MINIMUM_FARE = 1000      # XAF - Prix minimum
PLATFORM_FEE_RATE = Decimal("0.20")  # 20% commission plateforme
COURIER_EARNING_RATE = Decimal("0.80")  # 80% pour le coursier

# Road Factor (Majoration pour estimer distance routière)
ROAD_FACTOR = 1.3  # +30% sur la distance à vol d'oiseau

# Rayon de la Terre en km
EARTH_RADIUS_KM = 6371.0


# ============================================
# DISTANCE CALCULATION (Mock OSRM via Haversine)
# ============================================

def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calcule la distance à vol d'oiseau entre deux points GPS.
    Utilise la formule de Haversine.
    
    Args:
        lat1, lng1: Coordonnées du point de départ
        lat2, lng2: Coordonnées du point d'arrivée
    
    Returns:
        Distance en kilomètres (vol d'oiseau)
    """
    # Conversion degrés -> radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    # Formule de Haversine
    a = (
        math.sin(delta_lat / 2) ** 2 +
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return EARTH_RADIUS_KM * c


def get_routing_data(lat1: float, lng1: float, lat2: float, lng2: float) -> dict:
    """
    Calcule les données de routage entre deux points GPS.
    
    MVP: Utilise Haversine + facteur de majoration de 30% pour estimer
    la distance routière réelle (en attendant l'intégration OSRM).
    
    Args:
        lat1, lng1: Coordonnées du point de départ
        lat2, lng2: Coordonnées du point d'arrivée
    
    Returns:
        dict: {
            "distance_km": float,  # Distance routière estimée
            "duration_min": int    # Durée estimée en minutes
        }
    """
    # Distance à vol d'oiseau
    crow_distance = haversine_distance(lat1, lng1, lat2, lng2)
    
    # Application du facteur routier (+30%)
    road_distance = crow_distance * ROAD_FACTOR
    
    # Estimation de la durée (moyenne 25 km/h en ville africaine)
    # Formule: distance / vitesse * 60 (pour avoir des minutes)
    avg_speed_kmh = 25
    duration_min = int(math.ceil((road_distance / avg_speed_kmh) * 60))
    
    return {
        "distance_km": round(road_distance, 2),
        "duration_min": max(duration_min, 1)  # Minimum 1 minute
    }


# ============================================
# PRICING ENGINE
# ============================================

def round_up_to_hundred(value: int) -> int:
    """
    Arrondit un prix à la centaine supérieure.
    Ex: 1320 -> 1400, 1500 -> 1500, 1501 -> 1600
    """
    return int(math.ceil(value / 100) * 100)


def calculate_delivery_price(distance_km: float) -> dict:
    """
    Calcule le prix de livraison selon les règles métier DELIVR-CM.
    
    Règles (cf. CONTEXT.md):
        - Base = configurable (défaut: 500 XAF)
        - Prix/km = configurable (défaut: 150 XAF)
        - Minimum = configurable (défaut: 1000 XAF)
        - Arrondi à la centaine supérieure
        - Split: configurable commission plateforme
    
    Args:
        distance_km: Distance du trajet en kilomètres
    
    Returns:
        dict: {
            "client_price": int,    # Prix final payé par le client
            "platform_fee": int,    # Commission plateforme
            "courier_earning": int  # Gain net du coursier
        }
    """
    # Try to get config from IntegrationConfig, fallback to constants
    try:
        from integrations.services import ConfigService
        config = ConfigService.get_pricing_config()
        base_fare = config['base_fare']
        cost_per_km = config['cost_per_km']
        minimum_fare = config['minimum_fare']
        platform_fee_percent = config['platform_fee_percent']
    except Exception:
        # Fallback to constants if ConfigService unavailable
        base_fare = BASE_FARE
        cost_per_km = COST_PER_KM
        minimum_fare = MINIMUM_FARE
        platform_fee_percent = 20
    
    # Calcul du prix brut
    raw_price = base_fare + (distance_km * cost_per_km)
    
    # Arrondi à la centaine supérieure
    rounded_price = round_up_to_hundred(int(math.ceil(raw_price)))
    
    # Application du prix minimum
    client_price = max(rounded_price, minimum_fare)
    
    # Calcul du split
    platform_fee_rate = Decimal(str(platform_fee_percent)) / Decimal('100')
    courier_earning_rate = Decimal('1') - platform_fee_rate
    
    client_price_decimal = Decimal(str(client_price))
    platform_fee = int(client_price_decimal * platform_fee_rate)
    courier_earning = int(client_price_decimal * courier_earning_rate)
    
    return {
        "client_price": client_price,
        "platform_fee": platform_fee,
        "courier_earning": courier_earning
    }


# ============================================
# FONCTION COMBINÉE (Convenience)
# ============================================

def quote_delivery(lat1: float, lng1: float, lat2: float, lng2: float) -> dict:
    """
    Fonction de haut niveau pour obtenir un devis complet.
    Combine le calcul de distance et le pricing.
    
    Returns:
        dict: {
            "distance_km": float,
            "duration_min": int,
            "client_price": int,
            "platform_fee": int,
            "courier_earning": int
        }
    """
    routing = get_routing_data(lat1, lng1, lat2, lng2)
    pricing = calculate_delivery_price(routing["distance_km"])
    
    return {**routing, **pricing}


# ============================================
# TEST RAPIDE
# ============================================

if __name__ == "__main__":
    print("=" * 50)
    print("DELIVR-CM - Test du Pricing Engine")
    print("=" * 50)
    
    # Test avec une distance de 5.2 km
    test_distance = 5.2
    result = calculate_delivery_price(test_distance)
    
    print(f"\n📦 Simulation pour un trajet de {test_distance} km:")
    print(f"   - Calcul brut: {BASE_FARE} + ({test_distance} × {COST_PER_KM}) = {BASE_FARE + (test_distance * COST_PER_KM):.0f} XAF")
    print(f"   - Après arrondi centaine supérieure: {result['client_price']} XAF")
    print(f"\n💰 Répartition:")
    print(f"   - Prix client     : {result['client_price']:>6} XAF")
    print(f"   - Commission (20%): {result['platform_fee']:>6} XAF")
    print(f"   - Gain coursier   : {result['courier_earning']:>6} XAF")
    
    # Vérification de la cohérence
    assert result['platform_fee'] + result['courier_earning'] == result['client_price'], "Erreur: Le split n'est pas cohérent!"
    print("\n✅ Vérification OK: platform_fee + courier_earning = client_price")
    
    # Test avec coordonnées GPS (Akwa -> Bonanjo, Douala)
    print("\n" + "=" * 50)
    print("Test avec coordonnées GPS réelles (Douala)")
    print("=" * 50)
    
    # Akwa (Douala)
    akwa = (4.0511, 9.6942)
    # Bonanjo (Douala)
    bonanjo = (4.0435, 9.7043)
    
    quote = quote_delivery(akwa[0], akwa[1], bonanjo[0], bonanjo[1])
    
    print(f"\n🗺️  Trajet: Akwa → Bonanjo")
    print(f"   - Distance routière: {quote['distance_km']} km")
    print(f"   - Durée estimée    : {quote['duration_min']} min")
    print(f"   - Prix client      : {quote['client_price']} XAF")
    print(f"   - Commission       : {quote['platform_fee']} XAF")
    print(f"   - Gain coursier    : {quote['courier_earning']} XAF")
    
    print("\n" + "=" * 50)
    print("✅ Tous les tests passés avec succès!")
    print("=" * 50)
