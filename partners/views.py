"""
Partners App Views - Partner Portal & API Key Management
"""
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import CreateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import models
from rest_framework_api_key.models import APIKey
from .models import PartnerAPIKey

from .forms import PartnerSignupForm
from core.models import UserRole



class PartnerLoginView(LoginView):
    """
    Partner login view.
    Redirects to dashboard on successful login.
    """
    
    template_name = 'partners/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('partners:dashboard')
    
    def form_invalid(self, form):
        messages.error(self.request, "Identifiants incorrects. Veuillez réessayer.")
        return super().form_invalid(form)


class PartnerLogoutView(LogoutView):
    """
    Partner logout view.
    Redirects to home page after logout.
    """
    
    next_page = reverse_lazy('home:home')




class PartnerSignupView(CreateView):
    """
    Partner registration view.
    Creates a BUSINESS user awaiting approval.
    """
    
    form_class = PartnerSignupForm
    template_name = 'partners/signup.html'
    success_url = reverse_lazy('partners:pending')
    
    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(
            self.request,
            "✅ Inscription réussie ! Votre compte est en attente de validation."
        )
        return redirect(self.success_url)


class PartnerPendingView(TemplateView):
    """
    Pending approval page for partners.
    """
    template_name = 'partners/pending.html'


class BusinessRequiredMixin(LoginRequiredMixin):
    """
    Mixin ensuring user is authenticated and has BUSINESS role.
    """
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if request.user.role != UserRole.BUSINESS:
            messages.error(request, "Accès réservé aux partenaires e-commerce.")
            return redirect('partners:signup')
        
        return super().dispatch(request, *args, **kwargs)


class PartnerDashboardView(BusinessRequiredMixin, View):
    """
    Partner dashboard with API key management and analytics.
    
    - If not approved: Shows pending message
    - If approved: Shows stats, API keys, orders, and financial info
    """
    
    template_name = 'partners/dashboard.html'
    
    def get(self, request):
        from django.utils import timezone
        from django.db.models import Count, Sum, Avg
        from django.db.models.functions import TruncDate
        from logistics.models import Delivery, DeliveryStatus
        from finance.models import Transaction
        from datetime import timedelta
        from decimal import Decimal
        
        context = {
            'is_approved': request.user.is_business_approved,
            'api_keys': [],
        }
        
        if request.user.is_business_approved:
            # List all API keys for this partner
            context['api_keys'] = PartnerAPIKey.objects.filter(
                partner=request.user,
                revoked=False
            ).order_by('-created')
            
            # ========================================
            # ANALYTICS: Get delivery stats for this partner
            # ========================================
            today = timezone.now().date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            partner_deliveries = Delivery.objects.filter(
                models.Q(sender=request.user) | models.Q(shop=request.user)
            )
            
            # Period filters
            today_deliveries = partner_deliveries.filter(created_at__date=today)
            week_deliveries = partner_deliveries.filter(created_at__date__gte=week_ago)
            month_deliveries = partner_deliveries.filter(created_at__date__gte=month_ago)
            
            # KPI: Total orders
            stats = {
                'today_orders': today_deliveries.count(),
                'week_orders': week_deliveries.count(),
                'month_orders': month_deliveries.count(),
                'total_orders': partner_deliveries.count(),
            }
            
            # KPI: Revenue (total_price sum)
            stats['today_revenue'] = today_deliveries.aggregate(
                total=Sum('total_price')
            )['total'] or Decimal('0')
            stats['week_revenue'] = week_deliveries.aggregate(
                total=Sum('total_price')
            )['total'] or Decimal('0')
            stats['month_revenue'] = month_deliveries.aggregate(
                total=Sum('total_price')
            )['total'] or Decimal('0')
            
            # KPI: Delivery success rate (completed vs total)
            completed = partner_deliveries.filter(status=DeliveryStatus.COMPLETED).count()
            total = partner_deliveries.exclude(status=DeliveryStatus.CANCELLED).count()
            stats['success_rate'] = round((completed / total * 100) if total > 0 else 0, 1)
            
            # KPI: Average delivery price
            stats['avg_order_value'] = partner_deliveries.aggregate(
                avg=Avg('total_price')
            )['avg'] or Decimal('0')
            
            # Chart: Daily orders for last 7 days
            daily_orders = week_deliveries.annotate(
                day=TruncDate('created_at')
            ).values('day').annotate(
                count=Count('id'),
                revenue=Sum('total_price')
            ).order_by('day')
            
            # Fill in missing days with zeros
            chart_data = []
            for i in range(7):
                day = today - timedelta(days=6-i)
                day_data = next((d for d in daily_orders if d['day'] == day), None)
                chart_data.append({
                    'date': day.strftime('%d/%m'),
                    'orders': day_data['count'] if day_data else 0,
                    'revenue': float(day_data['revenue']) if day_data else 0
                })
            
            stats['chart_data'] = chart_data
            
            # Top neighborhoods
            top_neighborhoods = partner_deliveries.values(
                'dropoff_neighborhood__name'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            stats['top_neighborhoods'] = [
                {'name': n['dropoff_neighborhood__name'] or 'GPS Direct', 'count': n['count']}
                for n in top_neighborhoods
            ]
            
            # Recent orders (last 5)
            stats['recent_orders'] = partner_deliveries.order_by('-created_at')[:5]
            
            # Financial info
            stats['wallet_balance'] = request.user.wallet_balance
            stats['debt_ceiling'] = request.user.debt_ceiling
            stats['recent_transactions'] = Transaction.objects.filter(
                user=request.user
            ).order_by('-created_at')[:5]
            
            context['stats'] = stats
        
        return render(request, self.template_name, context)

    
    def post(self, request):
        """Handle API key generation."""
        if not request.user.is_business_approved:
            messages.error(request, "Votre compte n'est pas encore validé.")
            return redirect('partners:dashboard')
        
        # Generate new API key linked to this partner
        key_count = PartnerAPIKey.objects.filter(partner=request.user).count()
        key_name = f"{request.user.full_name} - Clé #{key_count + 1}"
        
        api_key, key = PartnerAPIKey.objects.create_key(
            name=key_name,
            partner=request.user
        )
        
        # CRITICAL: Show the key only once via messages
        messages.success(
            request,
            f"🔑 Nouvelle clé API générée ! Copiez-la maintenant, elle ne sera plus visible : {key}"
        )
        
        return redirect('partners:dashboard')


class RevokeAPIKeyView(BusinessRequiredMixin, View):
    """
    Revoke an API key.
    """
    
    def post(self, request, key_id):
        if not request.user.is_business_approved:
            messages.error(request, "Compte non validé.")
            return redirect('partners:dashboard')
        
        
        try:
            api_key = PartnerAPIKey.objects.get(
                pk=key_id,
                partner=request.user  # Ownership check via FK
            )
            api_key.revoked = True
            api_key.save()
            messages.success(request, "🗑️ Clé API révoquée avec succès.")
        except PartnerAPIKey.DoesNotExist:
            messages.error(request, "Clé API non trouvée.")
        
        return redirect('partners:dashboard')


class PublicShopView(TemplateView):
    """
    Public checkout page for a shop (Hosted Checkout / Magic Link).
    
    Accessible WITHOUT login at: /book/<slug>/
    
    Business Logic:
    - Shop must exist and be approved
    - Shop wallet must be >= 0 (positive balance)
    - Displays order form with neighborhoods for dropdown
    """
    
    template_name = 'partners/public_checkout.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop_slug = self.kwargs.get('shop_slug')
        
        from core.models import User, UserRole
        from logistics.models import Neighborhood
        from django.shortcuts import get_object_or_404
        from django.http import Http404
        from decimal import Decimal
        
        # Get the shop by slug
        try:
            shop = User.objects.get(
                slug=shop_slug,
                role=UserRole.BUSINESS
            )
        except User.DoesNotExist:
            raise Http404("Boutique non trouvée")
        
        # Check if shop is approved
        if not shop.is_business_approved:
            raise Http404("Boutique non disponible")
        
        # Check wallet balance
        shop_unavailable = shop.wallet_balance < Decimal('0')
        
        # Get neighborhoods for dropdown
        neighborhoods = Neighborhood.objects.filter(
            is_active=True
        ).order_by('city', 'name')
        
        context.update({
            'shop': shop,
            'shop_unavailable': shop_unavailable,
            'neighborhoods': neighborhoods,
            'neighborhoods_by_city': self._group_neighborhoods_by_city(neighborhoods),
        })
        
        return context
    
    def _group_neighborhoods_by_city(self, neighborhoods):
        """Group neighborhoods by city for the select dropdown."""
        grouped = {}
        for n in neighborhoods:
            if n.city not in grouped:
                grouped[n.city] = []
            grouped[n.city].append(n)
        return grouped


# ============================================
# ORDERS HISTORY VIEW
# ============================================

class PartnerOrdersView(BusinessRequiredMixin, View):
    """
    Partner orders history with filtering, search, and pagination.
    """
    
    template_name = 'partners/orders.html'
    
    def get(self, request):
        from django.core.paginator import Paginator
        from django.utils import timezone
        from logistics.models import Delivery, DeliveryStatus
        from datetime import timedelta
        
        # Get partner's deliveries (via sender OR shop link)
        deliveries = Delivery.objects.filter(
            models.Q(sender=request.user) | models.Q(shop=request.user)
        ).order_by('-created_at')
        
        # Apply filters
        status_filter = request.GET.get('status', '')
        date_filter = request.GET.get('date', '')
        search = request.GET.get('search', '')
        
        if status_filter:
            deliveries = deliveries.filter(status=status_filter)
        
        if date_filter:
            today = timezone.now().date()
            if date_filter == 'today':
                deliveries = deliveries.filter(created_at__date=today)
            elif date_filter == 'week':
                deliveries = deliveries.filter(created_at__date__gte=today - timedelta(days=7))
            elif date_filter == 'month':
                deliveries = deliveries.filter(created_at__date__gte=today - timedelta(days=30))
        
        if search:
            deliveries = deliveries.filter(
                models.Q(recipient_name__icontains=search) |
                models.Q(recipient_phone__icontains=search) |
                models.Q(dropoff_address__icontains=search)
            )
        
        # Pagination
        paginator = Paginator(deliveries, 20)
        page = request.GET.get('page', 1)
        deliveries_page = paginator.get_page(page)
        
        context = {
            'deliveries': deliveries_page,
            'status_filter': status_filter,
            'date_filter': date_filter,
            'search': search,
            'status_choices': DeliveryStatus.choices,
            'total_count': paginator.count,
        }
        
        return render(request, self.template_name, context)


class PartnerOrderExportView(BusinessRequiredMixin, View):
    """
    Export partner orders to CSV.
    """
    
    def get(self, request):
        import csv
        from django.http import HttpResponse
        from logistics.models import Delivery
        
        deliveries = Delivery.objects.filter(
            models.Q(sender=request.user) | models.Q(shop=request.user)
        ).order_by('-created_at')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="delivr_orders.csv"'
        response.write('\ufeff')  # BOM for Excel
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Date', 'Destinataire', 'Téléphone', 'Adresse',
            'Statut', 'Prix (XAF)', 'Coursier'
        ])
        
        for d in deliveries:
            writer.writerow([
                str(d.id)[:8],
                d.created_at.strftime('%d/%m/%Y %H:%M'),
                d.recipient_name,
                d.recipient_phone,
                d.dropoff_address or 'GPS',
                d.get_status_display(),
                float(d.total_price),
                d.courier.full_name if d.courier else '-'
            ])
        
        return response


# ============================================
# WEBHOOKS CONFIGURATION VIEW
# ============================================

class PartnerWebhooksView(BusinessRequiredMixin, View):
    """
    Configure webhooks for delivery events.
    """
    
    template_name = 'partners/webhooks.html'
    
    def get(self, request):
        from .models import WebhookConfig
        
        # Get or create webhook config for this user
        config, created = WebhookConfig.objects.get_or_create(
            user=request.user,
            defaults={'events': ['order.created', 'order.completed']}
        )
        
        context = {
            'config': config,
            'available_events': [
                ('order.created', 'Nouvelle commande', 'Déclenché quand une commande est créée'),
                ('order.assigned', 'Coursier assigné', 'Déclenché quand un coursier accepte'),
                ('order.picked_up', 'Colis récupéré', 'Déclenché au ramassage'),
                ('order.completed', 'Livraison terminée', 'Déclenché à la livraison'),
                ('order.cancelled', 'Commande annulée', 'Déclenché en cas d\'annulation'),
            ],
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        from .models import WebhookConfig
        import secrets
        
        config, _ = WebhookConfig.objects.get_or_create(user=request.user)
        
        action = request.POST.get('action')
        
        if action == 'save':
            config.url = request.POST.get('url', '')
            config.events = request.POST.getlist('events')
            config.is_active = bool(request.POST.get('is_active'))
            config.save()
            messages.success(request, '✅ Configuration webhook sauvegardée !')
        
        elif action == 'regenerate_secret':
            config.secret = secrets.token_hex(32)
            config.save()
            messages.success(request, f'🔑 Nouveau secret: {config.secret}')
        
        elif action == 'test':
            # Test webhook
            from .services import WebhookService
            success, message = WebhookService.test_webhook(config)
            if success:
                messages.success(request, f'✅ Test réussi: {message}')
            else:
                messages.error(request, f'❌ Échec: {message}')
        
        return redirect('partners:webhooks')


# ============================================
# BRANDING / CUSTOMIZATION VIEW
# ============================================

class PartnerBrandingView(BusinessRequiredMixin, View):
    """
    Customize checkout page branding.
    """
    
    template_name = 'partners/branding.html'
    
    def get(self, request):
        context = {
            'user': request.user,
            'preview_url': f'/book/{request.user.slug}/' if request.user.slug else None,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        user = request.user
        
        # Update branding fields
        user.brand_color = request.POST.get('brand_color', '#00d084')
        user.welcome_message = request.POST.get('welcome_message', '')
        
        # Handle logo upload
        if 'shop_logo' in request.FILES:
            user.shop_logo = request.FILES['shop_logo']
        
        user.save()
        messages.success(request, '✅ Personnalisation sauvegardée !')
        
        return redirect('partners:branding')


# ============================================
# INVOICES / BILLING VIEW
# ============================================

class PartnerInvoicesView(BusinessRequiredMixin, View):
    """
    Partner invoices list with filtering and download.
    """
    
    template_name = 'partners/invoices.html'
    
    def get(self, request):
        from django.core.paginator import Paginator
        from finance.models import Invoice, InvoiceType
        
        # Get partner's invoices
        invoices = Invoice.objects.filter(user=request.user).order_by('-created_at')
        
        # Apply filters
        type_filter = request.GET.get('type', '')
        year_filter = request.GET.get('year', '')
        
        if type_filter:
            invoices = invoices.filter(invoice_type=type_filter)
        
        if year_filter:
            invoices = invoices.filter(created_at__year=int(year_filter))
        
        # Get available years for filter
        years = Invoice.objects.filter(user=request.user).dates('created_at', 'year')
        
        # Pagination
        paginator = Paginator(invoices, 20)
        page = request.GET.get('page', 1)
        invoices_page = paginator.get_page(page)
        
        # Summary stats
        from django.db.models import Sum
        total_amount = invoices.aggregate(total=Sum('amount'))['total'] or 0
        
        context = {
            'invoices': invoices_page,
            'type_filter': type_filter,
            'year_filter': year_filter,
            'type_choices': InvoiceType.choices,
            'years': [y.year for y in years],
            'total_count': paginator.count,
            'total_amount': total_amount,
        }
        
        return render(request, self.template_name, context)


# ============================================
# TRACKING VIEW - Real-time delivery map
# ============================================

class PartnerTrackingView(BusinessRequiredMixin, View):
    """
    Real-time tracking of partner's active deliveries on a map.
    """
    
    template_name = 'partners/tracking.html'
    
    def get(self, request):
        from logistics.models import Delivery, DeliveryStatus
        
        # Get active deliveries (in progress)
        active_statuses = [
            DeliveryStatus.ASSIGNED,
            DeliveryStatus.EN_ROUTE_PICKUP,
            DeliveryStatus.ARRIVED_PICKUP,
            DeliveryStatus.PICKED_UP,
            DeliveryStatus.IN_TRANSIT,
            DeliveryStatus.ARRIVED_DROPOFF,
        ]
        
        active_deliveries = Delivery.objects.filter(
            models.Q(sender=request.user) | models.Q(shop=request.user),
            status__in=active_statuses
        ).select_related('courier', 'pickup_neighborhood', 'dropoff_neighborhood').order_by('-created_at')
        
        # Build deliveries data for map
        deliveries_data = []
        for d in active_deliveries:
            deliveries_data.append({
                'id': str(d.id),
                'tracking_code': d.tracking_code if hasattr(d, 'tracking_code') else str(d.id)[:8].upper(),
                'status': d.status,
                'status_display': d.get_status_display(),
                'recipient_name': d.recipient_name,
                'recipient_phone': d.recipient_phone,
                'pickup_address': d.pickup_address or (d.pickup_neighborhood.name if d.pickup_neighborhood else 'GPS'),
                'dropoff_address': d.dropoff_address or (d.dropoff_neighborhood.name if d.dropoff_neighborhood else 'GPS'),
                'pickup_lat': float(d.pickup_lat) if d.pickup_lat else None,
                'pickup_lng': float(d.pickup_lng) if d.pickup_lng else None,
                'dropoff_lat': float(d.dropoff_lat) if d.dropoff_lat else None,
                'dropoff_lng': float(d.dropoff_lng) if d.dropoff_lng else None,
                'courier_name': d.courier.full_name if d.courier else None,
                'courier_phone': d.courier.phone_number if d.courier else None,
                'courier_lat': float(d.courier.last_lat) if d.courier and d.courier.last_lat else None,
                'courier_lng': float(d.courier.last_lng) if d.courier and d.courier.last_lng else None,
                'created_at': d.created_at.isoformat(),
            })
        
        import json
        context = {
            'active_deliveries': active_deliveries,
            'deliveries_json': json.dumps(deliveries_data),
            'total_active': len(deliveries_data),
        }
        
        return render(request, self.template_name, context)


# ============================================
# ANALYTICS VIEW - Advanced statistics
# ============================================

class PartnerAnalyticsView(BusinessRequiredMixin, View):
    """
    Advanced analytics with filters and charts.
    """
    
    template_name = 'partners/analytics.html'
    
    def get(self, request):
        from django.utils import timezone
        from django.db.models import Count, Sum, Avg
        from django.db.models.functions import TruncDate, TruncHour, ExtractHour
        from logistics.models import Delivery, DeliveryStatus
        from datetime import timedelta
        from decimal import Decimal
        import json
        
        # Get period filter
        period = request.GET.get('period', 'month')
        today = timezone.now().date()
        
        if period == 'week':
            start_date = today - timedelta(days=7)
        elif period == 'quarter':
            start_date = today - timedelta(days=90)
        elif period == 'year':
            start_date = today - timedelta(days=365)
        else:  # month
            start_date = today - timedelta(days=30)
        
        # Base queryset
        deliveries = Delivery.objects.filter(
            models.Q(sender=request.user) | models.Q(shop=request.user),
            created_at__date__gte=start_date
        )
        
        # ========================================
        # KPIs
        # ========================================
        stats = {}
        
        stats['total_orders'] = deliveries.count()
        stats['completed_orders'] = deliveries.filter(status=DeliveryStatus.COMPLETED).count()
        stats['cancelled_orders'] = deliveries.filter(status=DeliveryStatus.CANCELLED).count()
        
        stats['total_revenue'] = deliveries.aggregate(
            total=Sum('total_price')
        )['total'] or Decimal('0')
        
        stats['avg_order_value'] = deliveries.aggregate(
            avg=Avg('total_price')
        )['avg'] or Decimal('0')
        
        # Success rate
        non_cancelled = deliveries.exclude(status=DeliveryStatus.CANCELLED).count()
        completed = stats['completed_orders']
        stats['success_rate'] = round((completed / non_cancelled * 100) if non_cancelled > 0 else 0, 1)
        
        # ========================================
        # Chart: Daily orders
        # ========================================
        daily_orders = deliveries.annotate(
            day=TruncDate('created_at')
        ).values('day').annotate(
            count=Count('id'),
            revenue=Sum('total_price')
        ).order_by('day')
        
        daily_chart = [
            {
                'date': d['day'].strftime('%d/%m'),
                'orders': d['count'],
                'revenue': float(d['revenue'] or 0)
            }
            for d in daily_orders
        ]
        
        # ========================================
        # Chart: Orders by hour (peak hours)
        # ========================================
        hourly_orders = deliveries.annotate(
            hour=ExtractHour('created_at')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        hourly_chart = {d['hour']: d['count'] for d in hourly_orders}
        hourly_data = [hourly_chart.get(h, 0) for h in range(24)]
        
        # ========================================
        # Chart: Orders by neighborhood
        # ========================================
        neighborhood_orders = deliveries.values(
            'dropoff_neighborhood__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        neighborhood_chart = [
            {
                'name': n['dropoff_neighborhood__name'] or 'GPS Direct',
                'count': n['count']
            }
            for n in neighborhood_orders
        ]
        
        # ========================================
        # Chart: Orders by status
        # ========================================
        status_orders = deliveries.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        status_chart = [
            {
                'status': s['status'],
                'label': dict(DeliveryStatus.choices).get(s['status'], s['status']),
                'count': s['count']
            }
            for s in status_orders
        ]
        
        context = {
            'stats': stats,
            'period': period,
            'start_date': start_date,
            'daily_chart_json': json.dumps(daily_chart),
            'hourly_data_json': json.dumps(hourly_data),
            'neighborhood_chart_json': json.dumps(neighborhood_chart),
            'status_chart_json': json.dumps(status_chart),
        }
        
        return render(request, self.template_name, context)


# ============================================
# NOTIFICATIONS VIEW - Event history
# ============================================

class PartnerNotificationsView(BusinessRequiredMixin, View):
    """
    Partner notifications history.
    """
    
    template_name = 'partners/notifications.html'
    
    def get(self, request):
        from django.core.paginator import Paginator
        from .models import PartnerNotification, NotificationType
        
        # Get partner's notifications
        notifications = PartnerNotification.objects.filter(
            user=request.user
        ).order_by('-created_at')
        
        # Filter by type
        type_filter = request.GET.get('type', '')
        if type_filter:
            notifications = notifications.filter(notification_type=type_filter)
        
        # Filter by read status
        read_filter = request.GET.get('read', '')
        if read_filter == 'unread':
            notifications = notifications.filter(is_read=False)
        elif read_filter == 'read':
            notifications = notifications.filter(is_read=True)
        
        # Pagination
        paginator = Paginator(notifications, 20)
        page = request.GET.get('page', 1)
        notifications_page = paginator.get_page(page)
        
        # Unread count
        unread_count = PartnerNotification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        context = {
            'notifications': notifications_page,
            'type_filter': type_filter,
            'read_filter': read_filter,
            'type_choices': NotificationType.choices,
            'total_count': paginator.count,
            'unread_count': unread_count,
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        from .models import PartnerNotification
        
        action = request.POST.get('action')
        
        if action == 'mark_read':
            notification_id = request.POST.get('notification_id')
            PartnerNotification.objects.filter(
                id=notification_id,
                user=request.user
            ).update(is_read=True)
            
        elif action == 'mark_all_read':
            PartnerNotification.objects.filter(
                user=request.user,
                is_read=False
            ).update(is_read=True)
            messages.success(request, '✅ Toutes les notifications marquées comme lues.')
        
        return redirect('partners:notifications')


class PartnerOrderDetailView(BusinessRequiredMixin, View):
    """
    Detailed view of a single order.
    Shows timeline, courier info, OTPs, financial breakdown, and tracking.
    """
    
    template_name = 'partners/order_detail.html'
    
    def get(self, request, order_id):
        from logistics.models import Delivery, DeliveryStatus
        
        try:
            delivery = Delivery.objects.select_related(
                'courier', 'sender', 'shop',
                'pickup_neighborhood', 'dropoff_neighborhood'
            ).get(
                models.Q(sender=request.user) | models.Q(shop=request.user),
                pk=order_id
            )
        except Delivery.DoesNotExist:
            messages.error(request, "Commande non trouvée.")
            return redirect('partners:orders')
        
        # Build timeline events
        timeline = []
        timeline.append({
            'icon': '📝', 'label': 'Commande créée',
            'time': delivery.created_at, 'done': True
        })
        if delivery.assigned_at:
            courier_name = delivery.courier.full_name if delivery.courier else 'Coursier'
            timeline.append({
                'icon': '🏍️', 'label': f'Coursier assigné ({courier_name})',
                'time': delivery.assigned_at, 'done': True
            })
        elif delivery.status == DeliveryStatus.PENDING:
            timeline.append({
                'icon': '🔍', 'label': 'Recherche d\'un coursier...',
                'time': None, 'done': False
            })
        if delivery.picked_up_at:
            timeline.append({
                'icon': '📦', 'label': 'Colis récupéré',
                'time': delivery.picked_up_at, 'done': True
            })
        if delivery.in_transit_at:
            timeline.append({
                'icon': '🚀', 'label': 'En route vers le destinataire',
                'time': delivery.in_transit_at, 'done': True
            })
        if delivery.completed_at:
            timeline.append({
                'icon': '✅', 'label': 'Livraison confirmée',
                'time': delivery.completed_at, 'done': True
            })
        if delivery.status == DeliveryStatus.CANCELLED:
            timeline.append({
                'icon': '❌', 'label': 'Commande annulée',
                'time': None, 'done': True
            })
        
        # Get related transactions
        from finance.models import Transaction
        transactions = Transaction.objects.filter(
            delivery=delivery
        ).order_by('created_at')
        
        # Get related ratings
        from logistics.models import Rating
        ratings = Rating.objects.filter(delivery=delivery)
        
        context = {
            'delivery': delivery,
            'timeline': timeline,
            'transactions': transactions,
            'ratings': ratings,
            'tracking_url': f"/api/track/{delivery.id}/",
        }
        
        return render(request, self.template_name, context)


class PartnerProfileView(BusinessRequiredMixin, View):
    """
    Partner profile and settings page.
    Allows editing: name, phone, GPS location, password.
    """
    
    template_name = 'partners/profile.html'
    
    def get(self, request):
        from finance.models import Transaction
        
        # Last transactions for activity summary
        recent_transactions = Transaction.objects.filter(
            user=request.user
        ).order_by('-created_at')[:5]
        
        context = {
            'user': request.user,
            'recent_transactions': recent_transactions,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        from django.contrib.auth import get_user_model, update_session_auth_hash
        from django.contrib.gis.geos import Point
        
        User = get_user_model()
        user = request.user
        action = request.POST.get('action', 'update_profile')
        
        if action == 'update_profile':
            full_name = request.POST.get('full_name', '').strip()
            
            if full_name:
                user.full_name = full_name
            
            # GPS Location
            lat = request.POST.get('latitude', '').strip()
            lng = request.POST.get('longitude', '').strip()
            if lat and lng:
                try:
                    lat_f = float(lat)
                    lng_f = float(lng)
                    user.last_location = Point(lng_f, lat_f, srid=4326)
                    from django.utils import timezone
                    user.last_location_updated = timezone.now()
                except (ValueError, TypeError):
                    messages.error(request, "Coordonnées GPS invalides.")
                    return redirect('partners:profile')
            
            # Welcome message
            welcome_msg = request.POST.get('welcome_message', '').strip()
            user.welcome_message = welcome_msg
            
            user.save()
            messages.success(request, "✅ Profil mis à jour avec succès.")
        
        elif action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            
            if not user.check_password(current_password):
                messages.error(request, "❌ Mot de passe actuel incorrect.")
                return redirect('partners:profile')
            
            if len(new_password) < 8:
                messages.error(request, "❌ Le nouveau mot de passe doit contenir au moins 8 caractères.")
                return redirect('partners:profile')
            
            if new_password != confirm_password:
                messages.error(request, "❌ Les mots de passe ne correspondent pas.")
                return redirect('partners:profile')
            
            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, "✅ Mot de passe modifié avec succès.")
        
        return redirect('partners:profile')


class PartnerWalletView(BusinessRequiredMixin, View):
    """
    Wallet management page.
    Shows balance, transaction history, and allows deposit requests.
    """
    
    template_name = 'partners/wallet.html'
    
    def get(self, request):
        from finance.models import Transaction, TransactionType
        from django.core.paginator import Paginator
        
        # Get all transactions for this user
        transactions = Transaction.objects.filter(
            user=request.user
        ).order_by('-created_at')
        
        # Filter by type
        tx_type = request.GET.get('type', '')
        if tx_type:
            transactions = transactions.filter(transaction_type=tx_type)
        
        # Pagination
        paginator = Paginator(transactions, 20)
        page = request.GET.get('page', 1)
        transactions_page = paginator.get_page(page)
        
        # Summary stats
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        month_ago = today - timedelta(days=30)
        
        month_txs = Transaction.objects.filter(
            user=request.user,
            created_at__date__gte=month_ago
        )
        
        total_debits = month_txs.filter(
            amount__lt=0
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        total_credits = month_txs.filter(
            amount__gt=0
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        tx_count = month_txs.count()
        
        context = {
            'transactions': transactions_page,
            'tx_type': tx_type,
            'type_choices': TransactionType.choices,
            'total_count': paginator.count,
            'balance': request.user.wallet_balance,
            'total_debits': abs(total_debits),
            'total_credits': total_credits,
            'tx_count': tx_count,
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Handle deposit requests (manual for now, MoMo in future)."""
        from decimal import Decimal, InvalidOperation
        
        action = request.POST.get('action', '')
        
        if action == 'request_deposit':
            amount_str = request.POST.get('amount', '').strip()
            method = request.POST.get('method', 'MTN_MOMO')
            
            try:
                amount = Decimal(amount_str)
                if amount < Decimal('1000'):
                    messages.error(request, "❌ Montant minimum : 1 000 XAF")
                    return redirect('partners:wallet')
                if amount > Decimal('5000000'):
                    messages.error(request, "❌ Montant maximum : 5 000 000 XAF")
                    return redirect('partners:wallet')
            except (InvalidOperation, ValueError):
                messages.error(request, "❌ Montant invalide.")
                return redirect('partners:wallet')
            
            # Create a pending notification for admin
            from .models import PartnerNotification, NotificationType
            
            PartnerNotification.objects.create(
                user=request.user,
                notification_type=NotificationType.SYSTEM,
                title="Demande de rechargement wallet",
                message=(
                    f"Montant : {amount:,.0f} XAF\n"
                    f"Méthode : {method}\n"
                    f"Numéro : {request.user.phone_number}\n\n"
                    f"En attente de confirmation par l'équipe DELIVR-CM."
                ),
            )
            
            messages.success(
                request,
                f"✅ Demande de rechargement de {amount:,.0f} XAF enregistrée. "
                f"Notre équipe vous contactera via WhatsApp pour finaliser le paiement."
            )
        
        return redirect('partners:wallet')
