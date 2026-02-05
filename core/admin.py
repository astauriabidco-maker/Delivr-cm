"""
Django Admin configuration for CORE app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserRole


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
    actions = ['block_users', 'unblock_users', 'reset_debt_ceiling', 'approve_partners']

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
        """
        Approve business partners for API access.
        Sends a notification email (console print for now).
        """
        partners = queryset.filter(role=UserRole.BUSINESS, is_business_approved=False)
        updated = 0
        
        for partner in partners:
            partner.is_business_approved = True
            partner.save(update_fields=['is_business_approved'])
            updated += 1
            
            # Simulated email notification (print to console)
            print(f"""
            ═══════════════════════════════════════════
            📧 EMAIL NOTIFICATION (Simulation)
            ═══════════════════════════════════════════
            À: {partner.phone_number}
            Objet: 🎉 Votre compte DELIVR-CM est approuvé !
            
            Bonjour {partner.full_name},
            
            Bonne nouvelle ! Votre compte partenaire DELIVR-CM 
            a été validé par notre équipe.
            
            Vous pouvez maintenant :
            ✅ Générer vos clés API
            ✅ Intégrer notre service à votre boutique
            ✅ Consulter la documentation technique
            
            Connectez-vous : http://localhost:8000/partners/dashboard/
            
            L'équipe DELIVR-CM 🚀
            ═══════════════════════════════════════════
            """)
        
        self.message_user(
            request, 
            f"✅ {updated} partenaire(s) approuvé(s). Notifications envoyées."
        )


