"""
COURIER App - Views for Dashboard

Mobile-first web dashboard for couriers.
Uses Django templates with responsive design.
"""

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from core.models import User, UserRole
from core.courier_profile import CourierAvailability
from core.gamification import (
    GamificationService, get_courier_leaderboard,
    get_courier_badges_summary, LEVEL_THRESHOLDS
)
from .services import CourierStatsService, AvailabilityService


class CourierRequiredMixin(LoginRequiredMixin):
    """Mixin that requires user to be a courier."""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role != UserRole.COURIER:
            return redirect('home:index')
        return super().dispatch(request, *args, **kwargs)


class DashboardView(CourierRequiredMixin, TemplateView):
    """
    Main courier dashboard.
    
    Shows:
    - Today's stats (deliveries, earnings, distance)
    - Week overview chart
    - Current level & next level progress
    - Online/offline toggle
    - Quick actions
    """
    template_name = 'courier/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.request.user
        
        # Stats
        context['today'] = CourierStatsService.get_today_stats(courier)
        context['week'] = CourierStatsService.get_week_stats(courier)
        context['month'] = CourierStatsService.get_month_stats(courier)
        
        # Performance
        context['performance'] = CourierStatsService.get_performance_summary(courier)
        context['rank'] = CourierStatsService.get_courier_rank(courier)
        
        # Wallet
        context['wallet'] = CourierStatsService.get_wallet_summary(courier)
        
        # Recent deliveries
        context['recent_deliveries'] = CourierStatsService.get_recent_deliveries(courier, limit=5)
        
        # Level info
        context['level_info'] = LEVEL_THRESHOLDS.get(courier.courier_level)
        context['next_level'] = GamificationService.get_next_level_progress(courier)
        
        # For chart (JS data)
        context['week_data_json'] = json.dumps(context['week']['daily_breakdown'])
        
        return context


class EarningsView(CourierRequiredMixin, TemplateView):
    """Detailed earnings view with history."""
    template_name = 'courier/earnings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.request.user
        
        context['today'] = CourierStatsService.get_today_stats(courier)
        context['week'] = CourierStatsService.get_week_stats(courier)
        context['month'] = CourierStatsService.get_month_stats(courier)
        context['wallet'] = CourierStatsService.get_wallet_summary(courier)
        context['earnings_history'] = CourierStatsService.get_earnings_history(courier, days=30)
        context['recent_deliveries'] = CourierStatsService.get_recent_deliveries(courier, limit=20)
        
        # For chart
        context['earnings_data_json'] = json.dumps(context['earnings_history'])
        
        return context


class PerformanceView(CourierRequiredMixin, TemplateView):
    """Performance metrics and level progression."""
    template_name = 'courier/performance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.request.user
        
        context['performance'] = CourierStatsService.get_performance_summary(courier)
        context['rank'] = CourierStatsService.get_courier_rank(courier)
        context['level_thresholds'] = LEVEL_THRESHOLDS
        
        return context


class LeaderboardView(CourierRequiredMixin, TemplateView):
    """Courier leaderboard."""
    template_name = 'courier/leaderboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.request.user
        
        context['leaderboard'] = get_courier_leaderboard(limit=50)
        context['my_rank'] = CourierStatsService.get_courier_rank(courier)
        context['my_id'] = str(courier.id)
        
        return context


class AvailabilityView(CourierRequiredMixin, TemplateView):
    """Availability schedule management."""
    template_name = 'courier/availability.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.request.user
        
        context['is_online'] = courier.is_online
        context['last_online'] = courier.last_online_at
        context['schedule'] = AvailabilityService.get_availability_schedule(courier)
        
        # Days of week for form
        context['days_of_week'] = [
            {'value': 0, 'label': 'Lundi'},
            {'value': 1, 'label': 'Mardi'},
            {'value': 2, 'label': 'Mercredi'},
            {'value': 3, 'label': 'Jeudi'},
            {'value': 4, 'label': 'Vendredi'},
            {'value': 5, 'label': 'Samedi'},
            {'value': 6, 'label': 'Dimanche'},
        ]
        
        return context


class WalletView(CourierRequiredMixin, TemplateView):
    """Wallet summary and actions."""
    template_name = 'courier/wallet.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.request.user
        
        context['wallet'] = CourierStatsService.get_wallet_summary(courier)
        
        return context


class TransactionHistoryView(CourierRequiredMixin, TemplateView):
    """Transaction history view."""
    template_name = 'courier/transactions.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.request.user
        
        from finance.models import Transaction
        
        transactions = Transaction.objects.filter(
            user=courier
        ).order_by('-created_at')[:50]
        
        context['transactions'] = transactions
        context['wallet'] = CourierStatsService.get_wallet_summary(courier)
        
        return context


class ProfileView(CourierRequiredMixin, TemplateView):
    """Courier profile view."""
    template_name = 'courier/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.request.user
        
        context['courier'] = courier
        context['performance'] = CourierStatsService.get_performance_summary(courier)
        context['level_info'] = LEVEL_THRESHOLDS.get(courier.courier_level)
        
        return context


class BadgesView(CourierRequiredMixin, TemplateView):
    """Badges collection view."""
    template_name = 'courier/badges.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.request.user
        
        # Get summary from gamification service
        summary = get_courier_badges_summary(courier)
        context['badges_summary'] = summary
        
        # List of earned badge objects (from summary dict)
        context['earned_badges'] = summary['badges']
        
        # List of earned badge codes for easy checking
        earned_codes = [b['type'] for b in summary['badges']]
        context['earned_codes'] = earned_codes
        
        # All available badges with descriptions
        from core.courier_profile import BadgeType
        from core.gamification import BADGE_CRITERIA
        
        available_badges = []
        for badge_type in BadgeType:
            criteria = BADGE_CRITERIA.get(badge_type.value, {})
            # Get emoji icon from display name
            display = badge_type.label
            icon = display.split()[-1] if display else '🏅'
            
            available_badges.append({
                'code': badge_type.value,
                'display': display,
                'icon': icon,
                'hint': criteria.get('description', '')
            })
            
        context['available_badges'] = available_badges
        
        return context


class DeliveryHistoryView(CourierRequiredMixin, TemplateView):
    """Delivery history with GPS map."""
    template_name = 'courier/delivery_history.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        courier = self.request.user
        
        from logistics.models import Delivery, DeliveryStatus
        from django.db.models import Sum
        from datetime import datetime
        
        # Get filter params
        status = self.request.GET.get('status', '')
        start_date = self.request.GET.get('start_date', '')
        end_date = self.request.GET.get('end_date', '')
        
        # Base queryset - courier's assigned deliveries
        qs = Delivery.objects.filter(
            courier=courier
        ).select_related('dropoff_neighborhood')
        
        # Apply filters
        if status:
            qs = qs.filter(status=status)
        else:
            # By default show completed courses
            qs = qs.filter(status__in=[
                DeliveryStatus.COMPLETED,
                DeliveryStatus.CANCELLED,
                DeliveryStatus.FAILED
            ])
        
        if start_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                qs = qs.filter(created_at__date__gte=start)
            except ValueError:
                pass
        
        if end_date:
            try:
                end = datetime.strptime(end_date, '%Y-%m-%d')
                qs = qs.filter(created_at__date__lte=end)
            except ValueError:
                pass
        
        deliveries = qs.order_by('-created_at')[:100]
        
        # Stats for the filtered results
        completed = qs.filter(status=DeliveryStatus.COMPLETED)
        stats_agg = completed.aggregate(
            total_earnings=Sum('courier_earning'),
            total_distance=Sum('distance_km')
        )
        
        context['deliveries'] = deliveries
        context['current_status'] = status
        context['start_date'] = start_date
        context['end_date'] = end_date
        context['stats'] = {
            'total': qs.count(),
            'completed': completed.count(),
            'earnings': stats_agg['total_earnings'] or 0,
            'distance': stats_agg['total_distance'] or 0,
        }
        
        return context


# ============================================
# FUNCTION-BASED VIEWS (for AJAX/Forms)
# ============================================

@login_required
@require_POST
def toggle_online_status(request):
    """Toggle courier online/offline status (form POST)."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    new_status = AvailabilityService.toggle_online(request.user)
    
    return redirect('courier:availability')


@login_required
@require_POST
def add_availability_slot(request):
    """Add a new availability slot."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    day = int(request.POST.get('day_of_week', 0))
    start = request.POST.get('start_time', '08:00')
    end = request.POST.get('end_time', '18:00')
    
    try:
        AvailabilityService.add_slot(request.user, day, start, end)
    except Exception as e:
        # Handle duplicate or invalid slot
        pass
    
    return redirect('courier:availability')


@login_required
@require_POST
def delete_availability_slot(request, slot_id):
    """Delete an availability slot."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    AvailabilityService.remove_slot(request.user, str(slot_id))
    
    return redirect('courier:availability')


@login_required
@require_GET
def export_delivery_history_csv(request):
    """Export delivery history as CSV."""
    import csv
    from django.http import HttpResponse
    from logistics.models import Delivery, DeliveryStatus
    from datetime import datetime
    
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    courier = request.user
    
    # Get filter params (same as DeliveryHistoryView)
    status = request.GET.get('status', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    qs = Delivery.objects.filter(
        courier=courier
    ).select_related('dropoff_neighborhood')
    
    if status:
        qs = qs.filter(status=status)
    else:
        qs = qs.filter(status__in=[
            DeliveryStatus.COMPLETED,
            DeliveryStatus.CANCELLED,
            DeliveryStatus.FAILED
        ])
    
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            qs = qs.filter(created_at__date__gte=start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            qs = qs.filter(created_at__date__lte=end)
        except ValueError:
            pass
    
    deliveries = qs.order_by('-created_at')[:500]
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="courses_{courier.phone_number[-4:]}_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Pickup', 'Dropoff', 'Distance (km)', 
        'Statut', 'Gain (XAF)', 'Prix Total (XAF)'
    ])
    
    for d in deliveries:
        writer.writerow([
            d.created_at.strftime('%Y-%m-%d %H:%M'),
            d.pickup_address,
            d.dropoff_neighborhood.name if d.dropoff_neighborhood else 'N/A',
            f"{d.distance_km:.1f}" if d.distance_km else '0',
            d.get_status_display(),
            f"{d.courier_earning:.0f}" if d.courier_earning else '0',
            f"{d.total_price:.0f}" if d.total_price else '0',
        ])
    
    return response


# ============================================
# API ENDPOINTS (JSON responses)
# ============================================

@login_required
@require_GET
def api_get_stats(request):
    """API: Get current stats (for live updates)."""
    if request.user.role != UserRole.COURIER:
        return JsonResponse({'error': 'Not a courier'}, status=403)
    
    courier = request.user
    
    return JsonResponse({
        'today': CourierStatsService.get_today_stats(courier),
        'is_online': courier.is_online,
        'wallet': CourierStatsService.get_wallet_summary(courier),
    })


@login_required
@require_POST
def api_toggle_online(request):
    """API: Toggle online status."""
    if request.user.role != UserRole.COURIER:
        return JsonResponse({'error': 'Not a courier'}, status=403)
    
    new_status = AvailabilityService.toggle_online(request.user)
    
    return JsonResponse({
        'is_online': new_status,
        'message': 'En ligne' if new_status else 'Hors ligne'
    })


# ============================================
# WITHDRAWAL API ENDPOINTS
# ============================================

@login_required
@require_GET
def api_withdrawal_status(request):
    """API: Get withdrawal requests and eligibility."""
    if request.user.role != UserRole.COURIER:
        return JsonResponse({'error': 'Not a courier'}, status=403)
    
    from finance.models import WithdrawalRequest, WithdrawalService
    
    courier = request.user
    
    # Get recent withdrawals
    withdrawals = WithdrawalRequest.objects.filter(
        courier=courier
    ).order_by('-created_at')[:10]
    
    # Check if eligible for new withdrawal
    pending = WithdrawalRequest.objects.filter(
        courier=courier,
        status__in=['PENDING', 'PROCESSING']
    ).exists()
    
    can_withdraw = (
        courier.is_verified and
        not pending and
        courier.wallet_balance >= WithdrawalService.MINIMUM_WITHDRAWAL
    )
    
    return JsonResponse({
        'can_withdraw': can_withdraw,
        'balance': float(courier.wallet_balance),
        'minimum': float(WithdrawalService.MINIMUM_WITHDRAWAL),
        'maximum': float(WithdrawalService.MAXIMUM_WITHDRAWAL),
        'pending_request': pending,
        'recent_withdrawals': [
            {
                'id': str(w.id),
                'amount': float(w.amount),
                'status': w.status,
                'provider': w.provider,
                'created_at': w.created_at.isoformat(),
            }
            for w in withdrawals
        ]
    })


@login_required
@require_POST
def api_request_withdrawal(request):
    """API: Request a withdrawal."""
    if request.user.role != UserRole.COURIER:
        return JsonResponse({'error': 'Not a courier'}, status=403)
    
    from finance.models import WithdrawalService, MobileMoneyProvider
    from decimal import Decimal
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    amount = data.get('amount')
    provider = data.get('provider', 'MTN_MOMO')
    phone = data.get('phone_number')
    
    if not amount:
        return JsonResponse({'error': 'Montant requis'}, status=400)
    
    # Validate provider
    if provider not in [p.value for p in MobileMoneyProvider]:
        return JsonResponse({'error': 'Fournisseur invalide'}, status=400)
    
    try:
        withdrawal = WithdrawalService.create_request(
            courier=request.user,
            amount=Decimal(str(amount)),
            provider=provider,
            phone_number=phone
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Demande de retrait créée',
            'withdrawal': {
                'id': str(withdrawal.id),
                'amount': float(withdrawal.amount),
                'status': withdrawal.status,
                'provider': withdrawal.provider,
            }
        })
        
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Erreur serveur'}, status=500)

