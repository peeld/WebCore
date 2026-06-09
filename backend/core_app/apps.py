from django.apps import AppConfig


class CoreAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core_app'
    label = 'core_app'
    verbose_name = 'Core'

    def ready(self):
        import core_app.signals  # noqa: F401 — registers signal handlers
