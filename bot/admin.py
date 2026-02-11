"""
BOT App - Django Admin Configuration

Admin interface for NotificationConfiguration singleton.
Allows super-admins to toggle each notification ON/OFF
and customize message templates.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import NotificationConfiguration


@admin.register(NotificationConfiguration)
class NotificationConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for notification toggle configuration.
    
    Singleton model — only one instance exists.
    Organized in fieldsets matching the delivery lifecycle.
    """
    
    list_display = (
        '__str__',
        'notification_summary',
        'updated_at',
        'updated_by_display',
    )
    
    readonly_fields = ('updated_at', 'notification_matrix')
    
    fieldsets = (
        ('📊 Vue d\'ensemble', {
            'fields': ('notification_matrix',),
            'description': (
                '<p style="font-size:14px;color:#666;">'
                'Vue d\'ensemble de toutes les notifications. '
                'Activez ou désactivez chaque notification ci-dessous.</p>'
            ),
        }),
        ('📦 Commande créée (PENDING)', {
            'fields': (
                ('notify_sender_order_created', 'notify_recipient_order_created'),
                'msg_sender_order_created',
                'msg_recipient_order_created',
            ),
            'description': (
                '<p>📤 <strong>Expéditeur</strong> : Confirmation + codes OTP + lien de suivi<br/>'
                '📥 <strong>Destinataire</strong> : Code OTP de livraison + lien de suivi</p>'
            ),
        }),
        ('🏍️ Coursier assigné (ASSIGNED)', {
            'fields': (
                ('notify_sender_assigned', 'notify_recipient_assigned'),
                'msg_sender_assigned',
                'msg_recipient_assigned',
            ),
            'description': (
                '<p>📤 <strong>Expéditeur</strong> : Nom et téléphone du coursier<br/>'
                '📥 <strong>Destinataire</strong> : Un coursier est en chemin</p>'
            ),
        }),
        ('🚗 En route vers le ramassage (EN_ROUTE_PICKUP)', {
            'fields': (
                ('notify_sender_en_route_pickup', 'notify_recipient_en_route_pickup'),
                'msg_sender_en_route_pickup',
            ),
            'description': (
                '<p>📤 <strong>Expéditeur</strong> : Le coursier part chercher le colis<br/>'
                '📥 <strong>Destinataire</strong> : <em>Désactivé par défaut</em> '
                '(peut être activé pour les VIP)</p>'
            ),
        }),
        ('📍 Arrivé au ramassage (ARRIVED_PICKUP)', {
            'fields': (
                ('notify_sender_arrived_pickup', 'notify_recipient_arrived_pickup'),
                'msg_sender_arrived_pickup',
            ),
            'description': (
                '<p>📤 <strong>Expéditeur</strong> : '
                '"Le coursier est arrivé, préparez le code de ramassage"<br/>'
                '📥 <strong>Destinataire</strong> : <em>Désactivé par défaut</em></p>'
            ),
        }),
        ('📤 Colis récupéré (PICKED_UP)', {
            'fields': (
                ('notify_sender_picked_up', 'notify_recipient_picked_up'),
                'msg_sender_picked_up',
                'msg_recipient_picked_up',
            ),
            'description': (
                '<p>📤 <strong>Expéditeur</strong> : Colis récupéré, en route vers le destinataire<br/>'
                '📥 <strong>Destinataire</strong> : Votre colis arrive bientôt + rappel OTP</p>'
            ),
        }),
        ('🚀 En transit (IN_TRANSIT)', {
            'fields': (
                ('notify_sender_in_transit', 'notify_recipient_in_transit'),
                'msg_sender_in_transit',
                'msg_recipient_in_transit',
            ),
            'description': (
                '<p>📤 <strong>Expéditeur</strong> : Le coursier se dirige vers la destination<br/>'
                '📥 <strong>Destinataire</strong> : Rappel du code + lien de suivi</p>'
            ),
        }),
        ('📍 Arrivé à destination (ARRIVED_DROPOFF)', {
            'fields': (
                ('notify_sender_arrived_dropoff', 'notify_recipient_arrived_dropoff'),
                'msg_sender_arrived_dropoff',
                'msg_recipient_arrived_dropoff',
            ),
            'description': (
                '<p>📤 <strong>Expéditeur</strong> : Le coursier est chez le destinataire<br/>'
                '📥 <strong>Destinataire</strong> : "Le coursier est à votre porte, préparez le code"</p>'
            ),
        }),
        ('✅ Livraison terminée (COMPLETED)', {
            'fields': (
                ('notify_sender_completed', 'notify_recipient_completed'),
                'msg_sender_completed',
                'msg_recipient_completed',
            ),
            'description': (
                '<p>📤 <strong>Expéditeur</strong> : Confirmation de livraison réussie<br/>'
                '📥 <strong>Destinataire</strong> : Confirmation + remerciement</p>'
            ),
        }),
        ('❌ Annulation & Échec', {
            'fields': (
                ('notify_sender_cancelled', 'notify_recipient_cancelled'),
                'msg_sender_cancelled',
                'msg_recipient_cancelled',
                ('notify_sender_failed', 'notify_recipient_failed'),
                'msg_sender_failed',
                'msg_recipient_failed',
            ),
            'description': (
                '<p>Notifications en cas d\'annulation ou d\'échec de la livraison.</p>'
            ),
        }),
        ('📊 Autres notifications', {
            'fields': (
                'notify_dispute_updates',
                'notify_daily_summary',
                'notify_rating_request',
            ),
            'classes': ('collapse',),
        }),
        ('📝 Métadonnées', {
            'fields': ('notes', 'updated_at'),
        }),
    )
    
    def notification_summary(self, obj):
        """Show enabled/disabled count."""
        return obj.summary
    notification_summary.short_description = "Statut"
    
    def updated_by_display(self, obj):
        if obj.updated_by:
            return obj.updated_by.full_name or obj.updated_by.phone_number
        return "—"
    updated_by_display.short_description = "Modifié par"
    
    def notification_matrix(self, obj):
        """Visual matrix of all notification toggles."""
        stages = [
            ('📦 Commande créée', 'PENDING'),
            ('🏍️ Coursier assigné', 'ASSIGNED'),
            ('🚗 En route pickup', 'EN_ROUTE_PICKUP'),
            ('📍 Arrivé pickup', 'ARRIVED_PICKUP'),
            ('📤 Colis récupéré', 'PICKED_UP'),
            ('🚀 En transit', 'IN_TRANSIT'),
            ('📍 Arrivé destination', 'ARRIVED_DROPOFF'),
            ('✅ Livraison terminée', 'COMPLETED'),
            ('❌ Annulée', 'CANCELLED'),
            ('❌ Échouée', 'FAILED'),
        ]
        
        rows = ""
        for label, status in stages:
            sender_on = obj.is_enabled(status, 'sender')
            recipient_on = obj.is_enabled(status, 'recipient')
            
            sender_icon = '✅' if sender_on else '❌'
            recipient_icon = '✅' if recipient_on else '❌'
            
            sender_style = 'color:green;' if sender_on else 'color:red;'
            recipient_style = 'color:green;' if recipient_on else 'color:red;'
            
            rows += (
                f'<tr>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #eee;">{label}</td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #eee;text-align:center;">'
                f'<span style="{sender_style}font-size:16px;">{sender_icon}</span></td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #eee;text-align:center;">'
                f'<span style="{recipient_style}font-size:16px;">{recipient_icon}</span></td>'
                f'</tr>'
            )
        
        # Count totals
        total_on = sum(
            1 for _, status in stages
            for target in ['sender', 'recipient']
            if obj.is_enabled(status, target)
        )
        total = len(stages) * 2
        
        pct = (total_on / total * 100) if total > 0 else 0
        bar_color = '#4CAF50' if pct > 70 else '#FF9800' if pct > 40 else '#F44336'
        
        return format_html(
            '<div style="max-width:500px;">'
            '<table style="width:100%;border-collapse:collapse;margin-bottom:12px;">'
            '<thead>'
            '<tr style="background:#f5f5f5;">'
            '<th style="padding:8px 12px;text-align:left;">Étape</th>'
            '<th style="padding:8px 12px;text-align:center;">📤 Expéditeur</th>'
            '<th style="padding:8px 12px;text-align:center;">📥 Destinataire</th>'
            '</tr>'
            '</thead>'
            '<tbody>{}</tbody>'
            '</table>'
            '<div style="display:flex;align-items:center;gap:8px;">'
            '<div style="background:#eee;width:200px;height:12px;border-radius:6px;overflow:hidden;">'
            '<div style="background:{};width:{}%;height:100%;border-radius:6px;"></div>'
            '</div>'
            '<span style="font-weight:bold;font-size:13px;">{}/{} actives ({}%)</span>'
            '</div>'
            '</div>',
            rows, bar_color, pct, total_on, total, int(pct)
        )
    notification_matrix.short_description = "Matrice des notifications"
    
    def save_model(self, request, obj, form, change):
        """Track who made the change."""
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        """Only one config instance (singleton)."""
        return not NotificationConfiguration.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Cannot delete the configuration."""
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Redirect to the single config instance or create it."""
        obj, _ = NotificationConfiguration.objects.get_or_create(pk=1)
        from django.shortcuts import redirect
        return redirect(
            f'/admin/bot/notificationconfiguration/{obj.pk}/change/'
        )
