import uuid
from django.db import models, transaction
from django.conf import settings
from decimal import Decimal
from django.utils import timezone

class DisputeStatus(models.TextChoices):
    PENDING = 'PENDING', 'En attente'
    INVESTIGATING = 'INVESTIGATING', 'En cours d\'investigation'
    RESOLVED = 'RESOLVED', 'Résolu'
    REJECTED = 'REJECTED', 'Rejeté'
    CANCELLED = 'CANCELLED', 'Annulé'

class DisputeReason(models.TextChoices):
    ITEM_NOT_RECEIVED = 'ITEM_NOT_RECEIVED', 'Colis non reçu'
    ITEM_DAMAGED = 'ITEM_DAMAGED', 'Colis endommagé'
    ITEM_MISMATCH = 'ITEM_MISMATCH', 'Contenu non conforme'
    OVERCHARGED = 'OVERCHARGED', 'Surfacturation'
    COURIER_CONDUCT = 'COURIER_CONDUCT', 'Comportement du coursier'
    OTHER = 'OTHER', 'Autre'

class Dispute(models.Model):
    """
    Dispute model for handling delivery issues.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.ForeignKey(
        'logistics.Delivery',
        on_delete=models.CASCADE,
        related_name='disputes',
        verbose_name="Livraison"
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_disputes',
        verbose_name="Créé par"
    )
    
    reason = models.CharField(
        max_length=50,
        choices=DisputeReason.choices,
        verbose_name="Raison"
    )
    description = models.TextField(verbose_name="Description détaillée")
    status = models.CharField(
        max_length=20,
        choices=DisputeStatus.choices,
        default=DisputeStatus.PENDING,
        verbose_name="Statut"
    )
    
    # Evidence
    photo_evidence = models.ImageField(
        upload_to='disputes/evidence/',
        null=True,
        blank=True,
        verbose_name="Preuve photo"
    )
    
    # Resolution
    resolution_note = models.TextField(blank=True, verbose_name="Note de résolution")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_disputes',
        verbose_name="Résolu par"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Financial impact
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Montant remboursé"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Litige"
        verbose_name_plural = "Litiges"
        ordering = ['-created_at']

    def __str__(self):
        return f"Litige {str(self.id)[:8]} - {self.get_reason_display()}"


class RefundStatus(models.TextChoices):
    PENDING = 'PENDING', 'En attente'
    COMPLETED = 'COMPLETED', 'Effectué'
    FAILED = 'FAILED', 'Échoué'

class Refund(models.Model):
    """
    Refund model linked to a dispute and a transaction.
    """
    id = uuid.uuid4() # Manual generation to avoid duplicate issues on some systems, but better use default in models
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    dispute = models.OneToOneField(
        Dispute,
        on_delete=models.CASCADE,
        related_name='refund',
        verbose_name="Litige"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='refunds',
        verbose_name="Bénéficiaire"
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant"
    )
    
    transaction = models.OneToOneField(
        'finance.Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_record',
        verbose_name="Transaction liée"
    )
    
    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
        verbose_name="Statut"
    )
    
    reason = models.TextField(blank=True, verbose_name="Raison du remboursement")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Remboursement"
        verbose_name_plural = "Remboursements"
        ordering = ['-created_at']

    def __str__(self):
        return f"Remboursement {self.amount} XAF - {self.user.phone_number}"
