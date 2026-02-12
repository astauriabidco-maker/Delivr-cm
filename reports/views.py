"""
REPORTS App - Views for PDF Report Downloads

Provides API endpoints for generating and downloading PDF reports.
"""

import logging
from datetime import date
from django.http import HttpResponse, Http404
from django.views import View
from django.views.decorators.http import require_GET
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404

from core.models import User, UserRole
from .services import ReportGenerator
from django.conf import settings

logger = logging.getLogger(__name__)


def is_admin(user):
    return user.is_authenticated and user.role == UserRole.ADMIN


def is_courier(user):
    return user.is_authenticated and user.role == UserRole.COURIER


# ===========================================
# COURIER REPORT VIEWS
# ===========================================

class CourierPerformanceReportView(LoginRequiredMixin, View):
    """Generate performance report for the logged-in courier."""
    
    def get(self, request):
        if request.user.role != UserRole.COURIER:
            raise Http404("Non autorisé")
        
        try:
            pdf_buffer = ReportGenerator.generate_courier_performance_report(
                courier=request.user
            )
            
            response = HttpResponse(
                pdf_buffer.read(),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = \
                f'attachment; filename="performance_{request.user.phone_number}.pdf"'
            
            return response
            
        except ImportError as e:
            logger.error(f"[REPORTS] PDF generation failed: {e}")
            return HttpResponse(
                "WeasyPrint non installé. Contactez l'administrateur.",
                status=500
            )
        except Exception as e:
            logger.error(f"[REPORTS] Error generating report: {e}")
            return HttpResponse(f"Erreur: {e}", status=500)


class CourierEarningsReportView(LoginRequiredMixin, View):
    """Generate earnings report for the logged-in courier."""
    
    def get(self, request):
        if request.user.role != UserRole.COURIER:
            raise Http404("Non autorisé")
        
        # Optional month/year params
        month = request.GET.get('month')
        year = request.GET.get('year')
        
        try:
            pdf_buffer = ReportGenerator.generate_courier_earnings_report(
                courier=request.user,
                month=int(month) if month else None,
                year=int(year) if year else None
            )
            
            response = HttpResponse(
                pdf_buffer.read(),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = \
                f'attachment; filename="gains_{request.user.phone_number}.pdf"'
            
            return response
            
        except ImportError as e:
            logger.error(f"[REPORTS] PDF generation failed: {e}")
            return HttpResponse(
                "WeasyPrint non installé. Contactez l'administrateur.",
                status=500
            )
        except Exception as e:
            logger.error(f"[REPORTS] Error generating report: {e}")
            return HttpResponse(f"Erreur: {e}", status=500)


# ===========================================
# ADMIN REPORT VIEWS
# ===========================================

@login_required
@user_passes_test(is_admin)
def admin_courier_report(request, pk):
    """Generate performance report for a specific courier (admin only)."""
    courier = get_object_or_404(User, pk=pk, role=UserRole.COURIER)
    
    try:
        pdf_buffer = ReportGenerator.generate_courier_performance_report(courier)
        
        response = HttpResponse(
            pdf_buffer.read(),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = \
            f'attachment; filename="performance_{courier.phone_number}.pdf"'
        
        return response
        
    except Exception as e:
        logger.error(f"[REPORTS] Error generating admin report: {e}")
        return HttpResponse(f"Erreur: {e}", status=500)


@login_required
@user_passes_test(is_admin)
def fleet_kpi_report(request):
    """Generate fleet KPI report (admin only)."""
    try:
        pdf_buffer = ReportGenerator.generate_fleet_kpi_report()
        
        response = HttpResponse(
            pdf_buffer.read(),
            content_type='application/pdf'
        )
        response['Content-Disposition'] = 'attachment; filename="fleet_kpi_report.pdf"'
        
        return response
        
    except Exception as e:
        logger.error(f"[REPORTS] Error generating fleet report: {e}")
        return HttpResponse(f"Erreur: {e}", status=500)


# ===========================================
# OPERATOR DASHBOARD (REAL-TIME)
# ===========================================

from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncHour
from datetime import timedelta
from django.utils import timezone


class OperatorDashboardView(LoginRequiredMixin, View):
    """
    Real-time operator dashboard for monitoring deliveries.
    
    Features:
    - Live KPIs (deliveries, couriers, revenue)
    - Alerts for stuck deliveries
    - City filter
    """
    
    template_name = 'reports/operator_dashboard.html'
    
    def get(self, request):
        if request.user.role != UserRole.ADMIN:
            raise Http404("Accès réservé aux administrateurs")
        
        from logistics.models import Delivery, DeliveryStatus, City
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # City filter
        city_filter = request.GET.get('city', '')
        
        # Base querysets
        all_deliveries = Delivery.objects.all()
        couriers = User.objects.filter(role=UserRole.COURIER, is_verified=True)
        
        if city_filter:
            # Filter by pickup city (approximate via neighborhood)
            all_deliveries = all_deliveries.filter(
                dropoff_neighborhood__city=city_filter
            )
        
        today_deliveries = all_deliveries.filter(created_at__gte=today_start)
        
        # KPIs
        kpis = {
            'pending': all_deliveries.filter(status=DeliveryStatus.PENDING).count(),
            'in_progress': all_deliveries.filter(
                status__in=[
                    DeliveryStatus.ASSIGNED,
                    DeliveryStatus.PICKED_UP,
                    DeliveryStatus.IN_TRANSIT
                ]
            ).count(),
            'completed_today': today_deliveries.filter(status=DeliveryStatus.COMPLETED).count(),
            'cancelled_today': today_deliveries.filter(status=DeliveryStatus.CANCELLED).count(),
            'revenue_today': today_deliveries.filter(
                status=DeliveryStatus.COMPLETED
            ).aggregate(total=Sum('total_price'))['total'] or 0,
            'couriers_online': couriers.filter(is_online=True).count(),
            'couriers_total': couriers.count(),
        }
        
        # Average delivery time today
        completed_today = today_deliveries.filter(
            status=DeliveryStatus.COMPLETED,
            assigned_at__isnull=False,
            completed_at__isnull=False
        )
        if completed_today.exists():
            total_minutes = 0
            count = 0
            for d in completed_today:
                if d.assigned_at and d.completed_at:
                    duration = (d.completed_at - d.assigned_at).total_seconds() / 60
                    total_minutes += duration
                    count += 1
            kpis['avg_delivery_time'] = round(total_minutes / count) if count > 0 else 0
        else:
            kpis['avg_delivery_time'] = 0
        
        # Alerts: Stuck deliveries (> 45min in ASSIGNED/PICKED_UP without update)
        threshold = now - timedelta(minutes=45)
        stuck_deliveries = all_deliveries.filter(
            status__in=[DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP],
            assigned_at__lt=threshold
        ).select_related('courier', 'sender')[:10]
        
        # Couriers with high debt
        high_debt_couriers = couriers.filter(
            wallet_balance__lt=-1000
        ).order_by('wallet_balance')[:5]
        
        # Hourly chart data
        hourly_data = today_deliveries.annotate(
            hour=TruncHour('created_at')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        chart_data = [{'hour': h['hour'].strftime('%H:00'), 'count': h['count']} for h in hourly_data]
        
        context = {
            'kpis': kpis,
            'stuck_deliveries': stuck_deliveries,
            'high_debt_couriers': high_debt_couriers,
            'chart_data': chart_data,
            'city_filter': city_filter,
            'cities': City.choices,
        }
        
        return render(request, self.template_name, context)


@login_required
@user_passes_test(is_admin)
def live_stats_api(request):
    """
    API endpoint for live dashboard updates.
    
    Returns JSON with current KPIs for AJAX polling.
    """
    from logistics.models import Delivery, DeliveryStatus
    from django.db.models import Sum
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    all_deliveries = Delivery.objects.all()
    today_deliveries = all_deliveries.filter(created_at__gte=today_start)
    couriers = User.objects.filter(role=UserRole.COURIER, is_verified=True)
    
    data = {
        'pending': all_deliveries.filter(status=DeliveryStatus.PENDING).count(),
        'in_progress': all_deliveries.filter(
            status__in=[
                DeliveryStatus.ASSIGNED,
                DeliveryStatus.PICKED_UP,
                DeliveryStatus.IN_TRANSIT
            ]
        ).count(),
        'completed_today': today_deliveries.filter(status=DeliveryStatus.COMPLETED).count(),
        'revenue_today': float(today_deliveries.filter(
            status=DeliveryStatus.COMPLETED
        ).aggregate(total=Sum('total_price'))['total'] or 0),
        'couriers_online': couriers.filter(is_online=True).count(),
        'timestamp': now.isoformat(),
    }
    
    return JsonResponse(data)


# ===========================================
# PRICING SIMULATOR
# ===========================================

class PricingSimulatorView(LoginRequiredMixin, View):
    """
    Interactive pricing simulator for admin validation.
    
    Allows testing different configurations before deployment.
    """
    
    template_name = 'reports/pricing_simulator.html'
    
    def get(self, request):
        if request.user.role != UserRole.ADMIN:
            raise Http404("Accès réservé aux administrateurs")
        
        from logistics.pricing_simulator import PricingSimulator
        
        # Get parameters from query string or use defaults
        base_fare = float(request.GET.get('base_fare', settings.PRICING_BASE_FARE))
        cost_per_km = float(request.GET.get('cost_per_km', settings.PRICING_COST_PER_KM))
        minimum_fare = float(request.GET.get('minimum_fare', settings.PRICING_MINIMUM_FARE))
        
        simulator = PricingSimulator(
            base_fare=base_fare,
            cost_per_km=cost_per_km,
            minimum_fare=minimum_fare
        )
        
        scenarios = simulator.simulate_scenarios()
        breakpoints = simulator.get_breakpoints()
        current_config = PricingSimulator.get_current_config()
        
        context = {
            'scenarios': scenarios,
            'breakpoints': breakpoints,
            'current_config': current_config,
            'test_config': {
                'base_fare': base_fare,
                'cost_per_km': cost_per_km,
                'minimum_fare': minimum_fare,
            },
            'chart_labels': [s['distance_km'] for s in scenarios],
            'chart_prices': [s['total_price'] for s in scenarios],
        }
        
        return render(request, self.template_name, context)


@login_required
@user_passes_test(is_admin)
def pricing_csv_export(request):
    """Export pricing scenarios as CSV."""
    from logistics.pricing_simulator import PricingSimulator
    
    base_fare = float(request.GET.get('base_fare', settings.PRICING_BASE_FARE))
    cost_per_km = float(request.GET.get('cost_per_km', settings.PRICING_COST_PER_KM))
    minimum_fare = float(request.GET.get('minimum_fare', settings.PRICING_MINIMUM_FARE))
    
    simulator = PricingSimulator(
        base_fare=base_fare,
        cost_per_km=cost_per_km,
        minimum_fare=minimum_fare
    )
    
    csv_content = simulator.generate_csv_report()
    
    response = HttpResponse(csv_content, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="pricing_simulation.csv"'
    
    return response

