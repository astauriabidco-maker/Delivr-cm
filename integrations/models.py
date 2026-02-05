"""
Integrations App - Configuration Models

Singleton pattern for storing integration configurations.
Uses hybrid approach: secrets from .env, business config from DB.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class IntegrationConfig(models.Model):
    """
    Singleton configuration model for all integrations.
    
    Uses a single row with ID=1.
    Business configurations are stored in DB and can be modified.
    Secrets remain in .env and are displayed as read-only.
    """
    
    # ===========================================
    # WHATSAPP PROVIDER CONFIGURATION
    # ===========================================
    
    PROVIDER_CHOICES = [
        ('twilio', 'Twilio'),
        ('meta', 'Meta Cloud API'),
    ]
    
    active_whatsapp_provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='twilio',
        verbose_name='Provider WhatsApp actif',
        help_text='Sélectionnez le provider pour les notifications WhatsApp'
    )
    
    # Twilio Configuration (modifiable in DB)
    twilio_whatsapp_number = models.CharField(
        max_length=50,
        default='whatsapp:+14155238886',
        verbose_name='Numéro WhatsApp Twilio',
        help_text='Format: whatsapp:+XXXXXXXXXXX'
    )
    
    # Meta Configuration (modifiable in DB)
    meta_phone_number_id = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name='Phone Number ID Meta',
        help_text='ID du numéro de téléphone dans Meta Business'
    )
    
    meta_verify_token = models.CharField(
        max_length=100,
        default='delivr-cm-webhook-verify-token',
        verbose_name='Token de vérification Meta',
        help_text='Token utilisé pour vérifier les webhooks Meta'
    )
    
    # ===========================================
    # PRICING ENGINE CONFIGURATION
    # ===========================================
    
    pricing_base_fare = models.PositiveIntegerField(
        default=500,
        validators=[MinValueValidator(0)],
        verbose_name='Tarif de base (FCFA)',
        help_text='Montant de base pour toute livraison'
    )
    
    pricing_cost_per_km = models.PositiveIntegerField(
        default=150,
        validators=[MinValueValidator(0)],
        verbose_name='Coût par kilomètre (FCFA)',
        help_text='Coût additionnel par kilomètre parcouru'
    )
    
    pricing_minimum_fare = models.PositiveIntegerField(
        default=1000,
        validators=[MinValueValidator(0)],
        verbose_name='Tarif minimum (FCFA)',
        help_text='Prix plancher pour toute livraison'
    )
    
    platform_fee_percent = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Commission plateforme (%)',
        help_text='Pourcentage prélevé par la plateforme sur chaque livraison'
    )
    
    courier_debt_ceiling = models.PositiveIntegerField(
        default=2500,
        validators=[MinValueValidator(0)],
        verbose_name='Plafond dette coursier (FCFA)',
        help_text='Montant maximum de dette autorisé avant blocage'
    )
    
    # ===========================================
    # EXTERNAL SERVICES CONFIGURATION
    # ===========================================
    
    osrm_base_url = models.URLField(
        default='http://osrm:5000',
        verbose_name='URL OSRM',
        help_text='URL du service de routing OSRM'
    )
    
    nominatim_base_url = models.URLField(
        default='http://nominatim:8080',
        verbose_name='URL Nominatim',
        help_text='URL du service de géocodage Nominatim'
    )
    
    # ===========================================
    # METADATA
    # ===========================================
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Dernière modification'
    )
    
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Modifié par',
        related_name='integration_config_updates'
    )
    
    class Meta:
        verbose_name = 'Configuration des Intégrations'
        verbose_name_plural = 'Configuration des Intégrations'
    
    def __str__(self):
        return 'Configuration des Intégrations'
    
    def save(self, *args, **kwargs):
        """Enforce singleton pattern - always use pk=1."""
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion of singleton."""
        pass
    
    @classmethod
    def get_solo(cls):
        """
        Get or create the singleton instance.
        
        Returns:
            IntegrationConfig: The single configuration instance
        """
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def calculate_sample_price(self, distance_km: float = 5.0) -> dict:
        """
        Calculate a sample delivery price for display purposes.
        
        Args:
            distance_km: Sample distance in kilometers
            
        Returns:
            dict with total_price, platform_fee, and courier_earning
        """
        raw_price = self.pricing_base_fare + (self.pricing_cost_per_km * distance_km)
        total_price = max(raw_price, self.pricing_minimum_fare)
        platform_fee = int(total_price * self.platform_fee_percent / 100)
        courier_earning = total_price - platform_fee
        
        return {
            'distance_km': distance_km,
            'total_price': int(total_price),
            'platform_fee': platform_fee,
            'courier_earning': courier_earning,
        }
