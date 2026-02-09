"""
LOGISTICS App - Smart Routing Service

Calculates optimal delivery routes by combining:
1. OSRM (free open-source routing engine) for base route
2. DELIVR-CM crowdsourced traffic data (heatmap)
3. Active traffic events (accidents, road closures, etc.)

The service generates strategic waypoints that, when passed to
Google Maps/Waze via deep links, force the navigation app to
follow our optimized route instead of its default.

Architecture:
    POST /api/traffic/smart-route/
        → SmartRoutingService.get_smart_route(origin, destination)
            → OSRM: get base route + alternatives
            → TrafficService: check congestion along each route
            → TrafficEvent: check incidents near each route
            → Score each route (penalty = congestion + events)
            → Return best route with waypoints for nav app
"""

import math
import logging
import requests
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, asdict, field

from django.utils import timezone

from .traffic_service import TrafficService, TrafficLevel, CELL_SIZE_DEG

logger = logging.getLogger(__name__)

# ============================================
# CONSTANTS
# ============================================

# OSRM public server (free, supports Cameroon)
OSRM_BASE_URL = 'http://router.project-osrm.org'

# Penalty weights for route scoring
PENALTY_DENSE = 3.0       # Dense traffic cell penalty (minutes)
PENALTY_BLOQUE = 8.0      # Blocked cell penalty (minutes)
PENALTY_MODERE = 1.0      # Moderate traffic penalty
PENALTY_ACCIDENT = 10.0   # Active accident
PENALTY_ROAD_CLOSED = 50.0  # Road completely closed
PENALTY_POLICE = 2.0      # Police checkpoint (slight delay)
PENALTY_FLOODING = 15.0   # Flooding
PENALTY_ROADWORK = 5.0    # Roadworks

# Event type → penalty mapping
EVENT_PENALTIES = {
    'ACCIDENT': PENALTY_ACCIDENT,
    'ROAD_CLOSED': PENALTY_ROAD_CLOSED,
    'POLICE': PENALTY_POLICE,
    'FLOODING': PENALTY_FLOODING,
    'ROADWORK': PENALTY_ROADWORK,
    'TRAFFIC_JAM': 6.0,
    'POTHOLE': 1.0,
    'HAZARD': 3.0,
    'FUEL_STATION': 0,  # Not a penalty
    'OTHER': 1.0,
}

# Maximum distance (meters) to consider an event as affecting a route
EVENT_PROXIMITY_METERS = 300

# Number of waypoints to inject for nav app deep linking
MAX_WAYPOINTS_FOR_NAV = 5

# Waypoint spacing (minimum meters between waypoints)
MIN_WAYPOINT_SPACING = 500


# ============================================
# DATA CLASSES
# ============================================

@dataclass
class RouteSegment:
    """A segment of a route with traffic info."""
    lat: float
    lng: float
    speed_kmh: float
    level: str
    cell_id: str


@dataclass
class TrafficWarning:
    """An alert about a traffic condition on the route."""
    type: str          # 'congestion', 'event', 'closure'
    severity: str      # 'info', 'warning', 'danger'
    message: str
    latitude: float
    longitude: float
    penalty_minutes: float


@dataclass
class SmartRoute:
    """Optimized route result."""
    # Route geometry (list of [lat, lng])
    coordinates: List[List[float]]
    
    # Strategic waypoints for nav app deep linking
    waypoints: List[List[float]]
    
    # Metrics
    distance_km: float
    base_eta_minutes: float     # Without traffic
    smart_eta_minutes: float    # With traffic penalties
    
    # Traffic analysis  
    traffic_score: float        # 0-100 (100 = fully congested)
    congested_segments: int
    total_segments: int
    
    # Warnings
    warnings: List[Dict] = field(default_factory=list)
    
    # Alternative routes
    alternatives: List[Dict] = field(default_factory=list)
    
    # Deep link URLs
    google_maps_url: str = ''
    waze_url: str = ''
    apple_maps_url: str = ''
    
    def to_dict(self):
        return asdict(self)


# ============================================
# MAIN SERVICE
# ============================================

class SmartRoutingService:
    """
    Intelligent routing that combines OSRM with real-time
    crowdsourced traffic data from DELIVR-CM couriers.
    """
    
    @classmethod
    def get_smart_route(
        cls,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        avoid_events: bool = True,
    ) -> Optional[SmartRoute]:
        """
        Calculate the best route from origin to destination.
        
        1. Get route(s) from OSRM
        2. Analyze traffic on each route
        3. Check for events near each route
        4. Score and rank routes
        5. Generate waypoints for nav app
        6. Build deep links
        """
        try:
            # Step 1: Get routes from OSRM
            osrm_routes = cls._fetch_osrm_routes(
                origin_lat, origin_lng,
                dest_lat, dest_lng,
            )
            
            if not osrm_routes:
                logger.warning("[SMART-ROUTE] OSRM returned no routes")
                return cls._fallback_route(
                    origin_lat, origin_lng,
                    dest_lat, dest_lng,
                )
            
            # Step 2-3: Score each route
            scored_routes = []
            for i, route in enumerate(osrm_routes):
                scored = cls._score_route(route, avoid_events)
                scored['index'] = i
                scored_routes.append(scored)
            
            # Step 4: Pick the best route (lowest total penalty)
            scored_routes.sort(key=lambda r: r['total_penalty'])
            best = scored_routes[0]
            best_route = osrm_routes[best['index']]
            
            # Step 5: Generate strategic waypoints
            waypoints = cls._generate_smart_waypoints(
                best_route['coordinates'],
                best.get('avoid_zones', []),
            )
            
            # Step 6: Build deep links
            google_url = cls._build_google_maps_url(
                origin_lat, origin_lng,
                dest_lat, dest_lng,
                waypoints,
            )
            waze_url = cls._build_waze_url(dest_lat, dest_lng)
            apple_url = cls._build_apple_maps_url(
                origin_lat, origin_lng,
                dest_lat, dest_lng,
                waypoints,
            )
            
            # Build alternatives summary
            alternatives = []
            for scored in scored_routes[1:]:
                alt_route = osrm_routes[scored['index']]
                alternatives.append({
                    'distance_km': round(alt_route['distance_m'] / 1000, 1),
                    'base_eta_minutes': round(alt_route['duration_s'] / 60, 1),
                    'smart_eta_minutes': round(
                        alt_route['duration_s'] / 60 + scored['total_penalty'], 1
                    ),
                    'traffic_score': scored['traffic_score'],
                    'congested_segments': scored['congested_count'],
                    'warnings_count': len(scored['warnings']),
                })
            
            return SmartRoute(
                coordinates=best_route['coordinates'],
                waypoints=waypoints,
                distance_km=round(best_route['distance_m'] / 1000, 1),
                base_eta_minutes=round(best_route['duration_s'] / 60, 1),
                smart_eta_minutes=round(
                    best_route['duration_s'] / 60 + best['total_penalty'], 1
                ),
                traffic_score=best['traffic_score'],
                congested_segments=best['congested_count'],
                total_segments=best['total_segments'],
                warnings=best['warnings'],
                alternatives=alternatives,
                google_maps_url=google_url,
                waze_url=waze_url,
                apple_maps_url=apple_url,
            )
            
        except Exception as e:
            logger.exception(f"[SMART-ROUTE] Error: {e}")
            return cls._fallback_route(
                origin_lat, origin_lng,
                dest_lat, dest_lng,
            )
    
    # ==========================================
    # OSRM INTEGRATION
    # ==========================================
    
    @classmethod
    def _fetch_osrm_routes(
        cls,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> List[Dict]:
        """
        Fetch route(s) from OSRM.
        
        Note: OSRM uses lng,lat order (GeoJSON convention).
        Returns up to 3 alternatives.
        """
        # OSRM format: /route/v1/driving/lng1,lat1;lng2,lat2
        coords = f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        url = f"{OSRM_BASE_URL}/route/v1/driving/{coords}"
        
        params = {
            'overview': 'full',          # Full route geometry
            'geometries': 'geojson',     # GeoJSON format
            'alternatives': 'true',      # Get alternative routes
            'steps': 'false',            # No turn-by-turn (we don't need it)
            'annotations': 'duration,distance',  # Segment annotations
        }
        
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 'Ok':
                logger.warning(f"[OSRM] Error: {data.get('message', 'Unknown')}")
                return []
            
            routes = []
            for route in data.get('routes', []):
                geometry = route.get('geometry', {})
                coords_list = geometry.get('coordinates', [])
                
                # OSRM returns [lng, lat] → convert to [lat, lng]
                coordinates = [[c[1], c[0]] for c in coords_list]
                
                routes.append({
                    'coordinates': coordinates,
                    'distance_m': route.get('distance', 0),
                    'duration_s': route.get('duration', 0),
                })
            
            logger.info(
                f"[OSRM] Got {len(routes)} route(s), "
                f"best: {routes[0]['distance_m']/1000:.1f}km / "
                f"{routes[0]['duration_s']/60:.0f}min"
            )
            return routes
            
        except requests.RequestException as e:
            logger.error(f"[OSRM] Request failed: {e}")
            return []
    
    # ==========================================
    # ROUTE SCORING
    # ==========================================
    
    @classmethod
    def _score_route(cls, route: Dict, check_events: bool) -> Dict:
        """
        Score a route based on traffic heatmap + active events.
        
        Returns dict with:
        - total_penalty: total time penalty in minutes
        - traffic_score: 0-100 congestion score
        - congested_count: number of congested segments
        - warnings: list of warnings
        - avoid_zones: list of zones to avoid
        """
        coordinates = route['coordinates']
        total_penalty = 0.0
        congested_count = 0
        total_segments = 0
        warnings = []
        avoid_zones = []
        
        # Sample coordinates along the route (every ~200m = every cell)
        sampled = cls._sample_coordinates(coordinates, interval_m=200)
        total_segments = len(sampled)
        
        # Check each sampled point against traffic heatmap
        checked_cells = set()
        for lat, lng in sampled:
            cell_id = TrafficService.latlng_to_cell(lat, lng)
            
            if cell_id in checked_cells:
                continue
            checked_cells.add(cell_id)
            
            cell_data = TrafficService.get_cell_traffic(cell_id)
            if not cell_data:
                continue
            
            level = cell_data.get('level', TrafficLevel.UNKNOWN)
            
            if level == TrafficLevel.DENSE:
                total_penalty += PENALTY_DENSE
                congested_count += 1
                
            elif level == TrafficLevel.BLOQUE:
                total_penalty += PENALTY_BLOQUE
                congested_count += 1
                avoid_zones.append([lat, lng])
                warnings.append({
                    'type': 'congestion',
                    'severity': 'danger',
                    'message': f"🔴 Trafic bloqué ({cell_data.get('avg_speed_kmh', 0):.0f} km/h)",
                    'latitude': lat,
                    'longitude': lng,
                    'penalty_minutes': PENALTY_BLOQUE,
                })
                
            elif level == TrafficLevel.MODERE:
                total_penalty += PENALTY_MODERE
        
        # Check active traffic events
        if check_events:
            from logistics.models import TrafficEvent
            
            active_events = TrafficEvent.objects.filter(
                is_active=True,
                expires_at__gt=timezone.now(),
            ).only('id', 'event_type', 'severity', 'location', 'address')
            
            for event in active_events:
                # Extract lat/lng from PointField
                event_lat = event.location.y
                event_lng = event.location.x
                
                # Check if event is near the route
                min_dist = float('inf')
                closest_point = None
                
                for lat, lng in sampled[::3]:  # Check every 3rd point for speed
                    dist = cls._haversine_m(
                        lat, lng,
                        event_lat,
                        event_lng,
                    )
                    if dist < min_dist:
                        min_dist = dist
                        closest_point = (lat, lng)
                
                if min_dist <= EVENT_PROXIMITY_METERS:
                    event_type = event.event_type
                    penalty = EVENT_PENALTIES.get(event_type, 1.0)
                    
                    # Scale penalty by severity
                    severity_multiplier = {
                        'LOW': 0.5, 'MEDIUM': 1.0,
                        'HIGH': 1.5, 'CRITICAL': 2.0,
                    }.get(event.severity, 1.0)
                    
                    actual_penalty = penalty * severity_multiplier
                    total_penalty += actual_penalty
                    congested_count += 1
                    
                    if event_type == 'ROAD_CLOSED':
                        avoid_zones.append([event_lat, event_lng])
                    
                    # Map event type to emoji
                    event_emojis = {
                        'ACCIDENT': '🚗', 'POLICE': '👮',
                        'ROAD_CLOSED': '🚧', 'FLOODING': '🌊',
                        'POTHOLE': '🕳️', 'TRAFFIC_JAM': '🚦',
                        'ROADWORK': '🏗️', 'HAZARD': '⚠️',
                    }
                    warn_severity = 'danger' if actual_penalty >= 10 else (
                        'warning' if actual_penalty >= 3 else 'info'
                    )
                    
                    emoji = event_emojis.get(event_type, '📍')
                    address = event.address or ''
                    
                    warnings.append({
                        'type': 'event',
                        'severity': warn_severity,
                        'message': f"{emoji} {event_type.replace('_', ' ').title()}"
                                   f"{f' — {address}' if address else ''}",
                        'latitude': event_lat,
                        'longitude': event_lng,
                        'penalty_minutes': actual_penalty,
                    })
        
        # Calculate traffic score (0-100)
        if total_segments > 0:
            traffic_score = min(100, (congested_count / max(total_segments, 1)) * 100)
        else:
            traffic_score = 0
        
        return {
            'total_penalty': total_penalty,
            'traffic_score': round(traffic_score, 1),
            'congested_count': congested_count,
            'total_segments': total_segments,
            'warnings': warnings,
            'avoid_zones': avoid_zones,
        }
    
    @classmethod
    def _sample_coordinates(
        cls,
        coordinates: List[List[float]],
        interval_m: float = 200,
    ) -> List[Tuple[float, float]]:
        """Sample coordinates along a route at regular intervals."""
        if not coordinates:
            return []
        
        sampled = [tuple(coordinates[0])]
        accumulated_dist = 0.0
        
        for i in range(1, len(coordinates)):
            prev = coordinates[i - 1]
            curr = coordinates[i]
            dist = cls._haversine_m(prev[0], prev[1], curr[0], curr[1])
            accumulated_dist += dist
            
            if accumulated_dist >= interval_m:
                sampled.append(tuple(curr))
                accumulated_dist = 0.0
        
        # Always include the last point
        last = tuple(coordinates[-1])
        if sampled[-1] != last:
            sampled.append(last)
        
        return sampled
    
    # ==========================================
    # WAYPOINT GENERATION
    # ==========================================
    
    @classmethod
    def _generate_smart_waypoints(
        cls,
        coordinates: List[List[float]],
        avoid_zones: List[List[float]],
    ) -> List[List[float]]:
        """
        Generate strategic waypoints for nav app deep linking.
        
        These waypoints force Google Maps/Waze to follow our
        optimized route through key intersections.
        
        Strategy:
        - Place waypoints at regular intervals along the route
        - Add extra waypoints near avoid zones (to route around them)
        - Max 5 waypoints (Google Maps limit for free)
        """
        if len(coordinates) < 3:
            return []
        
        # Calculate total route length
        total_dist = 0.0
        for i in range(1, len(coordinates)):
            total_dist += cls._haversine_m(
                coordinates[i-1][0], coordinates[i-1][1],
                coordinates[i][0], coordinates[i][1],
            )
        
        if total_dist < 500:
            # Short route, no waypoints needed
            return []
        
        # Generate evenly spaced waypoints
        target_count = min(MAX_WAYPOINTS_FOR_NAV, max(2, int(total_dist / 1000)))
        interval = total_dist / (target_count + 1)
        
        waypoints = []
        accumulated = 0.0
        wp_count = 0
        
        for i in range(1, len(coordinates)):
            prev = coordinates[i - 1]
            curr = coordinates[i]
            seg_dist = cls._haversine_m(prev[0], prev[1], curr[0], curr[1])
            accumulated += seg_dist
            
            if accumulated >= interval and wp_count < target_count:
                waypoints.append([round(curr[0], 6), round(curr[1], 6)])
                accumulated = 0.0
                wp_count += 1
        
        return waypoints
    
    # ==========================================
    # DEEP LINKS
    # ==========================================
    
    @classmethod
    def _build_google_maps_url(
        cls,
        origin_lat: float, origin_lng: float,
        dest_lat: float, dest_lng: float,
        waypoints: List[List[float]],
    ) -> str:
        """
        Build Google Maps navigation URL with waypoints.
        
        Format:
        https://www.google.com/maps/dir/origin/wp1/wp2/destination/
        
        Or for mobile deep link:
        google.navigation:q=lat,lng (single destination, no waypoints)
        comgooglemaps://?saddr=&daddr=wp1+to:wp2+to:dest
        """
        # Web URL format (works on both mobile and desktop)
        parts = [f"{origin_lat},{origin_lng}"]
        for wp in waypoints:
            parts.append(f"{wp[0]},{wp[1]}")
        parts.append(f"{dest_lat},{dest_lng}")
        
        path = '/'.join(parts)
        return f"https://www.google.com/maps/dir/{path}/@{dest_lat},{dest_lng},14z/data=!4m2!4m1!3e0"
    
    @classmethod
    def _build_waze_url(cls, dest_lat: float, dest_lng: float) -> str:
        """
        Build Waze navigation URL.
        
        Waze doesn't support waypoints in deep links,
        but it has its own traffic-based routing.
        """
        return f"https://waze.com/ul?ll={dest_lat},{dest_lng}&navigate=yes"
    
    @classmethod
    def _build_apple_maps_url(
        cls,
        origin_lat: float, origin_lng: float,
        dest_lat: float, dest_lng: float,
        waypoints: List[List[float]],
    ) -> str:
        """Build Apple Maps URL."""
        return (
            f"https://maps.apple.com/?saddr={origin_lat},{origin_lng}"
            f"&daddr={dest_lat},{dest_lng}"
            f"&dirflg=d"
        )
    
    # ==========================================
    # FALLBACK ROUTE
    # ==========================================
    
    @classmethod
    def _fallback_route(
        cls,
        origin_lat: float, origin_lng: float,
        dest_lat: float, dest_lng: float,
    ) -> SmartRoute:
        """
        Fallback when OSRM is unavailable.
        Returns a straight-line route with basic estimated ETA.
        """
        dist_m = cls._haversine_m(origin_lat, origin_lng, dest_lat, dest_lng)
        dist_km = dist_m / 1000
        # Average 25 km/h in Douala
        eta_min = (dist_km / 25) * 60
        
        google_url = cls._build_google_maps_url(
            origin_lat, origin_lng, dest_lat, dest_lng, [],
        )
        waze_url = cls._build_waze_url(dest_lat, dest_lng)
        
        return SmartRoute(
            coordinates=[
                [origin_lat, origin_lng],
                [dest_lat, dest_lng],
            ],
            waypoints=[],
            distance_km=round(dist_km, 1),
            base_eta_minutes=round(eta_min, 1),
            smart_eta_minutes=round(eta_min, 1),
            traffic_score=0,
            congested_segments=0,
            total_segments=1,
            warnings=[{
                'type': 'info',
                'severity': 'info',
                'message': '⚠️ Itinéraire approximatif (OSRM indisponible)',
                'latitude': origin_lat,
                'longitude': origin_lng,
                'penalty_minutes': 0,
            }],
            alternatives=[],
            google_maps_url=google_url,
            waze_url=waze_url,
            apple_maps_url='',
        )
    
    # ==========================================
    # HELPERS
    # ==========================================
    
    @staticmethod
    def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Distance in meters between two GPS points."""
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlng / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
