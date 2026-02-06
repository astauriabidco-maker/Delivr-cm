"""
COURIER App - Onboarding Views

Views for the multi-step courier onboarding wizard.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.utils import timezone

from core.models import UserRole
from core.onboarding import CourierOnboarding, OnboardingStep, OnboardingStatus
from core.onboarding_service import OnboardingService


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def get_step_number(onboarding):
    """Get current step number (1-6) from onboarding record."""
    step_map = {
        OnboardingStep.PHONE_VERIFICATION: 1,
        OnboardingStep.DOCUMENTS_UPLOADED: 2,
        OnboardingStep.EMERGENCY_CONTACT: 3,
        OnboardingStep.CAUTION_PAID: 4,
        OnboardingStep.CONTRACT_SIGNED: 5,
        OnboardingStep.ADMIN_VALIDATED: 6,
        OnboardingStep.PROBATION: 6,
        OnboardingStep.COMPLETED: 6,
    }
    return step_map.get(onboarding.current_step, 1)


@login_required
def onboarding_router(request):
    """
    Main onboarding entry point.
    Routes to the appropriate step based on current progress.
    """
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    # Get or create onboarding record
    onboarding = OnboardingService.start_onboarding(request.user)
    
    # Route to appropriate step
    step = onboarding.current_step
    
    if step == OnboardingStep.PHONE_VERIFICATION:
        return redirect('courier:onboarding-phone')
    elif step == OnboardingStep.DOCUMENTS_UPLOADED:
        return redirect('courier:onboarding-documents')
    elif step == OnboardingStep.EMERGENCY_CONTACT:
        return redirect('courier:onboarding-emergency')
    elif step == OnboardingStep.CAUTION_PAID:
        return redirect('courier:onboarding-caution')
    elif step == OnboardingStep.CONTRACT_SIGNED:
        return redirect('courier:onboarding-contract')
    else:
        # Admin validation, probation, or completed
        return redirect('courier:onboarding-status')


@login_required
def onboarding_phone(request):
    """Step 1: Phone verification."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    onboarding = OnboardingService.start_onboarding(request.user)
    
    # Check if already verified
    if onboarding.phone_verified:
        return redirect('courier:onboarding-documents')
    
    context = {
        'step': 1,
        'onboarding': onboarding,
        'otp_sent': onboarding.phone_otp_sent_at is not None
    }
    return render(request, 'courier/onboarding/step_phone.html', context)


@login_required
@require_POST
def onboarding_send_otp(request):
    """Send OTP to courier's phone."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    onboarding = OnboardingService.start_onboarding(request.user)
    result = OnboardingService.send_phone_otp(onboarding, get_client_ip(request))
    
    if result['success']:
        messages.success(request, f"Code envoyé par {result['provider']}")
    else:
        messages.error(request, result.get('error', 'Échec de l\'envoi'))
    
    return redirect('courier:onboarding-phone')


@login_required
@require_POST
def onboarding_verify_otp(request):
    """Verify OTP code."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    onboarding = OnboardingService.start_onboarding(request.user)
    otp_code = request.POST.get('otp_code', '').strip()
    
    result = OnboardingService.verify_phone_otp(onboarding, otp_code)
    
    if result['success']:
        messages.success(request, "Téléphone vérifié ✓")
        return redirect('courier:onboarding-documents')
    else:
        messages.error(request, result.get('error', 'Code invalide'))
        return redirect('courier:onboarding-phone')


@login_required
def onboarding_documents(request):
    """Step 2: Document upload."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    onboarding = OnboardingService.start_onboarding(request.user)
    
    if request.method == 'POST':
        # Collect uploaded files and data
        documents = {}
        
        # Files
        for field in ['cni_front', 'cni_back', 'selfie_with_cni', 'casier_judiciaire',
                      'driving_license', 'carte_grise', 'vehicle_photo']:
            if field in request.FILES:
                documents[field] = request.FILES[field]
        
        # Text fields
        for field in ['cni_number', 'driving_license_category', 'vehicle_plate', 'vehicle_type']:
            if request.POST.get(field):
                documents[field] = request.POST[field]
        
        # Date fields
        for field in ['cni_expiry_date', 'casier_issue_date']:
            if request.POST.get(field):
                from datetime import datetime
                try:
                    documents[field] = datetime.strptime(request.POST[field], '%Y-%m-%d').date()
                except ValueError:
                    pass
        
        result = OnboardingService.submit_documents(onboarding, documents)
        
        if result['documents_complete']:
            messages.success(request, "Documents enregistrés ✓")
            return redirect('courier:onboarding-emergency')
        else:
            messages.info(request, "Documents sauvegardés. Complétez les champs obligatoires.")
    
    context = {
        'step': 2,
        'onboarding': onboarding,
    }
    return render(request, 'courier/onboarding/step_documents.html', context)


@login_required
def onboarding_emergency(request):
    """Step 3: Emergency contact."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    onboarding = OnboardingService.start_onboarding(request.user)
    
    if request.method == 'POST':
        data = {
            'name': request.POST.get('emergency_name', ''),
            'phone': request.POST.get('emergency_phone', ''),
            'relation': request.POST.get('emergency_relation', ''),
            'home_address': request.POST.get('home_address', ''),
            'home_city': request.POST.get('home_city', 'Douala'),
        }
        
        result = OnboardingService.submit_emergency_contact(onboarding, data)
        messages.success(request, "Contact d'urgence enregistré ✓")
        return redirect('courier:onboarding-caution')
    
    context = {
        'step': 3,
        'onboarding': onboarding,
    }
    return render(request, 'courier/onboarding/step_emergency.html', context)


@login_required
def onboarding_caution(request):
    """Step 4: Caution payment."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    onboarding = OnboardingService.start_onboarding(request.user)
    
    if request.method == 'POST':
        transaction_id = request.POST.get('transaction_id', '').strip()
        payment_method = request.POST.get('payment_method', '')
        
        if not transaction_id:
            messages.error(request, "Veuillez entrer l'ID de transaction")
            return redirect('courier:onboarding-caution')
        
        result = OnboardingService.process_caution_payment(
            onboarding, transaction_id, payment_method
        )
        messages.success(request, "Paiement de caution enregistré ✓")
        return redirect('courier:onboarding-contract')
    
    context = {
        'step': 4,
        'onboarding': onboarding,
    }
    return render(request, 'courier/onboarding/step_caution.html', context)


@login_required
def onboarding_contract(request):
    """Step 5: Contract signing."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    onboarding = OnboardingService.start_onboarding(request.user)
    
    if request.method == 'POST':
        accept_terms = request.POST.get('accept_terms')
        accept_data = request.POST.get('accept_data')
        signature_text = request.POST.get('signature_text', '')
        
        if not accept_terms or not accept_data:
            messages.error(request, "Vous devez accepter les conditions")
            return redirect('courier:onboarding-contract')
        
        result = OnboardingService.sign_contract(
            onboarding, signature_text, get_client_ip(request)
        )
        messages.success(request, "Contrat signé ✓ " + result.get('message', ''))
        return redirect('courier:onboarding-status')
    
    context = {
        'step': 5,
        'onboarding': onboarding,
    }
    return render(request, 'courier/onboarding/step_contract.html', context)


@login_required
def onboarding_status(request):
    """Step 6: Validation status / Probation."""
    if request.user.role != UserRole.COURIER:
        return redirect('home:index')
    
    onboarding = OnboardingService.start_onboarding(request.user)
    
    # If fully completed, redirect to dashboard
    if onboarding.current_step == OnboardingStep.COMPLETED:
        return redirect('courier:dashboard')
    
    context = {
        'step': 6,
        'onboarding': onboarding,
    }
    return render(request, 'courier/onboarding/step_validation.html', context)
