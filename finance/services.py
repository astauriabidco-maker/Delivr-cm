"""
FINANCE App - Business Services for DELIVR-CM

High-level financial operations for delivery completion and wallet management.
"""

import logging
from decimal import Decimal
from django.db import transaction

from finance.models import WalletService, TransactionType, Transaction
from logistics.models import PaymentMethod, DeliveryStatus

logger = logging.getLogger(__name__)


@transaction.atomic
def process_delivery_completion(delivery) -> Decimal:
    """
    Process financial operations when a delivery is completed.
    
    This is the main entry point for financial settlement after delivery.
    Implements the DELIVR-CM business rules from CONTEXT.md:
    
    - CASH_P2P: Courier keeps cash, platform debits commission (creates debt)
    - PREPAID_WALLET: Courier is credited their earning
    
    Also implements the "Kill Switch" - automatic courier blocking when
    debt exceeds the ceiling.
    
    Args:
        delivery: Completed Delivery instance with:
            - courier: The assigned courier
            - payment_method: CASH_P2P or PREPAID_WALLET
            - platform_fee: Commission amount
            - courier_earning: Courier's share
    
    Returns:
        Decimal: The courier's new wallet balance
    
    Raises:
        ValueError: If delivery has no courier or invalid state
    """
    from core.models import UserRole, User
    
    # ========================================
    # VALIDATION
    # ========================================
    courier = delivery.courier
    if not courier:
        raise ValueError("La livraison n'a pas de coursier assigné")
    
    if courier.role != UserRole.COURIER:
        raise ValueError(f"L'utilisateur {courier.phone_number} n'est pas un coursier")
    
    # Lock the courier row for atomic update
    courier = User.objects.select_for_update().get(pk=courier.pk)
    
    logger.info(
        f"[FINANCE] Processing delivery {str(delivery.id)[:8]} | "
        f"Method: {delivery.payment_method} | "
        f"Courier: {courier.phone_number} | "
        f"Balance before: {courier.wallet_balance} XAF"
    )
    
    # ========================================
    # PAYMENT PROCESSING
    # ========================================
    
    if delivery.payment_method == PaymentMethod.CASH_P2P:
        # ----------------------------------------
        # CASE 1: CASH Payment (Client → Courier)
        # ----------------------------------------
        # Business Rule:
        # - Courier keeps 100% of cash from client
        # - Platform DEBITS platform_fee from courier's wallet
        # - This can create NEGATIVE balance (debt)
        
        amount = delivery.platform_fee  # Will be stored as negative
        
        tx = WalletService.debit(
            user=courier,
            amount=amount,
            transaction_type=TransactionType.COMMISSION,
            delivery=delivery,
            description=f"Commission livraison CASH #{str(delivery.id)[:8]}",
            allow_negative=True  # Enable debt system for couriers
        )
        
        logger.info(
            f"[FINANCE] CASH_P2P: Debited {amount} XAF from courier | "
            f"New balance: {courier.wallet_balance} XAF"
        )
    
    elif delivery.payment_method == PaymentMethod.PREPAID_WALLET:
        # ----------------------------------------
        # CASE 2: PREPAID Payment (Business → Platform)
        # ----------------------------------------
        # Business Rule:
        # - Business was debited at order creation (already done)
        # - Courier is CREDITED courier_earning at delivery completion
        
        amount = delivery.courier_earning  # Positive credit
        
        tx = WalletService.credit(
            user=courier,
            amount=amount,
            transaction_type=TransactionType.DELIVERY_CREDIT,
            delivery=delivery,
            description=f"Gain livraison PREPAID #{str(delivery.id)[:8]}"
        )
        
        logger.info(
            f"[FINANCE] PREPAID: Credited {amount} XAF to courier | "
            f"New balance: {courier.wallet_balance} XAF"
        )
    
    else:
        raise ValueError(f"Méthode de paiement non supportée: {delivery.payment_method}")
    
    # Refresh courier to get updated balance
    courier.refresh_from_db()
    
    # ========================================
    # KILL SWITCH - Automatic Debt Blocking
    # ========================================
    # If courier's wallet goes below -debt_ceiling, block them
    
    if courier.wallet_balance < -courier.debt_ceiling:
        courier.is_active = False
        courier.save(update_fields=['is_active'])
        
        logger.warning(
            f"[KILL SWITCH] 🚨 Coursier {courier.phone_number} BLOQUÉ pour dette excessive! "
            f"Solde: {courier.wallet_balance} XAF | Plafond: -{courier.debt_ceiling} XAF"
        )
        
        # Could trigger notification here (WhatsApp, SMS, etc.)
        print(
            f"\n⚠️  ALERTE DETTE EXCESSIVE ⚠️\n"
            f"   Coursier: {courier.phone_number}\n"
            f"   Solde actuel: {courier.wallet_balance} XAF\n"
            f"   Plafond dette: -{courier.debt_ceiling} XAF\n"
            f"   → Compte BLOQUÉ automatiquement\n"
        )
    
    return courier.wallet_balance


@transaction.atomic
def debit_business_for_prepaid_order(business, delivery) -> Transaction:
    """
    Debit a business wallet when they create a prepaid delivery order.
    
    This should be called BEFORE the delivery is dispatched.
    
    Args:
        business: Business user instance (sender)
        delivery: Delivery instance with calculated total_price
    
    Returns:
        Transaction: The debit transaction record
    
    Raises:
        ValueError: If business has insufficient funds
    """
    from core.models import UserRole
    
    if business.role != UserRole.BUSINESS:
        raise ValueError("Only BUSINESS users can use PREPAID_WALLET")
    
    if business.wallet_balance < delivery.total_price:
        raise ValueError(
            f"Solde insuffisant: {business.wallet_balance} XAF "
            f"(requis: {delivery.total_price} XAF)"
        )
    
    tx = WalletService.debit(
        user=business,
        amount=delivery.total_price,
        transaction_type=TransactionType.PREPAID_DEBIT,
        delivery=delivery,
        description=f"Commande prépayée #{str(delivery.id)[:8]}",
        allow_negative=False
    )
    
    logger.info(
        f"[FINANCE] Business {business.phone_number} debited {delivery.total_price} XAF "
        f"for prepaid order {str(delivery.id)[:8]}"
    )
    
    return tx


def get_courier_financial_status(courier) -> dict:
    """
    Get a summary of a courier's financial status.
    
    Useful for dashboards and status checks.
    
    Args:
        courier: User instance with role COURIER
    
    Returns:
        dict: {
            "balance": Decimal,
            "debt_ceiling": Decimal,
            "debt_remaining": Decimal,  # How much more debt allowed
            "is_blocked": bool,
            "status": str  # "healthy", "warning", "blocked"
        }
    """
    from core.models import UserRole
    
    if courier.role != UserRole.COURIER:
        raise ValueError("User is not a courier")
    
    balance = courier.wallet_balance
    ceiling = courier.debt_ceiling
    
    # Calculate remaining debt capacity
    # If balance is 500, debt_remaining = 500 + 2500 = 3000 (can go down to -2500)
    # If balance is -1000, debt_remaining = -1000 + 2500 = 1500
    debt_remaining = balance + ceiling
    
    is_blocked = balance < -ceiling
    
    # Determine status
    if is_blocked:
        status = "blocked"
    elif debt_remaining < ceiling * Decimal("0.3"):  # Less than 30% remaining
        status = "warning"
    else:
        status = "healthy"
    
    return {
        "balance": balance,
        "debt_ceiling": ceiling,
        "debt_remaining": max(debt_remaining, Decimal("0")),
        "is_blocked": is_blocked,
        "status": status
    }


# ============================================
# TEST RAPIDE
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("DELIVR-CM - Test du Service Financier")
    print("=" * 60)
    print("\nCe module doit être testé via Django shell:")
    print("  docker-compose exec web python manage.py shell")
    print("\nExemple de test:")
    print("""
    from finance.services import process_delivery_completion
    from logistics.models import Delivery
    
    # Récupérer une livraison complétée
    delivery = Delivery.objects.filter(status='COMPLETED').first()
    
    # Traiter le paiement
    new_balance = process_delivery_completion(delivery)
    print(f"Nouveau solde: {new_balance} XAF")
    """)
    print("=" * 60)
