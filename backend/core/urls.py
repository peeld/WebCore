"""Root URL configuration.

Core URLs are declared statically. Module URLs are appended by _module_urlpatterns()
which reads INSTALLED_MODULE_APPS from settings at startup.
"""
import importlib
import logging

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

logger = logging.getLogger(__name__)


def _module_urlpatterns():
    """Build URL patterns for all installed modules.

    Each module is mounted at /api/<app_label>/ where underscores become
    hyphens (e.g. user_auth -> /api/user-auth/).
    Modules without a urls.py are skipped with a warning.
    """
    patterns = []
    for app_label in getattr(settings, 'INSTALLED_MODULE_APPS', []):
        try:
            urls_module = importlib.import_module(f"{app_label}.urls")
            prefix = app_label.replace('_', '-')
            patterns.append(
                path(f"api/{prefix}/", include((urls_module, app_label)))
            )
            logger.debug("Registered URLs for module '%s' at /api/%s/", app_label, prefix)
        except ModuleNotFoundError as exc:
            urls_module_name = f"{app_label}.urls"
            if exc.name == urls_module_name:
                logger.warning(
                    "Module '%s' has no urls.py -- skipping URL registration", app_label
                )
            else:
                # Missing transitive dependency -- fail loudly rather than silently skip.
                raise
    return patterns


handler404 = 'core.error_handlers.handler404'
handler500 = 'core.error_handlers.handler500'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core_app.urls')),
] + _module_urlpatterns()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
