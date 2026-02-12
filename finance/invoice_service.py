"""
FINANCE App - Invoice Generation Service

Generates PDF invoices and receipts using WeasyPrint.
"""

import io
import logging
from decimal import Decimal
from typing import Optional
from datetime import date

from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone
from .models import Invoice, InvoiceType

logger = logging.getLogger(__name__)


class InvoiceService:
    """
    Service class for generating invoices and receipts.
    
    Uses WeasyPrint to convert HTML templates to PDF.
    """
    
    @classmethod
    @transaction.atomic
    def generate_delivery_receipt(cls, delivery) -> 'Invoice':
        """
        Generate a receipt for a completed delivery.
        
        Args:
            delivery: Completed Delivery instance
            
        Returns:
            Invoice instance with PDF attached
        """
        from finance.models import Invoice, InvoiceType
        
        # Check if receipt already exists
        existing = Invoice.objects.filter(
            delivery=delivery,
            invoice_type=InvoiceType.DELIVERY_RECEIPT
        ).first()
        
        if existing:
            logger.info(f"Receipt already exists for delivery {delivery.id}")
            return existing
        
        # Prepare context for template
        context = cls._get_delivery_receipt_context(delivery)
        
        # Generate PDF
        pdf_content = cls._render_pdf('finance/pdf/delivery_receipt.html', context)
        
        # Create invoice record
        invoice_number = Invoice.get_next_invoice_number()
        
        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            invoice_type=InvoiceType.DELIVERY_RECEIPT,
            user=delivery.sender,
            delivery=delivery,
            amount=delivery.total_price,
            description=f"Reçu livraison {str(delivery.id)[:8]} - {delivery.recipient_name or delivery.recipient_phone}"
        )
        
        # Attach PDF file
        filename = f"receipt_{invoice_number}.pdf"
        invoice.pdf_file.save(filename, ContentFile(pdf_content), save=True)
        
        logger.info(f"Generated receipt {invoice_number} for delivery {delivery.id}")
        
        return invoice
    
    @classmethod
    @transaction.atomic
    def generate_courier_statement(
        cls, 
        courier, 
        year: int, 
        month: int
    ) -> 'Invoice':
        """
        Generate monthly earnings statement for a courier.
        
        Args:
            courier: User instance (COURIER role)
            year: Statement year
            month: Statement month (1-12)
            
        Returns:
            Invoice instance with PDF attached
        """
        from finance.models import Invoice, InvoiceType
        from logistics.models import Delivery, DeliveryStatus
        
        # Calculate period
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year + 1, 1, 1)
        else:
            period_end = date(year, month + 1, 1)
        
        # Check if statement already exists
        existing = Invoice.objects.filter(
            user=courier,
            invoice_type=InvoiceType.COURIER_STATEMENT,
            period_start=period_start
        ).first()
        
        if existing:
            logger.info(f"Statement already exists for courier {courier.id} - {year}/{month}")
            return existing
        
        # Get deliveries for the period
        deliveries = Delivery.objects.filter(
            courier=courier,
            status=DeliveryStatus.COMPLETED,
            completed_at__date__gte=period_start,
            completed_at__date__lt=period_end
        ).order_by('completed_at')
        
        # Calculate totals
        stats = deliveries.aggregate(
            total_earnings=Sum('courier_earning'),
            total_deliveries=Count('id'),
            total_distance=Sum('distance_km')
        )
        
        total_earnings = stats['total_earnings'] or Decimal('0')
        
        # Prepare context
        context = {
            'courier': courier,
            'period_start': period_start,
            'period_end': period_end,
            'deliveries': deliveries,
            'total_earnings': total_earnings,
            'total_deliveries': stats['total_deliveries'] or 0,
            'total_distance': stats['total_distance'] or 0,
            'generated_at': timezone.now(),
        }
        
        # Generate PDF
        pdf_content = cls._render_pdf('finance/pdf/courier_statement.html', context)
        
        # Create invoice
        invoice_number = Invoice.get_next_invoice_number()
        month_name = period_start.strftime('%B %Y')
        
        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            invoice_type=InvoiceType.COURIER_STATEMENT,
            user=courier,
            amount=total_earnings,
            period_start=period_start,
            period_end=period_end,
            description=f"Relevé coursier - {month_name}"
        )
        
        filename = f"statement_{invoice_number}.pdf"
        invoice.pdf_file.save(filename, ContentFile(pdf_content), save=True)
        
        logger.info(f"Generated statement {invoice_number} for courier {courier.id}")
        
        return invoice
    
    @classmethod
    @transaction.atomic
    def generate_b2b_invoice(
        cls,
        partner,
        year: int,
        month: int
    ) -> 'Invoice':
        """
        Generate monthly invoice for B2B partner.
        
        Args:
            partner: User instance (BUSINESS role)
            year: Invoice year
            month: Invoice month (1-12)
            
        Returns:
            Invoice instance with PDF attached
        """
        from finance.models import Invoice, InvoiceType
        from logistics.models import Delivery, DeliveryStatus
        
        # Calculate period
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year + 1, 1, 1)
        else:
            period_end = date(year, month + 1, 1)
        
        # Check if invoice already exists
        existing = Invoice.objects.filter(
            user=partner,
            invoice_type=InvoiceType.B2B_INVOICE,
            period_start=period_start
        ).first()
        
        if existing:
            logger.info(f"Invoice already exists for partner {partner.id} - {year}/{month}")
            return existing
        
        # Get deliveries for the period
        deliveries = Delivery.objects.filter(
            sender=partner,
            created_at__date__gte=period_start,
            created_at__date__lt=period_end
        ).exclude(status=DeliveryStatus.CANCELLED).order_by('created_at')
        
        # Calculate totals
        stats = deliveries.aggregate(
            total_amount=Sum('total_price'),
            total_deliveries=Count('id')
        )
        
        total_amount = stats['total_amount'] or Decimal('0')
        
        # Status breakdown
        completed = deliveries.filter(status=DeliveryStatus.COMPLETED).count()
        pending = deliveries.exclude(status=DeliveryStatus.COMPLETED).count()
        
        # Prepare context
        context = {
            'partner': partner,
            'period_start': period_start,
            'period_end': period_end,
            'deliveries': deliveries,
            'total_amount': total_amount,
            'total_deliveries': stats['total_deliveries'] or 0,
            'completed_count': completed,
            'pending_count': pending,
            'generated_at': timezone.now(),
        }
        
        # Generate PDF
        pdf_content = cls._render_pdf('finance/pdf/b2b_invoice.html', context)
        
        # Create invoice
        invoice_number = Invoice.get_next_invoice_number()
        month_name = period_start.strftime('%B %Y')
        
        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            invoice_type=InvoiceType.B2B_INVOICE,
            user=partner,
            amount=total_amount,
            period_start=period_start,
            period_end=period_end,
            description=f"Facture partenaire - {month_name}"
        )
        
        filename = f"invoice_{invoice_number}.pdf"
        invoice.pdf_file.save(filename, ContentFile(pdf_content), save=True)
        
        logger.info(f"Generated invoice {invoice_number} for partner {partner.id}")
        
        return invoice
    
    @staticmethod
    def _get_delivery_receipt_context(delivery) -> dict:
        """Prepare context for delivery receipt template."""
        return {
            'delivery': delivery,
            'sender': delivery.sender,
            'recipient_name': delivery.recipient_name or 'N/A',
            'recipient_phone': delivery.recipient_phone,
            'pickup_address': delivery.pickup_address or 'GPS',
            'dropoff_address': delivery.dropoff_address or (
                delivery.dropoff_neighborhood.name if delivery.dropoff_neighborhood else 'GPS'
            ),
            'distance_km': round(delivery.distance_km, 1),
            'total_price': delivery.total_price,
            'payment_method': delivery.get_payment_method_display(),
            'status': delivery.get_status_display(),
            'created_at': delivery.created_at,
            'completed_at': delivery.completed_at,
            'generated_at': timezone.now(),
        }
    
    @staticmethod
    def _render_pdf(template_name: str, context: dict) -> bytes:
        """
        Render HTML template to PDF bytes using WeasyPrint.
        
        Args:
            template_name: Path to Django template
            context: Template context dict
            
        Returns:
            PDF content as bytes
        """
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
        except ImportError:
            logger.error("WeasyPrint not installed. Run: pip install weasyprint")
            raise ImportError("WeasyPrint is required for PDF generation")
        
        # Render HTML
        html_content = render_to_string(template_name, context)
        
        # Configure fonts
        font_config = FontConfiguration()
        
        # Generate PDF
        pdf_buffer = io.BytesIO()
        HTML(string=html_content).write_pdf(
            pdf_buffer,
            font_config=font_config
        )
        
        return pdf_buffer.getvalue()
    
    @classmethod
    def send_receipt_via_whatsapp(cls, invoice: 'Invoice') -> bool:
        """
        Send invoice PDF via WhatsApp to the user.
        
        Args:
            invoice: Invoice instance with pdf_file attached
            
        Returns:
            True if sent successfully
        """
        try:
            from bot.services import send_whatsapp_document
            
            if not invoice.pdf_file:
                logger.warning(f"No PDF file for invoice {invoice.invoice_number}")
                return False
            
            # Get recipient phone
            if invoice.delivery:
                phone = invoice.delivery.recipient_phone
            else:
                phone = invoice.user.phone_number
            
            # Build message
            message = f"📄 Votre reçu DELIVR-CM #{invoice.invoice_number}"
            
            # Send document
            send_whatsapp_document(
                phone=phone,
                document_url=invoice.pdf_file.url,
                filename=f"DELIVR-CM_{invoice.invoice_number}.pdf",
                caption=message
            )
            
            logger.info(f"Sent invoice {invoice.invoice_number} to {phone}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send invoice via WhatsApp: {e}")
            return False
