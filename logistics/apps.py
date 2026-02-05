from django.apps import AppConfig


class LogisticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'logistics'
    
    def ready(self):
        # Register signals for auto-dispatch
        import logistics.signals  # noqa: F401
