"""
Pricing Engine for DELIVR-CM

Calculates delivery prices based on distance (OSRM routing).
"""

import math
import logging
import requests
from decimal import Decimal, ROUND_UP
from typing import Tuple, Optional
from django.conf import settings
from django.contrib.gis.geos import Point

logger = logging.getLogger(__name__)


class PricingEngine:
    """
    Price calculation engine based on OSRM routing distance.
    
    Formula: Price = Max(MinimumFare, RoundUp100(BaseFare + Distance * CostPerKm))
    Split: Platform 20% / Courier 80%
    """

    def __init__(self):
        self.base_fare = Decimal(str(settings.PRICING_BASE_FARE))
        self.cost_per_km = Decimal(str(settings.PRICING_COST_PER_KM))
        self.minimum_fare = Decimal(str(settings.PRICING_MINIMUM_FARE))
        self.platform_fee_percent = Decimal(str(settings.PLATFORM_FEE_PERCENT)) / 100
        self.osrm_base_url = settings.OSRM_BASE_URL

    def get_route_distance(self, origin: Point, destination: Point) -> Optional[float]:
        """
        Get driving distance in kilometers from OSRM.
        
        Args:
            origin: PostGIS Point (pickup location)
            destination: PostGIS Point (dropoff location)
            
        Returns:
            Distance in km or None if OSRM fails
        """
        try:
            # OSRM expects lng,lat format
            url = (
                f"{self.osrm_base_url}/route/v1/driving/"
                f"{origin.x},{origin.y};{destination.x},{destination.y}"
                f"?overview=false"
            )
            
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            if data.get('code') == 'Ok' and data.get('routes'):
                # OSRM returns distance in meters
                distance_meters = data['routes'][0]['distance']
                return distance_meters / 1000  # Convert to km
            
            logger.warning(f"OSRM returned unexpected response: {data}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"OSRM request failed: {e}")
            return None

    def get_haversine_distance(self, origin: Point, destination: Point) -> float:
        """
        Calculate straight-line (haversine) distance in kilometers.
        Fallback when OSRM is unavailable.
        
        Args:
            origin: PostGIS Point
            destination: PostGIS Point
            
        Returns:
            Distance in km
        """
        R = 6371  # Earth radius in km
        
        lat1, lon1 = math.radians(origin.y), math.radians(origin.x)
        lat2, lon2 = math.radians(destination.y), math.radians(destination.x)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c

    def round_to_hundred(self, amount: Decimal) -> Decimal:
        """
        Round up to the nearest 100 XAF.
        
        Example: 1320 -> 1400, 1500 -> 1500, 1501 -> 1600
        """
        return (amount / 100).quantize(Decimal('1'), rounding=ROUND_UP) * 100

    def calculate_price(
        self, 
        origin: Point, 
        destination: Point,
        use_fallback: bool = True,
        safety_margin: float = 0.0
    ) -> Tuple[float, Decimal, Decimal, Decimal]:
        """
        Calculate delivery price.
        
        Args:
            origin: Pickup location (PostGIS Point)
            destination: Dropoff location (PostGIS Point)
            use_fallback: Use Haversine if OSRM fails
            safety_margin: Additional margin (0.2 = 20% for neighborhood estimation)
            
        Returns:
            Tuple of (distance_km, total_price, platform_fee, courier_earning)
            
        Raises:
            ValueError: If distance cannot be calculated
        """
        # Try OSRM first
        distance_km = self.get_route_distance(origin, destination)
        
        if distance_km is None:
            if use_fallback:
                # Fallback: Haversine + 30% margin
                distance_km = self.get_haversine_distance(origin, destination) * 1.3
                logger.info(f"Using Haversine fallback: {distance_km:.2f} km")
            else:
                raise ValueError("Could not calculate route distance")
        
        # Apply safety margin (for neighborhood estimation)
        if safety_margin > 0:
            distance_km *= (1 + safety_margin)
        
        # Calculate raw price
        raw_price = self.base_fare + (Decimal(str(distance_km)) * self.cost_per_km)
        
        # Round to nearest 100
        rounded_price = self.round_to_hundred(raw_price)
        
        # Apply minimum fare
        total_price = max(self.minimum_fare, rounded_price)
        
        # Calculate split
        platform_fee = (total_price * self.platform_fee_percent).quantize(Decimal('0.01'))
        courier_earning = total_price - platform_fee
        
        return (
            round(distance_km, 2),
            total_price,
            platform_fee,
            courier_earning
        )

    def estimate_from_neighborhood(
        self, 
        shop_location: Point, 
        neighborhood_center: Point
    ) -> Tuple[float, Decimal, Decimal, Decimal]:
        """
        Estimate price for e-commerce order (exact GPS unknown).
        Uses neighborhood center + 20% safety margin.
        
        Args:
            shop_location: Shop pickup location
            neighborhood_center: Center of delivery neighborhood
            
        Returns:
            Tuple of (distance_km, total_price, platform_fee, courier_earning)
        """
        return self.calculate_price(
            origin=shop_location,
            destination=neighborhood_center,
            safety_margin=0.2  # 20% margin for neighborhood uncertainty
        )


# Singleton instance
pricing_engine = PricingEngine()
