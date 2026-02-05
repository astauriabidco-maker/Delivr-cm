"""
LOGISTICS App - Deliveries & Routing for DELIVR-CM

Handles: Deliveries, Neighborhoods, Dispatch, Routing
"""

import uuid
import random
import string
from django.contrib.gis.db import models
from django.conf import settings
from decimal import Decimal


class DeliveryStatus(models.TextChoices):
    """Delivery status enumeration."""
    PENDING = 'PENDING', 'En attente'
    ASSIGNED = 'ASSIGNED', 'Coursier assigné'
    PICKED_UP = 'PICKED_UP', 'Colis récupéré'
    IN_TRANSIT = 'IN_TRANSIT', 'En transit'
    COMPLETED = 'COMPLETED', 'Livré'
    CANCELLED = 'CANCELLED', 'Annulé'
    FAILED = 'FAILED', 'Échec livraison'


class PaymentMethod(models.TextChoices):
    """Payment method enumeration."""
    CASH_P2P = 'CASH_P2P', 'Cash (Client → Coursier)'
    PREPAID_WALLET = 'PREPAID_WALLET', 'Prépayé (Wallet Marchand)'


class City(models.TextChoices):
    """Supported cities."""
    DOUALA = 'DOUALA', 'Douala'
    YAOUNDE = 'YAOUNDE', 'Yaoundé'


class Neighborhood(models.Model):
    """
    Neighborhood/Quartier model for price estimation.
    Used when exact GPS is not available (E-commerce API).
    
    The center_geo represents the barycenter of the neighborhood
    for distance calculations.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    city = models.CharField(
        max_length=20,
        choices=City.choices,
        verbose_name="Ville"
    )
    name = models.CharField(max_length=100, verbose_name="Nom du quartier")
    
    # Barycenter for price estimation
    center_geo = models.PointField(
        srid=4326,
        verbose_name="Centre du quartier (GPS)"
    )
    radius_km = models.FloatField(
        default=1.5,
        verbose_name="Rayon approximatif (km)"
    )
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Quartier"
        verbose_name_plural = "Quartiers"
        unique_together = ['city', 'name']
        ordering = ['city', 'name']

    def __str__(self):
        return f"{self.name} ({self.city})"


class Delivery(models.Model):
    """
    Core delivery/course model.
    
    Pricing is frozen at creation time to prevent disputes.
    OTP code secures the delivery handoff.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Actors
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sent_deliveries',
        verbose_name="Expéditeur"
    )
    recipient_phone = models.CharField(
        max_length=15,
        verbose_name="Téléphone destinataire"
    )
    recipient_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Nom destinataire"
    )
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_deliveries',
        verbose_name="Coursier"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        verbose_name="Statut"
    )
    
    # Payment
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH_P2P,
        verbose_name="Méthode de paiement"
    )
    
    # Locations (PostGIS Points)
    pickup_geo = models.PointField(
        srid=4326,
        verbose_name="Point de ramassage (GPS)"
    )
    pickup_address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Adresse ramassage (optionnel)"
    )
    dropoff_geo = models.PointField(
        srid=4326,
        null=True,
        blank=True,
        verbose_name="Point de livraison (GPS)"
    )
    dropoff_address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Adresse livraison (optionnel)"
    )
    dropoff_neighborhood = models.ForeignKey(
        Neighborhood,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Quartier livraison (si pas de GPS)"
    )
    
    # Package Info
    package_description = models.TextField(
        blank=True,
        verbose_name="Description du colis"
    )
    package_photo = models.ImageField(
        upload_to='packages/',
        null=True,
        blank=True,
        verbose_name="Photo du colis"
    )
    proof_photo = models.ImageField(
        upload_to='proofs/',
        null=True,
        blank=True,
        verbose_name="Photo preuve de livraison"
    )
    pickup_photo = models.ImageField(
        upload_to='pickups/',
        null=True,
        blank=True,
        verbose_name="Photo du colis au retrait"
    )
    
    # Pricing (frozen at creation)
    distance_km = models.FloatField(
        default=0.0,
        verbose_name="Distance (km)"
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Prix total (XAF)"
    )
    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Commission plateforme (XAF)"
    )
    courier_earning = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Gain coursier (XAF)"
    )
    
    # Security
    otp_code = models.CharField(
        max_length=4,
        blank=True,
        verbose_name="Code OTP livraison"
    )
    pickup_otp = models.CharField(
        max_length=4,
        blank=True,
        verbose_name="Code OTP retrait"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    in_transit_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # E-commerce Reference
    external_order_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID commande externe"
    )
    shop = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shop_deliveries',
        verbose_name="Boutique (B2B)"
    )

    class Meta:
        verbose_name = "Livraison"
        verbose_name_plural = "Livraisons"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['courier', 'status']),
        ]

    def __str__(self):
        return f"Livraison {str(self.id)[:8]} - {self.status}"

    def save(self, *args, **kwargs):
        # Generate delivery OTP if not set (for recipient)
        if not self.otp_code:
            self.otp_code = ''.join(random.choices(string.digits, k=4))
        # Generate pickup OTP if not set (for sender)
        if not self.pickup_otp:
            self.pickup_otp = ''.join(random.choices(string.digits, k=4))
        super().save(*args, **kwargs)

    @property
    def is_pending(self) -> bool:
        return self.status == DeliveryStatus.PENDING

    @property
    def is_completed(self) -> bool:
        return self.status == DeliveryStatus.COMPLETED

    @property
    def has_exact_dropoff(self) -> bool:
        """Check if we have exact GPS for dropoff."""
        return self.dropoff_geo is not None
