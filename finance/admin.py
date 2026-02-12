"""
Django Admin configuration for FINANCE app.
"""

from django.contrib import admin
from django.core.files.base import ContentFile
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
    
    actions = ['export_transactions_csv']
    
    @admin.action(description="📥 Exporter en CSV")
    def export_transactions_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions_delivr.csv"'
        response.write('\ufeff')
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Utilisateur', 'Type', 'Montant', 'Solde avant', 'Solde après',
            'Statut', 'Description', 'Référence', 'Date'
        ])
        
        for t in queryset.select_related('user'):
            writer.writerow([
                str(t.id)[:8],
                t.user.phone_number,
                t.get_transaction_type_display(),
                f"{t.amount} XAF",
                f"{t.balance_before} XAF",
                f"{t.balance_after} XAF",
                t.get_status_display(),
                t.description,
                t.reference,
                t.created_at.strftime('%d/%m/%Y %H:%M'),
            ])
        return response


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


# ===========================================
# WITHDRAWAL REQUEST ADMIN
# ===========================================

from .models import WithdrawalRequest, WithdrawalStatus, MobileMoneyProvider

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    """Admin for Withdrawal Requests with approval workflow."""
    
    list_display = (
        'short_id',
        'courier_phone',
        'amount_display',
        'provider',
        'phone_number',
        'status_badge',
        'processed_by_display',
        'created_at',
    )
    list_filter = ('status', 'provider', 'created_at')
    search_fields = (
        'id',
        'courier__phone_number',
        'courier__full_name',
        'phone_number',
        'external_transaction_id',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'id',
        'courier',
        'amount',
        'provider',
        'phone_number',
        'external_transaction_id',
        'transaction',
        'created_at',
        'processed_at',
    )
    
    fieldsets = (
        ('Demande', {
            'fields': ('id', 'courier', 'amount', 'status')
        }),
        ('Mobile Money', {
            'fields': ('provider', 'phone_number', 'external_transaction_id')
        }),
        ('Traitement', {
            'fields': ('processed_by', 'rejection_reason', 'processed_at')
        }),
        ('Transaction liée', {
            'fields': ('transaction',),
            'classes': ('collapse',)
        }),
        ('Historique', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_withdrawals', 'reject_withdrawals']
    
    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = "ID"
    
    def courier_phone(self, obj):
        name = obj.courier.full_name or ''
        return f"{obj.courier.phone_number} {name}".strip()
    courier_phone.short_description = "Coursier"
    
    def amount_display(self, obj):
        return f"{obj.amount:,.0f} XAF"
    amount_display.short_description = "Montant"
    
    def status_badge(self, obj):
        from django.utils.html import format_html
        colors = {
            'PENDING': '#f59e0b',
            'PROCESSING': '#3b82f6',
            'COMPLETED': '#10b981',
            'FAILED': '#ef4444',
            'REJECTED': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="padding:3px 8px;border-radius:12px;color:white;background:{};font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Statut"
    
    def processed_by_display(self, obj):
        if obj.processed_by:
            return obj.processed_by.phone_number
        return "—"
    processed_by_display.short_description = "Traité par"
    
    @admin.action(description="✅ Approuver les retraits sélectionnés")
    def approve_withdrawals(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status=WithdrawalStatus.PENDING).update(
            status=WithdrawalStatus.PROCESSING,
            processed_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f"✅ {updated} retrait(s) approuvé(s) et en cours de traitement.")
    
    @admin.action(description="❌ Rejeter les retraits sélectionnés")
    def reject_withdrawals(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status=WithdrawalStatus.PENDING).update(
            status=WithdrawalStatus.REJECTED,
            processed_by=request.user,
            processed_at=timezone.now(),
            rejection_reason="Rejeté en masse par l'administrateur"
        )
        self.message_user(request, f"❌ {updated} retrait(s) rejeté(s).")


# ===========================================
# MOBILE PAYMENT ADMIN
# ===========================================

from .models import MobilePayment, MobilePaymentProvider, MobilePaymentStatus

@admin.register(MobilePayment)
class MobilePaymentAdmin(admin.ModelAdmin):
    """Admin for Mobile Money Payments (MTN MoMo / Orange Money)."""
    
    list_display = (
        'short_id',
        'provider_badge',
        'phone_number',
        'amount_display',
        'status_badge',
        'delivery_link',
        'callback_received',
        'created_at',
    )
    list_filter = ('provider', 'status', 'callback_received', 'created_at')
    search_fields = (
        'id',
        'phone_number',
        'external_reference',
        'provider_transaction_id',
        'delivery__id',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'id',
        'delivery',
        'provider',
        'phone_number',
        'amount',
        'external_reference',
        'provider_transaction_id',
        'pay_token',
        'payment_url',
        'callback_received',
        'callback_data',
        'created_at',
        'updated_at',
        'confirmed_at',
    )
    
    fieldsets = (
        ('Paiement', {
            'fields': ('id', 'provider', 'phone_number', 'amount', 'status')
        }),
        ('Livraison liée', {
            'fields': ('delivery',)
        }),
        ('Références', {
            'fields': ('external_reference', 'provider_transaction_id')
        }),
        ('Orange Money (WebPayment)', {
            'fields': ('pay_token', 'payment_url'),
            'classes': ('collapse',)
        }),
        ('Erreurs', {
            'fields': ('error_code', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Callback', {
            'fields': ('callback_received', 'callback_data'),
            'classes': ('collapse',)
        }),
        ('Historique', {
            'fields': ('created_at', 'updated_at', 'confirmed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = "ID"
    
    def provider_badge(self, obj):
        from django.utils.html import format_html
        colors = {'MTN': '#ffcc00', 'OM': '#ff6600'}
        labels = {'MTN': '📱 MTN MoMo', 'OM': '🍊 Orange Money'}
        color = colors.get(obj.provider, '#6b7280')
        label = labels.get(obj.provider, obj.provider)
        text_color = '#000' if obj.provider == 'MTN' else '#fff'
        return format_html(
            '<span style="padding:3px 8px;border-radius:12px;color:{};background:{};font-size:11px;font-weight:bold;">{}</span>',
            text_color, color, label
        )
    provider_badge.short_description = "Opérateur"
    
    def amount_display(self, obj):
        return f"{obj.amount:,.0f} XAF"
    amount_display.short_description = "Montant"
    
    def status_badge(self, obj):
        from django.utils.html import format_html
        colors = {
            'PENDING': '#f59e0b',
            'SUCCESSFUL': '#10b981',
            'FAILED': '#ef4444',
            'CANCELLED': '#6b7280',
            'TIMEOUT': '#8b5cf6',
            'REJECTED': '#dc2626',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="padding:3px 8px;border-radius:12px;color:white;background:{};font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Statut"
    
    def delivery_link(self, obj):
        if obj.delivery:
            return str(obj.delivery.id)[:8]
        return "—"
    delivery_link.short_description = "Livraison"
    
    def has_add_permission(self, request):
        """Payments are created programmatically only."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Payments cannot be deleted for audit trail."""
        return False

