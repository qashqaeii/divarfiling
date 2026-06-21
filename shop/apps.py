from django.apps import AppConfig


class ShopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'shop'
    verbose_name = 'فروشگاه'

    def ready(self):
        from divar_shop.startup_checks import run_production_checks, sync_site_from_settings
        sync_site_from_settings()
        run_production_checks()

