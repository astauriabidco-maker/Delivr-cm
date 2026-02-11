import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import Dispute, DisputeStatus, Refund, RefundStatus
from finance.models import WalletService, TransactionType

logger = logging.getLogger(__name__)

class SupportService:
    """
    Service for handling disputes and refunds.
    """

    @staticmethod
    @transaction.atomic
    def create_dispute(delivery, creator, reason, description, photo_evidence=None):
        """
        Create a new dispute for a delivery.
        """
        dispute = Dispute.objects.create(
            delivery=delivery,
            creator=creator,
            reason=reason,
            description=description,
            photo_evidence=photo_evidence
        )
        logger.info(f"Dispute created: {dispute.id} for delivery {delivery.id}")
        
        # Trigger notification
        try:
            from bot.whatsapp_service import send_dispute_notification
            send_dispute_notification(dispute)
        except Exception as e:
            logger.error(f"Failed to send dispute creation notification: {e}")
            
        return dispute

    @staticmethod
    @transaction.atomic
    def resolve_dispute(dispute, admin_user, resolution_note, refund_amount=Decimal('0.00')):
        """
        Resolve a dispute and optionally trigger a refund.
        """
        if dispute.status in [DisputeStatus.RESOLVED, DisputeStatus.REJECTED]:
            raise ValueError("Ce litige est déjà clôturé.")

        dispute.status = DisputeStatus.RESOLVED
        dispute.resolution_note = resolution_note
        dispute.resolved_by = admin_user
        dispute.resolved_at = timezone.now()
        dispute.refund_amount = refund_amount
        dispute.save()

        if refund_amount > 0:
            SupportService._trigger_refund(dispute, admin_user)

        logger.info(f"Dispute resolved: {dispute.id} by {admin_user.id}")
        
        # Trigger notification
        try:
            from bot.whatsapp_service import send_dispute_notification
            send_dispute_notification(dispute)
        except Exception as e:
            logger.error(f"Failed to send dispute resolution notification: {e}")
            
        return dispute

    @staticmethod
    @transaction.atomic
    def reject_dispute(dispute, admin_user, rejection_reason):
        """
        Reject a dispute with a reason.
        """
        if dispute.status in [DisputeStatus.RESOLVED, DisputeStatus.REJECTED]:
            raise ValueError("Ce litige est déjà clôturé.")

        dispute.status = DisputeStatus.REJECTED
        dispute.resolution_note = rejection_reason
        dispute.resolved_by = admin_user
        dispute.resolved_at = timezone.now()
        dispute.save()

        logger.info(f"Dispute rejected: {dispute.id} by {admin_user.id}")
        
        # Trigger notification
        try:
            from bot.whatsapp_service import send_dispute_notification
            send_dispute_notification(dispute)
        except Exception as e:
            logger.error(f"Failed to send dispute rejection notification: {e}")
            
        return dispute

    @staticmethod
    @transaction.atomic
    def _trigger_refund(dispute, admin_user):
        """
        Internal method to process a refund linked to a dispute.
        """
        # Create refund record
        refund = Refund.objects.create(
            dispute=dispute,
            user=dispute.delivery.sender, # Usually refunding the sender
            amount=dispute.refund_amount,
            reason=dispute.resolution_note
        )

        try:
            # Credit user's wallet
            from finance.models import TransactionType
            tx = WalletService.credit(
                user=refund.user,
                amount=refund.amount,
                transaction_type=TransactionType.REFUND,
                description=f"Remboursement litige #{str(dispute.id)[:8]}",
                delivery=dispute.delivery
            )
            
            refund.transaction = tx
            refund.status = RefundStatus.COMPLETED
            refund.completed_at = timezone.now()
            refund.save()
            
            logger.info(f"Refund processed: {refund.id} for amount {refund.amount}")
        except Exception as e:
            refund.status = RefundStatus.FAILED
            refund.save()
            logger.error(f"Refund failed for dispute {dispute.id}: {e}")
            raise e

    @staticmethod
    def get_advanced_stats():
        """
        Get advanced statistics for the platform.
        """
        from logistics.models import Delivery, DeliveryStatus
        from django.db.models import Avg, Count, Sum, F, ExpressionWrapper, fields
        from datetime import timedelta
        
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        
        deliveries = Delivery.objects.filter(created_at__gte=last_30_days)
        
        # Delivery success rate
        total_deliveries = deliveries.count()
        completed_deliveries = deliveries.filter(status=DeliveryStatus.COMPLETED).count()
        success_rate = (completed_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
        
        # Average delivery time
        time_diff = ExpressionWrapper(
            F('completed_at') - F('assigned_at'),
            output_field=fields.DurationField()
        )
        avg_time = deliveries.filter(
            status=DeliveryStatus.COMPLETED,
            assigned_at__isnull=False,
            completed_at__isnull=False
        ).annotate(duration=time_diff).aggregate(Avg('duration'))['duration__avg']
        
        # Dispute rate
        total_disputes = Dispute.objects.filter(created_at__gte=last_30_days).count()
        dispute_rate = (total_disputes / total_deliveries * 100) if total_deliveries > 0 else 0
        
        # Financial stats
        total_revenue = deliveries.aggregate(Sum('total_price'))['total_price__sum'] or 0
        total_platform_fees = deliveries.aggregate(Sum('platform_fee'))['platform_fee__sum'] or 0
        
        # Active couriers
        from core.models import User, UserRole
        active_couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_online=True
        ).count()

        return {
            'total_deliveries': total_deliveries,
            'success_rate': round(success_rate, 2),
            'avg_delivery_time_minutes': int(avg_time.total_seconds() / 60) if avg_time else 0,
            'dispute_rate': round(dispute_rate, 2),
            'total_revenue': total_revenue,
            'total_platform_fees': total_platform_fees,
            'active_couriers_online': active_couriers,
        }
