"""ASGI entry point (reserved for future async/WebSocket support)."""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.production')
application = get_asgi_application()
