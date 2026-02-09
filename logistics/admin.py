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

