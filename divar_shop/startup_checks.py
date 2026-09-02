"""اعتبارسنجی تنظیمات production هنگام بالا آمدن Django."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

_INSECURE_SECRET_PREFIXES = ('django-insecure-',)
_WEAK_LICENSE_SECRETS = frozenset({
    '',
    'change-this-secret-key-in-production',
})


def sync_site_from_settings() -> None:
    """همگام‌سازی django.contrib.sites با SITE_URL برای sitemap و ایمیل‌ها."""
    site_url = getattr(settings, 'SITE_URL', '').strip().rstrip('/')
    if not site_url:
        return

    parsed = urlparse(site_url)
    domain = parsed.netloc or parsed.path
    if not domain:
        return

    try:
        from django.contrib.sites.models import Site
        from django.db.utils import OperationalError, ProgrammingError

        site_id = getattr(settings, 'SITE_ID', 1)
        name = getattr(settings, 'SITE_NAME', domain)
        Site.objects.update_or_create(
            pk=site_id,
            defaults={'domain': domain, 'name': name},
        )
    except (ImportError, OperationalError, ProgrammingError):
        logger.debug('Site sync skipped (sites app or database unavailable).')


def run_production_checks() -> None:
    if settings.DEBUG:
        return

    secret = settings.SECRET_KEY or ''
    if any(secret.startswith(p) for p in _INSECURE_SECRET_PREFIXES) or len(secret) < 50:
        raise ImproperlyConfigured(
            'SECRET_KEY must be a random string of at least 50 characters when DEBUG=False.'
        )

    license_secret = getattr(settings, 'LICENSE_SECRET_KEY', '') or ''
    if license_secret in _WEAK_LICENSE_SECRETS or len(license_secret) < 32:
        raise ImproperlyConfigured(
            'LICENSE_SECRET_KEY must be at least 32 characters when DEBUG=False.'
        )

    bot_key = getattr(settings, 'LICENSE_BOT_API_KEY', '') or ''
    if not bot_key:
        logger.critical(
            'LICENSE_BOT_API_KEY is empty — license bot API will reject all requests in production.'
        )

    merchant = getattr(settings, 'ZIBAL_MERCHANT_ID', '') or ''
    if not merchant:
        logger.warning(
            'ZIBAL_MERCHANT_ID is empty — online payment will fail until configured.'
        )

    from workspace.carto_basemap import warn_if_carto_key_missing

    warn_if_carto_key_missing()
