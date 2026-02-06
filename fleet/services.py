"""
FLEET App - Services for Fleet Management

Business intelligence and KPI calculation for fleet operations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Avg, Count, F, Q, Min, Max
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point

from core.models import User, UserRole
from core.courier_profile import CourierPerformanceLog, CourierBadge
from core.gamification import LEVEL_THRESHOLDS
from logistics.models import Delivery, DeliveryStatus, Neighborhood


class FleetKPIService:
    """
    Service for calculating fleet management KPIs.
    
    Provides real-time and historical metrics for admin dashboard.
    """
    
    @staticmethod
    def get_fleet_overview() -> Dict[str, Any]:
        """
        Get high-level fleet overview stats.
        
        Returns:
            Dict with key fleet metrics.
        """
        now = timezone.now()
        today = now.date()
        
        # Courier counts
        all_couriers = User.objects.filter(role=UserRole.COURIER, is_active=True)
        
        total_couriers = all_couriers.count()
        verified_couriers = all_couriers.filter(is_verified=True).count()
        online_couriers = all_couriers.filter(is_verified=True, is_online=True).count()
        blocked_couriers = all_couriers.filter(
            wallet_balance__lt=-F('debt_ceiling')
        ).count()
        
        # Level distribution
        level_distribution = {}
        for level_code in LEVEL_THRESHOLDS.keys():
            level_distribution[level_code] = all_couriers.filter(
                courier_level=level_code
            ).count()
        
        # Pending verification
        pending_verification = all_couriers.filter(
            is_verified=False,
            cni_document__isnull=False
        ).count()
        
        return {
            'total_couriers': total_couriers,
            'verified_couriers': verified_couriers,
            'online_couriers': online_couriers,
            'offline_couriers': verified_couriers - online_couriers,
            'blocked_couriers': blocked_couriers,
            'pending_verification': pending_verification,
            'level_distribution': level_distribution,
            'online_percentage': round((online_couriers / verified_couriers * 100), 1) if verified_couriers > 0 else 0,
        }
    
    @staticmethod
    def get_delivery_kpis(days: int = 7) -> Dict[str, Any]:
        """
        Get delivery performance KPIs for the past N days.
        """
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        deliveries = Delivery.objects.filter(
            created_at__gte=start_date
        )
        
        # Status breakdown
        status_counts = deliveries.values('status').annotate(count=Count('id'))
        status_dict = {s['status']: s['count'] for s in status_counts}
        
        total = deliveries.count()
        completed = status_dict.get(DeliveryStatus.COMPLETED, 0)
        cancelled = status_dict.get(DeliveryStatus.CANCELLED, 0)
        failed = status_dict.get(DeliveryStatus.FAILED, 0)
        pending = status_dict.get(DeliveryStatus.PENDING, 0)
        
        # Success rate
        success_rate = (completed / total * 100) if total > 0 else 0
        
        # Revenue
        revenue_data = Delivery.objects.filter(
            completed_at__gte=start_date,
            status=DeliveryStatus.COMPLETED
        ).aggregate(
            total_revenue=Sum('total_price'),
            total_platform_fee=Sum('platform_fee'),
            total_courier_earning=Sum('courier_earning'),
            total_distance=Sum('distance_km'),
        )
        
        # Daily breakdown
        daily_deliveries = deliveries.filter(
            status=DeliveryStatus.COMPLETED
        ).annotate(
            day=TruncDate('completed_at')
        ).values('day').annotate(
            count=Count('id'),
            revenue=Sum('total_price')
        ).order_by('day')
        
        return {
            'period_days': days,
            'total_deliveries': total,
            'completed': completed,
            'cancelled': cancelled,
            'failed': failed,
            'pending': pending,
            'success_rate': round(success_rate, 1),
            'total_revenue': float(revenue_data['total_revenue'] or 0),
            'platform_earnings': float(revenue_data['total_platform_fee'] or 0),
            'courier_payouts': float(revenue_data['total_courier_earning'] or 0),
            'total_distance_km': round(revenue_data['total_distance'] or 0, 1),
            'avg_deliveries_per_day': round(completed / days, 1) if days > 0 else 0,
            'daily_breakdown': list(daily_deliveries),
        }
    
    @staticmethod
    def get_response_time_metrics() -> Dict[str, Any]:
        """
        Calculate average response times for delivery acceptance.
        """
        # Get deliveries with assignment timestamps
        recent_deliveries = Delivery.objects.filter(
            assigned_at__isnull=False,
            created_at__gte=timezone.now() - timedelta(days=7)
        )
        
        if not recent_deliveries.exists():
            return {
                'avg_assignment_time_minutes': 0,
                'avg_pickup_time_minutes': 0,
                'avg_delivery_duration_minutes': 0,
            }
        
        # Calculate average times
        assignment_times = []
        pickup_times = []
        delivery_times = []
        
        for d in recent_deliveries:
            if d.assigned_at and d.created_at:
                assignment_times.append((d.assigned_at - d.created_at).total_seconds() / 60)
            if d.picked_up_at and d.assigned_at:
                pickup_times.append((d.picked_up_at - d.assigned_at).total_seconds() / 60)
            if d.completed_at and d.picked_up_at:
                delivery_times.append((d.completed_at - d.picked_up_at).total_seconds() / 60)
        
        return {
            'avg_assignment_time_minutes': round(sum(assignment_times) / len(assignment_times), 1) if assignment_times else 0,
            'avg_pickup_time_minutes': round(sum(pickup_times) / len(pickup_times), 1) if pickup_times else 0,
            'avg_delivery_duration_minutes': round(sum(delivery_times) / len(delivery_times), 1) if delivery_times else 0,
        }
    
    @staticmethod
    def get_top_performers(limit: int = 10) -> List[Dict]:
        """Get top performing couriers."""
        couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=True,
            is_active=True
        ).order_by('-total_deliveries_completed')[:limit]
        
        return [
            {
                'id': str(c.id),
                'name': c.full_name or f"Coursier {c.phone_number[-4:]}",
                'phone': c.phone_number,
                'level': c.courier_level,
                'level_icon': LEVEL_THRESHOLDS[c.courier_level]['icon'],
                'total_deliveries': c.total_deliveries_completed,
                'average_rating': c.average_rating,
                'is_online': c.is_online,
                'wallet_balance': float(c.wallet_balance),
            }
            for c in couriers
        ]
    
    @staticmethod
    def get_problem_couriers() -> List[Dict]:
        """
        Get couriers that need attention.
        
        Criteria:
        - High debt (>80% of ceiling)
        - Low acceptance rate (<70%)
        - Inactive for >7 days
        - Multiple cancellations recently
        """
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        
        problems = []
        
        couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=True,
            is_active=True
        )
        
        for c in couriers:
            issues = []
            severity = 0
            
            # High debt
            if c.wallet_balance < 0:
                debt_ratio = abs(c.wallet_balance) / c.debt_ceiling if c.debt_ceiling > 0 else 0
                if debt_ratio > 0.8:
                    issues.append(f"Dette élevée ({debt_ratio*100:.0f}%)")
                    severity += 3 if debt_ratio > 0.9 else 2
            
            # Blocked
            if c.is_courier_blocked:
                issues.append("Compte bloqué")
                severity += 4
            
            # Low acceptance
            if c.acceptance_rate < 70:
                issues.append(f"Taux acceptation faible ({c.acceptance_rate:.0f}%)")
                severity += 2
            
            # Inactive
            if c.last_online_at and c.last_online_at < week_ago:
                days_inactive = (now - c.last_online_at).days
                issues.append(f"Inactif depuis {days_inactive} jours")
                severity += 1
            
            if issues:
                problems.append({
                    'id': str(c.id),
                    'name': c.full_name or f"Coursier {c.phone_number[-4:]}",
                    'phone': c.phone_number,
                    'issues': issues,
                    'severity': severity,
                    'wallet_balance': float(c.wallet_balance),
                    'debt_ceiling': float(c.debt_ceiling),
                })
        
        # Sort by severity
        problems.sort(key=lambda x: x['severity'], reverse=True)
        
        return problems
    
    @staticmethod
    def get_zone_coverage() -> List[Dict]:
        """
        Calculate courier coverage per neighborhood.
        
        Returns list of neighborhoods with courier count within 3km.
        """
        neighborhoods = Neighborhood.objects.filter(is_active=True)
        online_couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=True,
            is_online=True,
            last_location__isnull=False
        )
        
        coverage = []
        
        for n in neighborhoods:
            # Count couriers within 3km of neighborhood center
            nearby_count = online_couriers.filter(
                last_location__distance_lte=(n.center_geo, 3000)  # 3km in meters
            ).count()
            
            coverage.append({
                'neighborhood_id': str(n.id),
                'name': n.name,
                'city': n.city,
                'couriers_nearby': nearby_count,
                'status': 'good' if nearby_count >= 2 else ('warning' if nearby_count == 1 else 'critical'),
                'center_lat': n.center_geo.y,
                'center_lng': n.center_geo.x,
            })
        
        return coverage
    
    # ===========================================
    # ADVANCED ANALYTICS
    # ===========================================
    
    @staticmethod
    def get_hourly_trends() -> Dict[str, Any]:
        """
        Get delivery trends by hour of day.
        
        Returns hourly distribution for optimization.
        """
        week_ago = timezone.now() - timedelta(days=7)
        
        hourly = Delivery.objects.filter(
            created_at__gte=week_ago
        ).annotate(
            hour=TruncHour('created_at')
        ).values('hour').annotate(
            count=Count('id'),
            completed=Count('id', filter=Q(status=DeliveryStatus.COMPLETED))
        ).order_by('hour')
        
        # Aggregate by hour of day (0-23)
        hour_distribution = {i: {'orders': 0, 'completed': 0} for i in range(24)}
        for h in hourly:
            if h['hour']:
                hour_of_day = h['hour'].hour
                hour_distribution[hour_of_day]['orders'] += h['count']
                hour_distribution[hour_of_day]['completed'] += h['completed']
        
        # Find peak hours
        peak_hours = sorted(
            hour_distribution.items(),
            key=lambda x: x[1]['orders'],
            reverse=True
        )[:3]
        
        return {
            'distribution': hour_distribution,
            'peak_hours': [{'hour': h, **data} for h, data in peak_hours],
            'peak_hour_label': f"{peak_hours[0][0]}:00" if peak_hours else "N/A",
        }
    
    @staticmethod
    def get_delivery_heatmap_data() -> List[Dict]:
        """
        Get delivery locations for heatmap visualization.
        
        Returns pickup and dropoff points with intensity.
        """
        week_ago = timezone.now() - timedelta(days=7)
        
        deliveries = Delivery.objects.filter(
            created_at__gte=week_ago,
            pickup_location__isnull=False,
            dropoff_location__isnull=False
        ).select_related('pickup_neighborhood', 'dropoff_neighborhood')
        
        points = []
        for d in deliveries[:500]:  # Limit for performance
            if d.pickup_location:
                points.append({
                    'lat': d.pickup_location.y,
                    'lng': d.pickup_location.x,
                    'type': 'pickup',
                    'intensity': 1,
                })
            if d.dropoff_location:
                points.append({
                    'lat': d.dropoff_location.y,
                    'lng': d.dropoff_location.x,
                    'type': 'dropoff',
                    'intensity': 1,
                })
        
        return points
    
    @staticmethod
    def get_weekly_comparison() -> Dict[str, Any]:
        """
        Compare this week vs last week performance.
        """
        now = timezone.now()
        this_week_start = now - timedelta(days=7)
        last_week_start = now - timedelta(days=14)
        
        def get_week_stats(start, end):
            deliveries = Delivery.objects.filter(
                created_at__gte=start,
                created_at__lt=end
            )
            completed = deliveries.filter(status=DeliveryStatus.COMPLETED)
            
            revenue = completed.aggregate(
                total=Sum('total_price'),
                platform=Sum('platform_fee')
            )
            
            return {
                'total': deliveries.count(),
                'completed': completed.count(),
                'revenue': float(revenue['total'] or 0),
                'platform_earnings': float(revenue['platform'] or 0),
            }
        
        this_week = get_week_stats(this_week_start, now)
        last_week = get_week_stats(last_week_start, this_week_start)
        
        # Calculate changes
        def calc_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round((current - previous) / previous * 100, 1)
        
        return {
            'this_week': this_week,
            'last_week': last_week,
            'changes': {
                'deliveries': calc_change(this_week['completed'], last_week['completed']),
                'revenue': calc_change(this_week['revenue'], last_week['revenue']),
            }
        }
    
    @staticmethod
    def get_courier_ranking(limit: int = 20) -> List[Dict]:
        """
        Get detailed courier ranking with multiple metrics.
        """
        month_ago = timezone.now() - timedelta(days=30)
        
        couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=True,
            is_active=True
        ).annotate(
            month_deliveries=Count(
                'assigned_deliveries',
                filter=Q(
                    assigned_deliveries__completed_at__gte=month_ago,
                    assigned_deliveries__status=DeliveryStatus.COMPLETED
                )
            ),
            month_revenue=Sum(
                'assigned_deliveries__courier_earning',
                filter=Q(
                    assigned_deliveries__completed_at__gte=month_ago,
                    assigned_deliveries__status=DeliveryStatus.COMPLETED
                )
            )
        ).order_by('-month_deliveries')[:limit]
        
        ranking = []
        for i, c in enumerate(couriers, 1):
            ranking.append({
                'rank': i,
                'id': str(c.id),
                'name': c.full_name or f"Coursier {c.phone_number[-4:]}",
                'phone': c.phone_number,
                'level': c.courier_level,
                'level_icon': LEVEL_THRESHOLDS.get(c.courier_level, {}).get('icon', '🚴'),
                'month_deliveries': c.month_deliveries or 0,
                'month_revenue': float(c.month_revenue or 0),
                'total_deliveries': c.total_deliveries_completed,
                'rating': c.average_rating,
                'is_online': c.is_online,
            })
        
        return ranking


class AlertService:
    """Service for managing fleet alerts."""
    
    ALERT_TYPES = {
        'HIGH_DEBT': {'severity': 'warning', 'icon': '💰', 'message': 'Coursier avec dette élevée'},
        'BLOCKED': {'severity': 'danger', 'icon': '🚫', 'message': 'Coursier bloqué'},
        'INACTIVE': {'severity': 'info', 'icon': '😴', 'message': 'Coursier inactif'},
        'LOW_COVERAGE': {'severity': 'warning', 'icon': '📍', 'message': 'Zone mal couverte'},
        'LOW_ACCEPTANCE': {'severity': 'warning', 'icon': '❌', 'message': 'Taux acceptation faible'},
        'PENDING_VERIFICATION': {'severity': 'info', 'icon': '📋', 'message': 'Vérification en attente'},
    }
    
    @classmethod
    def get_active_alerts(cls) -> List[Dict]:
        """Get all active alerts that need attention."""
        alerts = []
        now = timezone.now()
        
        # Check for blocked couriers
        blocked = User.objects.filter(
            role=UserRole.COURIER,
            is_active=True,
            wallet_balance__lt=-F('debt_ceiling')
        )
        for c in blocked:
            alerts.append({
                'type': 'BLOCKED',
                'courier_id': str(c.id),
                'courier_name': c.full_name or c.phone_number,
                'message': f"Coursier bloqué - dette: {abs(c.wallet_balance):.0f} XAF",
                **cls.ALERT_TYPES['BLOCKED']
            })
        
        # Check for high debt (>80%)
        high_debt = User.objects.filter(
            role=UserRole.COURIER,
            is_active=True,
            wallet_balance__lt=0
        ).exclude(
            wallet_balance__lt=-F('debt_ceiling')  # Exclude already blocked
        )
        for c in high_debt:
            debt_ratio = abs(c.wallet_balance) / c.debt_ceiling if c.debt_ceiling > 0 else 0
            if debt_ratio > 0.8:
                alerts.append({
                    'type': 'HIGH_DEBT',
                    'courier_id': str(c.id),
                    'courier_name': c.full_name or c.phone_number,
                    'message': f"Dette à {debt_ratio*100:.0f}% du plafond",
                    **cls.ALERT_TYPES['HIGH_DEBT']
                })
        
        # Check for inactive couriers (>7 days)
        week_ago = now - timedelta(days=7)
        inactive = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=True,
            is_active=True,
            last_online_at__lt=week_ago
        )
        for c in inactive:
            days_inactive = (now - c.last_online_at).days
            alerts.append({
                'type': 'INACTIVE',
                'courier_id': str(c.id),
                'courier_name': c.full_name or c.phone_number,
                'message': f"Inactif depuis {days_inactive} jours",
                **cls.ALERT_TYPES['INACTIVE']
            })
        
        # Check for pending verifications
        pending_count = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=False,
            cni_document__isnull=False
        ).count()
        if pending_count > 0:
            alerts.append({
                'type': 'PENDING_VERIFICATION',
                'count': pending_count,
                'message': f"{pending_count} coursier(s) en attente de vérification",
                **cls.ALERT_TYPES['PENDING_VERIFICATION']
            })
        
        # Sort by severity
        severity_order = {'danger': 0, 'warning': 1, 'info': 2}
        alerts.sort(key=lambda x: severity_order.get(x['severity'], 99))
        
        return alerts
    
    @classmethod
    def get_alert_summary(cls) -> Dict[str, int]:
        """Get count of alerts by severity."""
        alerts = cls.get_active_alerts()
        
        return {
            'total': len(alerts),
            'danger': len([a for a in alerts if a['severity'] == 'danger']),
            'warning': len([a for a in alerts if a['severity'] == 'warning']),
            'info': len([a for a in alerts if a['severity'] == 'info']),
        }
