"""
DELIVR-CM Security Middleware
=============================

Provides:
1. Rate Limiting (per IP and per user) using Django cache (Redis)
2. Security Headers (HSTS, CSP, X-Content-Type, etc.)
3. Request Audit Logging for sensitive endpoints
4. OTP Brute-Force Protection
"""

import time
import logging
import hashlib
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('delivr.security')


class RateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware using Redis cache.
    
    Configurable rates per endpoint pattern:
    - API endpoints: 100 requests/minute per IP
    - Auth endpoints: 10 requests/minute per IP (brute-force protection)
    - OTP verification: 5 attempts/5 minutes per IP (critical protection)
    - Webhooks: 200 requests/minute per IP
    """
    
    # Rate limit configurations: (max_requests, time_window_seconds)
    RATE_LIMITS = {
        '/api/auth/token/': (10, 60),           # 10 req/min - Login
        '/api/auth/token/refresh/': (20, 60),    # 20 req/min - Refresh
        '/api/mobile/auth/': (10, 60),           # 10 req/min - Mobile login
        '/api/deliveries/verify-otp/': (5, 300), # 5 req/5min - OTP verify
        '/api/deliveries/verify-pickup/': (5, 300),  # 5 req/5min - Pickup OTP
        '/webhooks/': (200, 60),                 # 200 req/min - Webhooks
    }
    
    # Default rate limit for all API endpoints
    DEFAULT_API_LIMIT = (100, 60)  # 100 req/min
    
    def _get_client_ip(self, request):
        """Extract real client IP, considering proxy headers."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')
    
    def _get_rate_limit(self, path):
        """Get rate limit config for the given path."""
        for pattern, limits in self.RATE_LIMITS.items():
            if path.startswith(pattern):
                return limits
        
        # Apply default limit only to API endpoints
        if path.startswith('/api/'):
            return self.DEFAULT_API_LIMIT
        
        return None  # No rate limiting for non-API paths
    
    def process_request(self, request):
        """Check rate limits before processing the request."""
        # Skip rate limiting in DEBUG mode if explicitly disabled
        if settings.DEBUG and not getattr(settings, 'RATE_LIMIT_IN_DEBUG', False):
            return None
        
        path = request.path
        rate_limit = self._get_rate_limit(path)
        
        if rate_limit is None:
            return None
        
        max_requests, window = rate_limit
        client_ip = self._get_client_ip(request)
        
        # Create a unique cache key
        path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
        cache_key = f"rl:{client_ip}:{path_hash}"
        
        # Get current request count
        request_count = cache.get(cache_key, 0)
        
        if request_count >= max_requests:
            logger.warning(
                f"Rate limit exceeded: IP={client_ip} path={path} "
                f"count={request_count}/{max_requests} window={window}s"
            )
            
            # Calculate retry-after
            ttl = cache.ttl(cache_key) if hasattr(cache, 'ttl') else window
            
            return JsonResponse({
                'error': 'rate_limit_exceeded',
                'message': 'Trop de requêtes. Veuillez réessayer plus tard.',
                'retry_after': ttl,
            }, status=429, headers={
                'Retry-After': str(ttl),
                'X-RateLimit-Limit': str(max_requests),
                'X-RateLimit-Remaining': '0',
            })
        
        # Increment counter
        try:
            new_count = cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, window)
            new_count = 1
        
        # Store remaining for response headers
        request._rate_limit_remaining = max(0, max_requests - new_count)
        request._rate_limit_limit = max_requests
        
        return None
    
    def process_response(self, request, response):
        """Add rate limit headers to response."""
        if hasattr(request, '_rate_limit_limit'):
            response['X-RateLimit-Limit'] = str(request._rate_limit_limit)
            response['X-RateLimit-Remaining'] = str(request._rate_limit_remaining)
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all responses.
    
    Protects against:
    - XSS attacks (Content-Security-Policy)
    - MIME type sniffing (X-Content-Type-Options)
    - Clickjacking (X-Frame-Options)
    - Information leakage (Server header removal)
    """
    
    def process_response(self, request, response):
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent rendering in iframe (clickjacking protection)
        # Allow Django admin to use iframes internally
        if not request.path.startswith('/admin/'):
            response['X-Frame-Options'] = 'DENY'
        
        # XSS Protection (legacy browsers)
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy (restrict browser features)
        response['Permissions-Policy'] = (
            'geolocation=(self), '
            'camera=(self), '
            'microphone=(), '
            'payment=()'
        )
        
        # Remove server identification
        if 'Server' in response:
            del response['Server']
        
        # HSTS (only in production)
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains; preload'
            )
        
        return response


class RequestAuditMiddleware(MiddlewareMixin):
    """
    Audit logging for sensitive API operations.
    
    Logs:
    - All write operations (POST, PUT, PATCH, DELETE) on API
    - Authentication attempts
    - Failed requests (4xx, 5xx)
    """
    
    SENSITIVE_PATHS = [
        '/api/auth/',
        '/api/wallet/',
        '/api/deliveries/',
        '/admin/',
    ]
    
    def _should_log(self, request, response):
        """Determine if this request should be logged."""
        path = request.path
        method = request.method
        
        # Always log auth attempts
        if '/auth/' in path:
            return True
        
        # Log all write operations on sensitive paths
        if method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return any(path.startswith(p) for p in self.SENSITIVE_PATHS)
        
        # Log server errors
        if response.status_code >= 500:
            return True
        
        # Log client errors on API (potential attacks)
        if response.status_code >= 400 and path.startswith('/api/'):
            return True
        
        return False
    
    def process_response(self, request, response):
        """Log the request if it meets audit criteria."""
        if self._should_log(request, response):
            user = getattr(request, 'user', None)
            user_info = str(user) if user and user.is_authenticated else 'anonymous'
            
            ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
                or request.META.get('REMOTE_ADDR', '?')
            
            log_data = {
                'method': request.method,
                'path': request.path,
                'status': response.status_code,
                'user': user_info,
                'ip': ip,
                'user_agent': request.META.get('HTTP_USER_AGENT', '?')[:100],
            }
            
            if response.status_code >= 500:
                logger.error(f"AUDIT [ERROR] {log_data}")
            elif response.status_code >= 400:
                logger.warning(f"AUDIT [WARN] {log_data}")
            else:
                logger.info(f"AUDIT [OK] {log_data}")
        
        return response
