"""
ASGI برای سرویس WebSocket تالار گفتگو (مستقل از Gunicorn HTTP).

اجرای پیشنهادی:
  daphne -b 127.0.0.1 -p 8001 divar_shop.asgi_ws:application
"""
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'divar_shop.settings')

django_asgi_app = get_asgi_application()

from community_forum.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    ),
})
