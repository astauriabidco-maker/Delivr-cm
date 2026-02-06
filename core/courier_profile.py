"""
CORE App - Courier Profile Models for DELIVR-CM

Extended models for Fleet Management:
- CourierAvailability: Shift scheduling
- CourierPerformanceLog: Daily performance aggregation
- CourierBadge: Achievement tracking
"""

import uuid
from django.db import models
from django.conf import settings
from decimal import Decimal


class DayOfWeek(models.IntegerChoices):
    """Days of the week for availability scheduling."""
    MONDAY = 0, 'Lundi'
    TUESDAY = 1, 'Mardi'
    WEDNESDAY = 2, 'Mercredi'
    THURSDAY = 3, 'Jeudi'
    FRIDAY = 4, 'Vendredi'
    SATURDAY = 5, 'Samedi'
    SUNDAY = 6, 'Dimanche'


class CourierAvailability(models.Model):
    """
    Courier shift scheduling.
    
    Allows couriers to define when they are typically available,
    which helps with capacity planning and dispatch optimization.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='availability_slots',
        verbose_name="Coursier"
    )
    day_of_week = models.IntegerField(
        choices=DayOfWeek.choices,
        verbose_name="Jour de la semaine"
    )
    start_time = models.TimeField(verbose_name="Heure de début")
    end_time = models.TimeField(verbose_name="Heure de fin")
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Ce créneau est-il actuellement actif?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Disponibilité Coursier"
        verbose_name_plural = "Disponibilités Coursiers"
        ordering = ['day_of_week', 'start_time']
        unique_together = ['courier', 'day_of_week', 'start_time']

    def __str__(self):
        return f"{self.courier.phone_number} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

    @property
    def duration_hours(self) -> float:
        """Calculate slot duration in hours."""
        from datetime import datetime, timedelta
        start = datetime.combine(datetime.today(), self.start_time)
        end = datetime.combine(datetime.today(), self.end_time)
        if end < start:  # Crosses midnight
            end += timedelta(days=1)
        return (end - start).total_seconds() / 3600


class CourierPerformanceLog(models.Model):
    """
    Daily aggregated performance metrics for couriers.
    
    Used for:
    - Performance tracking over time
    - Trend analysis
    - Level progression evaluation
    - Admin dashboards
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='performance_logs',
        verbose_name="Coursier"
    )
    date = models.DateField(verbose_name="Date")
    
    # Delivery Metrics
    deliveries_completed = models.PositiveIntegerField(
        default=0,
        verbose_name="Livraisons complétées"
    )
    deliveries_cancelled = models.PositiveIntegerField(
        default=0,
        verbose_name="Livraisons annulées"
    )
    deliveries_failed = models.PositiveIntegerField(
        default=0,
        verbose_name="Livraisons échouées"
    )
    
    # Financial Metrics
    total_earnings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Gains du jour (XAF)"
    )
    total_commission_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Commissions payées (XAF)"
    )
    
    # Distance & Time
    total_distance_km = models.FloatField(
        default=0.0,
        verbose_name="Distance parcourue (km)"
    )
    total_online_minutes = models.PositiveIntegerField(
        default=0,
        verbose_name="Temps en ligne (min)"
    )
    average_response_seconds = models.PositiveIntegerField(
        default=0,
        verbose_name="Temps de réponse moyen (sec)"
    )
    
    # Rating
    ratings_received = models.PositiveIntegerField(
        default=0,
        verbose_name="Évaluations reçues"
    )
    ratings_sum = models.FloatField(
        default=0.0,
        verbose_name="Somme des notes"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log Performance Coursier"
        verbose_name_plural = "Logs Performance Coursiers"
        ordering = ['-date']
        unique_together = ['courier', 'date']
        indexes = [
            models.Index(fields=['courier', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.courier.phone_number} - {self.date}"

    @property
    def average_rating(self) -> float:
        """Calculate average rating for the day."""
        if self.ratings_received == 0:
            return 0.0
        return round(self.ratings_sum / self.ratings_received, 2)

    @property
    def success_rate(self) -> float:
        """Calculate success rate for the day."""
        total = self.deliveries_completed + self.deliveries_cancelled + self.deliveries_failed
        if total == 0:
            return 100.0
        return round((self.deliveries_completed / total) * 100, 1)


class BadgeType(models.TextChoices):
    """Types of badges that can be earned."""
    FIRST_DELIVERY = 'FIRST_DELIVERY', 'Première Course 🎉'
    STREAK_10 = 'STREAK_10', '10 Courses Sans Annulation 🔥'
    STREAK_50 = 'STREAK_50', '50 Courses Sans Annulation 💪'
    STREAK_100 = 'STREAK_100', '100 Courses Sans Annulation 🏆'
    NIGHT_OWL = 'NIGHT_OWL', 'Livreur Nocturne 🦉'
    EARLY_BIRD = 'EARLY_BIRD', 'Lève-Tôt 🌅'
    SPEED_DEMON = 'SPEED_DEMON', 'Temps de Réponse <2min ⚡'
    DISTANCE_100 = 'DISTANCE_100', '100 km Parcourus 🚴'
    DISTANCE_500 = 'DISTANCE_500', '500 km Parcourus 🛵'
    DISTANCE_1000 = 'DISTANCE_1000', '1000 km Parcourus 🏍️'
    PERFECT_WEEK = 'PERFECT_WEEK', 'Semaine Parfaite ⭐'
    TOP_RATED = 'TOP_RATED', 'Note 5 Étoiles 🌟'
    VETERAN = 'VETERAN', '500 Livraisons 🎖️'
    LEGEND = 'LEGEND', '1000 Livraisons 👑'


class CourierBadge(models.Model):
    """
    Badge/achievement earned by a courier.
    
    Badges are awarded automatically based on performance
    milestones and special achievements.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='badges',
        verbose_name="Coursier"
    )
    badge_type = models.CharField(
        max_length=50,
        choices=BadgeType.choices,
        verbose_name="Type de badge"
    )
    earned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'obtention"
    )
    # Optional: delivery that triggered the badge
    triggered_by_delivery = models.ForeignKey(
        'logistics.Delivery',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Livraison déclencheuse"
    )

    class Meta:
        verbose_name = "Badge Coursier"
        verbose_name_plural = "Badges Coursiers"
        ordering = ['-earned_at']
        unique_together = ['courier', 'badge_type']

    def __str__(self):
        return f"{self.courier.phone_number} - {self.get_badge_type_display()}"

    @property
    def icon(self) -> str:
        """Extract emoji icon from badge display name."""
        display = self.get_badge_type_display()
        # Return last character (the emoji)
        return display.split()[-1] if display else '🏅'


class CourierZonePreference(models.Model):
    """
    Courier preferred working zones (neighborhoods).
    
    Helps with dispatch optimization by matching
    couriers with deliveries in their preferred areas.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='zone_preferences',
        verbose_name="Coursier"
    )
    neighborhood = models.ForeignKey(
        'logistics.Neighborhood',
        on_delete=models.CASCADE,
        verbose_name="Quartier"
    )
    priority = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Priorité",
        help_text="1 = haute priorité"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Préférence Zone Coursier"
        verbose_name_plural = "Préférences Zones Coursiers"
        ordering = ['priority']
        unique_together = ['courier', 'neighborhood']

    def __str__(self):
        return f"{self.courier.phone_number} - {self.neighborhood.name}"
