"""کاتالوگ مرکزی اعلان‌های موبایل — نوع، کانال، مقصد، اولویت."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Tuple


CHANNEL_REMINDERS = 'df_reminders'
CHANNEL_MATCHES = 'df_matches'
CHANNEL_EXTRACT = 'df_extract'
CHANNEL_ACCOUNT = 'df_account'
CHANNEL_DIGEST = 'df_digest'
CHANNEL_ANNOUNCEMENTS = 'df_announcements'
CHANNEL_SUPPORT = 'df_support'

PRIORITY_HIGH = 'high'
PRIORITY_DEFAULT = 'default'

GROUP_REMINDERS = 'reminders'
GROUP_MATCHES = 'customer_match'
GROUP_EXTRACT = 'extract'
GROUP_LICENSE = 'license'
GROUP_DIGEST = 'digest'
GROUP_ANNOUNCEMENTS = 'announcements'
GROUP_SUPPORT = 'support'


@dataclass(frozen=True)
class NotificationSpec:
    type: str
    title_fa: str
    pref_key: Optional[str]
    channel: str
    priority: str
    default_deep_link: str
    group: str
    heads_up_in_foreground: bool
    display_fcm_notification: bool
    replaceable: bool


SPECS: Dict[str, NotificationSpec] = {
    'reminder_call': NotificationSpec(
        'reminder_call', 'یادآور تماس', 'crm_reminders',
        CHANNEL_REMINDERS, PRIORITY_HIGH, 'divarfiling://calendar',
        GROUP_REMINDERS, True, False, False,
    ),
    'reminder_visit': NotificationSpec(
        'reminder_visit', 'یادآور بازدید', 'crm_reminders',
        CHANNEL_REMINDERS, PRIORITY_HIGH, 'divarfiling://calendar',
        GROUP_REMINDERS, True, False, False,
    ),
    'today_digest': NotificationSpec(
        'today_digest', 'برنامه امروز', 'today_digest',
        CHANNEL_DIGEST, PRIORITY_DEFAULT, 'divarfiling://crm/today',
        GROUP_DIGEST, False, False, True,
    ),
    'overdue_followup': NotificationSpec(
        'overdue_followup', 'پیگیری معوق', 'overdue_followup',
        CHANNEL_REMINDERS, PRIORITY_HIGH, 'divarfiling://crm/today',
        GROUP_DIGEST, False, False, True,
    ),
    'extract_complete': NotificationSpec(
        'extract_complete', 'پایان استخراج', 'extract_complete',
        CHANNEL_EXTRACT, PRIORITY_DEFAULT, 'divarfiling://extract',
        GROUP_EXTRACT, False, False, False,
    ),
    'extract_schedule_due': NotificationSpec(
        'extract_schedule_due', 'زمان استخراج', 'extract_schedule_due',
        CHANNEL_EXTRACT, PRIORITY_DEFAULT, 'divarfiling://extract/schedules',
        GROUP_EXTRACT, False, False, True,
    ),
    'extract_schedule_created': NotificationSpec(
        'extract_schedule_created', 'زمان‌بندی استخراج', 'extract_schedule_due',
        CHANNEL_EXTRACT, PRIORITY_DEFAULT, 'divarfiling://extract/schedules',
        GROUP_EXTRACT, False, False, False,
    ),
    'customer_match': NotificationSpec(
        'customer_match', 'فایل مناسب مشتری', 'customer_match',
        CHANNEL_MATCHES, PRIORITY_HIGH, 'divarfiling://crm',
        GROUP_MATCHES, False, False, False,
    ),
    'license_expiry': NotificationSpec(
        'license_expiry', 'لایسنس', 'license_alerts',
        CHANNEL_ACCOUNT, PRIORITY_HIGH, 'divarfiling://plans',
        GROUP_LICENSE, True, False, True,
    ),
    'support_reply': NotificationSpec(
        'support_reply', 'پاسخ پشتیبانی', 'announcements',
        CHANNEL_SUPPORT, PRIORITY_HIGH, 'divarfiling://support',
        GROUP_SUPPORT, True, False, False,
    ),
    'welcome': NotificationSpec(
        'welcome', 'خوش‌آمد', None,
        CHANNEL_ANNOUNCEMENTS, PRIORITY_DEFAULT, 'divarfiling://home',
        GROUP_ANNOUNCEMENTS, False, True, True,
    ),
    'announcement': NotificationSpec(
        'announcement', 'اطلاعیه', 'announcements',
        CHANNEL_ANNOUNCEMENTS, PRIORITY_DEFAULT, 'divarfiling://notifications',
        GROUP_ANNOUNCEMENTS, False, True, False,
    ),
    'app_update': NotificationSpec(
        'app_update', 'بروزرسانی اپ', 'announcements',
        CHANNEL_ANNOUNCEMENTS, PRIORITY_DEFAULT, 'divarfiling://notifications',
        GROUP_ANNOUNCEMENTS, False, True, True,
    ),
    'product_update': NotificationSpec(
        'product_update', 'قابلیت جدید', 'announcements',
        CHANNEL_ANNOUNCEMENTS, PRIORITY_DEFAULT, 'divarfiling://notifications',
        GROUP_ANNOUNCEMENTS, False, True, False,
    ),
    'filing_retention_warning': NotificationSpec(
        'filing_retention_warning', 'هشدار پاک‌سازی فایلینگ', 'announcements',
        CHANNEL_ANNOUNCEMENTS, PRIORITY_DEFAULT, 'divarfiling://filing?retention_warning=1',
        GROUP_ANNOUNCEMENTS, True, False, True,
    ),
}

BROADCAST_TYPES: Tuple[str, ...] = (
    'announcement',
    'app_update',
    'product_update',
)

BROADCAST_DEEP_LINKS: Tuple[Tuple[str, str], ...] = (
    ('divarfiling://notifications', 'مرکز اعلان‌ها'),
    ('divarfiling://home', 'میزکار'),
    ('divarfiling://crm/today', 'کارهای امروز'),
    ('divarfiling://plans', 'پلن و لایسنس'),
    ('divarfiling://extract', 'استخراج'),
    ('divarfiling://support', 'پشتیبانی'),
    ('divarfiling://more', 'منوی بیشتر'),
)

ALLOWED_DEEP_LINK_PREFIXES: FrozenSet[str] = frozenset({
    'divarfiling://home',
    'divarfiling://crm',
    'divarfiling://calendar',
    'divarfiling://extract',
    'divarfiling://filing',
    'divarfiling://settings',
    'divarfiling://plans',
    'divarfiling://license',
    'divarfiling://support',
    'divarfiling://more',
    'divarfiling://notifications',
    'divarfiling://ai',
    'divarfiling://tools',
    'divarfiling://payment',
})

TYPE_TO_PREF = {spec.type: spec.pref_key for spec in SPECS.values() if spec.pref_key}

ACTIONABLE_TYPES = frozenset({
    'reminder_call',
    'reminder_visit',
    'overdue_followup',
    'license_expiry',
    'support_reply',
    'customer_match',
})


def get_spec(notification_type: str) -> NotificationSpec:
    return SPECS.get(notification_type) or NotificationSpec(
        notification_type,
        'اعلان',
        None,
        CHANNEL_ANNOUNCEMENTS,
        PRIORITY_DEFAULT,
        'divarfiling://notifications',
        GROUP_ANNOUNCEMENTS,
        False,
        True,
        False,
    )


def sanitize_deep_link(deep_link: str, notification_type: str = '') -> str:
    link = (deep_link or '').strip()
    if link.startswith('divarfiling://'):
        for prefix in ALLOWED_DEEP_LINK_PREFIXES:
            if link == prefix or link.startswith(prefix + '/') or link.startswith(prefix + '?'):
                return link[:300]
    return get_spec(notification_type).default_deep_link


def dedup_key_for(notification_type: str, data: Optional[dict] = None) -> str:
    payload = data or {}
    if notification_type in ('reminder_call', 'reminder_visit') and payload.get('reminder_id'):
        return f'reminder:{payload["reminder_id"]}'
    if notification_type == 'today_digest':
        return f'today_digest:{payload.get("day") or ""}'
    if notification_type == 'overdue_followup':
        return f'overdue_followup:{payload.get("day") or ""}'
    if notification_type == 'license_expiry':
        return f'license:{payload.get("license_id")}:{payload.get("threshold")}'
    if notification_type == 'extract_schedule_due' and payload.get('schedule_id'):
        return f'extract_due:{payload["schedule_id"]}:{payload.get("day") or ""}'
    if notification_type == 'customer_match' and payload.get('digest'):
        return f'match_digest:{payload.get("day") or ""}:{payload.get("top_contact_id") or ""}'
    if notification_type == 'customer_match' and payload.get('contact_id'):
        return f'match:{payload["contact_id"]}:{payload.get("day") or ""}'
    if notification_type == 'welcome':
        return 'welcome'
    if notification_type in ('announcement', 'app_update', 'product_update') and payload.get('broadcast_id'):
        return f'broadcast:{payload["broadcast_id"]}'
    if notification_type == 'filing_retention_warning' and payload.get('cycle_key'):
        return f'retention_warning:{payload["cycle_key"]}'
    return ''
