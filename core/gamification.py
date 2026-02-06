"""
CORE App - Gamification Service for DELIVR-CM

Handles:
- Courier level progression (Bronze → Platinum)
- Badge awarding based on achievements
- Performance statistics updates
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Avg, Count, F
from django.utils import timezone

from .models import User
from .courier_profile import (
    CourierBadge, BadgeType, 
    CourierPerformanceLog
)

logger = logging.getLogger(__name__)


# ============================================
# LEVEL THRESHOLDS CONFIGURATION
# ============================================

LEVEL_THRESHOLDS = {
    'BRONZE': {
        'min_deliveries': 0,
        'min_rating': 0.0,
        'label': 'Bronze',
        'color': '#CD7F32',
        'icon': '🥉',
        'perks': ['Accès standard aux commandes']
    },
    'SILVER': {
        'min_deliveries': 50,
        'min_rating': 4.5,
        'label': 'Silver',
        'color': '#C0C0C0',
        'icon': '🥈',
        'perks': ['Priorité +1 dans le dispatch', 'Badge Silver visible']
    },
    'GOLD': {
        'min_deliveries': 200,
        'min_rating': 4.7,
        'label': 'Gold',
        'color': '#FFD700',
        'icon': '🥇',
        'perks': ['Priorité +2 dans le dispatch', 'Plafond dette augmenté', 'Badge Gold visible']
    },
    'PLATINUM': {
        'min_deliveries': 500,
        'min_rating': 4.9,
        'label': 'Platine',
        'color': '#E5E4E2',
        'icon': '💎',
        'perks': ['Priorité maximale', 'Pas de plafond dette', 'Accès VIP', 'Badge Platine visible']
    },
}


# ============================================
# BADGE CRITERIA
# ============================================

BADGE_CRITERIA = {
    BadgeType.FIRST_DELIVERY: {
        'check': lambda stats: stats['total_deliveries'] >= 1,
        'description': 'Compléter votre première livraison'
    },
    BadgeType.STREAK_10: {
        'check': lambda stats: stats['best_streak'] >= 10,
        'description': '10 livraisons consécutives sans annulation'
    },
    BadgeType.STREAK_50: {
        'check': lambda stats: stats['best_streak'] >= 50,
        'description': '50 livraisons consécutives sans annulation'
    },
    BadgeType.STREAK_100: {
        'check': lambda stats: stats['best_streak'] >= 100,
        'description': '100 livraisons consécutives sans annulation'
    },
    BadgeType.DISTANCE_100: {
        'check': lambda stats: stats['total_distance'] >= 100,
        'description': 'Parcourir 100 km au total'
    },
    BadgeType.DISTANCE_500: {
        'check': lambda stats: stats['total_distance'] >= 500,
        'description': 'Parcourir 500 km au total'
    },
    BadgeType.DISTANCE_1000: {
        'check': lambda stats: stats['total_distance'] >= 1000,
        'description': 'Parcourir 1000 km au total'
    },
    BadgeType.SPEED_DEMON: {
        'check': lambda stats: stats['avg_response_time'] > 0 and stats['avg_response_time'] < 120,
        'description': 'Temps de réponse moyen inférieur à 2 minutes'
    },
    BadgeType.TOP_RATED: {
        'check': lambda stats: stats['average_rating'] == 5.0 and stats['total_ratings'] >= 10,
        'description': 'Maintenir une note parfaite de 5 étoiles (min 10 avis)'
    },
    BadgeType.VETERAN: {
        'check': lambda stats: stats['total_deliveries'] >= 500,
        'description': 'Compléter 500 livraisons'
    },
    BadgeType.LEGEND: {
        'check': lambda stats: stats['total_deliveries'] >= 1000,
        'description': 'Compléter 1000 livraisons'
    },
}


class GamificationService:
    """
    Service for managing courier gamification.
    
    Handles level progression and badge awarding based on
    courier performance metrics.
    """
    
    @staticmethod
    def get_courier_stats(courier: User) -> Dict[str, Any]:
        """
        Get comprehensive stats for a courier.
        
        Returns dict with all metrics needed for level/badge evaluation.
        """
        return {
            'total_deliveries': courier.total_deliveries_completed,
            'total_distance': courier.total_distance_km,
            'average_rating': courier.average_rating,
            'total_ratings': courier.total_ratings_count,
            'acceptance_rate': courier.acceptance_rate,
            'cancellation_count': courier.cancellation_count,
            'current_streak': courier.consecutive_success_streak,
            'best_streak': courier.best_streak,
            'avg_response_time': courier.average_response_seconds,
            'wallet_balance': float(courier.wallet_balance),
            'current_level': courier.courier_level,
        }
    
    @staticmethod
    def calculate_level(stats: Dict[str, Any]) -> str:
        """
        Calculate the appropriate level based on courier stats.
        
        Level progression is based on:
        - Number of completed deliveries
        - Average rating
        
        Returns the level code (BRONZE, SILVER, GOLD, PLATINUM).
        """
        current_level = 'BRONZE'
        
        for level_code in ['PLATINUM', 'GOLD', 'SILVER']:
            threshold = LEVEL_THRESHOLDS[level_code]
            if (stats['total_deliveries'] >= threshold['min_deliveries'] and
                stats['average_rating'] >= threshold['min_rating']):
                current_level = level_code
                break
        
        return current_level
    
    @classmethod
    def update_courier_level(cls, courier: User) -> Optional[str]:
        """
        Check and update courier level if eligible.
        
        Returns:
            New level if promoted, None if no change.
        """
        stats = cls.get_courier_stats(courier)
        calculated_level = cls.calculate_level(stats)
        
        # Level hierarchy for comparison
        level_order = ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM']
        current_index = level_order.index(courier.courier_level)
        calculated_index = level_order.index(calculated_level)
        
        # Only allow promotion (not demotion)
        if calculated_index > current_index:
            old_level = courier.courier_level
            courier.courier_level = calculated_level
            
            # Apply level-specific perks
            if calculated_level == 'GOLD':
                # Increase debt ceiling for Gold
                courier.debt_ceiling = Decimal('5000.00')
            elif calculated_level == 'PLATINUM':
                # No debt ceiling for Platinum
                courier.debt_ceiling = Decimal('50000.00')
            
            courier.save(update_fields=['courier_level', 'debt_ceiling'])
            
            logger.info(
                f"[GAMIFICATION] Courier {courier.phone_number} promoted: "
                f"{old_level} → {calculated_level}"
            )
            
            return calculated_level
        
        return None
    
    @classmethod
    def check_and_award_badges(cls, courier: User, delivery=None) -> List[str]:
        """
        Check all badge criteria and award new badges.
        
        Args:
            courier: The courier to check
            delivery: Optional delivery that triggered this check
            
        Returns:
            List of newly awarded badge types.
        """
        stats = cls.get_courier_stats(courier)
        awarded = []
        
        # Get existing badges
        existing_badges = set(
            CourierBadge.objects.filter(courier=courier)
            .values_list('badge_type', flat=True)
        )
        
        for badge_type, criteria in BADGE_CRITERIA.items():
            # Skip if already has this badge
            if badge_type in existing_badges:
                continue
            
            # Check if criteria is met
            try:
                if criteria['check'](stats):
                    CourierBadge.objects.create(
                        courier=courier,
                        badge_type=badge_type,
                        triggered_by_delivery=delivery
                    )
                    awarded.append(badge_type)
                    logger.info(
                        f"[GAMIFICATION] Badge awarded to {courier.phone_number}: "
                        f"{badge_type}"
                    )
            except Exception as e:
                logger.warning(f"Error checking badge {badge_type}: {e}")
        
        return awarded
    
    @classmethod
    @transaction.atomic
    def process_delivery_completion(cls, courier: User, delivery) -> Dict[str, Any]:
        """
        Process gamification updates after a delivery is completed.
        
        Updates:
        - Performance counters
        - Streak tracking
        - Level progression
        - Badge awards
        
        Returns dict with any achievements earned.
        """
        result = {
            'level_up': None,
            'new_badges': [],
            'streak': courier.consecutive_success_streak
        }
        
        # Update performance counters
        courier.total_deliveries_completed = F('total_deliveries_completed') + 1
        courier.total_distance_km = F('total_distance_km') + delivery.distance_km
        courier.consecutive_success_streak = F('consecutive_success_streak') + 1
        courier.save(update_fields=[
            'total_deliveries_completed', 
            'total_distance_km',
            'consecutive_success_streak'
        ])
        
        # Refresh from DB to get updated values
        courier.refresh_from_db()
        
        # Update best streak if current is higher
        if courier.consecutive_success_streak > courier.best_streak:
            courier.best_streak = courier.consecutive_success_streak
            courier.save(update_fields=['best_streak'])
        
        result['streak'] = courier.consecutive_success_streak
        
        # Check for level up
        new_level = cls.update_courier_level(courier)
        if new_level:
            result['level_up'] = new_level
        
        # Check for new badges
        new_badges = cls.check_and_award_badges(courier, delivery)
        result['new_badges'] = new_badges
        
        return result
    
    @classmethod
    def process_delivery_cancellation(cls, courier: User, delivery) -> None:
        """
        Process gamification updates after a delivery is cancelled.
        
        Resets the consecutive success streak.
        """
        courier.cancellation_count = F('cancellation_count') + 1
        courier.consecutive_success_streak = 0  # Reset streak
        courier.save(update_fields=['cancellation_count', 'consecutive_success_streak'])
        
        # Update acceptance rate
        courier.refresh_from_db()
        total = courier.total_deliveries_completed + courier.cancellation_count
        if total > 0:
            rate = (courier.total_deliveries_completed / total) * 100
            courier.acceptance_rate = round(rate, 1)
            courier.save(update_fields=['acceptance_rate'])
    
    @classmethod
    def add_rating(cls, courier: User, rating: float) -> None:
        """
        Add a new rating for a courier and recalculate average.
        
        Args:
            courier: The courier being rated
            rating: Rating value (1-5)
        """
        if not (1 <= rating <= 5):
            raise ValueError("Rating must be between 1 and 5")
        
        # Recalculate average (weighted)
        total_sum = courier.average_rating * courier.total_ratings_count
        new_total_count = courier.total_ratings_count + 1
        new_average = (total_sum + rating) / new_total_count
        
        courier.average_rating = round(new_average, 2)
        courier.total_ratings_count = new_total_count
        courier.save(update_fields=['average_rating', 'total_ratings_count'])
        
        # Check for level up after rating update
        cls.update_courier_level(courier)
        
        # Check for TOP_RATED badge
        cls.check_and_award_badges(courier)
    
    @staticmethod
    def get_level_info(level_code: str) -> Dict[str, Any]:
        """Get level details including perks."""
        return LEVEL_THRESHOLDS.get(level_code, LEVEL_THRESHOLDS['BRONZE'])
    
    @staticmethod
    def get_next_level_progress(courier: User) -> Dict[str, Any]:
        """
        Calculate progress towards next level.
        
        Returns dict with:
        - next_level: Next level code or None
        - deliveries_needed: Number of deliveries to reach next level
        - rating_needed: Minimum rating required
        - progress_percent: Overall progress (0-100)
        """
        level_order = ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM']
        current_index = level_order.index(courier.courier_level)
        
        if current_index >= len(level_order) - 1:
            # Already at max level
            return {
                'next_level': None,
                'deliveries_needed': 0,
                'rating_needed': 0,
                'progress_percent': 100
            }
        
        next_level = level_order[current_index + 1]
        threshold = LEVEL_THRESHOLDS[next_level]
        
        deliveries_needed = max(0, threshold['min_deliveries'] - courier.total_deliveries_completed)
        rating_needed = threshold['min_rating']
        
        # Calculate progress (weighted: 70% deliveries, 30% rating)
        delivery_progress = min(100, (courier.total_deliveries_completed / threshold['min_deliveries']) * 100) if threshold['min_deliveries'] > 0 else 100
        rating_progress = min(100, (courier.average_rating / threshold['min_rating']) * 100) if threshold['min_rating'] > 0 else 100
        
        progress = (delivery_progress * 0.7) + (rating_progress * 0.3)
        
        return {
            'next_level': next_level,
            'next_level_info': LEVEL_THRESHOLDS[next_level],
            'deliveries_needed': deliveries_needed,
            'deliveries_required': threshold['min_deliveries'],
            'rating_needed': rating_needed,
            'current_rating': courier.average_rating,
            'progress_percent': round(progress, 1)
        }


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_courier_leaderboard(limit: int = 10, city: str = None) -> List[Dict]:
    """
    Get top couriers by total deliveries.
    
    Args:
        limit: Number of couriers to return
        city: Optional city filter
        
    Returns:
        List of courier dicts with rank and stats.
    """
    from .models import UserRole
    
    queryset = User.objects.filter(
        role=UserRole.COURIER,
        is_verified=True,
        is_active=True
    ).order_by('-total_deliveries_completed', '-average_rating')
    
    if limit:
        queryset = queryset[:limit]
    
    leaderboard = []
    for rank, courier in enumerate(queryset, 1):
        leaderboard.append({
            'rank': rank,
            'courier_id': str(courier.id),
            'name': courier.full_name or f"Coursier {courier.phone_number[-4:]}",
            'level': courier.courier_level,
            'level_icon': LEVEL_THRESHOLDS[courier.courier_level]['icon'],
            'total_deliveries': courier.total_deliveries_completed,
            'average_rating': courier.average_rating,
            'current_streak': courier.consecutive_success_streak,
        })
    
    return leaderboard


def get_courier_badges_summary(courier: User) -> Dict[str, Any]:
    """Get summary of courier's badges."""
    badges = CourierBadge.objects.filter(courier=courier).order_by('-earned_at')
    
    return {
        'total_badges': badges.count(),
        'badges': [
            {
                'type': b.badge_type,
                'display': b.get_badge_type_display(),
                'icon': b.icon,
                'earned_at': b.earned_at.isoformat()
            }
            for b in badges
        ],
        'available_badges': len(BadgeType.choices),
        'completion_percent': round((badges.count() / len(BadgeType.choices)) * 100, 1)
    }
