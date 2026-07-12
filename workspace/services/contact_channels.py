"""کانال‌های پیام‌رسانی مخاطب CRM — شبکه‌های فعال و شناسه/شماره."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import quote

from workspace.services.crm import normalize_phone
from workspace.services.public_share_common import (
    SOCIAL_NETWORK_DEFS,
    WHATSAPP_ICON_FILE,
    normalize_social_links,
    resolve_social_href,
)

CONTACT_BUILTIN_CHANNELS: Tuple[Dict[str, Any], ...] = (
    {
        'key': 'whatsapp',
        'label': 'واتساپ',
        'icon': 'fab fa-whatsapp',
        'icon_file': WHATSAPP_ICON_FILE,
        'color': '#25D366',
        'uses_phone': True,
        'mode': 'whatsapp',
    },
    {
        'key': 'sms',
        'label': 'پیامک',
        'icon': 'fas fa-sms',
        'icon_file': '',
        'color': '#2563EB',
        'uses_phone': True,
        'mode': 'sms',
    },
    {
        'key': 'phone',
        'label': 'تماس',
        'icon': 'fas fa-phone',
        'icon_file': '',
        'color': '#10B981',
        'uses_phone': True,
        'mode': 'tel',
    },
)

_ALL_KEYS: Set[str] = {c['key'] for c in CONTACT_BUILTIN_CHANNELS} | {d['key'] for d in SOCIAL_NETWORK_DEFS}

_SOURCE_CHANNEL_HINTS = {
    'تلگرام': 'telegram',
    'اینستاگرام': 'instagram',
    'دیوار': 'phone',
    'سایت': 'phone',
}


def _phone_wa_href(phone: str) -> str:
    key = normalize_phone(phone or '')
    if not key:
        return ''
    digits = key[1:] if key.startswith('0') else key
    if digits.startswith('98'):
        return f'https://wa.me/{digits}'
    return f'https://wa.me/98{digits}'


def _phone_sms_href(phone: str) -> str:
    key = normalize_phone(phone or '')
    return f'sms:{key}' if key else ''


def _phone_tel_href(phone: str) -> str:
    key = normalize_phone(phone or '')
    return f'tel:{key}' if key else ''


def normalize_active_channels(
    raw: Optional[Sequence[str]],
    *,
    social_links: Optional[dict] = None,
    phone: str = '',
) -> List[str]:
    """فهرست یکتا از کلیدهای کانال فعال."""
    out: List[str] = []
    seen: Set[str] = set()
    for item in raw or []:
        key = str(item or '').strip()
        if key and key in _ALL_KEYS and key not in seen:
            out.append(key)
            seen.add(key)
    return out


def default_active_channels_for_source(source: str = '') -> List[str]:
    key = _SOURCE_CHANNEL_HINTS.get((source or '').strip())
    if key:
        return [key]
    return []


def contact_channels_from_post(post) -> Tuple[List[str], Dict[str, str]]:
    """خواندن کانال‌های فعال و شناسه‌ها از POST فرم مخاطب."""
    social_raw = {}
    for defn in SOCIAL_NETWORK_DEFS:
        key = defn['key']
        social_raw[key] = post.get(f'contact_social_{key}') or ''
    social_links = normalize_social_links(social_raw)

    active: List[str] = []
    for key in _ALL_KEYS:
        flag = post.get(f'contact_active_{key}')
        if flag in ('on', '1', 'true', 'True', True):
            active.append(key)

    phone = post.get('phone') or post.get('phone_alt') or ''
    return normalize_active_channels(active, social_links=social_links, phone=phone), social_links


def contact_channels_form_list(
    customer=None,
    *,
    social_links: Optional[dict] = None,
    active_channels: Optional[Sequence[str]] = None,
    phone: str = '',
) -> List[Dict[str, Any]]:
    """لیست کامل کانال‌ها برای فرم ایجاد/ویرایش مخاطب."""
    links = normalize_social_links(
        social_links if social_links is not None
        else (getattr(customer, 'social_links', None) or {})
    )
    active_set = set(
        active_channels if active_channels is not None
        else (getattr(customer, 'active_channels', None) or [])
    )
    phone_val = phone or (getattr(customer, 'phone', None) or '')

    items: List[Dict[str, Any]] = []
    for ch in CONTACT_BUILTIN_CHANNELS:
        key = ch['key']
        items.append({
            **ch,
            'active': key in active_set,
            'handle': phone_val,
            'placeholder': 'از فیلد موبایل',
            'readonly_handle': True,
            'ready': bool(normalize_phone(phone_val)),
        })
    for defn in SOCIAL_NETWORK_DEFS:
        key = defn['key']
        handle = links.get(key, '')
        items.append({
            'key': key,
            'label': defn['label'],
            'icon': defn['icon'],
            'icon_file': defn.get('icon_file', ''),
            'color': defn['color'],
            'placeholder': defn['placeholder'],
            'uses_phone': False,
            'mode': 'telegram' if key == 'telegram' else 'copy_open',
            'active': key in active_set,
            'handle': handle,
            'readonly_handle': False,
            'ready': bool(handle and resolve_social_href(key, handle)),
        })
    return items


def contact_channels_form_list_for_form(form) -> List[Dict[str, Any]]:
    """لیست کانال‌ها با توجه به وضعیت bound/unbound فرم."""
    if getattr(form, 'is_bound', False):
        active, links = contact_channels_from_post(form.data)
        phone = form.data.get('phone', '')
        return contact_channels_form_list(
            None,
            social_links=links,
            active_channels=active,
            phone=phone,
        )
    instance = form.instance
    if instance.pk:
        return contact_channels_form_list(instance)
    return contact_channels_form_list(None)


def contact_channels_for_display(customer, *, message: str = '') -> List[Dict[str, Any]]:
    """کانال‌های فعال مخاطب با لینک پیام — برای صفحه جزئیات و پنل."""
    links = normalize_social_links(getattr(customer, 'social_links', None) or {})
    active = normalize_active_channels(
        getattr(customer, 'active_channels', None) or [],
        social_links=links,
        phone=customer.phone or '',
    )
    phone = customer.phone or ''
    out: List[Dict[str, Any]] = []

    for key in active:
        if key == 'whatsapp':
            href = _phone_wa_href(phone)
            if not href:
                continue
            if message:
                href = f'{href}?text={quote(message)}'
            out.append({
                'key': 'whatsapp',
                'label': 'واتساپ',
                'icon': 'fab fa-whatsapp',
                'icon_file': WHATSAPP_ICON_FILE,
                'color': '#25D366',
                'href': href,
                'mode': 'link',
            })
            continue
        if key == 'sms':
            href = _phone_sms_href(phone)
            if href:
                out.append({
                    'key': 'sms',
                    'label': 'پیامک',
                    'icon': 'fas fa-sms',
                    'icon_file': '',
                    'color': '#2563EB',
                    'href': href,
                    'mode': 'link',
                })
            continue
        if key == 'phone':
            href = _phone_tel_href(phone)
            if href:
                out.append({
                    'key': 'phone',
                    'label': 'تماس',
                    'icon': 'fas fa-phone',
                    'icon_file': '',
                    'color': '#10B981',
                    'href': href,
                    'mode': 'link',
                })
            continue

        raw = links.get(key, '')
        if not raw:
            continue
        href = resolve_social_href(key, raw)
        if not href:
            continue
        defn = next((d for d in SOCIAL_NETWORK_DEFS if d['key'] == key), None)
        if not defn:
            continue
        out.append({
            'key': key,
            'label': defn['label'],
            'icon': defn['icon'],
            'icon_file': defn.get('icon_file', ''),
            'color': defn['color'],
            'href': href,
            'mode': 'telegram' if key == 'telegram' else 'copy_open',
            'handle': raw,
        })
    return out


def merge_contact_channels(primary, secondary) -> None:
    """ادغام کانال‌ها هنگام merge مخاطبین."""
    sec_links = normalize_social_links(getattr(secondary, 'social_links', None) or {})
    pri_links = normalize_social_links(getattr(primary, 'social_links', None) or {})
    merged_links = {**sec_links, **pri_links}

    pri_active = list(getattr(primary, 'active_channels', None) or [])
    sec_active = list(getattr(secondary, 'active_channels', None) or [])
    merged_active = normalize_active_channels(
        pri_active + sec_active,
        social_links=merged_links,
        phone=primary.phone or secondary.phone or '',
    )
    primary.social_links = merged_links
    primary.active_channels = merged_active
