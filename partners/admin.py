"""
Django Admin configuration for PARTNERS app.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import WebhookConfig, PartnerNotification, NotificationType, PartnerAPIKey


@admin.register(PartnerAPIKey)
class PartnerAPIKeyAdmin(admin.ModelAdmin):
    """Admin for Partner API Keys."""
    
    list_display = (
        'name',
        'partner_display',
        'revoked_badge',
        'created',
        'expiry_date',
    )
    list_filter = ('revoked',)
    search_fields = (
        'name',
        'partner__full_name',
        'partner__phone_number',
    )
    ordering = ('-created',)
    
    readonly_fields = ('prefix', 'hashed_key', 'created')
    
    fieldsets = (
        ('Clé API', {
            'fields': ('name', 'partner', 'prefix', 'revoked')
        }),
        ('Validité', {
            'fields': ('expiry_date',),
            'description': 'Laissez vide pour une clé sans expiration.'
        }),
        ('Technique', {
            'fields': ('hashed_key', 'created'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['revoke_keys']
    
    def partner_display(self, obj):
        return f"{obj.partner.full_name} ({obj.partner.phone_number})"
    partner_display.short_description = "Partenaire"
    
    def revoked_badge(self, obj):
        if obj.revoked:
            return format_html(
                '<span style="padding:2px 6px;border-radius:8px;color:white;background:#ef4444;font-size:11px;">Révoquée</span>'
            )
        return format_html(
            '<span style="padding:2px 6px;border-radius:8px;color:white;background:#10b981;font-size:11px;">Active</span>'
        )
    revoked_badge.short_description = "Statut"
    
    @admin.action(description="🚫 Révoquer les clés sélectionnées")
    def revoke_keys(self, request, queryset):
        updated = queryset.update(revoked=True)
        self.message_user(request, f"❌ {updated} clé(s) révoquée(s).")


@admin.register(WebhookConfig)
class WebhookConfigAdmin(admin.ModelAdmin):
    """Admin for Partner Webhook Configurations."""
    
    list_display = (
        'partner_display',
        'url_short',
        'is_active',
        'events_count',
        'last_status_badge',
        'failure_count',
        'last_triggered',
    )
    list_filter = ('is_active', 'last_status_code')
    search_fields = (
        'user__phone_number',
        'user__full_name',
        'url',
    )
    ordering = ('-updated_at',)
    
    readonly_fields = (
        'secret',
        'last_triggered',
        'last_status_code',
        'failure_count',
        'created_at',
        'updated_at',
    )
    
    fieldsets = (
        ('Partenaire', {
            'fields': ('user', 'is_active')
        }),
        ('Configuration', {
            'fields': ('url', 'events')
        }),
        ('Sécurité', {
            'fields': ('secret',),
            'description': 'Le secret HMAC est utilisé pour signer les webhooks. '
                         'Partagez-le uniquement avec le partenaire via un canal sécurisé.'
        }),
        ('Monitoring', {
            'fields': ('last_triggered', 'last_status_code', 'failure_count'),
            'classes': ('collapse',)
        }),
        ('Historique', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['reset_failures', 'deactivate_webhooks']
    
    def partner_display(self, obj):
        return obj.user.full_name or obj.user.phone_number
    partner_display.short_description = "Partenaire"
    
    def url_short(self, obj):
        if obj.url:
            url = obj.url
            return url[:40] + ('…' if len(url) > 40 else '')
        return "—"
    url_short.short_description = "URL"
    
    def events_count(self, obj):
        count = len(obj.events) if obj.events else 0
        return f"{count} événement(s)"
    events_count.short_description = "Événements"
    
    def last_status_badge(self, obj):
        from django.utils.html import format_html
        if obj.last_status_code is None:
            return "—"
        code = obj.last_status_code
        color = '#10b981' if 200 <= code < 300 else '#ef4444'
        return format_html(
            '<span style="padding:2px 6px;border-radius:8px;color:white;background:{};font-size:11px;">{}</span>',
            color, code
        )
    last_status_badge.short_description = "Dernier HTTP"
    
    @admin.action(description="🔄 Réinitialiser le compteur d'échecs")
    def reset_failures(self, request, queryset):
        updated = queryset.update(failure_count=0)
        self.message_user(request, f"✅ Compteur réinitialisé pour {updated} webhook(s).")
    
    @admin.action(description="🚫 Désactiver les webhooks sélectionnés")
    def deactivate_webhooks(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"❌ {updated} webhook(s) désactivé(s).")


@admin.register(PartnerNotification)
class PartnerNotificationAdmin(admin.ModelAdmin):
    """Admin for Partner Notifications."""
    
    list_display = (
        'title_short',
        'partner_display',
        'type_badge',
        'delivery_link',
        'is_read',
        'created_at',
    )
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = (
        'title',
        'message',
        'user__phone_number',
        'user__full_name',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'user',
        'notification_type',
        'title',
        'message',
        'delivery',
        'created_at',
    )
    
    fieldsets = (
        ('Notification', {
            'fields': ('user', 'notification_type', 'title', 'message')
        }),
        ('Livraison liée', {
            'fields': ('delivery',)
        }),
        ('Statut', {
            'fields': ('is_read',)
        }),
        ('Historique', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def title_short(self, obj):
        return obj.title[:40] + ('…' if len(obj.title) > 40 else '')
    title_short.short_description = "Titre"
    
    def partner_display(self, obj):
        return obj.user.full_name or obj.user.phone_number
    partner_display.short_description = "Partenaire"
    
    def type_badge(self, obj):
        from django.utils.html import format_html
        colors = {
            'order_created': '#3b82f6',
            'order_assigned': '#8b5cf6',
            'order_picked_up': '#f59e0b',
            'order_completed': '#10b981',
            'order_cancelled': '#ef4444',
            'payment_received': '#059669',
            'invoice_generated': '#6366f1',
            'system': '#6b7280',
        }
        color = colors.get(obj.notification_type, '#6b7280')
        return format_html(
            '<span style="padding:2px 6px;border-radius:8px;color:white;background:{};font-size:11px;">{}</span>',
            color, obj.get_notification_type_display()
        )
    type_badge.short_description = "Type"
    
    def delivery_link(self, obj):
        if obj.delivery:
            return str(obj.delivery.id)[:8]
        return "—"
    delivery_link.short_description = "Livraison"
    
    @admin.action(description="✅ Marquer comme lu")
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f"✅ {updated} notification(s) marquée(s) comme lue(s).")
    
    @admin.action(description="📩 Marquer comme non lu")
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f"📩 {updated} notification(s) marquée(s) comme non lue(s).")
