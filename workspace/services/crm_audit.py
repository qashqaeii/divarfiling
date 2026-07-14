"""لاگ ممیزی عملیات تیم آژانس."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from workspace.models import CRMAgency, CRMAgencyAuditLog
from workspace.services.jalali_input import format_jalali_date, to_persian_digits

AUDIT_CATEGORIES: Dict[str, Dict[str, str]] = {
    'all': {'label': 'همه رویدادها', 'icon': 'fa-layer-group'},
    'messages': {'label': 'پیام‌ها', 'icon': 'fa-envelope'},
    'announcements': {'label': 'اطلاعیه‌ها', 'icon': 'fa-bullhorn'},
    'leads': {'label': 'سرنخ‌ها', 'icon': 'fa-user-plus'},
    'settings': {'label': 'تنظیمات', 'icon': 'fa-gear'},
    'webhooks': {'label': 'وب‌هوک', 'icon': 'fa-plug'},
    'sync': {'label': 'همگام‌سازی', 'icon': 'fa-arrows-rotate'},
}

_EVENT_META: Dict[str, Dict[str, str]] = {
    'announcement.created': {
        'category': 'announcements',
        'tone': 'create',
        'icon': 'fa-bullhorn',
        'title': 'اطلاعیه جدید منتشر شد',
        'verb': 'انتشار',
    },
    'announcement.updated': {
        'category': 'announcements',
        'tone': 'update',
        'icon': 'fa-pen',
        'title': 'اطلاعیه ویرایش شد',
        'verb': 'ویرایش',
    },
    'announcement.deleted': {
        'category': 'announcements',
        'tone': 'delete',
        'icon': 'fa-trash-can',
        'title': 'اطلاعیه حذف شد',
        'verb': 'حذف',
    },
    'message.sent': {
        'category': 'messages',
        'tone': 'create',
        'icon': 'fa-paper-plane',
        'title': 'پیام ارسال شد',
        'verb': 'ارسال',
    },
    'message.broadcast': {
        'category': 'messages',
        'tone': 'create',
        'icon': 'fa-tower-broadcast',
        'title': 'پیام گروهی ارسال شد',
        'verb': 'پیام گروهی',
    },
    'message.deleted': {
        'category': 'messages',
        'tone': 'delete',
        'icon': 'fa-message-slash',
        'title': 'پیام حذف شد',
        'verb': 'حذف پیام',
    },
    'lead.assigned': {
        'category': 'leads',
        'tone': 'assign',
        'icon': 'fa-user-check',
        'title': 'سرنخ به مشاور تخصیص یافت',
        'verb': 'تخصیص',
    },
    'lead.bulk_assigned': {
        'category': 'leads',
        'tone': 'assign',
        'icon': 'fa-users-gear',
        'title': 'تخصیص گروهی سرنخ‌ها',
        'verb': 'تخصیص گروهی',
    },
    'agency.updated': {
        'category': 'settings',
        'tone': 'update',
        'icon': 'fa-building-circle-check',
        'title': 'تنظیمات آژانس به‌روز شد',
        'verb': 'به‌روزرسانی',
    },
    'api_key.regenerated': {
        'category': 'settings',
        'tone': 'warn',
        'icon': 'fa-key',
        'title': 'کلید API بازتولید شد',
        'verb': 'بازتولید کلید',
    },
    'webhook.created': {
        'category': 'webhooks',
        'tone': 'create',
        'icon': 'fa-plug-circle-plus',
        'title': 'وب‌هوک جدید ثبت شد',
        'verb': 'ثبت وب‌هوک',
    },
    'webhook.deleted': {
        'category': 'webhooks',
        'tone': 'delete',
        'icon': 'fa-plug-circle-xmark',
        'title': 'وب‌هوک حذف شد',
        'verb': 'حذف وب‌هوک',
    },
    'webhook.tested': {
        'category': 'webhooks',
        'tone': 'info',
        'icon': 'fa-vial',
        'title': 'وب‌هوک آزمایش شد',
        'verb': 'آزمایش',
    },
    'sync.import': {
        'category': 'sync',
        'tone': 'sync',
        'icon': 'fa-file-import',
        'title': 'ورود داده از فایل',
        'verb': 'ورود',
    },
    'sync.export': {
        'category': 'sync',
        'tone': 'sync',
        'icon': 'fa-file-export',
        'title': 'خروج داده به فایل',
        'verb': 'خروج',
    },
}

_DEFAULT_META = {
    'category': 'settings',
    'tone': 'info',
    'icon': 'fa-circle-info',
    'title': 'رویداد تیم',
    'verb': 'عملیات',
}

_AUDIT_SKIP_FIELDS = frozenset({
    'updated_at', 'created_at', 'id', 'pk',
})

_AUDIT_AGENCY_FIELD_LABELS = {
    'name': 'نام آژانس',
    'lead_routing_policy': 'سیاست تخصیص سرنخ',
    'api_key': 'کلید API',
    'slug': 'شناسه آژانس',
}


def _audit_field_labels(fields: List[str]) -> List[str]:
    labels: List[str] = []
    for field in fields or []:
        if field in _AUDIT_SKIP_FIELDS:
            continue
        label = _AUDIT_AGENCY_FIELD_LABELS.get(field)
        if label and label not in labels:
            labels.append(label)
    return labels


def _agency_update_summary(actor_name: str, fields: List[str]) -> str:
    labels = _audit_field_labels(fields)
    if len(labels) == 1:
        return f'{actor_name} {labels[0]} را به‌روز کرد.'
    if len(labels) > 1:
        return f'{actor_name} تنظیمات آژانس ({ " و ".join(labels) }) را به‌روز کرد.'
    return f'{actor_name} تنظیمات آژانس را تغییر داد.'


def log_agency_audit(
    agency: CRMAgency,
    actor,
    event: str,
    payload: Optional[Dict[str, Any]] = None,
) -> CRMAgencyAuditLog:
    return CRMAgencyAuditLog.objects.create(
        agency=agency,
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        event=event,
        payload=payload or {},
    )


def get_audit_event_meta(event: str) -> Dict[str, str]:
    return {**_DEFAULT_META, **_EVENT_META.get(event, {})}


def _actor_name(log: CRMAgencyAuditLog) -> str:
    if not log.actor_id:
        return 'سیستم'
    return (
        log.actor.get_full_name().strip()
        or log.actor.username
        or 'کاربر'
    )


def _time_label(dt) -> str:
    local = timezone.localtime(dt)
    return to_persian_digits(local.strftime('%H:%M'))


def _date_group_label(dt) -> str:
    local = timezone.localtime(dt)
    today = timezone.localdate()
    if local.date() == today:
        return 'امروز'
    if local.date() == today - timedelta(days=1):
        return 'دیروز'
    return format_jalali_date(dt) or '—'


def _payload_chips(event: str, payload: Dict[str, Any]) -> List[Dict[str, str]]:
    chips: List[Dict[str, str]] = []
    p = payload or {}

    if event.startswith('announcement.'):
        if p.get('announcement_id'):
            chips.append({'label': 'شناسه', 'value': str(p['announcement_id'])})

    elif event.startswith('message.'):
        kind = p.get('kind')
        if kind == 'direct':
            chips.append({'label': 'نوع', 'value': 'مستقیم'})
        elif kind == 'broadcast':
            chips.append({'label': 'نوع', 'value': 'گروهی'})
        if p.get('thread_id'):
            chips.append({'label': 'گفتگو', 'value': str(p['thread_id'])})
        if p.get('recipient_count'):
            chips.append({'label': 'گیرنده', 'value': to_persian_digits(str(p['recipient_count']))})

    elif event == 'lead.assigned':
        if p.get('customer_id'):
            chips.append({'label': 'مخاطب', 'value': str(p['customer_id'])})
        if p.get('member_id'):
            chips.append({'label': 'مشاور', 'value': str(p['member_id'])})

    elif event == 'lead.bulk_assigned':
        if p.get('count'):
            chips.append({'label': 'تعداد', 'value': to_persian_digits(str(p['count']))})
        if p.get('member_id'):
            chips.append({'label': 'مشاور', 'value': str(p['member_id'])})

    elif event == 'agency.updated':
        labels = _audit_field_labels(p.get('fields') or [])
        if labels:
            chips.append({'label': 'موارد', 'value': ' و '.join(labels)})

    elif event.startswith('webhook.'):
        if p.get('webhook_id'):
            chips.append({'label': 'وب‌هوک', 'value': str(p['webhook_id'])})
        if 'ok' in p:
            chips.append({
                'label': 'نتیجه',
                'value': 'موفق' if p['ok'] else 'ناموفق',
            })

    elif event.startswith('sync.'):
        for key, label in (
            ('contacts', 'مخاطب'),
            ('properties', 'ملک'),
            ('deals', 'معامله'),
            ('skipped', 'ردشده'),
            ('conflicts', 'تعارض'),
        ):
            if p.get(key):
                chips.append({'label': label, 'value': to_persian_digits(str(p[key]))})

    return chips


def _summary(event: str, payload: Dict[str, Any], actor_name: str) -> str:
    meta = get_audit_event_meta(event)
    p = payload or {}

    if event == 'message.broadcast':
        roles = p.get('target_roles') or []
        if roles:
            return f'{actor_name} پیام گروهی برای نقش‌های انتخاب‌شده ارسال کرد.'
        return f'{actor_name} پیام گروهی برای تیم ارسال کرد.'

    if event == 'lead.bulk_assigned':
        count = p.get('count', 0)
        return f'{actor_name} {to_persian_digits(str(count))} سرنخ را به‌صورت گروهی تخصیص داد.'

    if event == 'agency.updated':
        return _agency_update_summary(actor_name, p.get('fields') or [])

    if event == 'api_key.regenerated':
        return f'{actor_name} کلید API آژانس را بازتولید کرد — اتصال‌های قبلی باطل می‌شوند.'

    if event == 'webhook.tested':
        ok = p.get('ok')
        if ok is True:
            return f'{actor_name} ارسال آزمایشی وب‌هوک را با موفقیت انجام داد.'
        if ok is False:
            return f'{actor_name} ارسال آزمایشی وب‌هوک ناموفق بود.'
        return f'{actor_name} وب‌هوک را آزمایش کرد.'

    if event.startswith('sync.'):
        parts = []
        for key, label in (('contacts', 'مخاطب'), ('properties', 'ملک'), ('deals', 'معامله')):
            if p.get(key):
                parts.append(f'{to_persian_digits(str(p[key]))} {label}')
        if parts:
            return f'{actor_name} عملیات {meta["verb"]}: ' + '، '.join(parts)
        return f'{actor_name} عملیات {meta["verb"]} انجام داد.'

    return f'{actor_name} عملیات {meta["verb"]} را انجام داد.'


def describe_audit_log(log: CRMAgencyAuditLog) -> Dict[str, Any]:
    meta = get_audit_event_meta(log.event)
    actor_name = _actor_name(log)
    payload = log.payload or {}
    summary = _summary(log.event, payload, actor_name)
    chips = _payload_chips(log.event, payload)
    category = meta['category']
    return {
        'id': log.pk,
        'event': log.event,
        'category': category,
        'category_label': AUDIT_CATEGORIES.get(category, {}).get('label', category),
        'tone': meta['tone'],
        'icon': meta['icon'],
        'title': meta['title'],
        'summary': summary,
        'actor_name': actor_name,
        'actor_is_system': not log.actor_id,
        'time_label': _time_label(log.created_at),
        'datetime_label': format_jalali_date(log.created_at),
        'payload_chips': chips,
        'search_text': ' '.join(filter(None, [
            log.event,
            meta['title'],
            summary,
            actor_name,
            meta.get('verb', ''),
            ' '.join(c['value'] for c in chips),
        ])).lower(),
    }


def _build_stats(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    today = timezone.localdate()
    today_count = 0
    by_category: Dict[str, int] = {k: 0 for k in AUDIT_CATEGORIES if k != 'all'}
    tones: Dict[str, int] = {}

    for entry in entries:
        created = entry.get('_created_at')
        if created and timezone.localtime(created).date() == today:
            today_count += 1
        cat = entry.get('category')
        if cat in by_category:
            by_category[cat] += 1
        tone = entry.get('tone', 'info')
        tones[tone] = tones.get(tone, 0) + 1

    return {
        'total': len(entries),
        'today': today_count,
        'by_category': by_category,
        'tones': tones,
    }


def build_audit_timeline(logs: List[CRMAgencyAuditLog]) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []
    current_label: Optional[str] = None

    for log in logs:
        described = describe_audit_log(log)
        described['_created_at'] = log.created_at
        entries.append(described)

        group_label = _date_group_label(log.created_at)
        if group_label != current_label:
            current_label = group_label
            groups.append({'label': group_label, 'entries': []})
        groups[-1]['entries'].append(described)

    return {
        'groups': groups,
        'stats': _build_stats(entries),
        'categories': AUDIT_CATEGORIES,
    }


def audit_event_label(event: str) -> str:
    return get_audit_event_meta(event).get('title', event)
