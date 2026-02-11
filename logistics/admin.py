"""
Django Admin configuration for LOGISTICS app.
"""

from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import Delivery, Neighborhood, DeliveryStatus


@admin.register(Neighborhood)
class NeighborhoodAdmin(GISModelAdmin):
    """Admin for Neighborhood/Quartier with map widget and CSV import."""
    
    list_display = ('name', 'city', 'radius_km', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('name',)
    ordering = ('city', 'name')
    change_list_template = 'admin/logistics/neighborhood_changelist.html'
    
    # GIS map settings
    gis_widget_kwargs = {
        'attrs': {
            'default_lon': 9.7,  # Cameroon longitude
            'default_lat': 4.0,  # Cameroon latitude
            'default_zoom': 12,
        }
    }
    
    def get_urls(self):
        from django.urls import path
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='logistics_neighborhood_import_csv'),
        ]
        return custom_urls + super().get_urls()
    
    def import_csv(self, request):
        import csv, io
        from django.shortcuts import redirect
        from django.contrib.gis.geos import Point
        from django.contrib import messages
        from .models import City
        
        if request.method == 'POST' and request.FILES.get('csv_file'):
            csv_file = request.FILES['csv_file']
            decoded = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
            
            created = 0
            skipped = 0
            errors = []
            
            for i, row in enumerate(reader, start=2):
                try:
                    name = row.get('name', '').strip()
                    city = row.get('city', '').strip()
                    lat = float(row.get('latitude', '0'))
                    lon = float(row.get('longitude', '0'))
                    radius = float(row.get('radius_km', '1.5'))
                    
                    if not name or not city:
                        errors.append(f"Ligne {i}: nom ou ville manquant")
                        continue
                    
                    if city not in [c.value for c in City]:
                        errors.append(f"Ligne {i}: ville '{city}' invalide")
                        continue
                    
                    obj, was_created = Neighborhood.objects.update_or_create(
                        name=name,
                        city=city,
                        defaults={
                            'center_geo': Point(lon, lat, srid=4326),
                            'radius_km': radius,
                            'is_active': True,
                        }
                    )
                    if was_created:
                        created += 1
                    else:
                        skipped += 1
                except Exception as e:
                    errors.append(f"Ligne {i}: {e}")
            
            msg = f"✅ {created} quartier(s) créé(s), {skipped} mis à jour."
            if errors:
                msg += f" ⚠️ {len(errors)} erreur(s): {'; '.join(errors[:5])}"
            messages.success(request, msg)
            
            from core.models import AdminActivityLog
            AdminActivityLog.log(
                user=request.user,
                action=AdminActivityLog.ActionType.IMPORT,
                target_model='Neighborhood',
                details={'created': created, 'skipped': skipped, 'errors': len(errors)},
            )
            
            return redirect('..')
        
        from django.template.response import TemplateResponse
        return TemplateResponse(request, 'admin/logistics/neighborhood_import.html', {
            'title': 'Importer des quartiers (CSV)',
            'opts': self.model._meta,
        })


@admin.register(Delivery)
class DeliveryAdmin(GISModelAdmin):
    """Admin for Delivery with full details."""
    
    list_display = (
        'short_id',
        'status',
        'payment_method',
        'sender_phone',
        'recipient_phone',
        'courier_name',
        'total_price',
        'created_at'
    )
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = (
        'id',
        'sender__phone_number',
        'recipient_phone',
        'courier__phone_number',
        'external_order_id'
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'id',
        'otp_code',
        'distance_km',
        'total_price',
        'platform_fee',
        'courier_earning',
        'created_at',
        'assigned_at',
        'picked_up_at',
        'completed_at'
    )
    
    fieldsets = (
        ('Identification', {
            'fields': ('id', 'status', 'external_order_id')
        }),
        ('Acteurs', {
            'fields': ('sender', 'recipient_phone', 'recipient_name', 'courier', 'shop')
        }),
        ('Paiement', {
            'fields': ('payment_method',)
        }),
        ('Localisations', {
            'fields': (
                'pickup_geo', 'pickup_address',
                'dropoff_geo', 'dropoff_address', 'dropoff_neighborhood'
            )
        }),
        ('Colis', {
            'fields': ('package_description', 'package_photo')
        }),
        ('Tarification', {
            'fields': ('distance_km', 'total_price', 'platform_fee', 'courier_earning')
        }),
        ('Sécurité', {
            'fields': ('otp_code',),
            'classes': ('collapse',)
        }),
        ('Historique', {
            'fields': ('created_at', 'assigned_at', 'picked_up_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = "ID"

    def sender_phone(self, obj):
        return obj.sender.phone_number if obj.sender else "-"
    sender_phone.short_description = "Expéditeur"

    def courier_name(self, obj):
        if obj.courier:
            return obj.courier.full_name or obj.courier.phone_number
        return "-"
    courier_name.short_description = "Coursier"

    # Quick actions
    actions = ['mark_as_completed', 'mark_as_cancelled', 'export_deliveries_csv']
    
    @admin.action(description="📥 Exporter en CSV")
    def export_deliveries_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="livraisons_delivr.csv"'
        response.write('\ufeff')
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Statut', 'Paiement', 'Expéditeur', 'Destinataire',
            'Coursier', 'Distance (km)', 'Prix Total', 'Commission', 'Gain Coursier',
            'Créée le', 'Livrée le'
        ])
        
        for d in queryset.select_related('sender', 'courier'):
            writer.writerow([
                str(d.id)[:8],
                d.get_status_display(),
                d.get_payment_method_display(),
                d.sender.phone_number if d.sender else '-',
                d.recipient_phone,
                d.courier.phone_number if d.courier else '-',
                d.distance_km,
                f"{d.total_price} XAF",
                f"{d.platform_fee} XAF",
                f"{d.courier_earning} XAF",
                d.created_at.strftime('%d/%m/%Y %H:%M') if d.created_at else '',
                d.completed_at.strftime('%d/%m/%Y %H:%M') if d.completed_at else '',
            ])
        return response

    @admin.action(description="Marquer comme livré")
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(
            status__in=[DeliveryStatus.PICKED_UP, DeliveryStatus.IN_TRANSIT]
        ).update(
            status=DeliveryStatus.COMPLETED,
            completed_at=timezone.now()
        )
        self.message_user(request, f"{updated} livraison(s) marquée(s) comme livrée(s).")

    @admin.action(description="Annuler les livraisons")
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.filter(
            status__in=[DeliveryStatus.PENDING, DeliveryStatus.ASSIGNED]
        ).update(status=DeliveryStatus.CANCELLED)
        self.message_user(request, f"{updated} livraison(s) annulée(s).")


# ===========================================
# RATING ADMIN
# ===========================================

from .models import Rating, RatingType

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    """Admin for delivery Ratings/Reviews."""
    
    list_display = (
        'short_id',
        'delivery_link',
        'rating_type',
        'rater_display',
        'rated_display',
        'score_stars',
        'comment_short',
        'created_at',
    )
    list_filter = ('rating_type', 'score', 'created_at')
    search_fields = (
        'id',
        'rater__phone_number',
        'rater__full_name',
        'rated__phone_number',
        'rated__full_name',
        'comment',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    readonly_fields = (
        'id',
        'delivery',
        'rater',
        'rated',
        'rating_type',
        'score',
        'created_at',
    )
    
    fieldsets = (
        ('Évaluation', {
            'fields': ('id', 'delivery', 'rating_type')
        }),
        ('Acteurs', {
            'fields': ('rater', 'rated')
        }),
        ('Note', {
            'fields': ('score', 'comment')
        }),
        ('Historique', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = "ID"
    
    def delivery_link(self, obj):
        return str(obj.delivery.id)[:8]
    delivery_link.short_description = "Livraison"
    
    def rater_display(self, obj):
        return obj.rater.full_name or obj.rater.phone_number
    rater_display.short_description = "Évaluateur"
    
    def rated_display(self, obj):
        return obj.rated.full_name or obj.rated.phone_number
    rated_display.short_description = "Évalué"
    
    def score_stars(self, obj):
        from django.utils.html import format_html
        stars = '⭐' * obj.score + '☆' * (5 - obj.score)
        return format_html('<span title="{}/5">{}</span>', obj.score, stars)
    score_stars.short_description = "Note"
    
    def comment_short(self, obj):
        if obj.comment:
            return obj.comment[:50] + ('…' if len(obj.comment) > 50 else '')
        return "—"
    comment_short.short_description = "Commentaire"
    
    def has_add_permission(self, request):
        """Ratings are created by users only."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Ratings are immutable."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete ratings."""
        return request.user.is_superuser


# ===========================================
# TRAFFIC EVENTS ADMIN
# ===========================================

from .models import TrafficEvent, TrafficEventVote

@admin.register(TrafficEvent)
class TrafficEventAdmin(GISModelAdmin):
    """Admin for Traffic Events (Waze-like reports)."""
    
    list_display = (
        'short_id',
        'event_type',
        'severity',
        'address',
        'reporter_name',
        'votes_display',
        'confidence_display',
        'is_active',
        'created_at',
        'expires_at',
    )
    list_filter = ('event_type', 'severity', 'is_active', 'created_at')
    search_fields = ('address', 'description', 'reporter__phone_number', 'reporter__full_name')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'upvotes', 'downvotes', 'created_at')
    
    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = "ID"
    
    def reporter_name(self, obj):
        return obj.reporter.full_name or obj.reporter.phone_number
    reporter_name.short_description = "Signalé par"
    
    def votes_display(self, obj):
        return f"👍 {obj.upvotes} / 👎 {obj.downvotes}"
    votes_display.short_description = "Votes"
    
    def confidence_display(self, obj):
        score = obj.confidence_score
        if score >= 70:
            emoji = "🟢"
        elif score >= 40:
            emoji = "🟡"
        else:
            emoji = "🔴"
        return f"{emoji} {score}%"
    confidence_display.short_description = "Confiance"
    
    actions = ['deactivate_events', 'activate_events']
    
    @admin.action(description="🚫 Désactiver les événements sélectionnés")
    def deactivate_events(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_active=False, resolved_at=timezone.now())
        self.message_user(request, f"{updated} événement(s) désactivé(s).")
    
    @admin.action(description="✅ Réactiver les événements sélectionnés")
    def activate_events(self, request, queryset):
        updated = queryset.update(is_active=True, resolved_at=None)
        self.message_user(request, f"{updated} événement(s) réactivé(s).")


# ===========================================
# DISPATCH CONFIGURATION ADMIN
# ===========================================

from .models import DispatchConfiguration

@admin.register(DispatchConfiguration)
class DispatchConfigurationAdmin(admin.ModelAdmin):
    """
    Admin for dispatch scoring configuration.
    
    Singleton model — only one instance exists.
    Admins can adjust all scoring weights, thresholds, and bonuses.
    """
    
    list_display = (
        '__str__',
        'weights_status',
        'radius_display',
        'threshold_display',
        'updated_at',
        'updated_by_display',
    )
    
    readonly_fields = ('updated_at', 'weight_total_display')
    
    fieldsets = (
        ('📊 Résumé des poids', {
            'fields': ('weight_total_display',),
            'description': (
                '<p style="font-size:14px;color:#666;">'
                'La somme de tous les poids <strong>doit être égale à 1.0</strong> (100%). '
                'Si ce n\'est pas le cas, un message d\'erreur s\'affichera à la sauvegarde.</p>'
            ),
        }),
        ('🔍 Paramètres de recherche', {
            'fields': (
                ('initial_radius_km', 'max_radius_km', 'radius_increment_km'),
                ('max_couriers_to_score', 'max_couriers_to_notify'),
            ),
            'description': (
                '<p>Contrôle la zone de recherche des coursiers autour du point de pickup.</p>'
            ),
        }),
        ('⚖️ Poids du scoring (DOIVENT sommer à 1.0)', {
            'fields': (
                ('weight_distance', 'weight_rating'),
                ('weight_history', 'weight_availability'),
                ('weight_financial', 'weight_response'),
                ('weight_level', 'weight_acceptance'),
            ),
            'description': (
                '<p><strong>Ces 8 facteurs déterminent quel coursier reçoit la course en premier.</strong></p>'
                '<ul>'
                '<li><strong>Distance</strong> : Plus le coursier est proche du pickup, meilleur est le score</li>'
                '<li><strong>Note moyenne</strong> : Note /5 donnée par les clients</li>'
                '<li><strong>Historique</strong> : Taux de réussite sur les 30 derniers jours</li>'
                '<li><strong>Disponibilité</strong> : Temps depuis la dernière course (éviter la surcharge)</li>'
                '<li><strong>Santé financière</strong> : Ratio dette/plafond du wallet</li>'
                '<li><strong>Temps de réponse</strong> : Vitesse moyenne d\'acceptation des courses</li>'
                '<li><strong>Niveau coursier</strong> : Bronze/Silver/Gold/Platinum</li>'
                '<li><strong>Taux d\'acceptation</strong> : % de courses acceptées vs refusées</li>'
                '</ul>'
            ),
        }),
        ('🎯 Seuils de décision', {
            'fields': (
                ('min_score_threshold', 'auto_assign_threshold'),
            ),
            'description': (
                '<p><strong>Score minimum</strong> : En dessous, le coursier est ignoré.<br/>'
                '<strong>Auto-assignation</strong> : Au-dessus, le meilleur coursier est assigné automatiquement.</p>'
            ),
        }),
        ('📏 Courbe de distance', {
            'fields': (
                ('distance_perfect_km', 'distance_zero_km'),
            ),
            'classes': ('collapse',),
            'description': (
                '<p>Score = 100 en dessous de "Distance parfaite", '
                'Score = 0 au-dessus de "Distance nulle", interpolé entre les deux.</p>'
            ),
        }),
        ('⭐ Scoring par note', {
            'fields': ('min_ratings_for_full_score',),
            'classes': ('collapse',),
            'description': (
                '<p>Si le coursier a moins de notes que ce seuil, '
                'son score "Note" est blendé entre sa note réelle et un score neutre (60).</p>'
            ),
        }),
        ('🏆 Score par niveau', {
            'fields': (
                ('level_score_bronze', 'level_score_silver'),
                ('level_score_gold', 'level_score_platinum'),
            ),
            'classes': ('collapse',),
        }),
        ('🔥 Bonus & Pénalités', {
            'fields': (
                'streak_bonus_enabled',
                ('streak_bonus_per_delivery', 'streak_bonus_max'),
                'probation_penalty',
            ),
            'description': (
                '<p><strong>Streak</strong> : Bonus ajouté au score total pour les séries de succès.<br/>'
                '<strong>Probation</strong> : Pénalité soustraite du score des coursiers en période d\'essai.</p>'
            ),
        }),
        ('🗄️ Cache & Performance', {
            'fields': ('courier_stats_cache_ttl',),
            'classes': ('collapse',),
        }),
        ('📝 Métadonnées', {
            'fields': ('notes', 'updated_at'),
        }),
    )
    
    def weights_status(self, obj):
        from django.utils.html import format_html
        total = obj.total_weight
        if obj.weights_valid:
            return format_html(
                '<span style="color:green;font-weight:bold;">✅ {:.0f}%</span>',
                total * 100
            )
        return format_html(
            '<span style="color:red;font-weight:bold;">❌ {:.1f}% (≠ 100%)</span>',
            total * 100
        )
    weights_status.short_description = "Poids"
    
    def radius_display(self, obj):
        return f"{obj.initial_radius_km} → {obj.max_radius_km} km"
    radius_display.short_description = "Rayon"
    
    def threshold_display(self, obj):
        return f"Min: {obj.min_score_threshold} | Auto: {obj.auto_assign_threshold}"
    threshold_display.short_description = "Seuils"
    
    def updated_by_display(self, obj):
        if obj.updated_by:
            return obj.updated_by.full_name or obj.updated_by.phone_number
        return "—"
    updated_by_display.short_description = "Modifié par"
    
    def weight_total_display(self, obj):
        from django.utils.html import format_html
        total = obj.total_weight
        weights = [
            ('Distance', obj.weight_distance),
            ('Note moyenne', obj.weight_rating),
            ('Historique', obj.weight_history),
            ('Disponibilité', obj.weight_availability),
            ('Santé financière', obj.weight_financial),
            ('Temps réponse', obj.weight_response),
            ('Niveau coursier', obj.weight_level),
            ("Taux d'acceptation", obj.weight_acceptance),
        ]
        
        bars = ""
        colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336', '#00BCD4', '#FFC107', '#795548']
        for i, (name, value) in enumerate(weights):
            pct = value * 100
            bars += (
                f'<div style="display:flex;align-items:center;margin:4px 0;">'
                f'<span style="width:150px;font-size:12px;">{name}</span>'
                f'<div style="background:#eee;width:300px;height:20px;border-radius:4px;overflow:hidden;">'
                f'<div style="background:{colors[i]};width:{pct}%;height:100%;"></div>'
                f'</div>'
                f'<span style="margin-left:8px;font-weight:bold;font-size:12px;">{pct:.0f}%</span>'
                f'</div>'
            )
        
        status_color = 'green' if obj.weights_valid else 'red'
        status_icon = '✅' if obj.weights_valid else '❌'
        
        return format_html(
            '<div style="padding:10px;background:#f8f9fa;border-radius:8px;max-width:500px;">'
            '{}'
            '<hr style="margin:8px 0;">'
            '<div style="font-size:14px;font-weight:bold;color:{};">'
            '{} Total : {:.0f}%'
            '</div>'
            '</div>',
            bars, status_color, status_icon, total * 100
        )
    weight_total_display.short_description = "Répartition des poids"
    
    def save_model(self, request, obj, form, change):
        """Track who made the change."""
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        """Only one config instance is allowed (singleton)."""
        return not DispatchConfiguration.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Cannot delete the configuration."""
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Redirect to the single config instance or create it."""
        obj, _ = DispatchConfiguration.objects.get_or_create(pk=1)
        from django.shortcuts import redirect
        return redirect(
            f'/admin/logistics/dispatchconfiguration/{obj.pk}/change/'
        )


