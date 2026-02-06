"""
FINANCE App - Celery Tasks for Automated Invoice Generation

Scheduled tasks for monthly courier statements and B2B invoices.
"""

import logging
from celery import shared_task
from datetime import date
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def generate_monthly_courier_statements(self, year: int = None, month: int = None):
    """
    Generate monthly statements for all active couriers.
    
    Should be scheduled to run on the 1st of each month.
    Generates statements for the previous month.
    
    Args:
        year: Year for statement (default: previous month's year)
        month: Month for statement (default: previous month)
    """
    from finance.invoice_service import InvoiceService
    from core.models import User, UserRole
    
    # Default to previous month
    if year is None or month is None:
        previous_month = date.today() - relativedelta(months=1)
        year = previous_month.year
        month = previous_month.month
    
    logger.info(f"[CELERY] Generating courier statements for {year}/{month}")
    
    # Get all active couriers
    couriers = User.objects.filter(
        role=UserRole.COURIER,
        is_active=True,
        is_approved=True
    )
    
    success_count = 0
    error_count = 0
    
    for courier in couriers:
        try:
            invoice = InvoiceService.generate_courier_statement(courier, year, month)
            logger.info(f"[CELERY] Generated statement {invoice.invoice_number} for {courier.phone_number}")
            success_count += 1
        except Exception as e:
            logger.error(f"[CELERY] Failed to generate statement for {courier.id}: {e}")
            error_count += 1
    
    logger.info(f"[CELERY] Courier statements complete: {success_count} success, {error_count} errors")
    
    return {
        'year': year,
        'month': month,
        'success': success_count,
        'errors': error_count
    }


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def generate_monthly_b2b_invoices(self, year: int = None, month: int = None):
    """
    Generate monthly invoices for all active B2B partners.
    
    Should be scheduled to run on the 1st of each month.
    Generates invoices for the previous month.
    
    Args:
        year: Year for invoice (default: previous month's year)
        month: Month for invoice (default: previous month)
    """
    from finance.invoice_service import InvoiceService
    from core.models import User, UserRole
    
    # Default to previous month
    if year is None or month is None:
        previous_month = date.today() - relativedelta(months=1)
        year = previous_month.year
        month = previous_month.month
    
    logger.info(f"[CELERY] Generating B2B invoices for {year}/{month}")
    
    # Get all approved business partners
    partners = User.objects.filter(
        role=UserRole.BUSINESS,
        is_active=True,
        is_business_approved=True
    )
    
    success_count = 0
    error_count = 0
    
    for partner in partners:
        try:
            invoice = InvoiceService.generate_b2b_invoice(partner, year, month)
            logger.info(f"[CELERY] Generated invoice {invoice.invoice_number} for {partner.company_name or partner.phone_number}")
            success_count += 1
        except Exception as e:
            logger.error(f"[CELERY] Failed to generate invoice for {partner.id}: {e}")
            error_count += 1
    
    logger.info(f"[CELERY] B2B invoices complete: {success_count} success, {error_count} errors")
    
    return {
        'year': year,
        'month': month,
        'success': success_count,
        'errors': error_count
    }


@shared_task
def generate_all_monthly_documents():
    """
    Meta-task that generates both courier statements and B2B invoices.
    
    Schedule this task to run on the 1st of each month at 6:00 AM.
    
    Example Celery Beat schedule (in settings.py):
    
        CELERY_BEAT_SCHEDULE = {
            'monthly-invoices': {
                'task': 'finance.tasks.generate_all_monthly_documents',
                'schedule': crontab(day_of_month=1, hour=6, minute=0),
            },
        }
    """
    logger.info("[CELERY] Starting monthly document generation")
    
    # Generate statements in parallel
    courier_result = generate_monthly_courier_statements.delay()
    b2b_result = generate_monthly_b2b_invoices.delay()
    
    return {
        'courier_statements_task': str(courier_result.id),
        'b2b_invoices_task': str(b2b_result.id)
    }
