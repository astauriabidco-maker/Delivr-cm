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
        'is_verified',
        'is_courier_blocked',
        'is_active',
        'date_joined'
    )
    list_filter = ('role', 'is_verified', 'is_active', 'is_staff')
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

    def is_courier_blocked(self, obj):
        """Display if courier is blocked due to debt."""
        if obj.role == UserRole.COURIER:
            return obj.is_courier_blocked
        return None
    is_courier_blocked.boolean = True
    is_courier_blocked.short_description = "Bloqué (dette)"
