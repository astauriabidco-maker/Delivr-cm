"""
CORE App - Custom User Model for DELIVR-CM

Handles: Users (Clients, Couriers, Businesses, Admins)
"""

import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.gis.db import models
from django.core.validators import RegexValidator
from django.utils.text import slugify
from decimal import Decimal


class UserRole(models.TextChoices):
    """User role enumeration."""
    ADMIN = 'ADMIN', 'Administrateur'
    CLIENT = 'CLIENT', 'Client Particulier'
    COURIER = 'COURIER', 'Coursier'
    BUSINESS = 'BUSINESS', 'E-commerçant'


class UserManager(BaseUserManager):
    """Custom user manager for phone-based authentication."""

    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Le numéro de téléphone est obligatoire')
        
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN)
        extra_fields.setdefault('is_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model using phone number as primary identifier.
    
    Key Business Logic:
    - wallet_balance can be NEGATIVE for couriers (debt system)
    - debt_ceiling blocks courier if wallet_balance < -debt_ceiling
    - slug is auto-generated for BUSINESS users (public checkout URL)
    """

    # Phone number validator for Cameroon (+237)
    phone_regex = RegexValidator(
        regex=r'^\+237[0-9]{9}$',
        message="Format: +237XXXXXXXXX (9 chiffres après +237)"
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        validators=[phone_regex],
        verbose_name="Numéro WhatsApp"
    )
    
    # Profile
    full_name = models.CharField(max_length=150, blank=True, verbose_name="Nom complet")
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CLIENT,
        verbose_name="Rôle"
    )
    
    # Slug for public checkout URL (BUSINESS users only)
    slug = models.SlugField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="URL publique",
        help_text="Ex: ma-boutique → delivr.cm/book/ma-boutique"
    )
    
    # Location (optional - last known position)
    last_location = models.PointField(
        null=True,
        blank=True,
        srid=4326,
        verbose_name="Dernière position GPS"
    )
    last_location_updated = models.DateTimeField(null=True, blank=True)
    
    # Wallet & Debt System
    wallet_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Solde Wallet (XAF)"
    )
    debt_ceiling = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('2500.00'),
        verbose_name="Plafond dette (XAF)"
    )
    
    # Business Partner Approval
    is_business_approved = models.BooleanField(
        default=False,
        verbose_name="Partenaire approuvé",
        help_text="Doit être activé par l'admin pour accès aux clés API"
    )
    
    # Branding for Public Checkout (BUSINESS users)
    shop_logo = models.ImageField(
        upload_to='branding/logos/',
        null=True,
        blank=True,
        verbose_name="Logo boutique"
    )
    brand_color = models.CharField(
        max_length=7,
        default='#00d084',
        verbose_name="Couleur principale",
        help_text="Code hex, ex: #00d084"
    )
    class BusinessType(models.TextChoices):
        SOCIAL = 'SOCIAL', 'Réseaux Sociaux (Instagram, FB, WA)'
        WEB = 'WEB', 'Site Web (WooCommerce, Shopify...)'
        BOTH = 'BOTH', 'Les deux (Réseaux Sociaux & Site Web)'

    business_type = models.CharField(
        max_length=20,
        choices=BusinessType.choices,
        default=BusinessType.SOCIAL,
        verbose_name="Type de business"
    )

    welcome_message = models.TextField(
        blank=True,
        verbose_name="Message de bienvenue",
        help_text="Affiché sur la page de commande publique"
    )

    
    # Verification (for couriers)
    is_verified = models.BooleanField(
        default=False,
        verbose_name="Documents vérifiés"
    )
    cni_document = models.FileField(
        upload_to='documents/cni/',
        null=True,
        blank=True,
        verbose_name="Photo CNI"
    )
    moto_document = models.FileField(
        upload_to='documents/moto/',
        null=True,
        blank=True,
        verbose_name="Photo Moto"
    )
    
    # ============================================
    # COURIER ONBOARDING (Semi-Automatic Approval)
    # ============================================
    
    class OnboardingStatus(models.TextChoices):
        """Courier onboarding progression."""
        PENDING = 'PENDING', 'Documents en attente'
        PROBATION = 'PROBATION', 'Période d\'essai'
        APPROVED = 'APPROVED', 'Approuvé'
        REJECTED = 'REJECTED', 'Rejeté'
    
    onboarding_status = models.CharField(
        max_length=20,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.PENDING,
        verbose_name="Statut onboarding"
    )
    probation_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Début période d'essai"
    )
    probation_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fin période d'essai"
    )
    probation_delivery_limit = models.PositiveIntegerField(
        default=10,
        verbose_name="Limite livraisons/jour (probation)"
    )
    probation_deliveries_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Livraisons pendant probation"
    )
    trust_score = models.FloatField(
        default=0.5,
        verbose_name="Score de confiance",
        help_text="0.0 à 1.0, calculé automatiquement"
    )
    
    # ============================================
    # COURIER EXTENDED PROFILE (Fleet Management)
    # ============================================

    
    class CourierLevel(models.TextChoices):
        """Courier progression levels for gamification."""
        BRONZE = 'BRONZE', 'Bronze'
        SILVER = 'SILVER', 'Silver'
        GOLD = 'GOLD', 'Gold'
        PLATINUM = 'PLATINUM', 'Platine'
    
    # Online Status & Availability
    is_online = models.BooleanField(
        default=False,
        verbose_name="En ligne",
        help_text="Le coursier est-il disponible pour recevoir des commandes?"
    )
    last_online_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dernière connexion"
    )
    
    # Courier Level & Gamification
    courier_level = models.CharField(
        max_length=20,
        choices=CourierLevel.choices,
        default=CourierLevel.BRONZE,
        verbose_name="Niveau coursier"
    )
    
    # Performance Statistics (denormalized for fast access)
    total_deliveries_completed = models.PositiveIntegerField(
        default=0,
        verbose_name="Livraisons complétées"
    )
    total_distance_km = models.FloatField(
        default=0.0,
        verbose_name="Distance totale (km)"
    )
    average_rating = models.FloatField(
        default=5.0,
        verbose_name="Note moyenne",
        help_text="Note sur 5 étoiles"
    )
    total_ratings_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre d'évaluations"
    )
    
    # Reliability Metrics
    acceptance_rate = models.FloatField(
        default=100.0,
        verbose_name="Taux d'acceptation (%)",
        help_text="Pourcentage de commandes acceptées"
    )
    cancellation_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Annulations"
    )
    consecutive_success_streak = models.PositiveIntegerField(
        default=0,
        verbose_name="Série de succès",
        help_text="Livraisons consécutives sans incident"
    )
    best_streak = models.PositiveIntegerField(
        default=0,
        verbose_name="Meilleure série"
    )
    
    # Response Time Tracking
    average_response_seconds = models.PositiveIntegerField(
        default=0,
        verbose_name="Temps de réponse moyen (sec)",
        help_text="Délai moyen pour accepter une commande"
    )
    
    # Django Auth Fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    
    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.full_name or self.phone_number} ({self.role})"

    def save(self, *args, **kwargs):
        """
        Auto-generate slug for BUSINESS users if not set.
        Uses full_name to create a unique URL-friendly slug.
        """
        if self.role == UserRole.BUSINESS and not self.slug and self.full_name:
            base_slug = slugify(self.full_name)
            slug = base_slug
            counter = 1
            
            # Ensure uniqueness
            while User.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        
        super().save(*args, **kwargs)

    @property
    def is_courier_blocked(self) -> bool:
        """
        Check if courier is blocked due to excessive debt.
        Kill Switch: wallet_balance < -debt_ceiling
        """
        if self.role != UserRole.COURIER:
            return False
        return self.wallet_balance < -self.debt_ceiling

    @property
    def is_courier(self) -> bool:
        return self.role == UserRole.COURIER

    @property
    def is_business(self) -> bool:
        return self.role == UserRole.BUSINESS
    
    @property
    def public_checkout_url(self) -> str:
        """Returns the public checkout URL for this business."""
        if self.slug:
            return f"/book/{self.slug}/"
        return ""


class AdminActivityLog(models.Model):
    """
    Audit log for admin actions.
    
    Tracks who did what, when, and from where.
    """
    
    class ActionType(models.TextChoices):
        CREATE = 'CREATE', 'Création'
        UPDATE = 'UPDATE', 'Modification'
        DELETE = 'DELETE', 'Suppression'
        APPROVE = 'APPROVE', 'Approbation'
        REJECT = 'REJECT', 'Rejet'
        BLOCK = 'BLOCK', 'Blocage'
        UNBLOCK = 'UNBLOCK', 'Déblocage'
        EXPORT = 'EXPORT', 'Export'
        IMPORT = 'IMPORT', 'Import'
        LOGIN = 'LOGIN', 'Connexion admin'
    
    user = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_activity_logs',
        verbose_name="Administrateur"
    )
    action = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        verbose_name="Action"
    )
    target_model = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Modèle cible"
    )
    target_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID cible"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Détails"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Adresse IP"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Log d'activité admin"
        verbose_name_plural = "Logs d'activité admin"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['target_model', 'created_at']),
        ]
    
    def __str__(self):
        user_str = self.user.phone_number if self.user else "System"
        return f"{user_str} | {self.action} | {self.target_model} | {self.created_at:%d/%m %H:%M}"
    
    @classmethod
    def log(cls, user, action, target_model='', target_id='', details=None, ip_address=None):
        """Convenience method to create a log entry."""
        return cls.objects.create(
            user=user,
            action=action,
            target_model=target_model,
            target_id=str(target_id) if target_id else '',
            details=details or {},
            ip_address=ip_address,
        )


class PromoCode(models.Model):
    """
    Promotional discount codes for deliveries.
    """
    
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'PERCENTAGE', 'Pourcentage (%)'
        FIXED = 'FIXED', 'Montant fixe (XAF)'
    
    code = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Code promo",
        help_text="Code unique, ex: BIENVENUE2025"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
        verbose_name="Type de remise"
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Valeur",
        help_text="Pourcentage (ex: 10) ou montant fixe (ex: 500)"
    )
    max_uses = models.PositiveIntegerField(
        default=0,
        verbose_name="Utilisations max",
        help_text="0 = illimité"
    )
    current_uses = models.PositiveIntegerField(
        default=0,
        verbose_name="Utilisations actuelles"
    )
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Montant minimum commande (XAF)"
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Remise max (XAF)",
        help_text="Plafond pour les remises en pourcentage"
    )
    valid_from = models.DateTimeField(
        verbose_name="Valide à partir de"
    )
    valid_until = models.DateTimeField(
        verbose_name="Valide jusqu'au"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif"
    )
    created_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_promos',
        verbose_name="Créé par"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Code promo"
        verbose_name_plural = "Codes promo"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} ({self.get_discount_type_display()}: {self.discount_value})"
    
    @property
    def is_valid(self):
        """Check if the promo code is currently valid."""
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from or now > self.valid_until:
            return False
        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False
        return True
    
    def apply_discount(self, total_price):
        """
        Apply the discount to a total price.
        
        Returns:
            Decimal: discounted price (never below 0)
        """
        if not self.is_valid:
            return total_price
        if total_price < self.min_order_amount:
            return total_price
        
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = total_price * self.discount_value / 100
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        else:
            discount = self.discount_value
        
        return max(Decimal('0.00'), total_price - discount)


