"""
COURIER App - Services for Dashboard Data

Aggregation services for courier statistics and performance data.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.db.models import Sum, Avg, Count, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from core.models import User, UserRole
from core.courier_profile import CourierPerformanceLog, CourierBadge, CourierAvailability
from core.gamification import (
    GamificationService, get_courier_leaderboard, 
    get_courier_badges_summary, LEVEL_THRESHOLDS
)
from logistics.models import Delivery, DeliveryStatus
from finance.models import Transaction, TransactionType


class CourierStatsService:
    """
    Service for aggregating courier statistics.
    
    Provides data for the courier dashboard including:
    - Daily/weekly/monthly stats
    - Earnings breakdown
    - Performance metrics
    """
    
    @staticmethod
    def get_today_stats(courier: User) -> Dict[str, Any]:
        """
        Get courier's stats for today.
        
        Returns:
            Dict with today's deliveries, earnings, distance, etc.
        """
        today = timezone.now().date()
        
        # Today's deliveries
        today_deliveries = Delivery.objects.filter(
            courier=courier,
            completed_at__date=today,
            status=DeliveryStatus.COMPLETED
        )
        
        deliveries_count = today_deliveries.count()
        
        # Aggregate stats
        agg = today_deliveries.aggregate(
            total_earnings=Sum('courier_earning'),
            total_distance=Sum('distance_km')
        )
        
        return {
            'date': today.isoformat(),
            'deliveries_count': deliveries_count,
            'earnings': float(agg['total_earnings'] or 0),
            'distance_km': round(agg['total_distance'] or 0, 1),
            'is_online': courier.is_online,
            'current_streak': courier.consecutive_success_streak,
        }
    
    @staticmethod
    def get_week_stats(courier: User) -> Dict[str, Any]:
        """
        Get courier's stats for the current week (Mon-Sun).
        
        Returns:
            Dict with weekly aggregates and daily breakdown.
        """
        today = timezone.now().date()
        # Start of week (Monday)
        start_of_week = today - timedelta(days=today.weekday())
        
        # Week's deliveries
        week_deliveries = Delivery.objects.filter(
            courier=courier,
            completed_at__date__gte=start_of_week,
            status=DeliveryStatus.COMPLETED
        )
        
        # Daily breakdown
        daily_breakdown = week_deliveries.annotate(
            day=TruncDate('completed_at')
        ).values('day').annotate(
            count=Count('id'),
            earnings=Sum('courier_earning'),
            distance=Sum('distance_km')
        ).order_by('day')
        
        # Aggregate totals
        agg = week_deliveries.aggregate(
            total_deliveries=Count('id'),
            total_earnings=Sum('courier_earning'),
            total_distance=Sum('distance_km')
        )
        
        # Build daily data for chart (fill in missing days)
        daily_data = []
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            day_info = next(
                (d for d in daily_breakdown if d['day'] == day), 
                None
            )
            daily_data.append({
                'date': day.isoformat(),
                'day_name': day.strftime('%a'),
                'count': day_info['count'] if day_info else 0,
                'earnings': float(day_info['earnings']) if day_info and day_info['earnings'] else 0,
                'distance': float(day_info['distance']) if day_info and day_info['distance'] else 0,
            })
        
        return {
            'start_date': start_of_week.isoformat(),
            'end_date': (start_of_week + timedelta(days=6)).isoformat(),
            'total_deliveries': agg['total_deliveries'] or 0,
            'total_earnings': float(agg['total_earnings'] or 0),
            'total_distance': round(agg['total_distance'] or 0, 1),
            'daily_breakdown': daily_data,
        }
    
    @staticmethod
    def get_month_stats(courier: User) -> Dict[str, Any]:
        """Get courier's stats for the current month."""
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        
        month_deliveries = Delivery.objects.filter(
            courier=courier,
            completed_at__date__gte=start_of_month,
            status=DeliveryStatus.COMPLETED
        )
        
        agg = month_deliveries.aggregate(
            total_deliveries=Count('id'),
            total_earnings=Sum('courier_earning'),
            total_distance=Sum('distance_km')
        )
        
        return {
            'month': today.strftime('%B %Y'),
            'total_deliveries': agg['total_deliveries'] or 0,
            'total_earnings': float(agg['total_earnings'] or 0),
            'total_distance': round(agg['total_distance'] or 0, 1),
        }
    
    @staticmethod
    def get_earnings_history(courier: User, days: int = 30) -> List[Dict]:
        """
        Get daily earnings history for the past N days.
        
        Used for earnings chart in dashboard.
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # Get daily earnings from transactions
        daily_earnings = Transaction.objects.filter(
            user=courier,
            transaction_type=TransactionType.DELIVERY_CREDIT,
            created_at__date__gte=start_date
        ).annotate(
            day=TruncDate('created_at')
        ).values('day').annotate(
            earnings=Sum('amount')
        ).order_by('day')
        
        # Build complete date range
        earnings_map = {e['day']: float(e['earnings']) for e in daily_earnings}
        
        history = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            history.append({
                'date': day.isoformat(),
                'earnings': earnings_map.get(day, 0)
            })
        
        return history
    
    @staticmethod
    def get_recent_deliveries(courier: User, limit: int = 20) -> List[Dict]:
        """Get recent delivery history."""
        deliveries = Delivery.objects.filter(
            courier=courier
        ).select_related(
            'sender', 'dropoff_neighborhood'
        ).order_by('-created_at')[:limit]
        
        return [
            {
                'id': str(d.id),
                'status': d.status,
                'status_display': d.get_status_display(),
                'pickup_address': d.pickup_address or 'GPS',
                'dropoff_address': d.dropoff_address or (
                    d.dropoff_neighborhood.name if d.dropoff_neighborhood else 'GPS'
                ),
                'distance_km': d.distance_km,
                'earning': float(d.courier_earning),
                'created_at': d.created_at.isoformat(),
                'completed_at': d.completed_at.isoformat() if d.completed_at else None,
            }
            for d in deliveries
        ]
    
    @staticmethod
    def get_wallet_summary(courier: User) -> Dict[str, Any]:
        """Get wallet balance and debt info."""
        # Calculate totals from transactions
        transactions_agg = Transaction.objects.filter(
            user=courier
        ).aggregate(
            total_earned=Sum('amount', filter=Q(transaction_type=TransactionType.DELIVERY_CREDIT)),
            total_commission=Sum('amount', filter=Q(transaction_type=TransactionType.COMMISSION)),
            total_withdrawn=Sum('amount', filter=Q(transaction_type=TransactionType.WITHDRAWAL)),
        )
        
        debt_used = abs(min(0, float(courier.wallet_balance)))
        debt_available = float(courier.debt_ceiling) - debt_used
        debt_percentage = (debt_used / float(courier.debt_ceiling)) * 100 if courier.debt_ceiling > 0 else 0
        
        return {
            'balance': float(courier.wallet_balance),
            'debt_ceiling': float(courier.debt_ceiling),
            'debt_used': debt_used,
            'debt_available': max(0, debt_available),
            'debt_percentage': round(debt_percentage, 1),
            'is_blocked': courier.is_courier_blocked,
            'total_earned': float(transactions_agg['total_earned'] or 0),
            'total_commission': abs(float(transactions_agg['total_commission'] or 0)),
            'available_for_withdrawal': max(0, float(courier.wallet_balance)),
        }
    
    @staticmethod
    def get_performance_summary(courier: User) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        stats = GamificationService.get_courier_stats(courier)
        next_level = GamificationService.get_next_level_progress(courier)
        badges = get_courier_badges_summary(courier)
        
        return {
            'level': courier.courier_level,
            'level_info': LEVEL_THRESHOLDS[courier.courier_level],
            'next_level': next_level,
            'total_deliveries': stats['total_deliveries'],
            'total_distance_km': round(stats['total_distance'], 1),
            'average_rating': stats['average_rating'],
            'total_ratings': stats['total_ratings'],
            'acceptance_rate': stats['acceptance_rate'],
            'current_streak': stats['current_streak'],
            'best_streak': stats['best_streak'],
            'cancellation_count': stats['cancellation_count'],
            'badges': badges,
        }
    
    @staticmethod
    def get_courier_rank(courier: User) -> Dict[str, Any]:
        """Get courier's rank among all active couriers."""
        # Get all verified couriers ordered by performance
        all_couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=True,
            is_active=True
        ).order_by('-total_deliveries_completed')
        
        total_couriers = all_couriers.count()
        
        # Find courier's position
        rank = 1
        for c in all_couriers:
            if c.id == courier.id:
                break
            rank += 1
        
        # Calculate percentile
        percentile = round(((total_couriers - rank + 1) / total_couriers) * 100, 1) if total_couriers > 0 else 0
        
        return {
            'rank': rank,
            'total_couriers': total_couriers,
            'percentile': percentile,
            'top_percent': 100 - percentile,
        }


class AvailabilityService:
    """Service for managing courier availability."""
    
    @staticmethod
    def get_availability_schedule(courier: User) -> List[Dict]:
        """Get courier's weekly availability schedule."""
        slots = CourierAvailability.objects.filter(
            courier=courier,
            is_active=True
        ).order_by('day_of_week', 'start_time')
        
        return [
            {
                'id': str(s.id),
                'day_of_week': s.day_of_week,
                'day_name': s.get_day_of_week_display(),
                'start_time': s.start_time.strftime('%H:%M'),
                'end_time': s.end_time.strftime('%H:%M'),
                'duration_hours': s.duration_hours,
            }
            for s in slots
        ]
    
    @staticmethod
    def add_slot(courier: User, day: int, start: str, end: str) -> CourierAvailability:
        """Add a new availability slot."""
        from datetime import time
        
        start_time = datetime.strptime(start, '%H:%M').time()
        end_time = datetime.strptime(end, '%H:%M').time()
        
        slot = CourierAvailability.objects.create(
            courier=courier,
            day_of_week=day,
            start_time=start_time,
            end_time=end_time
        )
        return slot
    
    @staticmethod
    def remove_slot(courier: User, slot_id: str) -> bool:
        """Remove an availability slot."""
        deleted, _ = CourierAvailability.objects.filter(
            courier=courier,
            id=slot_id
        ).delete()
        return deleted > 0
    
    @staticmethod
    def toggle_online(courier: User) -> bool:
        """Toggle courier's online status."""
        courier.is_online = not courier.is_online
        if courier.is_online:
            courier.last_online_at = timezone.now()
        courier.save(update_fields=['is_online', 'last_online_at'])
        return courier.is_online
    
    @staticmethod
    def set_online(courier: User, online: bool) -> None:
        """Set courier's online status explicitly."""
        courier.is_online = online
        if online:
            courier.last_online_at = timezone.now()
        courier.save(update_fields=['is_online', 'last_online_at'])
