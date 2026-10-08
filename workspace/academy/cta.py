"""اعتبارسنجی و resolve لینک CTA ویدیوهای آکادمی."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import Resolver404, resolve, reverse

from shop.bot_catalog import BOT_PRODUCT_SLUG, get_bot_product_url

# مقادیر legacy که در DB یا seed قبلی ذخیره شده‌اند → URL name
LEGACY_PATH_REWRITES: dict[str, tuple[str, dict[str, Any] | None]] = {
    '/shop/': ('product_detail', {'slug': BOT_PRODUCT_SLUG}),
    '/shop': ('product_detail', {'slug': BOT_PRODUCT_SLUG}),
}

# slug ویدیو → مسیر canonical (برای seed و migration)
CURRICULUM_CTA_ROUTES: dict[str, tuple[str, dict[str, Any] | None]] = {
    'academy-dashboard-overview': ('workspace:home', None),
    'academy-license-purchase-activation': ('product_detail', {'slug': BOT_PRODUCT_SLUG}),
    'academy-extract-divar-listings': ('workspace:dataset_list', None),
    'academy-filter-files': ('workspace:multi_listings', None),
    'academy-review-analyze-file': ('workspace:multi_listings', None),
    'academy-personal-files-map': ('workspace:crm_properties', None),
    'academy-file-cabinets-folders': ('workspace:home', None),
    'academy-what-is-crm': ('workspace:crm_dashboard', None),
    'academy-adding-a-new-contact-to-crm': ('workspace:crm_contacts', None),
    'academy-crm-reminders-and-follow-ups': ('workspace:crm_today', None),
    'academy-personal-files-and-sharing-with-customers': ('workspace:crm_properties', None),
}

_DANGEROUS_SCHEMES = frozenset({'javascript', 'data', 'vbscript', 'file'})


def reverse_route(name: str, kwargs: dict[str, Any] | None = None) -> str:
    return reverse(name, kwargs=kwargs or {})


def canonical_cta_path_for_slug(slug: str) -> str:
    spec = CURRICULUM_CTA_ROUTES.get(slug)
    if not spec:
        return ''
    name, kw = spec
    if name == 'product_detail':
        return get_bot_product_url()
    return reverse_route(name, kw)


def normalize_stored_action_url(raw: str) -> str:
    url = (raw or '').strip()
    if not url:
        return ''
    rewrite = LEGACY_PATH_REWRITES.get(url)
    if rewrite:
        name, kw = rewrite
        if name == 'product_detail':
            return get_bot_product_url()
        return reverse_route(name, kw)
    return url


def _is_external_url(url: str) -> bool:
    if url.startswith('//'):
        return True
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)


def validate_academy_action_url(url: str) -> str | None:
    """پیام خطا یا None اگر معتبر است."""
    url = (url or '').strip()
    if not url:
        return None

    if url.startswith('//'):
        return 'آدرس با // مجاز نیست.'

    parsed = urlparse(url)
    if parsed.scheme:
        if parsed.scheme.lower() in _DANGEROUS_SCHEMES:
            return f'نوع آدرس «{parsed.scheme}» مجاز نیست.'
        if parsed.scheme.lower() not in ('http', 'https', 'mailto', 'tel'):
            return f'نوع آدرس «{parsed.scheme}» پشتیبانی نمی‌شود.'
        if parsed.scheme.lower() in ('http', 'https'):
            host = (parsed.netloc or '').lower()
            site_url = getattr(settings, 'SITE_URL', '') or ''
            if site_url:
                allowed = {urlparse(site_url).netloc.lower()}
                if host and allowed and host not in allowed:
                    return 'لینک خارجی فقط برای دامنه سایت مجاز است.'
        return None

    if not url.startswith('/'):
        return 'مسیر داخلی باید با / شروع شود.'

    if '..' in url:
        return 'مسیر نامعتبر است.'

    path = url.split('?', 1)[0]
    try:
        resolve(path)
    except Resolver404:
        return f'مسیر داخلی «{path}» در URLconf پیدا نشد.'
    return None


def resolve_academy_action_url(stored: str) -> str:
    """URL نمایشی امن؛ خالی اگر نامعتبر."""
    url = normalize_stored_action_url(stored)
    if not url:
        return ''
    if validate_academy_action_url(url):
        return ''
    return url


def django_validate_action_url(value: str) -> None:
    err = validate_academy_action_url(value)
    if err:
        raise ValidationError(err)


def iter_cta_fix_targets():
    """(slug, new_path) برای migration idempotent."""
    from workspace.academy.seed_data import CURRICULUM_VIDEO_SLUGS

    for slug in CURRICULUM_VIDEO_SLUGS:
        canonical = canonical_cta_path_for_slug(slug)
        if canonical:
            yield slug, canonical

    for legacy, (name, kw) in LEGACY_PATH_REWRITES.items():
        if name == 'product_detail':
            fixed = get_bot_product_url()
        else:
            fixed = reverse_route(name, kw)
        yield legacy, fixed
