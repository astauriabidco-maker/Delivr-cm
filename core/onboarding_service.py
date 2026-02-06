"""
Onboarding Service for DELIVR-CM Couriers

Manages semi-automatic courier approval flow:
1. Courier submits documents (CNI, photo moto)
2. Fast-track to PROBATION mode (limited deliveries)
3. Auto-approve after successful probation
"""

import logging
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone

from core.models import User, UserRole

logger = logging.getLogger(__name__)


class OnboardingService:
    """
    Semi-automatic courier onboarding flow.
    
    Flow:
    1. PENDING: Courier registers, uploads documents
    2. PROBATION: Basic docs verified, limited to 10 deliveries/day
    3. APPROVED: 20+ successful deliveries + rating > 4.0 = auto-approve
    4. REJECTED: Admin manually rejects (fraud, behavior)
    """
    
    # Thresholds for auto-approval
    MIN_PROBATION_DELIVERIES = 20  # Deliveries needed during probation
    MIN_RATING_FOR_APPROVAL = 4.0  # Minimum average rating
    PROBATION_DAYS = 14  # Default probation period
    DAILY_LIMIT_PROBATION = 10  # Max deliveries per day during probation
    
    @staticmethod
    @transaction.atomic
    def start_probation(courier: User) -> bool:
        """
        Start probation period for a courier.
        
        Called when admin fast-tracks document review or auto-check passes.
        
        Args:
            courier: User with role=COURIER
            
        Returns:
            True if started, False if not eligible
        """
        if courier.role != UserRole.COURIER:
            logger.warning(f"Cannot start probation for non-courier {courier.id}")
            return False
        
        if courier.onboarding_status != User.OnboardingStatus.PENDING:
            logger.info(f"Courier {courier.id} already in {courier.onboarding_status}")
            return False
        
        # Check basic document requirements
        if not courier.cni_document:
            logger.warning(f"Courier {courier.id} missing CNI document")
            return False
        
        # Start probation
        courier.onboarding_status = User.OnboardingStatus.PROBATION
        courier.probation_start_date = date.today()
        courier.probation_end_date = date.today() + timedelta(days=OnboardingService.PROBATION_DAYS)
        courier.probation_deliveries_count = 0
        courier.is_verified = True  # Allow them to work
        courier.save(update_fields=[
            'onboarding_status',
            'probation_start_date',
            'probation_end_date',
            'probation_deliveries_count',
            'is_verified'
        ])
        
        logger.info(f"Started probation for courier {courier.id}")
        return True
    
    @staticmethod
    @transaction.atomic
    def record_probation_delivery(courier: User) -> dict:
        """
        Record a completed delivery during probation.
        
        Args:
            courier: Courier who completed delivery
            
        Returns:
            Dict with status and auto_approved flag
        """
        if courier.onboarding_status != User.OnboardingStatus.PROBATION:
            return {'status': 'not_in_probation', 'auto_approved': False}
        
        courier.probation_deliveries_count += 1
        courier.save(update_fields=['probation_deliveries_count'])
        
        # Check for auto-approval
        if OnboardingService._check_auto_approval(courier):
            OnboardingService._approve_courier(courier)
            return {'status': 'auto_approved', 'auto_approved': True}
        
        return {
            'status': 'recorded',
            'auto_approved': False,
            'count': courier.probation_deliveries_count,
            'needed': OnboardingService.MIN_PROBATION_DELIVERIES
        }
    
    @staticmethod
    def _check_auto_approval(courier: User) -> bool:
        """Check if courier qualifies for auto-approval."""
        return (
            courier.probation_deliveries_count >= OnboardingService.MIN_PROBATION_DELIVERIES
            and courier.average_rating >= OnboardingService.MIN_RATING_FOR_APPROVAL
        )
    
    @staticmethod
    @transaction.atomic
    def _approve_courier(courier: User):
        """Approve courier and lift probation restrictions."""
        courier.onboarding_status = User.OnboardingStatus.APPROVED
        courier.probation_end_date = None
        courier.probation_delivery_limit = 0  # No limit
        courier.trust_score = 0.8  # High initial trust
        courier.save(update_fields=[
            'onboarding_status',
            'probation_end_date',
            'probation_delivery_limit',
            'trust_score'
        ])
        
        logger.info(f"Auto-approved courier {courier.id} after probation")
        
        # Send congratulation notification
        OnboardingService._send_approval_notification(courier)
    
    @staticmethod
    def _send_approval_notification(courier: User):
        """Send WhatsApp notification for approval."""
        try:
            from bot.services import send_whatsapp_notification
            
            message = (
                "🎉 Félicitations ! Vous êtes maintenant un coursier certifié DELIVR-CM !\n\n"
                "✅ Accès complet à toutes les livraisons\n"
                "✅ Plus de limite quotidienne\n"
                "✅ Priorité sur les courses premium\n\n"
                "Bonne route et merci de votre confiance ! 🚴"
            )
            
            send_whatsapp_notification(courier.phone_number, message)
            
        except Exception as e:
            logger.warning(f"Failed to send approval notification: {e}")
    
    @staticmethod
    @transaction.atomic
    def reject_courier(courier: User, reason: str = "") -> bool:
        """
        Reject a courier (admin action).
        
        Args:
            courier: Courier to reject
            reason: Rejection reason for logs
            
        Returns:
            True if rejected
        """
        if courier.role != UserRole.COURIER:
            return False
        
        courier.onboarding_status = User.OnboardingStatus.REJECTED
        courier.is_verified = False
        courier.is_active = False  # Block account
        courier.save(update_fields=['onboarding_status', 'is_verified', 'is_active'])
        
        logger.warning(f"Rejected courier {courier.id}: {reason}")
        
        return True
    
    @staticmethod
    def can_accept_delivery(courier: User) -> tuple[bool, str]:
        """
        Check if courier can accept a new delivery.
        
        Returns:
            Tuple of (can_accept, reason)
        """
        if courier.onboarding_status == User.OnboardingStatus.PENDING:
            return (False, "Documents en attente de vérification")
        
        if courier.onboarding_status == User.OnboardingStatus.REJECTED:
            return (False, "Compte rejeté")
        
        if courier.onboarding_status == User.OnboardingStatus.PROBATION:
            # Check daily limit
            from logistics.models import Delivery, DeliveryStatus
            
            today = timezone.now().date()
            today_count = Delivery.objects.filter(
                courier=courier,
                created_at__date=today
            ).count()
            
            if today_count >= courier.probation_delivery_limit:
                return (
                    False, 
                    f"Limite journalière atteinte ({courier.probation_delivery_limit}/jour pendant la période d'essai)"
                )
        
        return (True, "OK")
    
    @staticmethod
    def notify_admin_for_review(courier: User):
        """
        Send notification to admins for manual review.
        
        Called when auto-approval conditions are borderline.
        """
        # TODO: Implement admin notification (email, Slack, etc.)
        logger.info(f"Admin review needed for courier {courier.id}")
    
    @staticmethod
    def get_onboarding_progress(courier: User) -> dict:
        """Get courier's onboarding progress summary."""
        return {
            'status': courier.onboarding_status,
            'status_display': courier.get_onboarding_status_display(),
            'probation_deliveries': courier.probation_deliveries_count,
            'required_deliveries': OnboardingService.MIN_PROBATION_DELIVERIES,
            'average_rating': courier.average_rating,
            'required_rating': OnboardingService.MIN_RATING_FOR_APPROVAL,
            'probation_end_date': courier.probation_end_date,
            'daily_limit': courier.probation_delivery_limit,
            'progress_percent': min(100, int(
                courier.probation_deliveries_count / OnboardingService.MIN_PROBATION_DELIVERIES * 100
            )) if courier.onboarding_status == User.OnboardingStatus.PROBATION else 100,
        }
