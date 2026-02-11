from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from decimal import Decimal

from .models import Dispute, DisputeStatus
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
        refund_amount = Decimal(request.POST.get('refund_amount', '0'))
        
        dispute = get_object_or_404(Dispute, pk=dispute_id)
        
        try:
            if action == 'resolve':
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
    def post(self, request, delivery_id):
        from logistics.models import Delivery
        from .models import DisputeReason
        from django.contrib.auth import get_user_model
        
        delivery = get_object_or_404(Delivery, pk=delivery_id)
        
        reason = request.POST.get('reason', 'OTHER')
        description = request.POST.get('description', '')
        photo = request.FILES.get('photo')
        
        # In this context, the creator might not be authenticated.
        # If so, we associate it with the sender user of the delivery
        # (who is usually the one with the tracking link).
        creator = request.user if request.user.is_authenticated else delivery.sender
        
        SupportService.create_dispute(
            delivery=delivery,
            creator=creator,
            reason=reason,
            description=description,
            photo_evidence=photo
        )
        
        messages.success(request, "✅ Votre signalement a été enregistré. Notre équipe support va l'analyser.")
        return redirect('delivery-tracking', delivery_id=delivery_id)
