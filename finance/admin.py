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


# ===========================================
# INVOICE ADMIN
# ===========================================

from .models import Invoice, InvoiceType


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin for Invoice/Receipt management."""
    
    list_display = (
        'invoice_number',
        'invoice_type',
        'user_display',
        'amount_display',
        'period_display',
        'has_pdf',
        'created_at'
    )
    list_filter = ('invoice_type', 'created_at')
    search_fields = (
        'invoice_number',
        'user__phone_number',
        'user__full_name',
        'description'
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'id',
        'invoice_number',
        'invoice_type',
        'user',
        'delivery',
        'amount',
        'period_start',
        'period_end',
        'pdf_file',
        'created_at'
    )
    
    fieldsets = (
        ('Facture', {
            'fields': ('id', 'invoice_number', 'invoice_type')
        }),
        ('Destinataire', {
            'fields': ('user', 'delivery')
        }),
        ('Montants', {
            'fields': ('amount', 'period_start', 'period_end')
        }),
        ('Document', {
            'fields': ('pdf_file', 'description')
        }),
        ('Historique', {
            'fields': ('created_at',)
        }),
    )
    
    actions = ['regenerate_pdf']
    
    def user_display(self, obj):
        return obj.user.phone_number
    user_display.short_description = "Utilisateur"
    
    def amount_display(self, obj):
        return f"{obj.amount:,.0f} XAF"
    amount_display.short_description = "Montant"
    
    def period_display(self, obj):
        if obj.period_start and obj.period_end:
            return f"{obj.period_start.strftime('%d/%m')} - {obj.period_end.strftime('%d/%m/%Y')}"
        return "-"
    period_display.short_description = "Période"
    
    def has_pdf(self, obj):
        return bool(obj.pdf_file)
    has_pdf.boolean = True
    has_pdf.short_description = "PDF"
    
    def regenerate_pdf(self, request, queryset):
        """Regenerate PDF for selected invoices."""
        from .invoice_service import InvoiceService
        
        count = 0
        for invoice in queryset:
            try:
                if invoice.invoice_type == InvoiceType.DELIVERY_RECEIPT and invoice.delivery:
                    context = InvoiceService._get_delivery_receipt_context(invoice.delivery)
                    pdf_content = InvoiceService._render_pdf(
                        'finance/pdf/delivery_receipt.html', context
                    )
                    invoice.pdf_file.save(
                        f"receipt_{invoice.invoice_number}.pdf",
                        ContentFile(pdf_content),
                        save=True
                    )
                    count += 1
            except Exception as e:
                self.message_user(request, f"Erreur {invoice.invoice_number}: {e}", level='error')
        
        self.message_user(request, f"{count} PDF régénéré(s) avec succès")
    regenerate_pdf.short_description = "Régénérer le PDF"
    
    def has_add_permission(self, request):
        """Invoices are created programmatically."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Invoices are immutable."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Invoices can be deleted by superusers only."""
        return request.user.is_superuser

