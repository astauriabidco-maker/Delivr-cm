"""
Django Admin configuration for FINANCE app.
"""

from django.contrib import admin
from .models import Transaction, TransactionType, TransactionStatus


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin for Transaction with audit trail."""
    
    list_display = (
        'short_id',
        'user_phone',
        'transaction_type',
        'formatted_amount',
        'balance_after',
        'status',
        'delivery_link',
        'created_at'
    )
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = (
        'id',
        'user__phone_number',
        'reference',
        'description'
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'id',
        'user',
        'transaction_type',
        'amount',
        'balance_before',
        'balance_after',
        'delivery',
        'created_at'
    )
    
    fieldsets = (
        ('Transaction', {
            'fields': ('id', 'user', 'transaction_type', 'status')
        }),
        ('Montants', {
            'fields': ('amount', 'balance_before', 'balance_after')
        }),
        ('Détails', {
            'fields': ('description', 'reference', 'delivery')
        }),
        ('Historique', {
            'fields': ('created_at',)
        }),
    )

    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = "ID"

    def user_phone(self, obj):
        return obj.user.phone_number
    user_phone.short_description = "Utilisateur"

    def formatted_amount(self, obj):
        """Format amount with sign and color indicator."""
        sign = '+' if obj.amount >= 0 else ''
        return f"{sign}{obj.amount} XAF"
    formatted_amount.short_description = "Montant"

    def delivery_link(self, obj):
        if obj.delivery:
            return str(obj.delivery.id)[:8]
        return "-"
    delivery_link.short_description = "Livraison"

    def has_add_permission(self, request):
        """Transactions should be created programmatically only."""
        return False

    def has_change_permission(self, request, obj=None):
        """Transactions are immutable."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Transactions cannot be deleted for audit trail."""
        return False
