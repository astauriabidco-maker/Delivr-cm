"""
Django Admin configuration for LOGISTICS app.
"""

from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import Delivery, Neighborhood, DeliveryStatus


@admin.register(Neighborhood)
class NeighborhoodAdmin(GISModelAdmin):
    """Admin for Neighborhood/Quartier with map widget."""
    
    list_display = ('name', 'city', 'radius_km', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('name',)
    ordering = ('city', 'name')
    
    # GIS map settings
    gis_widget_kwargs = {
        'attrs': {
            'default_lon': 9.7,  # Cameroon longitude
            'default_lat': 4.0,  # Cameroon latitude
            'default_zoom': 12,
        }
    }


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
    actions = ['mark_as_completed', 'mark_as_cancelled']

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
