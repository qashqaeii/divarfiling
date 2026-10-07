"""Template helpers for Advisor 360 presentation layer."""
from __future__ import annotations

from django import template

from workspace.constants import ACTIVITY_TYPES
from workspace.services.agency_activity import EVENT_TYPE_LABELS

register = template.Library()

_FOLLOWUP_LABELS = {
    'call': 'تماس',
    'visit': 'بازدید',
    'meeting': 'جلسه',
    'follow_up': 'پیگیری',
    'note': 'یادداشت',
    'whatsapp': 'واتساپ',
    'sms': 'پیامک',
    'email': 'ایمیل',
}

_EVENT_KEY_LABELS = {
    'follow_up': 'پیگیری مشتری',
    'customer_created': 'مخاطب جدید',
    'contact_created': 'مخاطب جدید',
    'property_created': 'فایل شخصی اضافه شد',
    'personal_property_created': 'فایل شخصی اضافه شد',
    'deal_created': 'معامله جدید',
    'deal_stage_changed': 'مرحله معامله تغییر کرد',
    'contract_created': 'قرارداد ایجاد شد',
    'dataset_created': 'استخراج جدید',
    'extraction_completed': 'استخراج تکمیل شد',
    'visit_created': 'بازدید ثبت شد',
    'call_created': 'تماس ثبت شد',
    'customer_activity': 'فعالیت مشتری',
    'deal_followup': 'پیگیری معامله',
    'property_visit': 'بازدید ملک',
}

_ACTIVITY_ICONS = {
    'تماس': 'phone',
    'پیامک': 'sms',
    'واتساپ': 'whatsapp',
    'پیام': 'messages',
    'بازدید': 'building',
    'پیگیری': 'calendar',
    'جلسه': 'handshake',
    'یادداشت': 'sticky_note',
    'وظیفه': 'list_todo',
    'یادآور': 'bell',
    'تغییر وضعیت': 'rotate_ccw',
    'املاک': 'house',
    'ایمیل': 'email',
}

_EVENT_ICONS = {
    'contact_created': 'user_plus',
    'personal_property_created': 'building',
    'property_created': 'building',
    'dataset_created': 'database',
    'extraction_completed': 'circle_check',
    'deal_created': 'handshake',
    'deal_stage_changed': 'trending_up',
    'contract_created': 'file_edit',
    'follow_up': 'calendar',
    'call': 'phone',
    'call_created': 'phone',
    'visit': 'building',
    'visit_created': 'building',
    'license_assigned': 'key',
    'license_unassigned': 'key',
    'advisor_data_export': 'download',
    'deal_followup': 'clipboard_list',
    'property_visit': 'building',
    'customer_activity': 'history',
    'space_item_published': 'share',
}

_HUB_EVENT_TONES = {
    'space_item_published': 'blue',
    'contact_created': 'teal',
    'personal_property_created': 'orange',
    'dataset_created': 'slate',
    'extraction_completed': 'slate',
    'deal_created': 'green',
    'deal_stage_changed': 'green',
    'follow_up': 'purple',
    'call': 'purple',
    'visit': 'purple',
    'contract_created': 'green',
    'license_assigned': 'indigo',
    'license_unassigned': 'indigo',
    'advisor_data_export': 'slate',
}

_OBJECT_TYPE_LABELS = {
    'customer': 'مخاطب',
    'property': 'فایل',
    'deal': 'معامله',
    'contract': 'قرارداد',
    'dataset': 'فایلینگ',
}


def _humanize_key(value: str) -> str:
    text = (value or '').strip().replace('_', ' ')
    if not text:
        return 'فعالیت'
    return _EVENT_KEY_LABELS.get(value, text)


@register.filter
def a360_activity_label(event):
    if not event:
        return ''
    ev_type = event.get('type', '')
    label = (event.get('label') or '').strip()

    if ev_type == 'agency_event':
        return EVENT_TYPE_LABELS.get(label, _humanize_key(label))
    if ev_type == 'deal_followup':
        mapped = _FOLLOWUP_LABELS.get(label, label)
        return f'پیگیری معامله — {mapped}' if mapped else 'پیگیری معامله'
    if ev_type == 'property_visit':
        return 'بازدید ثبت شد'
    if ev_type == 'customer_activity':
        if label in ACTIVITY_TYPES:
            if label == 'پیگیری':
                return 'پیگیری مشتری'
            if label == 'تماس':
                return 'تماس با مشتری'
            if label == 'بازدید':
                return 'بازدید مشتری'
            return f'{label} با مشتری'
        return _humanize_key(label)
    return _humanize_key(label)


@register.filter
def a360_activity_icon(event):
    """Decor icon key for activity timeline (Lucide via icon_slot)."""
    if not event:
        return 'dot'
    ev_type = event.get('type', '')
    label = (event.get('label') or '').strip()

    if ev_type == 'agency_event':
        return _EVENT_ICONS.get(label, 'zap')
    if ev_type == 'deal_followup':
        return _EVENT_ICONS.get(label, _EVENT_ICONS['deal_followup'])
    if ev_type == 'property_visit':
        return _EVENT_ICONS['property_visit']
    if ev_type == 'customer_activity':
        return _ACTIVITY_ICONS.get(label, 'history')
    return 'dot'


@register.filter
def a360_activity_kind(event):
    """Normalized filter key for client-side activity filtering."""
    if not event:
        return ''
    ev_type = event.get('type', '')
    label = (event.get('label') or '').strip()
    if ev_type == 'agency_event':
        return label or 'agency_event'
    if ev_type == 'deal_followup':
        return 'follow_up'
    if ev_type == 'property_visit':
        return 'visit'
    if ev_type == 'customer_activity':
        if label == 'تماس':
            return 'call'
        if label == 'بازدید':
            return 'visit'
        if label == 'پیگیری':
            return 'follow_up'
        return 'customer_activity'
    return ev_type or 'other'


@register.filter
def a360_deal_stage_status(stage):
    stage = (stage or '').strip()
    if stage in ('بسته‌شده',):
        return 'ok'
    if stage in ('از دست رفته',):
        return 'muted'
    if stage in ('قرارداد', 'پیش‌قرارداد'):
        return 'pending'
    return 'warn'


@register.filter
def a360_contact_status_status(status):
    status = (status or '').strip()
    if status in ('قرارداد',):
        return 'ok'
    if status in ('بایگانی',):
        return 'muted'
    if status in ('در حال پیگیری', 'بازدید انجام شد'):
        return 'pending'
    return 'warn'


@register.filter
def a360_property_status_status(status):
    status = (status or '').strip()
    if status in ('فعال',):
        return 'ok'
    if status in ('بایگانی', 'فروخته‌شده', 'اجاره‌رفته'):
        return 'muted'
    if status in ('در مذاکره', 'قرارداد'):
        return 'pending'
    return 'warn'


@register.filter
def a360_trend_text(delta_pct):
    if delta_pct is None:
        return ''
    try:
        value = float(delta_pct)
    except (TypeError, ValueError):
        return ''
    arrow = '↑' if value > 0 else '↓' if value < 0 else '→'
    abs_val = abs(value)
    if abs_val == int(abs_val):
        pct = str(int(abs_val))
    else:
        pct = f'{abs_val:g}'
    return f'{arrow} {pct}٪ نسبت به دوره قبل'


@register.filter
def a360_trend_tone(delta_pct):
    if delta_pct is None:
        return ''
    try:
        value = float(delta_pct)
    except (TypeError, ValueError):
        return ''
    if value > 0:
        return 'up'
    if value < 0:
        return 'down'
    return 'flat'


@register.simple_tag
def a360_display_name(user):
    full = (user.get_full_name() or '').strip()
    if full:
        return full
    phone = (getattr(user, 'phone', None) or '').strip()
    if phone:
        return phone
    return (getattr(user, 'username', None) or '').strip() or 'مشاور'


@register.simple_tag
def amh_greeting(user):
    """Time-aware Persian greeting for member hub hero."""
    from django.utils import timezone

    hour = timezone.localtime().hour
    if 5 <= hour < 12:
        prefix = 'صبح بخیر'
    elif 12 <= hour < 17:
        prefix = 'ظهر بخیر'
    elif 17 <= hour < 21:
        prefix = 'عصر بخیر'
    else:
        prefix = 'شب بخیر'
    name = a360_display_name(user)
    return f'{prefix}، {name}'


@register.filter
def agency_hub_event_icon(event_type):
    return _EVENT_ICONS.get((event_type or '').strip(), 'zap')


@register.filter
def agency_hub_event_tone(event_type):
    return _HUB_EVENT_TONES.get((event_type or '').strip(), 'purple')


@register.filter
def agency_hub_object_label(object_type):
    key = (object_type or '').strip().lower()
    if not key:
        return ''
    return _OBJECT_TYPE_LABELS.get(key, key)
