from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from datetime import timedelta

from .models import Dispute, DisputeReason, DisputeStatus
from .services import SupportService

@method_decorator(staff_member_required, name='dispatch')
class SupportBackofficeView(View):
    """
    Dedicated view for the support team to manage disputes.
    Accessible at /backoffice/support/disputes/
    """
    template_name = 'support/backoffice_disputes.html'
    
    def get(self, request):
        status_filter = request.GET.get('status')
        disputes = Dispute.objects.select_related('delivery', 'creator').order_by('-created_at')
        
        if status_filter:
            disputes = disputes.filter(status=status_filter)
            
        context = {
            'disputes': disputes,
            'pending_count': Dispute.objects.filter(status=DisputeStatus.PENDING).count(),
            'investigating_count': Dispute.objects.filter(status=DisputeStatus.INVESTIGATING).count(),
            'resolved_count': Dispute.objects.filter(status=DisputeStatus.RESOLVED).count(),
        }
        
        return render(request, self.template_name, context)
        
    def post(self, request):
        dispute_id = request.POST.get('dispute_id')
        action = request.POST.get('action')
        note = request.POST.get('note')

        dispute = get_object_or_404(Dispute, pk=dispute_id)
        
        try:
            if action == 'resolve':
                try:
                    refund_amount = Decimal(request.POST.get('refund_amount') or '0')
                except (InvalidOperation, TypeError, ValueError):
                    messages.error(request, "Montant de remboursement invalide.")
                    return redirect('support:backoffice_disputes')

                SupportService.resolve_dispute(
                    dispute=dispute,
                    admin_user=request.user,
                    resolution_note=note,
                    refund_amount=refund_amount
                )
                messages.success(request, f"✅ Litige #{dispute_id[:8]} résolu. Remboursement de {refund_amount} XAF effectué.")
            
            elif action == 'reject':
                SupportService.reject_dispute(
                    dispute=dispute,
                    admin_user=request.user,
                    rejection_reason=note
                )
                messages.warning(request, f"❌ Litige #{dispute_id[:8]} rejeté.")
                
        except Exception as e:
            messages.error(request, f"Erreur lors du traitement : {str(e)}")
            
        return redirect('support:backoffice_disputes')


class ClientDisputeCreateView(View):
    """
    Public view for clients to report issues from the tracking page.
    """
    max_delivery_age = timedelta(days=30)
    duplicate_window = timedelta(hours=24)
    max_reports_per_ip = 5

    def post(self, request, delivery_id):
        from django.contrib.auth import get_user_model
        from logistics.models import Delivery
        from core.models import UserRole
        
        delivery = get_object_or_404(Delivery, pk=delivery_id)

        if delivery.created_at < timezone.now() - self.max_delivery_age:
            return HttpResponseForbidden("Cette livraison est trop ancienne pour un signalement public.")

        share_token = request.POST.get('share_token') or request.GET.get('share_token') or request.GET.get('token')
        if share_token:
            cached_delivery_id = cache.get(f"share_link_{share_token}")
            if str(cached_delivery_id) != str(delivery.id):
                return HttpResponseForbidden("Lien de suivi invalide ou expiré.")
        
        reason = request.POST.get('reason', 'OTHER')
        if reason not in DisputeReason.values:
            reason = DisputeReason.OTHER

        description = request.POST.get('description', '').strip()
        if len(description) > 2000:
            return HttpResponseForbidden("Description trop longue.")

        photo = request.FILES.get('photo')

        recent_cutoff = timezone.now() - self.duplicate_window
        if Dispute.objects.filter(
            delivery=delivery,
            created_at__gte=recent_cutoff,
            status__in=[DisputeStatus.PENDING, DisputeStatus.INVESTIGATING],
        ).exists():
            return HttpResponseForbidden("Un signalement récent est déjà en cours pour cette livraison.")

        ip_address = request.META.get('REMOTE_ADDR', 'unknown')
        abuse_key = f"client_dispute_ip_{ip_address}"
        report_count = cache.get(abuse_key, 0)
        if report_count >= self.max_reports_per_ip:
            return HttpResponseForbidden("Trop de signalements. Veuillez réessayer plus tard.")
        
        if request.user.is_authenticated:
            creator = request.user
        else:
            if not delivery.recipient_phone:
                return HttpResponseForbidden("Impossible de rattacher ce signalement au destinataire.")
            User = get_user_model()
            creator, _ = User.objects.get_or_create(
                phone_number=delivery.recipient_phone,
                defaults={
                    'role': UserRole.CLIENT,
                    'full_name': delivery.recipient_name,
                }
            )
        
        SupportService.create_dispute(
            delivery=delivery,
            creator=creator,
            reason=reason,
            description=description,
            photo_evidence=photo
        )

        cache.set(abuse_key, report_count + 1, timeout=3600)
        
        messages.success(request, "✅ Votre signalement a été enregistré. Notre équipe support va l'analyser.")
        return redirect('delivery-tracking', delivery_id=delivery_id)
