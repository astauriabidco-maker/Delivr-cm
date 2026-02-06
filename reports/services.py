"""
REPORTS App - PDF Generation Service

Uses WeasyPrint to generate PDF reports from HTML templates.
"""

import logging
from io import BytesIO
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import date, timedelta

from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


# ===========================================
# REPORT GENERATOR SERVICE
# ===========================================

class ReportGenerator:
    """
    Service for generating PDF reports.
    
    Uses WeasyPrint for HTML-to-PDF conversion.
    Falls back to HTML if WeasyPrint is not available.
    """
    
    @staticmethod
    def _render_html(template_name: str, context: Dict[str, Any]) -> str:
        """Render HTML from Django template."""
        return render_to_string(template_name, context)
    
    @staticmethod
    def _html_to_pdf(html_content: str) -> BytesIO:
        """
        Convert HTML to PDF using WeasyPrint.
        
        Args:
            html_content: Rendered HTML string
            
        Returns:
            BytesIO buffer containing PDF data
        """
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            
            font_config = FontConfiguration()
            
            # Base CSS for all reports
            base_css = CSS(string='''
                @page {
                    size: A4;
                    margin: 1.5cm;
                }
                body {
                    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
                    font-size: 11pt;
                    color: #333;
                    line-height: 1.5;
                }
                h1 { font-size: 20pt; color: #1f2937; margin-bottom: 0.5em; }
                h2 { font-size: 14pt; color: #374151; margin-top: 1em; }
                h3 { font-size: 12pt; color: #4b5563; }
                table { width: 100%; border-collapse: collapse; margin: 1em 0; }
                th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
                th { background: #f9fafb; font-weight: 600; }
                .header { border-bottom: 2px solid #f59e0b; padding-bottom: 1em; margin-bottom: 1em; }
                .logo { font-size: 24pt; font-weight: bold; color: #f59e0b; }
                .stats-grid { display: flex; gap: 1em; flex-wrap: wrap; margin: 1em 0; }
                .stat-card { flex: 1; min-width: 120px; background: #fef3c7; padding: 1em; border-radius: 8px; }
                .stat-value { font-size: 24pt; font-weight: bold; color: #f59e0b; }
                .stat-label { font-size: 9pt; color: #6b7280; text-transform: uppercase; }
                .footer { margin-top: 2em; padding-top: 1em; border-top: 1px solid #e5e7eb; 
                          font-size: 9pt; color: #6b7280; text-align: center; }
            ''', font_config=font_config)
            
            html = HTML(string=html_content)
            pdf_buffer = BytesIO()
            html.write_pdf(pdf_buffer, stylesheets=[base_css], font_config=font_config)
            pdf_buffer.seek(0)
            
            return pdf_buffer
            
        except ImportError:
            logger.error("[REPORTS] WeasyPrint not installed. Run: pip install weasyprint")
            raise ImportError("WeasyPrint is required for PDF generation")
    
    @classmethod
    def generate_courier_performance_report(
        cls,
        courier,
        start_date: date = None,
        end_date: date = None
    ) -> BytesIO:
        """
        Generate a performance report for a courier.
        
        Args:
            courier: User model instance (courier)
            start_date: Report start date (default: 30 days ago)
            end_date: Report end date (default: today)
            
        Returns:
            BytesIO buffer containing PDF
        """
        from logistics.models import Delivery, DeliveryStatus
        from finance.models import Transaction, TransactionType
        from django.db.models import Sum, Count, Avg
        
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Query deliveries
        deliveries = Delivery.objects.filter(
            courier=courier,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        delivery_stats = deliveries.aggregate(
            total=Count('id'),
            completed=Count('id', filter=lambda q: q.status == DeliveryStatus.COMPLETED),
            cancelled=Count('id', filter=lambda q: q.status == DeliveryStatus.CANCELLED),
            total_distance=Sum('distance_km'),
            total_earnings=Sum('courier_earning', filter=lambda q: q.status == DeliveryStatus.COMPLETED)
        )
        
        # Daily breakdown
        daily_stats = deliveries.filter(
            status=DeliveryStatus.COMPLETED
        ).extra(
            select={'day': 'date(completed_at)'}
        ).values('day').annotate(
            count=Count('id'),
            earnings=Sum('courier_earning'),
            distance=Sum('distance_km')
        ).order_by('-day')[:14]  # Last 14 days
        
        context = {
            'courier': courier,
            'start_date': start_date,
            'end_date': end_date,
            'generated_at': timezone.now(),
            'stats': delivery_stats,
            'daily_breakdown': list(daily_stats),
            'level_info': {
                'current': courier.courier_level,
                'total_deliveries': courier.total_deliveries_completed,
                'streak': courier.consecutive_success_streak,
                'rating': courier.average_rating,
            }
        }
        
        html = cls._render_html('reports/courier_performance.html', context)
        return cls._html_to_pdf(html)
    
    @classmethod
    def generate_courier_earnings_report(
        cls,
        courier,
        month: int = None,
        year: int = None
    ) -> BytesIO:
        """
        Generate a monthly earnings report for a courier.
        
        Args:
            courier: User model instance
            month: Month number (1-12), default: current month
            year: Year, default: current year
            
        Returns:
            BytesIO buffer containing PDF
        """
        from logistics.models import Delivery, DeliveryStatus
        from finance.models import Transaction
        from django.db.models import Sum, Count
        import calendar
        
        now = timezone.now()
        if not month:
            month = now.month
        if not year:
            year = now.year
        
        # Date range for the month
        start_date = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)
        
        # Deliveries this month
        deliveries = Delivery.objects.filter(
            courier=courier,
            status=DeliveryStatus.COMPLETED,
            completed_at__date__gte=start_date,
            completed_at__date__lte=end_date
        )
        
        earnings = deliveries.aggregate(
            total_earnings=Sum('courier_earning'),
            total_deliveries=Count('id'),
            total_distance=Sum('distance_km')
        )
        
        # Transactions this month
        transactions = Transaction.objects.filter(
            user=courier,
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).order_by('-created_at')
        
        # Weekly breakdown
        weekly_data = []
        for week in range(5):
            week_start = start_date + timedelta(days=week * 7)
            week_end = min(week_start + timedelta(days=6), end_date)
            
            if week_start > end_date:
                break
                
            week_deliveries = deliveries.filter(
                completed_at__date__gte=week_start,
                completed_at__date__lte=week_end
            )
            
            week_stats = week_deliveries.aggregate(
                count=Count('id'),
                earnings=Sum('courier_earning')
            )
            
            weekly_data.append({
                'week': week + 1,
                'start': week_start,
                'end': week_end,
                'count': week_stats['count'] or 0,
                'earnings': week_stats['earnings'] or Decimal('0')
            })
        
        context = {
            'courier': courier,
            'month_name': calendar.month_name[month],
            'year': year,
            'start_date': start_date,
            'end_date': end_date,
            'generated_at': timezone.now(),
            'earnings': earnings,
            'weekly_breakdown': weekly_data,
            'transactions': list(transactions[:30]),
            'wallet_balance': courier.wallet_balance,
            'debt_ceiling': courier.debt_ceiling,
        }
        
        html = cls._render_html('reports/courier_earnings.html', context)
        return cls._html_to_pdf(html)
    
    @classmethod
    def generate_fleet_kpi_report(
        cls,
        start_date: date = None,
        end_date: date = None
    ) -> BytesIO:
        """
        Generate a fleet KPI report for administrators.
        
        Args:
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            BytesIO buffer containing PDF
        """
        from logistics.models import Delivery, DeliveryStatus
        from core.models import User, UserRole
        from django.db.models import Sum, Count, Avg, F
        
        if not end_date:
            end_date = timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Fleet overview
        couriers = User.objects.filter(role=UserRole.COURIER)
        
        fleet_stats = {
            'total': couriers.count(),
            'verified': couriers.filter(is_verified=True).count(),
            'online': couriers.filter(is_online=True).count(),
        }
        
        # Delivery stats
        deliveries = Delivery.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        delivery_stats = deliveries.aggregate(
            total=Count('id'),
            completed=Count('id', filter=lambda q: q.status == DeliveryStatus.COMPLETED),
            cancelled=Count('id', filter=lambda q: q.status == DeliveryStatus.CANCELLED),
            total_revenue=Sum('total_price', filter=lambda q: q.status == DeliveryStatus.COMPLETED),
            platform_fees=Sum('platform_fee', filter=lambda q: q.status == DeliveryStatus.COMPLETED),
        )
        
        # Top performers
        top_couriers = User.objects.filter(
            role=UserRole.COURIER,
            is_verified=True
        ).annotate(
            period_deliveries=Count(
                'assigned_deliveries',
                filter=lambda q: q.status == DeliveryStatus.COMPLETED and 
                                  q.completed_at__date__gte == start_date
            )
        ).order_by('-period_deliveries')[:10]
        
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'generated_at': timezone.now(),
            'fleet': fleet_stats,
            'deliveries': delivery_stats,
            'top_performers': list(top_couriers),
        }
        
        html = cls._render_html('reports/fleet_kpi.html', context)
        return cls._html_to_pdf(html)
