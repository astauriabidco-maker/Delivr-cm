"""
Traffic Simulation Script for DELIVR-CM

Simulates 8 couriers moving through various neighborhoods in Douala
at different speeds to populate the traffic heatmap.

Usage:
    docker compose exec web python manage.py shell < logistics/scripts/simulate_traffic.py

Or just:
    docker compose exec -T web python manage.py shell -c "exec(open('logistics/scripts/simulate_traffic.py').read())"
"""

import json
import time
import random
from logistics.services.traffic_service import TrafficService

print("🚦 DELIVR-CM - Simulation de trafic Douala")
print("=" * 50)

# Define simulated routes through Douala neighborhoods
ROUTES = {
    "Coursier_Akwa": {
        "name": "Route Akwa → Bonapriso",
        "speed_range": (20, 35),  # Fluide
        "waypoints": [
            (4.0480, 9.6920),   # Akwa centre
            (4.0462, 9.6935),
            (4.0445, 9.6950),
            (4.0430, 9.6960),
            (4.0415, 9.6975),
            (4.0400, 9.6990),   # Vers Bonapriso
            (4.0385, 9.7005),
            (4.0370, 9.7020),
        ],
    },
    "Coursier_Bonaberi": {
        "name": "Route Bonabéri (embouteillage classique)",
        "speed_range": (3, 8),  # Bloqué / Dense
        "waypoints": [
            (4.0720, 9.6650),   # Bonabéri
            (4.0710, 9.6670),
            (4.0700, 9.6690),
            (4.0690, 9.6710),
            (4.0680, 9.6730),
            (4.0670, 9.6750),
        ],
    },
    "Coursier_Deido": {
        "name": "Route Deïdo → Bali",
        "speed_range": (12, 20),  # Modéré
        "waypoints": [
            (4.0600, 9.6850),   # Deïdo
            (4.0585, 9.6870),
            (4.0570, 9.6890),
            (4.0555, 9.6910),
            (4.0540, 9.6930),
            (4.0525, 9.6950),   # Bali
        ],
    },
    "Coursier_Makepe": {
        "name": "Route Makepe → Bonamoussadi",
        "speed_range": (25, 40),  # Fluide
        "waypoints": [
            (4.0700, 9.7400),   # Makepe
            (4.0715, 9.7420),
            (4.0730, 9.7440),
            (4.0745, 9.7460),
            (4.0760, 9.7480),
            (4.0775, 9.7500),   # Bonamoussadi
        ],
    },
    "Coursier_Ndokotti": {
        "name": "Route Ndokotti (carrefour congestionné)",
        "speed_range": (2, 6),  # Bloqué
        "waypoints": [
            (4.0550, 9.7250),   # Ndokotti centre
            (4.0545, 9.7265),
            (4.0540, 9.7280),
            (4.0535, 9.7295),
            (4.0530, 9.7310),
        ],
    },
    "Coursier_Bepanda": {
        "name": "Route Bépanda",
        "speed_range": (10, 18),  # Modéré / Dense
        "waypoints": [
            (4.0450, 9.7350),   # Bépanda
            (4.0440, 9.7365),
            (4.0430, 9.7380),
            (4.0420, 9.7395),
            (4.0410, 9.7410),
        ],
    },
    "Coursier_Logbessou": {
        "name": "Route Logbessou → PK14",
        "speed_range": (30, 50),  # Fluide (route large)
        "waypoints": [
            (4.0300, 9.7600),   # Logbessou
            (4.0280, 9.7620),
            (4.0260, 9.7640),
            (4.0240, 9.7660),
            (4.0220, 9.7680),
            (4.0200, 9.7700),   # PK14
        ],
    },
    "Coursier_Cite": {
        "name": "Route Cité des Palmiers → New Bell",
        "speed_range": (6, 14),  # Dense
        "waypoints": [
            (4.0350, 9.7100),   # Cité des Palmiers
            (4.0340, 9.7080),
            (4.0330, 9.7060),
            (4.0320, 9.7040),
            (4.0310, 9.7020),   # New Bell
        ],
    },
}

# Get Redis connection
r = TrafficService._get_redis()
if not r:
    print("❌ Impossible de se connecter à Redis")
    exit(1)

print(f"✅ Redis connecté")
print(f"📍 Simulation de {len(ROUTES)} coursiers...")
print()

total_cells = set()

# Simulation passes to generate enough density (MIN_OBSERVATIONS = 2)
SIMULATION_PASSES = 3

def interpolate_points(p1, p2, step_deg=0.0008):
    """Generates intermediate points between two coordinates."""
    lat1, lng1 = p1
    lat2, lng2 = p2
    
    dist_deg = ((lat2-lat1)**2 + (lng2-lng1)**2)**0.5
    if dist_deg < step_deg:
        return [p2]
        
    num_steps = int(dist_deg / step_deg)
    points = []
    for i in range(1, num_steps + 1):
        fraction = i / num_steps
        lat = lat1 + (lat2 - lat1) * fraction
        lng = lng1 + (lng2 - lng1) * fraction
        points.append((lat, lng))
    return points

for pass_idx in range(SIMULATION_PASSES):
    print(f"\n🔄 Vague de simulation {pass_idx + 1}/{SIMULATION_PASSES}")
    
    for base_courier_id, route in ROUTES.items():
        courier_id = f"{base_courier_id}_{pass_idx}"
        speed_min, speed_max = route["speed_range"]
        waypoints = route["waypoints"]
        
        print(f"🏍️  {route['name']} ({base_courier_id})")
        
        # Start at the first point
        current_lat, current_lng = waypoints[0]
        
        # Initialize position in Redis without calculating speed (first fix)
        r.setex(
            f"traffic:fix:{courier_id}", 
            300, 
            json.dumps({
                "courier_id": courier_id,
                "latitude": current_lat,
                "longitude": current_lng,
                "timestamp": time.time() - 60 # Assume started 1 min ago
            })
        )
        
        points_processed = 0
        
        for i in range(len(waypoints) - 1):
            p1 = waypoints[i]
            p2 = waypoints[i+1]
            
            # Interpolate to ensure we hit every cell along the path
            segment_points = interpolate_points(p1, p2)
            
            for lat, lng in segment_points:
                # Simulate a realistic speed variation
                target_speed = random.uniform(speed_min, speed_max)
                
                # Calculate distance from PREVIOUS point to CURRENT point
                # We need to fetch the 'previous' point from what we just processed
                # But since we are simulating, we can just compute distance from last 'current'
                
                distance = TrafficService.haversine_distance(current_lat, current_lng, lat, lng)
                
                # Calculate time needed
                speed_ms = target_speed / 3.6
                if speed_ms > 0 and distance > 0:
                    dt = distance / speed_ms
                else:
                    dt = 5
                
                # Update "previous" fix timestamp to effectively simulate time passing
                # In a real scenario, we'd wait. Here we fake the previous timestamp.
                prev_fix = {
                    "courier_id": courier_id,
                    "latitude": current_lat,
                    "longitude": current_lng,
                    "timestamp": time.time() - dt
                }
                r.setex(f"traffic:fix:{courier_id}", 300, json.dumps(prev_fix))
                
                # Ingest new location
                speed = TrafficService.ingest_location(courier_id, lat, lng)
                
                if speed is not None:
                    cell_id = TrafficService.latlng_to_cell(lat, lng)
                    level = TrafficService.speed_to_level(speed)
                    if cell_id:
                        total_cells.add(cell_id)
                        # Only print occasionally to avoid spam
                        # if random.random() < 0.2:
                        #    print(f"   📍 {cell_id} → {speed:.1f} km/h")
                
                current_lat, current_lng = lat, lng
                points_processed += 1
        
        print(f"   ✅ {points_processed} points de GPS simulés")

print()
print("=" * 50)

# Clear heatmap cache to force fresh aggregation
r.delete("traffic:heatmap")

# Get fresh heatmap
cells = TrafficService.get_traffic_heatmap()
stats = TrafficService.get_traffic_stats()

print(f"🗺️  Heatmap: {len(cells)} cellules actives")
print()

# Summary by level
level_summary = {}
for cell in cells:
    level = cell["level"]
    level_summary[level] = level_summary.get(level, 0) + 1

emojis = {"FLUIDE": "🟢", "MODERE": "🟡", "DENSE": "🔴", "BLOQUE": "⛔"}
for level, count in sorted(level_summary.items()):
    emoji = emojis.get(level, "⚪")
    print(f"   {emoji} {level}: {count} cellules")

print()
print(f"📊 Vitesse moyenne ville: {stats['avg_city_speed_kmh']} km/h")
print(f"📊 Niveau global: {stats['overall_level']}")
print(f"📊 Coursiers simulés: {len(ROUTES)}")
print()
print("✅ Simulation terminée! Ouvrez l'API: http://localhost:8000/api/traffic/heatmap/")
print("✅ Ou testez l'app mobile pour voir la heatmap sur la carte!")
