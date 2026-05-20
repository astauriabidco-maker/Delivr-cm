"""
RELAY237 ASGI Configuration

Configures Django Channels with WebSocket support for real-time tracking.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'delivr_core.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

from logistics.routing import websocket_urlpatterns


class NativeFriendlyAllowedHostsOriginValidator:
    """
    Apply browser Origin validation when the header exists, while allowing
    native mobile WebSocket clients that do not send an Origin header.
    """

    def __init__(self, application):
        self.application = application
        self.origin_validator = AllowedHostsOriginValidator(application)

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        if b"origin" in headers:
            return await self.origin_validator(scope, receive, send)
        return await self.application(scope, receive, send)


application = ProtocolTypeRouter({
    # Django's ASGI application to handle traditional HTTP requests
    "http": django_asgi_app,
    
    # WebSocket handler for real-time tracking
    "websocket": NativeFriendlyAllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    ),
})
