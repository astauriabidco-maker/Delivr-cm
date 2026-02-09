"""
Django Admin configuration for CORE app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserRole, AdminActivityLog, PromoCode


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model with phone-based auth."""
    
    list_display = (
        'phone_number', 
        'full_name', 
        'role', 
        'wallet_balance',
        'debt_ceiling',
        'is_verified',
        'is_business_approved',
        'is_courier_blocked',
        'is_active',
        'date_joined'
    )
    list_filter = ('role', 'is_verified', 'is_business_approved', 'is_active', 'is_staff')
    search_fields = ('phone_number', 'full_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {
            'fields': ('phone_number', 'password')
        }),
        ('Profil', {
            'fields': ('full_name', 'role')
        }),
        ('Wallet & Dette', {
            'fields': ('wallet_balance', 'debt_ceiling'),
            'description': 'Solde négatif = Dette pour les coursiers'
        }),
        ('Partenaire E-commerce', {
            'fields': ('is_business_approved', 'slug'),
            'description': 'Approuver pour donner accès aux clés API. Le slug génère l\'URL publique.'
        }),
        ('Vérification Coursier', {
            'fields': ('is_verified', 'cni_document', 'moto_document'),
            'classes': ('collapse',)
        }),
        ('Localisation', {
            'fields': ('last_location', 'last_location_updated'),
            'classes': ('collapse',)
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'role', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_location_updated')
    
    # Bulk actions
    actions = [
        'block_users', 'unblock_users', 'reset_debt_ceiling',
        'approve_partners', 'export_users_csv'
    ]

    def is_courier_blocked(self, obj):
        """Display if courier is blocked due to debt."""
        if obj.role == UserRole.COURIER:
            return obj.is_courier_blocked
        return None
    is_courier_blocked.boolean = True
    is_courier_blocked.short_description = "Bloqué (dette)"
    
    @admin.action(description="🚫 Bloquer les utilisateurs sélectionnés")
    def block_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"✅ {updated} utilisateur(s) bloqué(s).")
    
    @admin.action(description="✅ Débloquer les utilisateurs sélectionnés")
    def unblock_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"✅ {updated} utilisateur(s) débloqué(s).")
    
    @admin.action(description="💰 Réinitialiser le plafond de dette (2500 XAF)")
    def reset_debt_ceiling(self, request, queryset):
        from decimal import Decimal
        updated = queryset.filter(role=UserRole.COURIER).update(
            debt_ceiling=Decimal('2500.00')
        )
        self.message_user(request, f"✅ Plafond de dette réinitialisé pour {updated} coursier(s).")

    @admin.action(description="🤝 Approuver les Partenaires E-commerce")
    def approve_partners(self, request, queryset):
        partners = queryset.filter(role=UserRole.BUSINESS, is_business_approved=False)
        updated = partners.update(is_business_approved=True)
        self.message_user(request, f"✅ {updated} partenaire(s) approuvé(s).")

    @admin.action(description="📥 Exporter en CSV")
    def export_users_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="utilisateurs_delivr.csv"'
        response.write('\ufeff')  # BOM for Excel UTF-8
        
        writer = csv.writer(response)
        writer.writerow([
            'Téléphone', 'Nom', 'Rôle', 'Solde Wallet', 'Vérifié',
            'Approuvé', 'Actif', 'En ligne', 'Note', 'Livraisons', 'Date inscription'
        ])
        
        for user in queryset:
            writer.writerow([
                user.phone_number,
                user.full_name,
                user.get_role_display(),
                f"{user.wallet_balance} XAF",
                'Oui' if user.is_verified else 'Non',
                'Oui' if user.is_business_approved else 'Non',
                'Oui' if user.is_active else 'Non',
                'Oui' if user.is_online else 'Non',
                f"{user.average_rating}/5",
                user.total_deliveries_completed,
                user.date_joined.strftime('%d/%m/%Y %H:%M'),
            ])
        
        AdminActivityLog.log(
            user=request.user,
            action=AdminActivityLog.ActionType.EXPORT,
            target_model='User',
            details={'count': queryset.count()},
        )
        return response


# ===========================================
# ADMIN ACTIVITY LOG
# ===========================================

@admin.register(AdminActivityLog)
class AdminActivityLogAdmin(admin.ModelAdmin):
    """Read-only admin for audit trail."""
    
    list_display = (
        'created_at',
        'user_display',
        'action_badge',
        'target_model',
        'target_id_short',
        'ip_address',
    )
    list_filter = ('action', 'target_model', 'created_at')
    search_fields = (
        'user__phone_number',
        'user__full_name',
        'target_model',
        'target_id',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'user', 'action', 'target_model', 'target_id',
        'details', 'ip_address', 'created_at',
    )
    
    def user_display(self, obj):
        if obj.user:
            return obj.user.full_name or obj.user.phone_number
        return "Système"
    user_display.short_description = "Admin"
    
    def action_badge(self, obj):
        from django.utils.html import format_html
        colors = {
            'CREATE': '#10b981', 'UPDATE': '#3b82f6', 'DELETE': '#ef4444',
            'APPROVE': '#059669', 'REJECT': '#dc2626', 'BLOCK': '#f59e0b',
            'UNBLOCK': '#8b5cf6', 'EXPORT': '#6366f1', 'IMPORT': '#0891b2',
            'LOGIN': '#6b7280',
        }
        color = colors.get(obj.action, '#6b7280')
        return format_html(
            '<span style="padding:2px 6px;border-radius:8px;color:white;background:{};font-size:11px;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = "Action"
    
    def target_id_short(self, obj):
        return obj.target_id[:8] if obj.target_id else "—"
    target_id_short.short_description = "ID"
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ===========================================
# PROMO CODE ADMIN
# ===========================================

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    """Admin for promotional codes."""
    
    list_display = (
        'code',
        'discount_display',
        'usage_display',
        'validity_badge',
        'valid_from',
        'valid_until',
        'is_active',
    )
    list_filter = ('discount_type', 'is_active', 'valid_from')
    search_fields = ('code', 'description')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Code Promo', {
            'fields': ('code', 'description', 'is_active')
        }),
        ('Remise', {
            'fields': ('discount_type', 'discount_value', 'max_discount_amount', 'min_order_amount')
        }),
        ('Limites', {
            'fields': ('max_uses', 'current_uses', 'valid_from', 'valid_until')
        }),
        ('Métadonnées', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('current_uses', 'created_at')
    actions = ['activate_codes', 'deactivate_codes']
    
    def discount_display(self, obj):
        if obj.discount_type == PromoCode.DiscountType.PERCENTAGE:
            return f"{obj.discount_value}%"
        return f"{obj.discount_value:,.0f} XAF"
    discount_display.short_description = "Remise"
    
    def usage_display(self, obj):
        limit = obj.max_uses if obj.max_uses > 0 else '∞'
        return f"{obj.current_uses}/{limit}"
    usage_display.short_description = "Utilisation"
    
    def validity_badge(self, obj):
        from django.utils.html import format_html
        if obj.is_valid:
            return format_html(
                '<span style="padding:2px 6px;border-radius:8px;color:white;background:#10b981;font-size:11px;">✅ Valide</span>'
            )
        return format_html(
            '<span style="padding:2px 6px;border-radius:8px;color:white;background:#ef4444;font-size:11px;">❌ Expiré</span>'
        )
    validity_badge.short_description = "Statut"
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    @admin.action(description="✅ Activer les codes sélectionnés")
    def activate_codes(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"✅ {updated} code(s) activé(s).")
    
    @admin.action(description="❌ Désactiver les codes sélectionnés")
    def deactivate_codes(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"❌ {updated} code(s) désactivé(s).")
