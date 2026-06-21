from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class LicensesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'licenses'
    verbose_name = 'لایسنس‌ها'

    def ready(self):
        from django.conf import settings
        from licenses.services.security import is_weak_license_secret

        if not settings.DEBUG and is_weak_license_secret():
            logger.critical(
                'LICENSE_SECRET_KEY is weak or default — set a strong key in production .env'
            )

