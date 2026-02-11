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


# ============================================
# FINANCIAL DASHBOARD
# ============================================

class FinanceDashboardView(AdminRequiredMixin, TemplateView):
    """Financial KPI dashboard with revenue, commissions, debts."""
    template_name = 'fleet/finance_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from django.db.models import Sum, Count
        from logistics.models import Delivery, DeliveryStatus
        from finance.models import Transaction, WithdrawalRequest, WithdrawalStatus
        from core.models import PromoCode
        from datetime import timedelta
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # === KPI Cards ===
        completed = Delivery.objects.filter(status=DeliveryStatus.COMPLETED)
        agg = completed.aggregate(
            total_revenue=Sum('total_price'),
            total_commission=Sum('platform_fee'),
            total_courier_earnings=Sum('courier_earning'),
        )
        context['total_revenue'] = f"{agg['total_revenue'] or 0:,.0f}"
        context['total_commission'] = f"{agg['total_commission'] or 0:,.0f}"
        context['total_courier_earnings'] = f"{agg['total_courier_earnings'] or 0:,.0f}"
        
        # Debts
        indebted = User.objects.filter(
            role=UserRole.COURIER,
            wallet_balance__lt=0
        )
        debt_agg = indebted.aggregate(total_debt=Sum('wallet_balance'))
        context['total_debt'] = f"{abs(debt_agg['total_debt'] or 0):,.0f}"
        context['indebted_couriers'] = indebted.count()
        
        # Withdrawals
        pending_w = WithdrawalRequest.objects.filter(status=WithdrawalStatus.PENDING)
        context['pending_withdrawals_count'] = pending_w.count()
        context['pending_withdrawals_amount'] = f"{pending_w.aggregate(t=Sum('amount'))['t'] or 0:,.0f}"
        
        # Today
        today_completed = completed.filter(completed_at__gte=today_start)
        context['today_deliveries'] = today_completed.count()
        context['today_revenue'] = f"{today_completed.aggregate(t=Sum('total_price'))['t'] or 0:,.0f}"
        
        # Wallet balance
        wallet_total = User.objects.filter(
            role=UserRole.COURIER
        ).aggregate(t=Sum('wallet_balance'))['t'] or 0
        context['total_wallet_balance'] = f"{wallet_total:,.0f}"
        
        # Active promos
        context['active_promos'] = PromoCode.objects.filter(
            is_active=True,
            valid_until__gte=now
        ).count()
        
        # === Daily Revenue Chart (30 days) ===
        daily_data = []
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).date()
            day_revenue = completed.filter(
                completed_at__date=day
            ).aggregate(r=Sum('total_price'))['r'] or 0
            daily_data.append({
                'date': day.strftime('%d/%m'),
                'revenue': float(day_revenue),
            })
        context['daily_revenue_json'] = json.dumps(daily_data)
        
        # === Payment Method Chart ===
        payment_methods = Delivery.objects.filter(
            status=DeliveryStatus.COMPLETED
        ).values('payment_method').annotate(
            count=Count('id')
        ).order_by('-count')
        
        pm_data = []
        method_labels = {'CASH': 'Espèces', 'PREPAID': 'Prépayé', 'MOMO': 'Mobile Money'}
        for pm in payment_methods:
            pm_data.append({
                'method': method_labels.get(pm['payment_method'], pm['payment_method']),
                'count': pm['count'],
            })
        context['payment_methods_json'] = json.dumps(pm_data)
        
        # === Top 10 Couriers ===
        from django.db.models import Subquery, OuterRef
        
        top_couriers = User.objects.filter(
            role=UserRole.COURIER,
            total_deliveries_completed__gt=0,
        ).order_by('-total_deliveries_completed')[:10]
        
        courier_data = []
        for c in top_couriers:
            courier_deliveries = Delivery.objects.filter(
                courier=c, status=DeliveryStatus.COMPLETED
            )
            rev = courier_deliveries.aggregate(
                revenue=Sum('total_price'),
                earnings=Sum('courier_earning'),
            )
            c.revenue = f"{rev['revenue'] or 0:,.0f}"
            c.earnings = f"{rev['earnings'] or 0:,.0f}"
            courier_data.append(c)
        context['top_couriers'] = courier_data
        
        # === Recent Transactions ===
        context['recent_transactions'] = Transaction.objects.select_related(
            'user'
        ).order_by('-created_at')[:15]
        
        return context


# ============================================
# REPORT GENERATION VIEW
# ============================================

class ReportView(AdminRequiredMixin, TemplateView):
    """Generate downloadable financial and operational reports."""
    template_name = 'fleet/reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from django.db.models import Sum, Count, Avg, F
        from logistics.models import Delivery, DeliveryStatus, Neighborhood
        from finance.models import Transaction, WithdrawalRequest, WithdrawalStatus
        from core.models import PromoCode
        from datetime import timedelta, datetime
        
        now = timezone.now()
        
        # ── Period Selection ──
        period = self.request.GET.get('period', '30')
        date_from = self.request.GET.get('from', '')
        date_to = self.request.GET.get('to', '')
        
        if date_from and date_to:
            try:
                start = timezone.make_aware(datetime.strptime(date_from, '%Y-%m-%d'))
                end = timezone.make_aware(datetime.strptime(date_to, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59))
                period_label = f"Du {start.strftime('%d/%m/%Y')} au {end.strftime('%d/%m/%Y')}"
            except ValueError:
                start = now - timedelta(days=30)
                end = now
                period_label = "30 derniers jours"
        else:
            days = int(period)
            start = now - timedelta(days=days)
            end = now
            period_labels = {7: '7 derniers jours', 30: '30 derniers jours', 90: '90 derniers jours'}
            period_label = period_labels.get(days, f'{days} derniers jours')
        
        context['period'] = period
        context['period_label'] = period_label
        context['date_from'] = date_from
        context['date_to'] = date_to
        context['report_date'] = now.strftime('%d/%m/%Y à %H:%M')
        context['is_print'] = self.request.GET.get('print') == '1'
        
        # ── FINANCIAL KPIs ──
        period_deliveries = Delivery.objects.filter(
            status=DeliveryStatus.COMPLETED,
            completed_at__gte=start,
            completed_at__lte=end,
        )
        
        fin_agg = period_deliveries.aggregate(
            total_revenue=Sum('total_price'),
            total_commission=Sum('platform_fee'),
            total_courier_earnings=Sum('courier_earning'),
            total_distance=Sum('distance_km'),
            avg_price=Avg('total_price'),
        )
        
        context['fin'] = {
            'revenue': fin_agg['total_revenue'] or 0,
            'commission': fin_agg['total_commission'] or 0,
            'courier_earnings': fin_agg['total_courier_earnings'] or 0,
            'total_distance': round(fin_agg['total_distance'] or 0, 1),
            'avg_price': round(fin_agg['avg_price'] or 0),
        }
        
        # Payment method breakdown
        pm_breakdown = period_deliveries.values('payment_method').annotate(
            count=Count('id'),
            total=Sum('total_price'),
        ).order_by('-count')
        
        method_labels = {
            'CASH': 'Espèces (Cash)', 
            'PREPAID': 'Prépayé (Wallet)', 
            'MOMO': 'Mobile Money',
            'CASH_P2P': 'Cash P2P',
            'PREPAID_WALLET': 'Prépayé Wallet',
        }
        context['payment_breakdown'] = [
            {
                'method': method_labels.get(pm['payment_method'], pm['payment_method']),
                'count': pm['count'],
                'total': pm['total'] or 0,
            }
            for pm in pm_breakdown
        ]
        
        # Withdrawals in period
        period_withdrawals = WithdrawalRequest.objects.filter(created_at__gte=start, created_at__lte=end)
        w_agg = period_withdrawals.aggregate(
            total_amount=Sum('amount'),
        )
        context['withdrawals'] = {
            'total_count': period_withdrawals.count(),
            'total_amount': w_agg['total_amount'] or 0,
            'pending': period_withdrawals.filter(status=WithdrawalStatus.PENDING).count(),
            'completed': period_withdrawals.filter(status=WithdrawalStatus.COMPLETED).count(),
            'rejected': period_withdrawals.filter(status=WithdrawalStatus.REJECTED).count(),
        }
        
        # Current debt snapshot
        indebted = User.objects.filter(role=UserRole.COURIER, wallet_balance__lt=0)
        debt_agg = indebted.aggregate(total_debt=Sum('wallet_balance'))
        context['debt'] = {
            'total': abs(debt_agg['total_debt'] or 0),
            'count': indebted.count(),
            'blocked': User.objects.filter(
                role=UserRole.COURIER,
                wallet_balance__lt=-F('debt_ceiling')
            ).count(),
        }
        
        # ── OPERATIONAL KPIs ──
        all_period_deliveries = Delivery.objects.filter(
            created_at__gte=start, created_at__lte=end
        )
        total_created = all_period_deliveries.count()
        completed_count = period_deliveries.count()
        cancelled_count = all_period_deliveries.filter(status=DeliveryStatus.CANCELLED).count()
        
        context['ops'] = {
            'total_created': total_created,
            'completed': completed_count,
            'cancelled': cancelled_count,
            'pending': all_period_deliveries.filter(status=DeliveryStatus.PENDING).count(),
            'success_rate': round((completed_count / total_created * 100), 1) if total_created > 0 else 0,
            'cancel_rate': round((cancelled_count / total_created * 100), 1) if total_created > 0 else 0,
        }
        
        # Fleet snapshot
        all_couriers = User.objects.filter(role=UserRole.COURIER, is_active=True)
        context['fleet_snapshot'] = {
            'total': all_couriers.count(),
            'verified': all_couriers.filter(is_verified=True).count(),
            'online': all_couriers.filter(is_online=True).count(),
            'new_in_period': all_couriers.filter(date_joined__gte=start).count(),
        }
        
        # ── TOP COURIERS ──
        top_couriers = []
        couriers_data = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=True,
        ).order_by('-total_deliveries_completed')[:10]
        
        for c in couriers_data:
            c_deliveries = period_deliveries.filter(courier=c)
            c_agg = c_deliveries.aggregate(
                count=Count('id'),
                revenue=Sum('total_price'),
                earnings=Sum('courier_earning'),
            )
            if c_agg['count'] and c_agg['count'] > 0:
                top_couriers.append({
                    'name': c.full_name or c.phone_number,
                    'phone': c.phone_number,
                    'deliveries': c_agg['count'],
                    'revenue': c_agg['revenue'] or 0,
                    'earnings': c_agg['earnings'] or 0,
                    'balance': c.wallet_balance,
                    'level': c.courier_level,
                })
        
        top_couriers.sort(key=lambda x: x['revenue'], reverse=True)
        context['top_couriers'] = top_couriers[:10]
        
        # ── DAILY BREAKDOWN ──
        days_count = (end - start).days + 1
        daily_data = []
        for i in range(min(days_count, 90)):
            day = (start + timedelta(days=i)).date()
            day_delivers = period_deliveries.filter(completed_at__date=day)
            day_agg = day_delivers.aggregate(
                count=Count('id'), 
                revenue=Sum('total_price'),
            )
            daily_data.append({
                'date': day.strftime('%d/%m'),
                'count': day_agg['count'] or 0,
                'revenue': float(day_agg['revenue'] or 0),
            })
        context['daily_data'] = daily_data
        context['daily_data_json'] = json.dumps(daily_data)
        
        # ── ZONE PERFORMANCE ──
        zones = Neighborhood.objects.filter(is_active=True)
        zone_data = []
        for zone in zones:
            zone_pickups = period_deliveries.filter(
                pickup_geo__distance_lte=(zone.center_geo, zone.radius_km * 1000)
            ).count() if zone.center_geo else 0
            zone_dropoffs = period_deliveries.filter(
                dropoff_geo__distance_lte=(zone.center_geo, zone.radius_km * 1000)
            ).count() if zone.center_geo else 0
            zone_data.append({
                'name': zone.name,
                'city': zone.city,
                'pickups': zone_pickups,
                'dropoffs': zone_dropoffs,
                'total': zone_pickups + zone_dropoffs,
            })
        zone_data.sort(key=lambda x: x['total'], reverse=True)
        context['zone_data'] = zone_data[:15]
        
        return context


# ============================================
# SETTINGS / CONFIGURATION VIEW (Super Admin)
# ============================================

class SuperAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only allows superusers (platform owners)."""
    def test_func(self):
        return self.request.user.is_superuser


class SettingsView(SuperAdminRequiredMixin, TemplateView):
    """
    Unified configuration hub for super-admins.
    
    Groups all platform configurations in one place:
    - Dispatch algorithm (weights, thresholds, radii)
    - Notification toggles (sender/recipient per status)
    """
    template_name = 'fleet/settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        from logistics.models import DispatchConfiguration
        from bot.models import NotificationConfiguration
        
        dispatch_config = DispatchConfiguration.get_config()
        notif_config = NotificationConfiguration.get_config()
        
        context['dispatch_config'] = dispatch_config
        context['notif_config'] = notif_config
        
        # Build notification matrix for display
        statuses = [
            ('📦 Commande créée', 'PENDING', 'order_created'),
            ('🏍️ Coursier assigné', 'ASSIGNED', 'assigned'),
            ('🚗 En route pickup', 'EN_ROUTE_PICKUP', 'en_route_pickup'),
            ('📍 Arrivé pickup', 'ARRIVED_PICKUP', 'arrived_pickup'),
            ('📤 Colis récupéré', 'PICKED_UP', 'picked_up'),
            ('🚀 En transit', 'IN_TRANSIT', 'in_transit'),
            ('📍 Arrivé destination', 'ARRIVED_DROPOFF', 'arrived_dropoff'),
            ('✅ Livraison terminée', 'COMPLETED', 'completed'),
            ('❌ Annulée', 'CANCELLED', 'cancelled'),
            ('❌ Échouée', 'FAILED', 'failed'),
        ]
        
        notif_matrix = []
        for label, status, key in statuses:
            notif_matrix.append({
                'label': label,
                'status': status,
                'key': key,
                'sender': notif_config.is_enabled(status, 'sender'),
                'recipient': notif_config.is_enabled(status, 'recipient'),
                'sender_field': f'notify_sender_{key}',
                'recipient_field': f'notify_recipient_{key}',
            })
        context['notif_matrix'] = notif_matrix
        
        # Dispatch weights for chart
        context['dispatch_weights'] = [
            {'name': 'Distance', 'value': dispatch_config.weight_distance, 'color': '#4CAF50'},
            {'name': 'Note moyenne', 'value': dispatch_config.weight_rating, 'color': '#2196F3'},
            {'name': 'Historique', 'value': dispatch_config.weight_history, 'color': '#FF9800'},
            {'name': 'Disponibilité', 'value': dispatch_config.weight_availability, 'color': '#9C27B0'},
            {'name': 'Finance', 'value': dispatch_config.weight_financial, 'color': '#F44336'},
            {'name': 'Réponse', 'value': dispatch_config.weight_response, 'color': '#00BCD4'},
            {'name': 'Niveau', 'value': dispatch_config.weight_level, 'color': '#FFC107'},
            {'name': 'Acceptation', 'value': dispatch_config.weight_acceptance, 'color': '#795548'},
        ]
        context['dispatch_weights_json'] = json.dumps(context['dispatch_weights'])
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle config updates."""
        section = request.POST.get('section', '')
        
        if section == 'dispatch':
            self._update_dispatch_config(request)
        elif section == 'notifications':
            self._update_notification_config(request)
        
        return redirect('fleet:settings')
    
    def _update_dispatch_config(self, request):
        """Update dispatch configuration from form data."""
        from logistics.models import DispatchConfiguration
        
        config = DispatchConfiguration.get_config()
        
        float_fields = [
            'initial_radius_km', 'max_radius_km', 'radius_increment_km',
            'weight_distance', 'weight_rating', 'weight_history',
            'weight_availability', 'weight_financial', 'weight_response',
            'weight_level', 'weight_acceptance',
            'min_score_threshold', 'auto_assign_threshold',
            'distance_perfect_km', 'distance_zero_km',
            'level_score_bronze', 'level_score_silver',
            'level_score_gold', 'level_score_platinum',
            'streak_bonus_per_delivery', 'streak_bonus_max',
            'probation_penalty',
        ]
        
        int_fields = [
            'max_couriers_to_score', 'max_couriers_to_notify',
            'min_ratings_for_full_score', 'courier_stats_cache_ttl',
        ]
        
        for field in float_fields:
            value = request.POST.get(field)
            if value:
                try:
                    setattr(config, field, float(value))
                except (ValueError, TypeError):
                    pass
        
        for field in int_fields:
            value = request.POST.get(field)
            if value:
                try:
                    setattr(config, field, int(value))
                except (ValueError, TypeError):
                    pass
        
        config.streak_bonus_enabled = 'streak_bonus_enabled' in request.POST
        config.notes = request.POST.get('notes', config.notes)
        config.updated_by = request.user
        
        # Validate weights
        if not config.weights_valid:
            messages.error(
                request,
                f"⚠️ La somme des poids doit être 1.0. "
                f"Somme actuelle : {config.total_weight:.2f}"
            )
            return
        
        config.save()
        messages.success(request, "✅ Configuration du dispatch mise à jour !")
    
    def _update_notification_config(self, request):
        """Update notification toggles from form data."""
        from bot.models import NotificationConfiguration
        
        config = NotificationConfiguration.get_config()
        
        # Toggle fields (checkboxes)
        toggle_fields = [
            'notify_sender_order_created', 'notify_recipient_order_created',
            'notify_sender_assigned', 'notify_recipient_assigned',
            'notify_sender_en_route_pickup', 'notify_recipient_en_route_pickup',
            'notify_sender_arrived_pickup', 'notify_recipient_arrived_pickup',
            'notify_sender_picked_up', 'notify_recipient_picked_up',
            'notify_sender_in_transit', 'notify_recipient_in_transit',
            'notify_sender_arrived_dropoff', 'notify_recipient_arrived_dropoff',
            'notify_sender_completed', 'notify_recipient_completed',
            'notify_sender_cancelled', 'notify_recipient_cancelled',
            'notify_sender_failed', 'notify_recipient_failed',
            'notify_dispute_updates', 'notify_daily_summary',
            'notify_rating_request',
        ]
        
        for field in toggle_fields:
            setattr(config, field, field in request.POST)
        
        config.notes = request.POST.get('notif_notes', config.notes)
        config.updated_by = request.user
        config.save()
        
        messages.success(request, "✅ Configuration des notifications mise à jour !")


