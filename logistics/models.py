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
    EN_ROUTE_PICKUP = 'EN_ROUTE_PICKUP', 'En route pour le retrait'
    ARRIVED_PICKUP = 'ARRIVED_PICKUP', 'Arrivé au retrait'
    PICKED_UP = 'PICKED_UP', 'Colis récupéré'
    IN_TRANSIT = 'IN_TRANSIT', 'En transit'
    ARRIVED_DROPOFF = 'ARRIVED_DROPOFF', 'Arrivé à la livraison'
    COMPLETED = 'COMPLETED', 'Livré'
    CANCELLED = 'CANCELLED', 'Annulé'
    FAILED = 'FAILED', 'Échec livraison'


class PaymentMethod(models.TextChoices):
    """Payment method enumeration."""
    CASH_P2P = 'CASH_P2P', 'Cash (Client → Coursier)'
    PREPAID_WALLET = 'PREPAID_WALLET', 'Prépayé (Wallet Marchand)'
    MOBILE_MONEY = 'MOBILE_MONEY', 'Mobile Money (MTN/Orange)'



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


class RatingType(models.TextChoices):
    """Who is being rated."""
    COURIER = 'COURIER', 'Client → Coursier'
    SENDER = 'SENDER', 'Coursier → Client'


class Rating(models.Model):
    """
    Rating model for delivery feedback.
    
    Allows clients to rate couriers and vice-versa after delivery completion.
    Used for quality control and gamification.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    delivery = models.ForeignKey(
        Delivery,
        on_delete=models.CASCADE,
        related_name='ratings',
        verbose_name="Livraison"
    )
    
    # Who gave the rating
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ratings_given',
        verbose_name="Évaluateur"
    )
    
    # Who received the rating
    rated = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ratings_received',
        verbose_name="Évalué"
    )
    
    rating_type = models.CharField(
        max_length=20,
        choices=RatingType.choices,
        verbose_name="Type"
    )
    
    score = models.PositiveSmallIntegerField(
        verbose_name="Note (1-5)",
        help_text="Note de 1 (mauvais) à 5 (excellent)"
    )
    
    comment = models.TextField(
        blank=True,
        verbose_name="Commentaire"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        ordering = ['-created_at']
        # One rating per delivery per direction
        unique_together = ['delivery', 'rater', 'rated']
        indexes = [
            models.Index(fields=['rated', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.rater} → {self.rated}: {self.score}⭐"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if not 1 <= self.score <= 5:
            raise ValidationError("La note doit être entre 1 et 5")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Update rated user's average rating
        self._update_user_rating()
    
    def _update_user_rating(self):
        """Update the rated user's average rating."""
        from django.db.models import Avg, Count
        
        stats = Rating.objects.filter(rated=self.rated).aggregate(
            avg=Avg('score'),
            count=Count('id')
        )
        
        self.rated.average_rating = round(stats['avg'] or 5.0, 2)
        self.rated.total_ratings_count = stats['count'] or 0
        self.rated.save(update_fields=['average_rating', 'total_ratings_count'])


# ============================================
# TRAFFIC EVENTS (Signalements type Waze)
# ============================================

class TrafficEventType(models.TextChoices):
    """Types d'événements signalés par les coursiers."""
    ACCIDENT = 'ACCIDENT', '🚗 Accident'
    POLICE = 'POLICE', '👮 Contrôle de police'
    ROAD_CLOSED = 'ROAD_CLOSED', '🚧 Route barrée'
    FLOODING = 'FLOODING', '🌊 Inondation'
    POTHOLE = 'POTHOLE', '🕳️ Nid-de-poule'
    TRAFFIC_JAM = 'TRAFFIC_JAM', '🚦 Embouteillage'
    ROADWORK = 'ROADWORK', '🏗️ Travaux'
    HAZARD = 'HAZARD', '⚠️ Danger sur la route'
    FUEL_STATION = 'FUEL_STATION', '⛽ Station essence ouverte'
    OTHER = 'OTHER', '📍 Autre'


class TrafficEventSeverity(models.TextChoices):
    """Sévérité de l'événement."""
    LOW = 'LOW', 'Faible'
    MEDIUM = 'MEDIUM', 'Moyen'
    HIGH = 'HIGH', 'Élevé'
    CRITICAL = 'CRITICAL', 'Critique'


class TrafficEvent(models.Model):
    """
    Événement trafic signalé par un coursier (système type Waze).
    
    Permet aux coursiers de signaler des incidents en temps réel
    pour aider les autres coursiers à éviter les zones problématiques.
    Chaque événement a un TTL basé sur son type et peut être
    confirmé/infirmé par d'autres coursiers (upvote/downvote).
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Qui signale
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reported_events',
        verbose_name="Signalé par"
    )
    
    # Type et sévérité
    event_type = models.CharField(
        max_length=20,
        choices=TrafficEventType.choices,
        verbose_name="Type d'événement"
    )
    severity = models.CharField(
        max_length=10,
        choices=TrafficEventSeverity.choices,
        default=TrafficEventSeverity.MEDIUM,
        verbose_name="Sévérité"
    )
    
    # Localisation
    location = models.PointField(
        srid=4326,
        verbose_name="Position GPS"
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Adresse approximative"
    )
    
    # Description
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    photo = models.ImageField(
        upload_to='traffic_events/',
        null=True,
        blank=True,
        verbose_name="Photo"
    )
    
    # Validation communautaire
    upvotes = models.PositiveIntegerField(default=0, verbose_name="Confirmations")
    downvotes = models.PositiveIntegerField(default=0, verbose_name="Infirmations")
    
    # Lifecycle
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        verbose_name="Expire à",
        help_text="L'événement sera masqué après cette date"
    )
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Résolu à")
    
    class Meta:
        verbose_name = "Événement trafic"
        verbose_name_plural = "Événements trafic"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'expires_at']),
            models.Index(fields=['event_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.address or 'GPS'}"
    
    @property
    def latitude(self):
        return self.location.y if self.location else None
    
    @property
    def longitude(self):
        return self.location.x if self.location else None
    
    @property
    def confidence_score(self):
        """Score de confiance basé sur les votes (0-100)."""
        total = self.upvotes + self.downvotes
        if total == 0:
            return 50  # Neutral
        return int((self.upvotes / total) * 100)
    
    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @classmethod
    def default_ttl_minutes(cls, event_type):
        """Durée de vie par défaut selon le type d'événement."""
        ttl_map = {
            TrafficEventType.ACCIDENT: 120,        # 2 heures
            TrafficEventType.POLICE: 60,           # 1 heure
            TrafficEventType.ROAD_CLOSED: 480,     # 8 heures
            TrafficEventType.FLOODING: 360,        # 6 heures
            TrafficEventType.POTHOLE: 1440,        # 24 heures
            TrafficEventType.TRAFFIC_JAM: 45,      # 45 minutes
            TrafficEventType.ROADWORK: 720,        # 12 heures
            TrafficEventType.HAZARD: 120,          # 2 heures
            TrafficEventType.FUEL_STATION: 240,    # 4 heures
            TrafficEventType.OTHER: 60,            # 1 heure
        }
        return ttl_map.get(event_type, 60)
    
    def save(self, *args, **kwargs):
        # Auto-set expiration if not already set
        if not self.expires_at:
            from django.utils import timezone
            from datetime import timedelta
            ttl = self.default_ttl_minutes(self.event_type)
            self.expires_at = timezone.now() + timedelta(minutes=ttl)
        super().save(*args, **kwargs)


class TrafficEventVote(models.Model):
    """
    Vote (confirmation/infirmation) d'un événement par un coursier.
    Un coursier ne peut voter qu'une fois par événement.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    event = models.ForeignKey(
        TrafficEvent,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name="Événement"
    )
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_votes',
        verbose_name="Votant"
    )
    is_upvote = models.BooleanField(verbose_name="Confirme ?")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Vote événement"
        verbose_name_plural = "Votes événements"
        unique_together = ['event', 'voter']
    
    def __str__(self):
        vote = "👍" if self.is_upvote else "👎"
        return f"{vote} {self.voter} sur {self.event}"


# ============================================
# DISPATCH CONFIGURATION (Admin-Configurable)
# ============================================

class DispatchConfiguration(models.Model):
    """
    Singleton model for dynamic dispatch scoring configuration.
    
    Allows platform admins to adjust dispatch algorithm weights
    and thresholds without code changes via Django Admin.
    
    Only ONE instance should exist at a time (enforced by save()).
    """
    
    class Meta:
        verbose_name = "Configuration du dispatch"
        verbose_name_plural = "Configuration du dispatch"
    
    # ---- Search parameters ----
    initial_radius_km = models.FloatField(
        default=3.0,
        verbose_name="Rayon initial (km)",
        help_text="Rayon de recherche initial pour trouver des coursiers"
    )
    max_radius_km = models.FloatField(
        default=10.0,
        verbose_name="Rayon maximum (km)",
        help_text="Rayon maximum de recherche si pas assez de coursiers"
    )
    radius_increment_km = models.FloatField(
        default=2.0,
        verbose_name="Incrément rayon (km)",
        help_text="De combien augmenter le rayon à chaque itération"
    )
    max_couriers_to_score = models.PositiveIntegerField(
        default=20,
        verbose_name="Max coursiers à évaluer",
        help_text="Nombre maximum de coursiers à scorer par commande"
    )
    max_couriers_to_notify = models.PositiveIntegerField(
        default=5,
        verbose_name="Max coursiers à notifier",
        help_text="Nombre de meilleurs coursiers qui recevront la notification"
    )
    
    # ---- Scoring weights (MUST sum to 1.0) ----
    weight_distance = models.FloatField(
        default=0.25,
        verbose_name="⚖️ Poids : Distance",
        help_text="Proximité au point de pickup (0.0 à 1.0)"
    )
    weight_rating = models.FloatField(
        default=0.20,
        verbose_name="⚖️ Poids : Note moyenne",
        help_text="Note /5 donnée par les clients (0.0 à 1.0)"
    )
    weight_history = models.FloatField(
        default=0.15,
        verbose_name="⚖️ Poids : Historique",
        help_text="Taux de livraisons réussies sur 30 jours (0.0 à 1.0)"
    )
    weight_availability = models.FloatField(
        default=0.10,
        verbose_name="⚖️ Poids : Disponibilité",
        help_text="Temps écoulé depuis la dernière course (0.0 à 1.0)"
    )
    weight_financial = models.FloatField(
        default=0.10,
        verbose_name="⚖️ Poids : Santé financière",
        help_text="Ratio dette/plafond (0.0 à 1.0)"
    )
    weight_response = models.FloatField(
        default=0.05,
        verbose_name="⚖️ Poids : Temps réponse",
        help_text="Rapidité moyenne d'acceptation des courses (0.0 à 1.0)"
    )
    weight_level = models.FloatField(
        default=0.10,
        verbose_name="⚖️ Poids : Niveau coursier",
        help_text="Bonus basé sur le niveau de gamification (0.0 à 1.0)"
    )
    weight_acceptance = models.FloatField(
        default=0.05,
        verbose_name="⚖️ Poids : Taux d'acceptation",
        help_text="Pourcentage de courses acceptées vs refusées (0.0 à 1.0)"
    )
    
    # ---- Thresholds ----
    min_score_threshold = models.FloatField(
        default=30.0,
        verbose_name="Score minimum",
        help_text="Score en dessous duquel un coursier n'est pas considéré (0-100)"
    )
    auto_assign_threshold = models.FloatField(
        default=80.0,
        verbose_name="Seuil d'auto-assignation",
        help_text="Score au-dessus duquel le meilleur coursier est assigné automatiquement (0-100)"
    )
    
    # ---- Distance scoring curve ----
    distance_perfect_km = models.FloatField(
        default=0.5,
        verbose_name="Distance parfaite (km)",
        help_text="Distance en dessous de laquelle le score distance = 100"
    )
    distance_zero_km = models.FloatField(
        default=8.0,
        verbose_name="Distance nulle (km)",
        help_text="Distance au-dessus de laquelle le score distance = 0"
    )
    
    # ---- Rating scoring ----
    min_ratings_for_full_score = models.PositiveIntegerField(
        default=10,
        verbose_name="Nb min de notes",
        help_text="Nombre minimum de notes pour que le score rating soit fiable (sinon score neutre)"
    )
    
    # ---- Level bonus points ----
    level_score_bronze = models.FloatField(
        default=25.0,
        verbose_name="Score niveau Bronze",
        help_text="Score attribué aux coursiers BRONZE (0-100)"
    )
    level_score_silver = models.FloatField(
        default=50.0,
        verbose_name="Score niveau Silver",
        help_text="Score attribué aux coursiers SILVER (0-100)"
    )
    level_score_gold = models.FloatField(
        default=80.0,
        verbose_name="Score niveau Gold",
        help_text="Score attribué aux coursiers GOLD (0-100)"
    )
    level_score_platinum = models.FloatField(
        default=100.0,
        verbose_name="Score niveau Platinum",
        help_text="Score attribué aux coursiers PLATINUM (0-100)"
    )
    
    # ---- Streak bonus ----
    streak_bonus_enabled = models.BooleanField(
        default=True,
        verbose_name="Bonus streak activé",
        help_text="Ajouter un bonus au score si le coursier a une série de succès active"
    )
    streak_bonus_per_delivery = models.FloatField(
        default=0.5,
        verbose_name="Bonus par livraison streak",
        help_text="Points bonus ajoutés par livraison consécutive réussie (max 10 pts)"
    )
    streak_bonus_max = models.FloatField(
        default=10.0,
        verbose_name="Bonus streak maximum",
        help_text="Bonus maximum attribuable via le streak"
    )
    
    # ---- Probation penalty ----
    probation_penalty = models.FloatField(
        default=15.0,
        verbose_name="Pénalité probation",
        help_text="Points retirés du score total pour les coursiers en probation"
    )
    
    # ---- Cache ----
    courier_stats_cache_ttl = models.PositiveIntegerField(
        default=300,
        verbose_name="Cache stats coursier (sec)",
        help_text="Durée du cache pour les statistiques des coursiers (en secondes)"
    )
    
    # ---- Metadata ----
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Modifié par"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notes admin",
        help_text="Notes internes sur les changements effectués"
    )
    
    def __str__(self):
        return "⚙️ Configuration du dispatch"
    
    @property
    def total_weight(self):
        """Sum of all scoring weights — should be 1.0."""
        return round(
            self.weight_distance +
            self.weight_rating +
            self.weight_history +
            self.weight_availability +
            self.weight_financial +
            self.weight_response +
            self.weight_level +
            self.weight_acceptance,
            4
        )
    
    @property
    def weights_valid(self):
        """Check if weights sum to 1.0 (with tolerance)."""
        return abs(self.total_weight - 1.0) < 0.01
    
    def clean(self):
        """Validate that weights sum to 1.0."""
        from django.core.exceptions import ValidationError
        if not self.weights_valid:
            raise ValidationError(
                f"La somme des poids doit être égale à 1.0. "
                f"Somme actuelle : {self.total_weight}"
            )
    
    def save(self, *args, **kwargs):
        """Enforce singleton pattern — only one config instance."""
        self.pk = 1
        super().save(*args, **kwargs)
        # Invalidate cache
        from django.core.cache import cache
        cache.delete('dispatch_configuration')
    
    @classmethod
    def get_config(cls):
        """
        Get the active dispatch configuration.
        Creates default config if none exists.
        Uses cache for performance.
        """
        from django.core.cache import cache
        
        config = cache.get('dispatch_configuration')
        if config is None:
            config, _ = cls.objects.get_or_create(pk=1)
            cache.set('dispatch_configuration', config, 600)  # Cache 10 min
        return config
    
    def get_level_score(self, level: str) -> float:
        """Get the score for a courier level."""
        level_map = {
            'BRONZE': self.level_score_bronze,
            'SILVER': self.level_score_silver,
            'GOLD': self.level_score_gold,
            'PLATINUM': self.level_score_platinum,
        }
        return level_map.get(level, self.level_score_bronze)
