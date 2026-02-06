"""
Pricing Simulator for DELIVR-CM

Allows testing and validating pricing configuration before deployment.
"""

import io
import csv
from decimal import Decimal, ROUND_UP
from typing import Optional
from django.conf import settings


class PricingSimulator:
    """
    Interactive pricing simulator for configuration validation.
    
    Features:
    - Simulate prices for various distances
    - Compare different pricing configurations
    - Generate CSV reports
    """
    
    def __init__(
        self,
        base_fare: Optional[float] = None,
        cost_per_km: Optional[float] = None,
        minimum_fare: Optional[float] = None,
        platform_fee_percent: Optional[float] = None
    ):
        """
        Initialize simulator with optional custom config.
        Falls back to settings if not provided.
        """
        self.base_fare = Decimal(str(base_fare or settings.PRICING_BASE_FARE))
        self.cost_per_km = Decimal(str(cost_per_km or settings.PRICING_COST_PER_KM))
        self.minimum_fare = Decimal(str(minimum_fare or settings.PRICING_MINIMUM_FARE))
        self.platform_fee_percent = Decimal(str(
            platform_fee_percent or settings.PLATFORM_FEE_PERCENT
        )) / 100
    
    def round_to_hundred(self, amount: Decimal) -> Decimal:
        """Round up to nearest 100 XAF."""
        return (amount / 100).quantize(Decimal('1'), rounding=ROUND_UP) * 100
    
    def calculate_for_distance(self, distance_km: float) -> dict:
        """
        Calculate pricing for a given distance.
        
        Returns:
            Dict with distance, raw_price, total_price, platform_fee, courier_earning
        """
        raw_price = self.base_fare + (Decimal(str(distance_km)) * self.cost_per_km)
        rounded_price = self.round_to_hundred(raw_price)
        total_price = max(self.minimum_fare, rounded_price)
        
        platform_fee = (total_price * self.platform_fee_percent).quantize(Decimal('1'))
        courier_earning = total_price - platform_fee
        
        return {
            'distance_km': distance_km,
            'raw_price': float(raw_price),
            'total_price': float(total_price),
            'platform_fee': float(platform_fee),
            'courier_earning': float(courier_earning),
            'profit_margin': float(self.platform_fee_percent * 100),
        }
    
    def simulate_scenarios(self, distances: list[float] = None) -> list[dict]:
        """
        Simulate pricing for multiple distances.
        
        Args:
            distances: List of distances in km (default: 1-20 km)
            
        Returns:
            List of pricing calculations
        """
        if distances is None:
            distances = [0.5, 1, 1.5, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20]
        
        return [self.calculate_for_distance(d) for d in distances]
    
    def compare_configs(
        self,
        config_a: dict,
        config_b: dict,
        test_distances: list[float] = None
    ) -> dict:
        """
        Compare two pricing configurations.
        
        Args:
            config_a: First config (base_fare, cost_per_km, minimum_fare)
            config_b: Second config
            test_distances: Distances to compare
            
        Returns:
            Comparison dict with differences
        """
        if test_distances is None:
            test_distances = [1, 2, 3, 5, 10]
        
        sim_a = PricingSimulator(**config_a)
        sim_b = PricingSimulator(**config_b)
        
        comparisons = []
        for distance in test_distances:
            result_a = sim_a.calculate_for_distance(distance)
            result_b = sim_b.calculate_for_distance(distance)
            
            comparisons.append({
                'distance_km': distance,
                'config_a_price': result_a['total_price'],
                'config_b_price': result_b['total_price'],
                'difference': result_b['total_price'] - result_a['total_price'],
                'percent_change': round(
                    (result_b['total_price'] - result_a['total_price']) / result_a['total_price'] * 100,
                    1
                )
            })
        
        return {
            'config_a': config_a,
            'config_b': config_b,
            'comparisons': comparisons,
            'summary': {
                'avg_difference': sum(c['difference'] for c in comparisons) / len(comparisons),
                'max_difference': max(c['difference'] for c in comparisons),
                'min_difference': min(c['difference'] for c in comparisons),
            }
        }
    
    def generate_csv_report(self) -> bytes:
        """
        Generate a CSV report of pricing scenarios.
        
        Returns:
            CSV content as bytes
        """
        scenarios = self.simulate_scenarios()
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'distance_km',
            'raw_price',
            'total_price',
            'platform_fee',
            'courier_earning'
        ])
        
        writer.writeheader()
        for scenario in scenarios:
            writer.writerow({
                'distance_km': scenario['distance_km'],
                'raw_price': int(scenario['raw_price']),
                'total_price': int(scenario['total_price']),
                'platform_fee': int(scenario['platform_fee']),
                'courier_earning': int(scenario['courier_earning']),
            })
        
        return output.getvalue().encode('utf-8')
    
    def get_breakpoints(self) -> list[dict]:
        """
        Find interesting pricing breakpoints.
        
        Returns:
            List of breakpoints where pricing jumps
        """
        breakpoints = []
        prev_price = None
        
        # Check every 0.5 km from 0 to 25 km
        for i in range(51):
            distance = i * 0.5
            result = self.calculate_for_distance(distance)
            
            if prev_price is not None and result['total_price'] != prev_price:
                breakpoints.append({
                    'at_km': distance,
                    'from_price': prev_price,
                    'to_price': result['total_price'],
                    'jump': result['total_price'] - prev_price
                })
            
            prev_price = result['total_price']
        
        return breakpoints
    
    @classmethod
    def get_current_config(cls) -> dict:
        """Get current pricing configuration from settings."""
        return {
            'base_fare': float(settings.PRICING_BASE_FARE),
            'cost_per_km': float(settings.PRICING_COST_PER_KM),
            'minimum_fare': float(settings.PRICING_MINIMUM_FARE),
            'platform_fee_percent': float(settings.PLATFORM_FEE_PERCENT),
        }
