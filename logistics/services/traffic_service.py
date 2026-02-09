"""
LOGISTICS App - Crowdsourced Traffic Service

Collects speed data from courier GPS updates to build a real-time
traffic picture of the city. Uses a grid-based segmentation to
aggregate multiple courier observations into traffic levels.

Architecture:
    CourierConsumer (WebSocket)
        → TrafficService.ingest_location()
            → Compute speed from consecutive GPS fixes
            → Map (lat, lng) → grid cell ID
            → Store in Redis: traffic:cell:<cell_id>
            → Aggregate speeds → traffic level (FLUIDE / MODERE / DENSE / BLOQUE)

Grid system:
    The city is divided into ~200m × 200m cells using a simple
    lat/lng grid. At Douala's latitude (4°N), 1° latitude ≈ 111 km
    and 1° longitude ≈ 110.7 km, so a 200m cell is approximately
    0.0018° × 0.0018°.
"""

import json
import math
import time
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


# ============================================
# CONSTANTS
# ============================================

# Grid cell size in degrees (~200m at equator/Douala latitude)
CELL_SIZE_DEG = 0.0018

# Douala bounding box (approximate)
DOUALA_BOUNDS = {
    'min_lat': 3.95,
    'max_lat': 4.15,
    'min_lng': 9.60,
    'max_lng': 9.85,
}

# Traffic level thresholds (km/h)
SPEED_FLUIDE = 25       # Above this → green
SPEED_MODERE = 15       # Above this → yellow
SPEED_DENSE = 5         # Above this → orange
# Below SPEED_DENSE    → red (blocked)

# Minimum number of observations to consider a cell reliable
MIN_OBSERVATIONS = 2

# Redis key prefix
REDIS_PREFIX = 'traffic'

# TTL for individual speed observations (10 minutes)
OBSERVATION_TTL = 600

# TTL for aggregated traffic data (5 minutes)
AGGREGATED_TTL = 300

# Maximum age of a position fix to compute speed (seconds)
MAX_FIX_AGE = 300  # 5 minutes (needed for very slow traffic: 3km/h = 200m in 4min)

# Minimum distance between fixes to compute speed (meters)
MIN_DISTANCE = 20

# Maximum realistic speed (km/h) - filter out GPS jumps
MAX_REALISTIC_SPEED = 80


# ============================================
# DATA CLASSES
# ============================================

@dataclass
class TrafficLevel:
    """Traffic level for a grid cell."""
    FLUIDE = 'FLUIDE'
    MODERE = 'MODERE'
    DENSE = 'DENSE'
    BLOQUE = 'BLOQUE'
    UNKNOWN = 'UNKNOWN'


@dataclass
class TrafficCell:
    """Traffic data for a single grid cell."""
    cell_id: str
    lat: float
    lng: float
    avg_speed_kmh: float
    level: str
    sample_count: int
    last_updated: str
    
    def to_dict(self):
        return asdict(self)


@dataclass
class CourierFix:
    """A single GPS fix from a courier."""
    courier_id: str
    latitude: float
    longitude: float
    timestamp: float  # Unix timestamp


# ============================================
# MAIN SERVICE
# ============================================

class TrafficService:
    """
    Crowdsourced traffic monitoring service.
    
    Uses courier GPS data to estimate real-time traffic conditions
    across the city grid.
    """
    
    # ---- Grid Helpers ----
    
    @staticmethod
    def latlng_to_cell(lat: float, lng: float) -> str:
        """
        Convert a lat/lng coordinate to a grid cell ID.
        
        Cell ID format: "cell_<row>_<col>"
        """
        if not (DOUALA_BOUNDS['min_lat'] <= lat <= DOUALA_BOUNDS['max_lat'] and
                DOUALA_BOUNDS['min_lng'] <= lng <= DOUALA_BOUNDS['max_lng']):
            return None  # Outside Douala
            
        row = int((lat - DOUALA_BOUNDS['min_lat']) / CELL_SIZE_DEG)
        col = int((lng - DOUALA_BOUNDS['min_lng']) / CELL_SIZE_DEG)
        return f"cell_{row}_{col}"
    
    @staticmethod
    def cell_to_center(cell_id: str) -> Tuple[float, float]:
        """
        Get the center coordinates of a grid cell.
        
        Returns (latitude, longitude).
        """
        parts = cell_id.split('_')
        row = int(parts[1])
        col = int(parts[2])
        lat = DOUALA_BOUNDS['min_lat'] + (row + 0.5) * CELL_SIZE_DEG
        lng = DOUALA_BOUNDS['min_lng'] + (col + 0.5) * CELL_SIZE_DEG
        return (lat, lng)
    
    @staticmethod
    def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two points in meters.
        Uses Haversine formula.
        """
        R = 6371000  # Earth's radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)
        
        a = (math.sin(dphi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    @staticmethod
    def speed_to_level(speed_kmh: float) -> str:
        """Convert average speed to a traffic level."""
        if speed_kmh >= SPEED_FLUIDE:
            return TrafficLevel.FLUIDE
        elif speed_kmh >= SPEED_MODERE:
            return TrafficLevel.MODERE
        elif speed_kmh >= SPEED_DENSE:
            return TrafficLevel.DENSE
        else:
            return TrafficLevel.BLOQUE
    
    @staticmethod
    def level_to_color(level: str) -> str:
        """Convert traffic level to display color."""
        return {
            TrafficLevel.FLUIDE: '#4CAF50',   # Green
            TrafficLevel.MODERE: '#FF9800',   # Orange
            TrafficLevel.DENSE: '#F44336',    # Red
            TrafficLevel.BLOQUE: '#880E4F',   # Dark Red
            TrafficLevel.UNKNOWN: '#9E9E9E',  # Grey
        }.get(level, '#9E9E9E')
    
    # ---- Redis helpers ----
    
    @staticmethod
    def _get_redis():
        """Get Redis connection."""
        try:
            import redis
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            # Parse from CHANNEL_LAYERS config if available
            channel_config = getattr(settings, 'CHANNEL_LAYERS', {})
            if 'default' in channel_config:
                hosts = channel_config['default'].get('CONFIG', {}).get('hosts', [])
                if hosts and isinstance(hosts[0], tuple):
                    host, port = hosts[0]
                    return redis.Redis(host=host, port=port, db=1, decode_responses=True)
            return redis.Redis.from_url(redis_url, db=1, decode_responses=True)
        except Exception as e:
            logger.error(f"[TRAFFIC] Failed to connect to Redis: {e}")
            return None
    
    # ---- Core Ingestion ----
    
    @classmethod
    def ingest_location(cls, courier_id: str, latitude: float, longitude: float) -> Optional[float]:
        """
        Process a courier GPS fix and compute speed.
        
        This is called every time a courier sends a location_update via WebSocket.
        
        1. Retrieve the previous fix for this courier from Redis
        2. Compute speed between previous and current fix
        3. Store the speed observation in the appropriate grid cell
        4. Save the current fix as the new "previous" fix
        
        Returns the computed speed in km/h, or None if no speed could be computed.
        """
        r = cls._get_redis()
        if not r:
            return None
        
        now = time.time()
        current_fix = CourierFix(
            courier_id=courier_id,
            latitude=latitude,
            longitude=longitude,
            timestamp=now
        )
        
        # Get previous fix for this courier
        prev_key = f"{REDIS_PREFIX}:fix:{courier_id}"
        prev_data = r.get(prev_key)
        
        speed_kmh = None
        
        if prev_data:
            try:
                prev = json.loads(prev_data)
                prev_fix = CourierFix(**prev)
                
                # Time delta
                dt = now - prev_fix.timestamp
                
                # Only compute speed if:
                # - Time gap is reasonable (not too old)
                # - Time gap is not too small (avoid division by zero noise)
                if 3 <= dt <= MAX_FIX_AGE:
                    distance_m = cls.haversine_distance(
                        prev_fix.latitude, prev_fix.longitude,
                        latitude, longitude
                    )
                    
                    # Only if distance is meaningful
                    if distance_m >= MIN_DISTANCE:
                        speed_ms = distance_m / dt
                        speed_kmh = speed_ms * 3.6
                        
                        # Filter out GPS jumps (unrealistic speeds)
                        if speed_kmh > MAX_REALISTIC_SPEED:
                            logger.debug(
                                f"[TRAFFIC] Filtered GPS jump: {speed_kmh:.1f} km/h "
                                f"from courier {courier_id[:8]}"
                            )
                            speed_kmh = None
                        else:
                            # Record this speed observation in the grid
                            cell_id = cls.latlng_to_cell(latitude, longitude)
                            if cell_id:
                                cls._record_observation(r, cell_id, speed_kmh, now)
                                
                                logger.debug(
                                    f"[TRAFFIC] Courier {courier_id[:8]} → "
                                    f"{cell_id} @ {speed_kmh:.1f} km/h"
                                )
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.debug(f"[TRAFFIC] Error parsing previous fix: {e}")
        
        # Store current fix
        r.setex(
            prev_key,
            MAX_FIX_AGE * 2,  # TTL = 2x max age
            json.dumps(asdict(current_fix))
        )
        
        return speed_kmh
    
    @classmethod
    def _record_observation(cls, r, cell_id: str, speed_kmh: float, timestamp: float):
        """
        Record a speed observation in a grid cell.
        
        Uses a Redis sorted set: the score is the timestamp, the member
        is the speed. This allows efficient cleanup of old observations.
        """
        obs_key = f"{REDIS_PREFIX}:obs:{cell_id}"
        
        # Add observation: member = "speed:timestamp", score = timestamp
        member = f"{speed_kmh:.1f}:{timestamp:.0f}"
        r.zadd(obs_key, {member: timestamp})
        
        # Remove observations older than OBSERVATION_TTL
        cutoff = timestamp - OBSERVATION_TTL
        r.zremrangebyscore(obs_key, '-inf', cutoff)
        
        # Set TTL on the key
        r.expire(obs_key, OBSERVATION_TTL + 60)
    
    # ---- Aggregation & Query ----
    
    @classmethod
    def get_cell_traffic(cls, cell_id: str) -> Optional[TrafficCell]:
        """
        Get current traffic data for a specific grid cell.
        """
        r = cls._get_redis()
        if not r:
            return None
        
        obs_key = f"{REDIS_PREFIX}:obs:{cell_id}"
        
        # Get all current observations
        now = time.time()
        cutoff = now - OBSERVATION_TTL
        observations = r.zrangebyscore(obs_key, cutoff, '+inf')
        
        if not observations or len(observations) < MIN_OBSERVATIONS:
            return None
        
        # Parse speeds
        speeds = []
        for obs in observations:
            try:
                speed_str = obs.split(':')[0]
                speeds.append(float(speed_str))
            except (ValueError, IndexError):
                continue
        
        if not speeds:
            return None
        
        avg_speed = sum(speeds) / len(speeds)
        lat, lng = cls.cell_to_center(cell_id)
        
        return TrafficCell(
            cell_id=cell_id,
            lat=lat,
            lng=lng,
            avg_speed_kmh=round(avg_speed, 1),
            level=cls.speed_to_level(avg_speed),
            sample_count=len(speeds),
            last_updated=datetime.fromtimestamp(now).isoformat()
        )
    
    @classmethod
    def get_traffic_heatmap(cls, 
                            min_lat: float = None, max_lat: float = None,
                            min_lng: float = None, max_lng: float = None
                            ) -> List[Dict]:
        """
        Get traffic heatmap data for the entire city or a bbox.
        
        Returns a list of TrafficCell dicts for all cells with data.
        This is the main API endpoint response.
        """
        r = cls._get_redis()
        if not r:
            return []
        
        # Check if we have a recent cached aggregation
        cache_key = f"{REDIS_PREFIX}:heatmap"
        cached = r.get(cache_key)
        if cached:
            try:
                cells = json.loads(cached)
                # Apply bbox filter if requested
                if min_lat or max_lat or min_lng or max_lng:
                    cells = [
                        c for c in cells
                        if (not min_lat or c['lat'] >= min_lat) and
                           (not max_lat or c['lat'] <= max_lat) and
                           (not min_lng or c['lng'] >= min_lng) and
                           (not max_lng or c['lng'] <= max_lng)
                    ]
                return cells
            except json.JSONDecodeError:
                pass
        
        # Build fresh heatmap by scanning all observation keys
        cells = cls._aggregate_all_cells(r)
        
        # Cache the result
        if cells:
            r.setex(cache_key, AGGREGATED_TTL, json.dumps(cells))
        
        # Apply bbox filter
        if min_lat or max_lat or min_lng or max_lng:
            cells = [
                c for c in cells
                if (not min_lat or c['lat'] >= min_lat) and
                   (not max_lat or c['lat'] <= max_lat) and
                   (not min_lng or c['lng'] >= min_lng) and
                   (not max_lng or c['lng'] <= max_lng)
            ]
        
        return cells
    
    @classmethod
    def _aggregate_all_cells(cls, r) -> List[Dict]:
        """
        Scan all observation keys and aggregate into cells.
        """
        cells = []
        now = time.time()
        cutoff = now - OBSERVATION_TTL
        
        # Scan for all observation keys
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=f"{REDIS_PREFIX}:obs:cell_*", count=100)
            
            for key in keys:
                cell_id = key.replace(f"{REDIS_PREFIX}:obs:", "")
                
                # Get observations
                observations = r.zrangebyscore(key, cutoff, '+inf')
                
                if not observations or len(observations) < MIN_OBSERVATIONS:
                    continue
                
                speeds = []
                for obs in observations:
                    try:
                        speed_str = obs.split(':')[0]
                        speeds.append(float(speed_str))
                    except (ValueError, IndexError):
                        continue
                
                if not speeds:
                    continue
                
                avg_speed = sum(speeds) / len(speeds)
                lat, lng = cls.cell_to_center(cell_id)
                
                cells.append({
                    'cell_id': cell_id,
                    'lat': round(lat, 6),
                    'lng': round(lng, 6),
                    'avg_speed': round(avg_speed, 1),
                    'level': cls.speed_to_level(avg_speed),
                    'color': cls.level_to_color(cls.speed_to_level(avg_speed)),
                    'samples': len(speeds),
                    'updated': datetime.fromtimestamp(now).isoformat(),
                })
            
            if cursor == 0:
                break
        
        logger.info(f"[TRAFFIC] Aggregated {len(cells)} active cells")
        return cells
    
    # ---- Statistics ----
    
    @classmethod
    def get_traffic_stats(cls) -> Dict:
        """
        Get overall traffic statistics for the city.
        """
        r = cls._get_redis()
        if not r:
            return {'active_cells': 0, 'online_couriers': 0}
        
        cells = cls.get_traffic_heatmap()
        
        # Count cells by level
        level_counts = {}
        total_speed = 0
        for cell in cells:
            level = cell.get('level', TrafficLevel.UNKNOWN)
            level_counts[level] = level_counts.get(level, 0) + 1
            total_speed += cell.get('avg_speed', 0)
        
        # Count active courier fixes
        courier_keys = list(r.scan_iter(match=f"{REDIS_PREFIX}:fix:*", count=100))
        
        avg_city_speed = total_speed / len(cells) if cells else 0
        
        return {
            'active_cells': len(cells),
            'online_couriers': len(courier_keys),
            'avg_city_speed_kmh': round(avg_city_speed, 1),
            'overall_level': cls.speed_to_level(avg_city_speed) if cells else TrafficLevel.UNKNOWN,
            'cells_by_level': level_counts,
            'timestamp': timezone.now().isoformat(),
        }
    
    # ---- Routing Integration ----
    
    @classmethod
    def get_route_traffic(cls, waypoints: List[Tuple[float, float]]) -> List[Dict]:
        """
        Get traffic data along a route (list of waypoints).
        
        For each waypoint, returns the traffic level of the corresponding cell.
        Useful for coloring a route polyline.
        """
        results = []
        seen_cells = set()
        
        for lat, lng in waypoints:
            cell_id = cls.latlng_to_cell(lat, lng)
            if not cell_id or cell_id in seen_cells:
                continue
            seen_cells.add(cell_id)
            
            cell = cls.get_cell_traffic(cell_id)
            if cell:
                results.append(cell.to_dict())
            else:
                center_lat, center_lng = cls.cell_to_center(cell_id)
                results.append({
                    'cell_id': cell_id,
                    'lat': center_lat,
                    'lng': center_lng,
                    'avg_speed_kmh': 0,
                    'level': TrafficLevel.UNKNOWN,
                    'sample_count': 0,
                    'last_updated': None,
                })
        
        return results
    
    # ---- Cleanup ----
    
    @classmethod
    def cleanup_stale_data(cls):
        """
        Remove stale traffic data.
        Called periodically by Celery beat.
        """
        r = cls._get_redis()
        if not r:
            return
        
        now = time.time()
        cutoff = now - OBSERVATION_TTL
        cleaned = 0
        
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=f"{REDIS_PREFIX}:obs:*", count=100)
            
            for key in keys:
                # Remove old observations
                removed = r.zremrangebyscore(key, '-inf', cutoff)
                cleaned += removed
                
                # Remove empty keys
                if r.zcard(key) == 0:
                    r.delete(key)
            
            if cursor == 0:
                break
        
        # Clear the heatmap cache to force refresh
        r.delete(f"{REDIS_PREFIX}:heatmap")
        
        logger.info(f"[TRAFFIC] Cleanup: removed {cleaned} stale observations")
        return cleaned
