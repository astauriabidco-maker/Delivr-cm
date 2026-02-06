"""
CORE App - Courier Onboarding System

Secure multi-step onboarding for couriers in Cameroon.
Documents: CNI, Casier Judiciaire, Permis, Carte Grise, Selfie
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class OnboardingStep(models.TextChoices):
    """Onboarding progression steps."""
    PHONE_VERIFICATION = 'PHONE_VERIFIED', 'Téléphone vérifié'
    DOCUMENTS_UPLOADED = 'DOCS_UPLOADED', 'Documents soumis'
    EMERGENCY_CONTACT = 'EMERGENCY', 'Contact d\'urgence'
    CAUTION_PAID = 'CAUTION', 'Caution payée'
    CONTRACT_SIGNED = 'CONTRACT', 'Contrat signé'
    ADMIN_VALIDATED = 'VALIDATED', 'Validé par admin'
    PROBATION = 'PROBATION', 'Période probatoire'
    COMPLETED = 'COMPLETED', 'Onboarding terminé'


class OnboardingStatus(models.TextChoices):
    """Overall onboarding status."""
    PENDING = 'PENDING', 'En cours'
    AWAITING_REVIEW = 'AWAITING', 'En attente de validation'
    APPROVED = 'APPROVED', 'Approuvé'
    REJECTED = 'REJECTED', 'Rejeté'
    SUSPENDED = 'SUSPENDED', 'Suspendu'


class VehicleType(models.TextChoices):
    """Type of vehicle used by courier."""
    MOTO = 'MOTO', 'Moto'
    BICYCLE = 'BICYCLE', 'Vélo'
    FOOT = 'FOOT', 'À pied'
    CAR = 'CAR', 'Voiture'


class CourierOnboarding(models.Model):
    """
    Complete onboarding record for a courier.
    
    Tracks all documents, verification steps, and caution payment.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    courier = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='onboarding',
        verbose_name="Coursier"
    )
    
    # Current Step & Status
    current_step = models.CharField(
        max_length=20,
        choices=OnboardingStep.choices,
        default=OnboardingStep.PHONE_VERIFICATION,
        verbose_name="Étape actuelle"
    )
    status = models.CharField(
        max_length=20,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.PENDING,
        verbose_name="Statut global"
    )
    
    # =========================================
    # STEP 1: Phone Verification (OTP)
    # =========================================
    phone_verified = models.BooleanField(default=False, verbose_name="Téléphone vérifié")
    phone_otp_code = models.CharField(max_length=6, blank=True, verbose_name="Code OTP")
    phone_otp_sent_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    
    # =========================================
    # STEP 2: Document Upload
    # =========================================
    
    # CNI (Carte Nationale d'Identité)
    cni_front = models.ImageField(
        upload_to='onboarding/cni/front/',
        null=True, blank=True,
        verbose_name="CNI Recto"
    )
    cni_back = models.ImageField(
        upload_to='onboarding/cni/back/',
        null=True, blank=True,
        verbose_name="CNI Verso"
    )
    cni_number = models.CharField(
        max_length=50, blank=True,
        verbose_name="Numéro CNI"
    )
    cni_expiry_date = models.DateField(
        null=True, blank=True,
        verbose_name="Date d'expiration CNI"
    )
    
    # Selfie with CNI (Anti-fraud)
    selfie_with_cni = models.ImageField(
        upload_to='onboarding/selfies/',
        null=True, blank=True,
        verbose_name="Selfie avec CNI",
        help_text="Photo de vous tenant votre CNI"
    )
    
    # Casier Judiciaire (Criminal Record - Bulletin n°3)
    casier_judiciaire = models.FileField(
        upload_to='onboarding/casier/',
        null=True, blank=True,
        verbose_name="Casier Judiciaire (Bulletin n°3)",
        help_text="Doit être récent (< 3 mois)"
    )
    casier_issue_date = models.DateField(
        null=True, blank=True,
        verbose_name="Date d'émission casier"
    )
    
    # Vehicle Documents
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.MOTO,
        verbose_name="Type de véhicule"
    )
    
    # Permis de conduire (si moto/voiture)
    driving_license = models.ImageField(
        upload_to='onboarding/permis/',
        null=True, blank=True,
        verbose_name="Permis de conduire"
    )
    driving_license_number = models.CharField(
        max_length=50, blank=True,
        verbose_name="Numéro permis"
    )
    driving_license_category = models.CharField(
        max_length=10, blank=True,
        verbose_name="Catégorie (A, B, etc.)"
    )
    
    # Carte Grise (si propriétaire du véhicule)
    carte_grise = models.ImageField(
        upload_to='onboarding/carte_grise/',
        null=True, blank=True,
        verbose_name="Carte Grise"
    )
    vehicle_plate = models.CharField(
        max_length=20, blank=True,
        verbose_name="Immatriculation"
    )
    
    # Photo du véhicule
    vehicle_photo = models.ImageField(
        upload_to='onboarding/vehicles/',
        null=True, blank=True,
        verbose_name="Photo du véhicule"
    )
    
    documents_submitted_at = models.DateTimeField(null=True, blank=True)
    
    # =========================================
    # STEP 3: Emergency Contact
    # =========================================
    emergency_contact_name = models.CharField(
        max_length=150, blank=True,
        verbose_name="Nom contact d'urgence"
    )
    emergency_contact_phone = models.CharField(
        max_length=15, blank=True,
        verbose_name="Téléphone urgence"
    )
    emergency_contact_relation = models.CharField(
        max_length=50, blank=True,
        verbose_name="Relation (Père, Mère, Époux, etc.)"
    )
    
    # Home Address (for accountability)
    home_address = models.TextField(
        blank=True,
        verbose_name="Adresse domicile",
        help_text="Quartier, rue, repère"
    )
    home_city = models.CharField(
        max_length=50, blank=True,
        default="Douala",
        verbose_name="Ville"
    )
    
    # =========================================
    # STEP 4: Caution Payment
    # =========================================
    caution_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=15000,  # 15,000 XAF default
        verbose_name="Montant caution (XAF)"
    )
    caution_paid = models.BooleanField(
        default=False,
        verbose_name="Caution payée"
    )
    caution_payment_method = models.CharField(
        max_length=20, blank=True,
        verbose_name="Méthode paiement (MOMO, ORANGE, CASH)"
    )
    caution_transaction_id = models.CharField(
        max_length=100, blank=True,
        verbose_name="ID transaction caution"
    )
    caution_paid_at = models.DateTimeField(null=True, blank=True)
    
    # =========================================
    # STEP 5: Contract Signing
    # =========================================
    contract_version = models.CharField(
        max_length=20, default="v1.0",
        verbose_name="Version contrat"
    )
    contract_signed = models.BooleanField(
        default=False,
        verbose_name="Contrat signé"
    )
    contract_signed_at = models.DateTimeField(null=True, blank=True)
    signature_data = models.TextField(
        blank=True,
        verbose_name="Signature (Base64 ou texte acceptation)"
    )
    contract_ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name="Adresse IP signature"
    )
    
    # =========================================
    # STEP 6: Admin Validation
    # =========================================
    admin_notes = models.TextField(
        blank=True,
        verbose_name="Notes admin"
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='validated_onboardings',
        verbose_name="Validé par"
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(
        blank=True,
        verbose_name="Motif de rejet"
    )
    
    # =========================================
    # STEP 7: Probation Period
    # =========================================
    probation_deliveries_required = models.PositiveIntegerField(
        default=10,
        verbose_name="Livraisons probatoires requises"
    )
    probation_deliveries_completed = models.PositiveIntegerField(
        default=0,
        verbose_name="Livraisons probatoires complétées"
    )
    probation_started_at = models.DateTimeField(null=True, blank=True)
    probation_completed_at = models.DateTimeField(null=True, blank=True)
    
    # =========================================
    # Timestamps
    # =========================================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Onboarding Coursier"
        verbose_name_plural = "Onboardings Coursiers"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Onboarding {self.courier.phone_number} - {self.get_status_display()}"
    
    @property
    def progress_percentage(self) -> int:
        """Calculate onboarding progress (0-100%)."""
        steps_completed = 0
        total_steps = 7
        
        if self.phone_verified:
            steps_completed += 1
        if self.documents_submitted_at:
            steps_completed += 1
        if self.emergency_contact_name:
            steps_completed += 1
        if self.caution_paid:
            steps_completed += 1
        if self.contract_signed:
            steps_completed += 1
        if self.status == OnboardingStatus.APPROVED:
            steps_completed += 1
        if self.probation_completed_at:
            steps_completed += 1
        
        return int((steps_completed / total_steps) * 100)
    
    @property
    def is_documents_complete(self) -> bool:
        """Check if all required documents are uploaded."""
        # CNI is always required
        if not self.cni_front or not self.selfie_with_cni:
            return False
        
        # Vehicle documents required for moto/car
        if self.vehicle_type in [VehicleType.MOTO, VehicleType.CAR]:
            if not self.driving_license:
                return False
        
        return True
    
    @property
    def is_probation_complete(self) -> bool:
        """Check if probation period is complete."""
        return self.probation_deliveries_completed >= self.probation_deliveries_required


class SMSOTPLog(models.Model):
    """
    Log of SMS OTP codes sent for verification.
    
    Supports Orange Cameroon and MTN Cameroon SMS APIs.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=15, verbose_name="Numéro")
    otp_code = models.CharField(max_length=6, verbose_name="Code OTP")
    
    # Provider info
    provider = models.CharField(
        max_length=20,
        verbose_name="Opérateur",
        help_text="ORANGE_CM, MTN_CM, ou WHATSAPP"
    )
    provider_message_id = models.CharField(
        max_length=100, blank=True,
        verbose_name="ID message opérateur"
    )
    
    # Status
    sent_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name="Expire à")
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Security
    attempts = models.PositiveIntegerField(default=0, verbose_name="Tentatives")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Log OTP SMS"
        verbose_name_plural = "Logs OTP SMS"
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"OTP {self.phone_number} - {self.otp_code} ({'✓' if self.verified else '⏳'})"
    
    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.verified and self.attempts < 5
