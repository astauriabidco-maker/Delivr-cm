"""
DELIVR-CM Monitoring & Health Check Endpoints
===============================================

Provides:
1. /health/ - Basic liveness check (for load balancers/Docker)
2. /health/ready/ - Readiness check (DB, Redis, Celery status)
3. /health/detailed/ - Full system diagnostics (admin only)
"""

import time
import logging
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

logger = logging.getLogger('delivr.monitoring')


@csrf_exempt
@require_GET
def health_check(request):
    """
    Basic liveness probe.
    Returns 200 if the Django process is alive.
    Used by Docker HEALTHCHECK and load balancers.
    """
    return JsonResponse({
        'status': 'ok',
        'service': 'delivr-cm',
        'timestamp': timezone.now().isoformat(),
    })


@csrf_exempt
@require_GET
def readiness_check(request):
    """
    Readiness probe - checks all critical dependencies.
    Returns 200 only if ALL dependencies are healthy.
    Returns 503 if any dependency is down.
    """
    checks = {}
    all_healthy = True
    
    # 1. Database Check
    try:
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_time = round((time.time() - start) * 1000, 2)
        checks['database'] = {
            'status': 'healthy',
            'response_time_ms': db_time,
            'engine': 'PostgreSQL/PostGIS',
        }
    except Exception as e:
        checks['database'] = {
            'status': 'unhealthy',
            'error': str(e),
        }
        all_healthy = False
        logger.error(f"Health check - Database unhealthy: {e}")
    
    # 2. Redis/Cache Check
    try:
        start = time.time()
        cache_key = '_healthcheck_ping'
        cache.set(cache_key, 'pong', 10)
        result = cache.get(cache_key)
        redis_time = round((time.time() - start) * 1000, 2)
        
        if result == 'pong':
            checks['redis'] = {
                'status': 'healthy',
                'response_time_ms': redis_time,
            }
        else:
            raise Exception("Cache read/write mismatch")
    except Exception as e:
        checks['redis'] = {
            'status': 'unhealthy',
            'error': str(e),
        }
        all_healthy = False
        logger.error(f"Health check - Redis unhealthy: {e}")
    
    # 3. Celery Check (via inspect ping)
    try:
        from delivr_core.celery import app as celery_app
        start = time.time()
        inspector = celery_app.control.inspect(timeout=3.0)
        ping_result = inspector.ping()
        celery_time = round((time.time() - start) * 1000, 2)
        
        if ping_result:
            worker_count = len(ping_result)
            checks['celery'] = {
                'status': 'healthy',
                'workers': worker_count,
                'response_time_ms': celery_time,
            }
        else:
            checks['celery'] = {
                'status': 'degraded',
                'error': 'No workers responding',
                'response_time_ms': celery_time,
            }
            # Celery being down is degraded, not critical
            logger.warning("Health check - No Celery workers responding")
    except Exception as e:
        checks['celery'] = {
            'status': 'unhealthy',
            'error': str(e),
        }
        logger.error(f"Health check - Celery unhealthy: {e}")
    
    status_code = 200 if all_healthy else 503
    overall_status = 'healthy' if all_healthy else 'unhealthy'
    
    return JsonResponse({
        'status': overall_status,
        'service': 'delivr-cm',
        'timestamp': timezone.now().isoformat(),
        'checks': checks,
    }, status=status_code)


@csrf_exempt
@require_GET
def detailed_health(request):
    """
    Detailed system diagnostics (admin-only or internal).
    Includes stats about deliveries, couriers, and system metrics.
    """
    # Require staff authentication for detailed info
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({
            'error': 'Unauthorized',
            'message': 'Staff access required for detailed diagnostics',
        }, status=403)
    
    from core.models import User, UserRole
    from logistics.models import Delivery, DeliveryStatus
    from finance.models import Transaction
    
    try:
        # System Stats
        stats = {
            'users': {
                'total': User.objects.count(),
                'couriers': User.objects.filter(role=UserRole.COURIER).count(),
                'couriers_active': User.objects.filter(
                    role=UserRole.COURIER, 
                    is_active=True,
                    is_verified=True
                ).count(),
                'businesses': User.objects.filter(role=UserRole.BUSINESS).count(),
                'clients': User.objects.filter(role=UserRole.CLIENT).count(),
            },
            'deliveries': {
                'total': Delivery.objects.count(),
                'pending': Delivery.objects.filter(status=DeliveryStatus.PENDING).count(),
                'in_transit': Delivery.objects.filter(status=DeliveryStatus.IN_TRANSIT).count(),
                'completed_today': Delivery.objects.filter(
                    status=DeliveryStatus.COMPLETED,
                    completed_at__date=timezone.now().date()
                ).count(),
            },
            'transactions': {
                'total': Transaction.objects.count(),
                'today': Transaction.objects.filter(
                    created_at__date=timezone.now().date()
                ).count(),
            },
        }
        
        return JsonResponse({
            'status': 'ok',
            'service': 'delivr-cm',
            'timestamp': timezone.now().isoformat(),
            'stats': stats,
        })
        
    except Exception as e:
        logger.error(f"Detailed health check error: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e),
        }, status=500)
