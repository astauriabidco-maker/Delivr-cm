"""
Mobile Payment Service for DELIVR-CM

Unified service for handling mobile money payments (MTN MoMo + Orange Money).
Routes requests to the appropriate provider based on phone number.
"""

import uuid
import logging
from decimal import Decimal
from typing import Optional
from django.utils import timezone
from django.db import transaction

from finance.models import (
    MobilePayment, 
    MobilePaymentProvider, 
    MobilePaymentStatus
)
from finance.mtn_momo_service import MTNMoMoService
from finance.orange_money_service import OrangeMoneyService
from logistics.models import Delivery, DeliveryStatus

logger = logging.getLogger(__name__)


class MobilePaymentService:
    """
    Unified mobile payment service.
    
    Automatically routes to MTN MoMo or Orange Money based on phone prefix.
    Handles initiation, callbacks, and status polling.
    """
    
    @staticmethod
    @transaction.atomic
    def initiate_payment(
        delivery: Delivery,
        phone: str,
        amount: Optional[Decimal] = None
    ) -> MobilePayment:
        """
        Initiate a mobile money payment for a delivery.
        
        Args:
            delivery: Delivery instance to pay for
            phone: Payer's phone number
            amount: Amount to charge (defaults to delivery.total_price)
            
        Returns:
            MobilePayment instance
            
        Raises:
            ValueError: If provider not supported or phone invalid
        """
        if amount is None:
            amount = delivery.total_price
        
        # Detect provider from phone
        provider = MobilePayment.detect_provider(phone)
        
        # Generate unique reference
        external_reference = str(uuid.uuid4())
        
        # Create payment record
        payment = MobilePayment.objects.create(
            delivery=delivery,
            provider=provider,
            phone_number=phone,
            amount=amount,
            status=MobilePaymentStatus.PENDING,
            external_reference=external_reference,
        )
        
        # Route to appropriate provider
        if provider == MobilePaymentProvider.MTN_MOMO:
            result = MTNMoMoService.request_to_pay(
                phone=phone,
                amount=amount,
                external_reference=external_reference,
                payer_message=f"Paiement livraison #{str(delivery.id)[:8]}",
                payee_note=f"DELIVR-CM Delivery {delivery.id}"
            )
            
            if result.get('success'):
                payment.provider_transaction_id = result.get('reference_id', '')
                payment.save(update_fields=['provider_transaction_id'])
                logger.info(f"[PAYMENT] MTN MoMo initiated for {delivery.id}")
            else:
                payment.status = MobilePaymentStatus.FAILED
                payment.error_code = result.get('error_code', 'INIT_FAILED')
                payment.error_message = result.get('error', 'Initiation failed')
                payment.save(update_fields=['status', 'error_code', 'error_message'])
                logger.error(f"[PAYMENT] MTN MoMo init failed: {result}")
        
        elif provider == MobilePaymentProvider.ORANGE_MONEY:
            result = OrangeMoneyService.init_payment(
                phone=phone,
                amount=amount,
                external_reference=external_reference,
                description=f"Livraison DELIVR-CM #{str(delivery.id)[:8]}"
            )
            
            if result.get('success'):
                payment.pay_token = result.get('pay_token', '')
                payment.payment_url = result.get('payment_url', '')
                payment.save(update_fields=['pay_token', 'payment_url'])
                logger.info(f"[PAYMENT] Orange Money initiated for {delivery.id}")
            else:
                payment.status = MobilePaymentStatus.FAILED
                payment.error_code = result.get('error_code', 'INIT_FAILED')
                payment.error_message = result.get('error', 'Initiation failed')
                payment.save(update_fields=['status', 'error_code', 'error_message'])
                logger.error(f"[PAYMENT] Orange Money init failed: {result}")
        
        return payment
    
    @staticmethod
    @transaction.atomic
    def process_callback(
        provider: str,
        reference_id: str,
        status: str,
        transaction_id: str = "",
        raw_data: dict = None
    ) -> Optional[MobilePayment]:
        """
        Process a payment callback from provider.
        
        Args:
            provider: 'MTN' or 'OM'
            reference_id: Our external_reference or provider's reference
            status: Provider status (will be normalized)
            transaction_id: Provider's transaction ID
            raw_data: Full callback payload
            
        Returns:
            Updated MobilePayment or None if not found
        """
        # Try to find payment by reference
        payment = None
        
        # Try external_reference
        try:
            payment = MobilePayment.objects.select_for_update().get(
                external_reference=reference_id
            )
        except MobilePayment.DoesNotExist:
            pass
        
        # Try provider_transaction_id (MTN)
        if not payment:
            try:
                payment = MobilePayment.objects.select_for_update().get(
                    provider_transaction_id=reference_id
                )
            except MobilePayment.DoesNotExist:
                pass
        
        # Try pay_token (Orange)
        if not payment:
            try:
                payment = MobilePayment.objects.select_for_update().get(
                    pay_token=reference_id
                )
            except MobilePayment.DoesNotExist:
                pass
        
        if not payment:
            logger.warning(f"[PAYMENT] Callback reference not found: {reference_id}")
            return None
        
        # Already processed - idempotency check
        if payment.status in [MobilePaymentStatus.SUCCESSFUL, MobilePaymentStatus.FAILED]:
            logger.info(f"[PAYMENT] Already processed: {payment.id} = {payment.status}")
            return payment
        
        # Normalize status
        status_upper = status.upper()
        status_map = {
            'SUCCESSFUL': MobilePaymentStatus.SUCCESSFUL,
            'SUCCESS': MobilePaymentStatus.SUCCESSFUL,
            'PENDING': MobilePaymentStatus.PENDING,
            'FAILED': MobilePaymentStatus.FAILED,
            'REJECTED': MobilePaymentStatus.REJECTED,
            'CANCELLED': MobilePaymentStatus.CANCELLED,
            'EXPIRED': MobilePaymentStatus.TIMEOUT,
            'TIMEOUT': MobilePaymentStatus.TIMEOUT,
        }
        
        new_status = status_map.get(status_upper, MobilePaymentStatus.FAILED)
        
        payment.status = new_status
        payment.callback_received = True
        payment.callback_data = raw_data
        
        if transaction_id:
            payment.provider_transaction_id = transaction_id
        
        if new_status == MobilePaymentStatus.SUCCESSFUL:
            payment.confirmed_at = timezone.now()
        
        payment.save()
        
        logger.info(f"[PAYMENT] Callback processed: {payment.id} -> {new_status}")
        
        # Trigger post-payment actions if successful
        if new_status == MobilePaymentStatus.SUCCESSFUL:
            MobilePaymentService._on_payment_success(payment)
        
        return payment
    
    @staticmethod
    def _on_payment_success(payment: MobilePayment):
        """Handle successful payment - confirm delivery."""
        delivery = payment.delivery
        
        # Mark delivery as paid (update payment status, not delivery status)
        # The delivery workflow continues separately
        
        logger.info(f"[PAYMENT] Success for delivery {delivery.id}")
        
        # Send WhatsApp confirmation
        try:
            from bot.services import send_whatsapp_notification
            
            message = (
                f"✅ Paiement reçu de {int(payment.amount)} XAF !\n\n"
                f"📦 Commande: #{str(delivery.id)[:8]}\n"
                f"💳 Via: {payment.get_provider_display()}\n\n"
                "Votre livraison sera effectuée sous peu. Merci !"
            )
            
            # Notify the sender
            if delivery.sender:
                send_whatsapp_notification(delivery.sender.phone_number, message)
            
        except Exception as e:
            logger.warning(f"[PAYMENT] WhatsApp notification failed: {e}")
    
    @staticmethod
    @transaction.atomic
    def poll_status(payment: MobilePayment) -> MobilePayment:
        """
        Poll provider for payment status update.
        
        Args:
            payment: MobilePayment to check
            
        Returns:
            Updated MobilePayment
        """
        if payment.status in [MobilePaymentStatus.SUCCESSFUL, MobilePaymentStatus.FAILED]:
            return payment  # Terminal state
        
        if payment.provider == MobilePaymentProvider.MTN_MOMO:
            ref = payment.provider_transaction_id or payment.external_reference
            result = MTNMoMoService.check_status(ref)
            
        elif payment.provider == MobilePaymentProvider.ORANGE_MONEY:
            result = OrangeMoneyService.check_status(
                pay_token=payment.pay_token,
                order_id=payment.external_reference
            )
        else:
            return payment
        
        if result.get('success'):
            status = result.get('status', 'PENDING')
            transaction_id = result.get('financial_transaction_id') or result.get('transaction_id', '')
            
            return MobilePaymentService.process_callback(
                provider=payment.provider,
                reference_id=payment.external_reference,
                status=status,
                transaction_id=transaction_id,
                raw_data=result.get('raw')
            ) or payment
        
        return payment
    
    @staticmethod
    def get_payment_status(delivery_id: str) -> Optional[dict]:
        """
        Get the latest payment status for a delivery.
        
        Args:
            delivery_id: UUID of the delivery
            
        Returns:
            Dict with payment info or None
        """
        payment = MobilePayment.objects.filter(
            delivery_id=delivery_id
        ).order_by('-created_at').first()
        
        if not payment:
            return None
        
        return {
            'id': str(payment.id),
            'provider': payment.provider,
            'provider_display': payment.get_provider_display(),
            'amount': payment.amount,
            'status': payment.status,
            'status_display': payment.get_status_display(),
            'payment_url': payment.payment_url,
            'created_at': payment.created_at,
            'confirmed_at': payment.confirmed_at,
        }
    
    @staticmethod
    def is_available() -> dict:
        """Check which payment providers are available."""
        return {
            'mtn_momo': MTNMoMoService.is_configured(),
            'orange_money': OrangeMoneyService.is_configured(),
        }
