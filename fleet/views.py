"""
FLEET App - Views for Fleet Management Dashboard

Admin views for fleet operations and courier management.
"""

import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.utils import timezone

from core.models import User, UserRole
from core.gamification import LEVEL_THRESHOLDS
from django.db.models import Q, F
from .services import FleetKPIService, AlertService


def is_admin(user):
    """Check if user is an admin."""
    return user.is_authenticated and user.role == UserRole.ADMIN


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin that requires user to be an admin."""
    
    def test_func(self):
        return self.request.user.role == UserRole.ADMIN


class DashboardView(AdminRequiredMixin, TemplateView):
    """
    Main fleet management dashboard.
    
    Shows:
    - Fleet overview (online/offline/blocked)
    - Delivery KPIs
    - Response time metrics
    - Active alerts
    - Top performers
    """
    template_name = 'fleet/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Fleet overview
        context['fleet'] = FleetKPIService.get_fleet_overview()
        
        # Delivery KPIs (7 days)
        context['delivery_kpis'] = FleetKPIService.get_delivery_kpis(days=7)
        
        # Response times
        context['response_times'] = FleetKPIService.get_response_time_metrics()
        
        # Alerts
        context['alerts'] = AlertService.get_active_alerts()[:5]  # Top 5
        context['alert_summary'] = AlertService.get_alert_summary()
        
        # Top performers
        context['top_performers'] = FleetKPIService.get_top_performers(limit=5)
        
        # Problem couriers
        context['problem_couriers'] = FleetKPIService.get_problem_couriers()[:5]
        
        # Level distribution for chart
        context['level_data_json'] = json.dumps(context['fleet']['level_distribution'])
        
        return context


class CourierListView(AdminRequiredMixin, ListView):
    """List all couriers with filters."""
    template_name = 'fleet/courier_list.html'
    context_object_name = 'couriers'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = User.objects.filter(
            role=UserRole.COURIER
        ).order_by('-date_joined')
        
        # Filters
        status = self.request.GET.get('status')
        if status == 'online':
            queryset = queryset.filter(is_online=True, is_verified=True)
        elif status == 'offline':
            queryset = queryset.filter(is_online=False, is_verified=True)
        elif status == 'blocked':
            queryset = queryset.filter(wallet_balance__lt=-F('debt_ceiling'))
        elif status == 'pending':
            queryset = queryset.filter(is_verified=False, cni_document__isnull=False)
        elif status == 'verified':
            queryset = queryset.filter(is_verified=True)
        
        level = self.request.GET.get('level')
        if level and level in LEVEL_THRESHOLDS:
            queryset = queryset.filter(courier_level=level)
        
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(phone_number__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fleet'] = FleetKPIService.get_fleet_overview()
        context['levels'] = LEVEL_THRESHOLDS
        context['current_filters'] = {
            'status': self.request.GET.get('status', ''),
            'level': self.request.GET.get('level', ''),
            'q': self.request.GET.get('q', ''),
        }
        return context


class CourierDetailView(AdminRequiredMixin, DetailView):
    """Detailed view of a single courier."""
    template_name = 'fleet/courier_detail.html'
    context_object_name = 'courier'
    
    def get_queryset(self):
        return User.objects.filter(role=UserRole.COURIER)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.object
        
        # Import here to avoid circular imports
        from courier.services import CourierStatsService
        
        # Stats
        context['today'] = CourierStatsService.get_today_stats(courier)
        context['week'] = CourierStatsService.get_week_stats(courier)
        context['month'] = CourierStatsService.get_month_stats(courier)
        context['wallet'] = CourierStatsService.get_wallet_summary(courier)
        context['performance'] = CourierStatsService.get_performance_summary(courier)
        context['recent_deliveries'] = CourierStatsService.get_recent_deliveries(courier, limit=10)
        
        # Level info
        context['level_info'] = LEVEL_THRESHOLDS.get(courier.courier_level)
        
        # Transactions
        from finance.models import Transaction
        context['transactions'] = Transaction.objects.filter(
            user=courier
        ).order_by('-created_at')[:20]
        
        return context


class AlertsView(AdminRequiredMixin, TemplateView):
    """View all active alerts."""
    template_name = 'fleet/alerts.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['alerts'] = AlertService.get_active_alerts()
        context['alert_summary'] = AlertService.get_alert_summary()
        return context


class AnalyticsView(AdminRequiredMixin, TemplateView):
    """Advanced analytics view."""
    template_name = 'fleet/analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Different time periods
        context['kpis_7d'] = FleetKPIService.get_delivery_kpis(days=7)
        context['kpis_30d'] = FleetKPIService.get_delivery_kpis(days=30)
        context['response_times'] = FleetKPIService.get_response_time_metrics()
        
        return context


class AdvancedAnalyticsView(AdminRequiredMixin, TemplateView):
    """Advanced analytics with charts and heatmap."""
    template_name = 'fleet/analytics_advanced.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Week comparison
        context['comparison'] = FleetKPIService.get_weekly_comparison()
        
        # Hourly trends
        context['hourly_trends'] = FleetKPIService.get_hourly_trends()
        context['hourly_json'] = json.dumps(context['hourly_trends']['distribution'])
        
        # Daily breakdown for chart
        kpis = FleetKPIService.get_delivery_kpis(days=14)
        daily_data = []
        for d in kpis.get('daily_breakdown', []):
            if d.get('day'):
                daily_data.append({
                    'day': d['day'].isoformat() if hasattr(d['day'], 'isoformat') else str(d['day']),
                    'count': d.get('count', 0),
                    'revenue': float(d.get('revenue', 0) or 0)
                })
        context['daily_json'] = json.dumps(daily_data)
        
        # Heatmap data
        context['heatmap_json'] = json.dumps(FleetKPIService.get_delivery_heatmap_data())
        
        # Courier ranking
        context['ranking'] = FleetKPIService.get_courier_ranking(limit=10)
        
        return context


class CoverageView(AdminRequiredMixin, TemplateView):
    """Zone coverage map view."""
    template_name = 'fleet/coverage.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['coverage'] = FleetKPIService.get_zone_coverage()
        context['coverage_json'] = json.dumps(context['coverage'])
        return context


class LiveMapView(AdminRequiredMixin, TemplateView):
    """Real-time courier positions map."""
    template_name = 'fleet/live_map.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fleet'] = FleetKPIService.get_fleet_overview()
        return context


class WithdrawalsListView(AdminRequiredMixin, TemplateView):
    """Admin view for managing withdrawal requests."""
    template_name = 'fleet/withdrawals.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from finance.models import WithdrawalRequest, WithdrawalStatus
        from django.db.models import Sum, Count
        
        # Get filter params
        status_filter = self.request.GET.get('status', '')
        provider_filter = self.request.GET.get('provider', '')
        
        # Base queryset
        qs = WithdrawalRequest.objects.select_related('courier', 'processed_by')
        
        if status_filter:
            qs = qs.filter(status=status_filter)
        if provider_filter:
            qs = qs.filter(provider=provider_filter)
        
        context['withdrawals'] = qs.order_by('-created_at')[:100]
        context['current_status'] = status_filter
        context['current_provider'] = provider_filter
        
        # Stats
        all_withdrawals = WithdrawalRequest.objects.all()
        context['stats'] = {
            'pending': all_withdrawals.filter(status=WithdrawalStatus.PENDING).count(),
            'processing': all_withdrawals.filter(status=WithdrawalStatus.PROCESSING).count(),
            'completed': all_withdrawals.filter(status=WithdrawalStatus.COMPLETED).count(),
            'total_amount': all_withdrawals.filter(
                status=WithdrawalStatus.COMPLETED
            ).aggregate(total=Sum('amount'))['total'] or 0,
        }
        
        return context


@login_required
@user_passes_test(is_admin)
@require_POST
def approve_withdrawal(request, pk):
    """Approve a pending withdrawal request."""
    from finance.models import WithdrawalRequest, WithdrawalService
    
    withdrawal = get_object_or_404(WithdrawalRequest, pk=pk)
    
    try:
        WithdrawalService.approve_request(withdrawal, request.user)
        messages.success(request, f"Retrait de {withdrawal.amount} XAF approuvé")
    except ValueError as e:
        messages.error(request, str(e))
    
    return redirect('fleet:withdrawals')


@login_required
@user_passes_test(is_admin)
@require_POST
def reject_withdrawal(request, pk):
    """Reject a pending withdrawal request."""
    from finance.models import WithdrawalRequest, WithdrawalService
    
    withdrawal = get_object_or_404(WithdrawalRequest, pk=pk)
    reason = request.POST.get('reason', 'Rejeté par admin')
    
    try:
        WithdrawalService.reject_request(withdrawal, request.user, reason)
        messages.success(request, "Demande de retrait rejetée")
    except ValueError as e:
        messages.error(request, str(e))
    
    return redirect('fleet:withdrawals')


@login_required
@user_passes_test(is_admin)
@require_POST
def complete_withdrawal(request, pk):
    """Mark a processing withdrawal as completed."""
    from finance.models import WithdrawalRequest, WithdrawalService
    
    withdrawal = get_object_or_404(WithdrawalRequest, pk=pk)
    transaction_id = request.POST.get('transaction_id', '')
    
    try:
        WithdrawalService.complete_request(withdrawal, transaction_id)
        messages.success(request, f"Retrait marqué comme terminé (ID: {transaction_id})")
    except ValueError as e:
        messages.error(request, str(e))
    
    return redirect('fleet:withdrawals')


# ============================================
# ONBOARDING ADMIN VIEWS
# ============================================

class OnboardingAdminView(AdminRequiredMixin, TemplateView):
    """Admin view for managing courier onboarding applications."""
    template_name = 'fleet/onboarding_admin.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from core.onboarding import CourierOnboarding, OnboardingStatus
        from django.db.models import Count
        
        # Filter by status
        status_filter = self.request.GET.get('status', '')
        
        qs = CourierOnboarding.objects.select_related('courier', 'validated_by')
        
        if status_filter:
            qs = qs.filter(status=status_filter)
        else:
            # Default: show awaiting first
            qs = qs.exclude(status=OnboardingStatus.PENDING)
        
        context['onboardings'] = qs.order_by('-created_at')[:50]
        context['current_status'] = status_filter
        context['pending_count'] = CourierOnboarding.objects.filter(
            status=OnboardingStatus.AWAITING_REVIEW
        ).count()
        
        # Stats
        all_onboardings = CourierOnboarding.objects.all()
        context['stats'] = {
            'pending': all_onboardings.filter(status=OnboardingStatus.AWAITING_REVIEW).count(),
            'approved': all_onboardings.filter(status=OnboardingStatus.APPROVED).count(),
            'rejected': all_onboardings.filter(status=OnboardingStatus.REJECTED).count(),
            'probation': all_onboardings.filter(
                status=OnboardingStatus.APPROVED,
                probation_completed_at__isnull=True
            ).count(),
        }
        
        return context


@login_required
@user_passes_test(is_admin)
@require_POST
def approve_onboarding(request, pk):
    """Approve a courier onboarding application."""
    from core.onboarding import CourierOnboarding
    from core.onboarding_service import OnboardingService
    
    onboarding = get_object_or_404(CourierOnboarding, pk=pk)
    notes = request.POST.get('notes', '')
    
    try:
        OnboardingService.admin_approve(onboarding, request.user, notes)
        messages.success(request, f"Dossier approuvé pour {onboarding.courier.phone_number}")
    except ValueError as e:
        messages.error(request, str(e))
    
    return redirect('fleet:onboarding-admin')


@login_required
@user_passes_test(is_admin)
@require_POST
def reject_onboarding(request, pk):
    """Reject a courier onboarding application."""
    from core.onboarding import CourierOnboarding
    from core.onboarding_service import OnboardingService
    
    onboarding = get_object_or_404(CourierOnboarding, pk=pk)
    reason = request.POST.get('reason', 'Dossier incomplet ou non conforme')
    
    try:
        OnboardingService.admin_reject(onboarding, request.user, reason)
        messages.success(request, f"Dossier rejeté pour {onboarding.courier.phone_number}")
    except ValueError as e:
        messages.error(request, str(e))
    
    return redirect('fleet:onboarding-admin')


# ============================================
# FUNCTION-BASED VIEWS (Actions)
# ============================================

@login_required
@user_passes_test(is_admin)
@require_POST
def verify_courier(request, pk):
    """Verify a courier's documents."""
    courier = get_object_or_404(User, pk=pk, role=UserRole.COURIER)
    
    courier.is_verified = True
    courier.save(update_fields=['is_verified'])
    
    messages.success(request, f"Coursier {courier.phone_number} vérifié avec succès.")
    
    # TODO: Send WhatsApp notification to courier
    
    return redirect('fleet:courier-detail', pk=pk)


@login_required
@user_passes_test(is_admin)
@require_POST
def toggle_block_courier(request, pk):
    """Toggle courier active status."""
    courier = get_object_or_404(User, pk=pk, role=UserRole.COURIER)
    
    courier.is_active = not courier.is_active
    courier.save(update_fields=['is_active'])
    
    status = "activé" if courier.is_active else "désactivé"
    messages.success(request, f"Coursier {courier.phone_number} {status}.")
    
    return redirect('fleet:courier-detail', pk=pk)


@login_required
@user_passes_test(is_admin)
@require_POST
def adjust_debt_ceiling(request, pk):
    """Adjust courier's debt ceiling."""
    courier = get_object_or_404(User, pk=pk, role=UserRole.COURIER)
    
    new_ceiling = request.POST.get('debt_ceiling')
    if new_ceiling:
        try:
            courier.debt_ceiling = Decimal(new_ceiling)
            courier.save(update_fields=['debt_ceiling'])
            messages.success(request, f"Plafond dette mis à jour: {courier.debt_ceiling} XAF")
        except (ValueError, TypeError):
            messages.error(request, "Valeur invalide pour le plafond dette.")
    
    return redirect('fleet:courier-detail', pk=pk)


@login_required
@user_passes_test(is_admin)
@require_POST
def acknowledge_alert(request, pk):
    """Acknowledge an alert (placeholder for future alert model)."""
    # For now, just redirect back
    messages.info(request, "Alerte marquée comme vue.")
    return redirect('fleet:alerts')


# ============================================
# API ENDPOINTS
# ============================================

@login_required
@user_passes_test(is_admin)
@require_GET
def api_fleet_stats(request):
    """API: Get real-time fleet stats."""
    return JsonResponse({
        'fleet': FleetKPIService.get_fleet_overview(),
        'delivery_kpis': FleetKPIService.get_delivery_kpis(days=1),
        'alert_summary': AlertService.get_alert_summary(),
    })


@login_required
@user_passes_test(is_admin)
@require_GET
def api_online_couriers(request):
    """API: Get list of online couriers with locations."""
    couriers = User.objects.filter(
        role=UserRole.COURIER,
        is_verified=True,
        is_online=True,
        last_location__isnull=False
    ).values(
        'id', 'first_name', 'phone_number', 'courier_level',
        'last_location', 'last_location_updated', 'average_rating'
    )
    
    result = []
    for c in couriers:
        result.append({
            'id': str(c['id']),
            'name': c['first_name'] or f"Coursier {c['phone_number'][-4:]}",
            'phone': c['phone_number'],
            'level': c['courier_level'],
            'rating': float(c['average_rating']) if c['average_rating'] else None,
            'lat': c['last_location'].y if c['last_location'] else None,
            'lng': c['last_location'].x if c['last_location'] else None,
            'last_update': c['last_location_updated'].isoformat() if c['last_location_updated'] else None,
            'in_delivery': False,  # TODO: check active delivery
        })
    
    return JsonResponse({'couriers': result})


@login_required
@user_passes_test(is_admin)
@require_GET
def api_courier_positions(request):
    """
    API: Get courier positions and active deliveries for live map.
    
    Returns:
        couriers: List of online couriers with positions
        deliveries: List of pending/in-progress deliveries
    """
    from logistics.models import Delivery, DeliveryStatus
    
    # Get online couriers
    couriers = User.objects.filter(
        role=UserRole.COURIER,
        is_verified=True,
        is_online=True,
        last_location__isnull=False
    ).select_related()
    
    # Get active deliveries for each courier
    active_deliveries = dict(
        Delivery.objects.filter(
            status__in=[DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP, DeliveryStatus.IN_TRANSIT],
            courier__isnull=False
        ).values_list('courier_id', 'id')
    )
    
    # Build courier list
    courier_list = []
    for c in couriers:
        courier_list.append({
            'id': str(c.id),
            'name': c.first_name or f"Coursier {c.phone_number[-4:]}",
            'phone': c.phone_number,
            'level': c.courier_level,
            'rating': float(c.average_rating) if c.average_rating else None,
            'lat': c.last_location.y if c.last_location else None,
            'lng': c.last_location.x if c.last_location else None,
            'last_update': c.last_location_updated.isoformat() if c.last_location_updated else None,
            'in_delivery': c.id in active_deliveries,
            'deliveries_today': c.total_deliveries_completed or 0,
        })
    
    # Get pending deliveries (waiting for courier)
    pending_deliveries = Delivery.objects.filter(
        status=DeliveryStatus.PENDING,
        pickup_geo__isnull=False
    ).values('id', 'pickup_geo', 'pickup_address', 'courier_earning', 'distance_km')[:20]
    
    delivery_list = []
    for d in pending_deliveries:
        delivery_list.append({
            'id': str(d['id']),
            'lat': d['pickup_geo'].y if d['pickup_geo'] else None,
            'lng': d['pickup_geo'].x if d['pickup_geo'] else None,
            'address': d['pickup_address'] or '',
            'earning': str(d['courier_earning']),
            'distance_km': d['distance_km'],
        })
    
    return JsonResponse({
        'couriers': courier_list,
        'deliveries': delivery_list
    })


@login_required
@user_passes_test(is_admin)
@require_GET
def api_check_alerts(request):
    """API: Get active alerts (for live updates)."""
    return JsonResponse({
        'alerts': AlertService.get_active_alerts(),
        'summary': AlertService.get_alert_summary(),
    })
