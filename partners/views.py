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
            # List all API keys for this user (by name prefix)
            user_key_prefix = f"partner_{request.user.id}_"
            context['api_keys'] = APIKey.objects.filter(
                name__startswith=user_key_prefix,
                revoked=False
            ).order_by('-created')
            
            # ========================================
            # ANALYTICS: Get delivery stats for this partner
            # ========================================
            today = timezone.now().date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            partner_deliveries = Delivery.objects.filter(sender=request.user)
            
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
        
        # Generate new API key
        user_key_prefix = f"partner_{request.user.id}_"
        key_count = APIKey.objects.filter(name__startswith=user_key_prefix).count()
        key_name = f"{user_key_prefix}key_{key_count + 1}"
        
        api_key, key = APIKey.objects.create_key(name=key_name)
        
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
        
        user_key_prefix = f"partner_{request.user.id}_"
        
        try:
            api_key = APIKey.objects.get(
                pk=key_id,
                name__startswith=user_key_prefix
            )
            api_key.revoked = True
            api_key.save()
            messages.success(request, "🗑️ Clé API révoquée avec succès.")
        except APIKey.DoesNotExist:
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
        
        # Get partner's deliveries
        deliveries = Delivery.objects.filter(sender=request.user).order_by('-created_at')
        
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
        
        deliveries = Delivery.objects.filter(sender=request.user).order_by('-created_at')
        
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


