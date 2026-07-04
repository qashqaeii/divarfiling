"""ابزارهای مشترک اشتراک عمومی آگهی و فایل شخصی."""
from __future__ import annotations

import secrets
from typing import Any, Dict
from urllib.parse import quote

from django.conf import settings
from django.urls import reverse

from workspace.mixins import get_or_create_settings
from workspace.models import WorkspaceSettings


def generate_share_token() -> str:
    return secrets.token_urlsafe(9)


def unique_share_token(model_cls) -> str:
    token = generate_share_token()
    while model_cls.objects.filter(share_token=token).exists():
        token = generate_share_token()
    return token


def consultant_name(user, settings: WorkspaceSettings, share) -> str:
    if share.consultant_name.strip():
        return share.consultant_name.strip()
    if settings.agency_name.strip():
        return settings.agency_name.strip()
    full = (user.get_full_name() or '').strip()
    if full:
        return full
    return 'مشاور املاک'


def consultant_phone(user, share) -> str:
    if share.consultant_phone.strip():
        return share.consultant_phone.strip()
    return (user.phone or '').strip()


def phone_whatsapp_digits(phone: str) -> str:
    digits = ''.join(c for c in (phone or '') if c.isdigit())
    if digits.startswith('98'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = digits[1:]
    return digits


def consultant_contact_urls(phone: str, message: str = '') -> Dict[str, str]:
    wa_digits = phone_whatsapp_digits(phone)
    tel = phone.strip() if phone else ''
    urls = {'tel_url': f'tel:{tel}' if tel else '', 'whatsapp_url': ''}
    if wa_digits:
        base = f'https://wa.me/98{wa_digits}'
        urls['whatsapp_url'] = f'{base}?text={quote(message)}' if message else base
    return urls


def absolute_public_share_url(url_name: str, *, share_token: str) -> str:
    """آدرس کامل صفحه عمومی — بدون نیاز به request."""
    path = reverse(url_name, kwargs={'share_token': share_token})
    base = (getattr(settings, 'SITE_URL', '') or '').strip().rstrip('/')
    return f'{base}{path}' if base else path


def public_share_to_dict(share, request, *, url_name: str) -> Dict[str, Any]:
    path = reverse(url_name, kwargs={'share_token': share.share_token})
    share_url = request.build_absolute_uri(path) if request else absolute_public_share_url(url_name, share_token=share.share_token)
    return {
        'share_url': share_url,
        'share_token': share.share_token,
        'view_count': share.view_count,
        'is_active': share.is_active,
        'consultant_name': share.consultant_name,
        'consultant_phone': share.consultant_phone,
        'welcome_message': share.welcome_message,
        'show_divar_link': share.show_divar_link,
        'show_full_address': getattr(share, 'show_full_address', False),
        'show_internal_notes': getattr(share, 'show_internal_notes', False),
    }


def build_map_navigation(latitude, longitude) -> Dict[str, Any] | None:
    """لینک مسیریابی برای صفحه عمومی — وقتی مختصات معتبر است."""
    if latitude is None or longitude is None:
        return None
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    if lat == 0 and lng == 0:
        return None
    dest = f'{lat},{lng}'
    return {
        'latitude': lat,
        'longitude': lng,
        'google_url': f'https://www.google.com/maps/dir/?api=1&destination={dest}',
        'neshan_url': f'https://neshan.org/maps/routing/car/destination/{lat},{lng}',
        'waze_url': f'https://waze.com/ul?ll={lat},{lng}&navigate=yes',
    }


def filter_public_feature_highlights(feature_profile: dict, highlights: list) -> list:
    """برچسب‌های تکراری با feature_profile.core را از نوار highlights حذف می‌کند."""
    skip: set[str] = set()
    for item in feature_profile.get('core', []):
        if not (item.get('known') and item.get('state') == 'yes'):
            continue
        for field in ('label', 'key'):
            val = str(item.get(field) or '').strip()
            if val:
                skip.add(val)
    filtered: list = []
    for text in highlights:
        label = str(text or '').strip()
        if not label:
            continue
        base = label.split(':')[0].replace(' ندارد', '').strip()
        if label in skip or base in skip:
            continue
        filtered.append(label)
    return filtered


def build_consultant_block(user, share, *, title: str = 'ملک') -> Dict[str, Any]:
    settings = get_or_create_settings(user)
    name = consultant_name(user, settings, share)
    phone = consultant_phone(user, share)
    wa_message = f'سلام {name}، درباره «{title}» اطلاعات بیشتری می‌خواهم.'
    return {
        'name': name,
        'phone': phone,
        'phone_display': phone,
        'has_phone': bool(phone),
        'agency_name': settings.agency_name.strip(),
        'agency_logo': settings.agency_logo,
        'welcome_message': share.welcome_message.strip(),
        **consultant_contact_urls(phone, wa_message),
    }
