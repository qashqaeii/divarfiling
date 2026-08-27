"""دستیار مدیریت — Rule Engine برای تبدیل داده به پیشنهاد و اقدام."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, Max, OuterRef, Q, Sum
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    ManagementAutomationExecution,
    ManagementAutomationRule,
)
from accounts.services.admin_dashboard import _date_range, _pct_change, _today
from accounts.services.admin_marketing import (
    SEGMENT_DEFAULT_TEMPLATES,
    build_segment_recipients,
    preview_segment,
    render_message,
)
from accounts.services.admin_marketing_send import (
    MarketingSendError,
    create_campaign_draft,
    run_campaign_send,
)
from accounts.services.admin_windows_app import WINDOWS_ACTIVATION_Q
from accounts.services.pending_orders import PENDING_ORDER_STATUSES, pending_orders_queryset
from accounts.services.sms import get_sms_balance_snapshot
from licenses.models import ClientAppEvent, License, LicenseActivation
from shop.models import DownloadLog, Order
from workspace.models import Customer, Ticket

User = get_user_model()

SEVERITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'opportunity': 3}
SEVERITY_LABELS = {
    'critical': 'نیازمند اقدام فوری',
    'high': 'پیشنهاد مهم',
    'medium': 'پیشنهاد',
    'opportunity': 'فرصت رشد',
}

INSIGHT_MESSAGE_TEMPLATES: Dict[str, str] = {
    'expired_not_renewed': (
        'سلام{name_part}، اشتراک فایلینگ دیوار شما به پایان رسیده. '
        'برای ادامه کار می‌تونید همین الان تمدید کنید: {link}'
    ),
    'license_expiring_3d': (
        'سلام 👋\n'
        'اشتراک فایلینگ دیوار شما به‌زودی به پایان می‌رسه.\n'
        'برای اینکه دسترسی‌تون قطع نشه، می‌تونید همین الان تمدیدش کنید: {link}'
    ),
    'pending_orders': SEGMENT_DEFAULT_TEMPLATES.get('pending_orders', ''),
    'failed_payments_today': (
        'سلام{name_part}، پرداخت سفارش «{product}» ناموفق بود. '
        'اگر به کمک نیاز دارید یا می‌خواهید دوباره تلاش کنید: {link}'
    ),
    'users_without_license_7d': SEGMENT_DEFAULT_TEMPLATES.get('users_without_license', ''),
    'windows_download_no_activate': (
        'سلام{name_part}، نسخه ویندوز فایلینگ دیوار را دانلود کردید. '
        'برای فعال‌سازی و شروع کار این راهنما را ببینید: {link}'
    ),
    'windows_activate_no_launch': (
        'سلام{name_part}، برنامه ویندوز فعال شده ولی هنوز اجرا نشده. '
        'برای شروع سریع این راهنما را ببینید: {link}'
    ),
    'high_renewal_chance': (
        'سلام{name_part}، خوشحالیم دوباره سر زدید! '
        'لایسنس قبلی‌تان تمام شده — برای تمدید سریع: {link}'
    ),
    'crm_not_started': (
        'سلام{name_part}، با CRM فایلینگ دیوار مشتریان خود را منظم ثبت کنید. '
        'شروع سریع: {link}'
    ),
}

AUTOMATION_RULE_CATALOG: List[Dict[str, Any]] = [
    {
        'key': 'license_expiring_3d',
        'name': 'یادآوری تمدید ۳ روز قبل',
        'insight_key': 'license_expiring_3d',
        'flow_key': 'license_renewal',
        'cadence': 'daily',
        'action_type': 'send_sms',
        'condition_label': '۳ روز مانده به پایان لایسنس',
        'audience_label': 'کاربران دارای لایسنس فعال',
        'action_label': 'ارسال SMS',
        'template_label': 'یادآوری تمدید',
        'cooldown_label': 'برای هر trigger فقط یک بار',
        'default_active': False,
        'max_recipients_per_run': 50,
        'cooldown_days': 7,
    },
    {
        'key': 'pending_recovery',
        'name': 'بازیابی خرید نیمه‌کاره',
        'insight_key': 'pending_orders',
        'flow_key': 'pending_recovery',
        'segment_key': 'pending_orders',
        'cadence': 'hourly',
        'action_type': 'send_sms',
        'condition_label': 'سفارش پرداخت‌نشده بیش از ۲ ساعت',
        'audience_label': 'کاربران با سفارش معلق',
        'action_label': 'ارسال SMS',
        'template_label': 'یادآوری خرید',
        'cooldown_label': 'حداکثر یک پیام در ۷ روز',
        'default_active': False,
        'max_recipients_per_run': 30,
        'cooldown_days': 7,
    },
    {
        'key': 'failed_payment_followup',
        'name': 'پیام بعد از پرداخت ناموفق',
        'insight_key': 'failed_payments_today',
        'flow_key': 'mgmt_failed_payment',
        'segment_key': 'failed_orders',
        'cadence': 'hourly',
        'action_type': 'send_sms',
        'condition_label': 'پرداخت ناموفق در ۲۴ ساعت اخیر',
        'audience_label': 'کاربران با پرداخت ناموفق',
        'action_label': 'ارسال SMS',
        'template_label': 'راهنمای پرداخت',
        'cooldown_label': 'یک بار برای هر سفارش',
        'default_active': False,
        'max_recipients_per_run': 30,
        'cooldown_days': 7,
    },
    {
        'key': 'users_onboarding',
        'name': 'خوش‌آمدگویی کاربر جدید',
        'insight_key': 'users_without_license_7d',
        'flow_key': 'mgmt_users_onboarding',
        'segment_key': 'users_without_license',
        'cadence': 'daily',
        'action_type': 'send_sms',
        'condition_label': 'ثبت‌نام بدون لایسنس — ۲۴ ساعت بعد',
        'audience_label': 'کاربران تازه‌ثبت‌نام',
        'action_label': 'ارسال SMS',
        'template_label': 'معرفی نسخه کامل',
        'cooldown_label': 'یک بار برای هر کاربر',
        'default_active': False,
        'max_recipients_per_run': 50,
        'cooldown_days': 14,
    },
    {
        'key': 'windows_activation_nudge',
        'name': 'راهنمای فعال‌سازی ویندوز',
        'insight_key': 'windows_download_no_activate',
        'flow_key': 'mgmt_windows_activation',
        'cadence': 'daily',
        'action_type': 'send_sms',
        'condition_label': 'دانلود بدون فعال‌سازی',
        'audience_label': 'کاربران دانلودکننده ویندوز',
        'action_label': 'ارسال SMS',
        'template_label': 'راهنمای فعال‌سازی',
        'cooldown_label': 'یک بار برای هر کاربر',
        'default_active': False,
        'max_recipients_per_run': 30,
        'cooldown_days': 14,
    },
    {
        'key': 'windows_activate_no_launch',
        'name': 'راهنمای اولین اجرای ویندوز',
        'insight_key': 'windows_activate_no_launch',
        'flow_key': 'mgmt_windows_launch',
        'cadence': 'daily',
        'action_type': 'send_sms',
        'condition_label': 'فعال‌سازی بدون اولین اجرا',
        'audience_label': 'کاربران فعال‌سازی‌شده',
        'action_label': 'ارسال SMS',
        'template_label': 'راهنمای شروع',
        'cooldown_label': 'یک بار برای هر کاربر',
        'default_active': False,
        'max_recipients_per_run': 30,
        'cooldown_days': 14,
    },
    {
        'key': 'expired_renewal_campaign',
        'name': 'کمپین بازگشت لایسنس منقضی',
        'insight_key': 'expired_not_renewed',
        'flow_key': 'license_renewal',
        'cadence': 'daily',
        'action_type': 'send_sms',
        'condition_label': 'منقضی تا ۱۴ روز — بدون تمدید',
        'audience_label': 'مشتریان قبلی',
        'action_label': 'ارسال SMS',
        'template_label': 'یادآوری تمدید',
        'cooldown_label': 'حداکثر یک پیام در ۷ روز',
        'default_active': False,
        'max_recipients_per_run': 50,
        'cooldown_days': 7,
    },
    {
        'key': 'crm_not_started_nudge',
        'name': 'آموزش شروع CRM',
        'insight_key': 'crm_not_started',
        'flow_key': 'mgmt_crm',
        'cadence': 'daily',
        'action_type': 'send_sms',
        'condition_label': 'لایسنس فعال بدون مشتری CRM',
        'audience_label': 'کاربران فعال',
        'action_label': 'ارسال SMS',
        'template_label': 'آموزش CRM',
        'cooldown_label': 'یک بار برای هر کاربر',
        'default_active': False,
        'max_recipients_per_run': 30,
        'cooldown_days': 30,
    },
    {
        'key': 'sms_balance_low',
        'name': 'هشدار موجودی SMS',
        'insight_key': 'sms_balance_low',
        'flow_key': 'mgmt_sms_alert',
        'cadence': 'hourly',
        'action_type': 'management_alert',
        'condition_label': 'موجودی زیر آستانه',
        'audience_label': 'مدیر سیستم',
        'action_label': 'هشدار مدیریت',
        'template_label': '—',
        'cooldown_label': 'یک هشدار در ساعت',
        'default_active': False,
        'max_recipients_per_run': 1,
        'cooldown_days': 0,
    },
    {
        'key': 'stale_tickets_alert',
        'name': 'هشدار تیکت بدون پاسخ',
        'insight_key': 'stale_tickets',
        'flow_key': 'mgmt_support_alert',
        'cadence': 'hourly',
        'action_type': 'manual_review',
        'condition_label': 'تیکت بیش از ۱۲ ساعت بدون پاسخ',
        'audience_label': 'تیم پشتیبانی',
        'action_label': 'بررسی دستی',
        'template_label': '—',
        'cooldown_label': 'یک هشدار در ساعت',
        'default_active': False,
        'max_recipients_per_run': 1,
        'cooldown_days': 0,
    },
]

MANAGEMENT_FLOW_KEYS = tuple(
    sorted({row['flow_key'] for row in AUTOMATION_RULE_CATALOG} | {'license_renewal', 'pending_recovery'})
)


@dataclass
class InsightAction:
    key: str
    label: str
    style: str = 'ghost'
    modal: str = ''


@dataclass
class ManagementInsight:
    key: str
    title: str
    what_happened: str
    importance: str
    context: str
    recommendation: str
    severity: str
    category: str
    count: int
    icon: str
    accent: str
    segment_key: Optional[str] = None
    segment_params: Dict[str, Any] = field(default_factory=dict)
    automation_key: Optional[str] = None
    flow_key: Optional[str] = None
    view_url: str = ''
    message_template: str = ''
    automation_available: bool = True
    actions: List[InsightAction] = field(default_factory=list)


def _site_link() -> str:
    from django.conf import settings
    return (getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir').rstrip('/') + '/'


def _count_expired_not_renewed() -> tuple[int, int]:
    """تعداد منقضی‌شده بدون تمدید + تعداد با سابقه خرید."""
    now = timezone.now()
    cutoff = now - timedelta(days=14)
    active_q = License.objects.filter(
        order__user=OuterRef('pk'),
        order__status='paid',
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    paid_before_q = Order.objects.filter(
        user=OuterRef('pk'),
        status='paid',
    )
    users = (
        User.objects.filter(is_active=True)
        .annotate(
            has_active=Exists(active_q),
            had_paid=Exists(paid_before_q),
            last_expired=Max(
                'orders__licenses__expires_at',
                filter=Q(
                    orders__licenses__status='expired',
                    orders__licenses__expires_at__gte=cutoff,
                    orders__licenses__expires_at__lte=now,
                ),
            ),
        )
        .filter(has_active=False, last_expired__isnull=False)
    )
    total = users.count()
    paid_count = users.filter(had_paid=True).count()
    return total, paid_count


def _count_license_expiring(days: int = 3) -> int:
    now = timezone.now()
    horizon = now + timedelta(days=days)
    return License.objects.filter(
        status='active',
        expires_at__isnull=False,
        expires_at__gt=now,
        expires_at__lte=horizon,
    ).count()


def _count_pending_orders() -> int:
    return pending_orders_queryset(dedupe_by_user=True).count()


def _count_failed_today() -> int:
    today = _today()
    return Order.objects.filter(status='failed', created_at__date=today).count()


def _count_users_without_license_recent(days: int = 7) -> int:
    since = timezone.now() - timedelta(days=days)
    now = timezone.now()
    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    return (
        User.objects.filter(is_active=True, date_joined__gte=since)
        .annotate(has_active=Exists(active_license_q))
        .filter(has_active=False)
        .count()
    )


def _count_windows_download_no_activate() -> int:
    activated_users = LicenseActivation.objects.filter(WINDOWS_ACTIVATION_Q).values('license__order__user_id')
    return (
        DownloadLog.objects.values('user_id')
        .distinct()
        .exclude(user_id__in=activated_users)
        .count()
    )


def _count_windows_activate_no_launch() -> int:
    launched_users = ClientAppEvent.objects.filter(
        event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
    ).values('user_id')
    return (
        LicenseActivation.objects.filter(WINDOWS_ACTIVATION_Q)
        .exclude(license__order__user_id__in=launched_users)
        .values('license__order__user_id')
        .distinct()
        .count()
    )


def _count_stale_tickets(hours: int = 12) -> int:
    cutoff = timezone.now() - timedelta(hours=hours)
    return (
        Ticket.objects.exclude(status='closed')
        .filter(staff_has_unread=True)
        .filter(Q(last_message_at__lte=cutoff) | Q(last_message_at__isnull=True, created_at__lte=cutoff))
        .count()
    )


def _count_high_renewal_chance() -> int:
    now = timezone.now()
    recent = now - timedelta(days=7)
    expired_cutoff = now - timedelta(days=30)
    active_q = License.objects.filter(
        order__user=OuterRef('pk'),
        order__status='paid',
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    renewed_q = Order.objects.filter(
        user=OuterRef('pk'),
        status='paid',
        paid_at__gte=recent,
    )
    return (
        User.objects.filter(is_active=True, last_login__gte=recent)
        .annotate(
            has_active=Exists(active_q),
            renewed_recently=Exists(renewed_q),
            had_license=Exists(
                Order.objects.filter(user=OuterRef('pk'), status='paid', licenses__isnull=False)
            ),
        )
        .filter(has_active=False, renewed_recently=False, had_license=True)
        .exclude(last_login__isnull=True)
        .count()
    )


def _count_crm_not_started() -> tuple[int, int]:
    now = timezone.now()
    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    has_crm_q = Customer.objects.filter(user=OuterRef('pk'))
    licensed = User.objects.filter(is_active=True).annotate(
        has_active=Exists(active_license_q),
    ).filter(has_active=True)
    total = licensed.count()
    if not total:
        return 0, 0
    without_crm = licensed.annotate(has_crm=Exists(has_crm_q)).filter(has_crm=False).count()
    return without_crm, total


def _revenue_drop_pct() -> tuple[int, int, float | None]:
    today = _today()
    cur_start = today - timedelta(days=6)
    prev_start = today - timedelta(days=13)
    prev_end = today - timedelta(days=7)
    cur = int(
        Order.objects.filter(status='paid', paid_at__date__gte=cur_start, paid_at__date__lte=today)
        .aggregate(t=Sum('amount'))['t'] or 0
    )
    prev = int(
        Order.objects.filter(status='paid', paid_at__date__gte=prev_start, paid_at__date__lte=prev_end)
        .aggregate(t=Sum('amount'))['t'] or 0
    )
    return cur, prev, _pct_change(cur, prev)


def _default_actions(insight: ManagementInsight) -> List[InsightAction]:
    actions = []
    if insight.view_url:
        actions.append(InsightAction(key='view', label='مشاهده', style='ghost'))
    if insight.segment_key or insight.message_template:
        actions.append(InsightAction(key='send', label='ارسال پیام', style='primary', modal='send'))
    if insight.automation_available and insight.automation_key:
        actions.append(InsightAction(key='automate', label='خودکارسازی', style='ghost', modal='automate'))
    return actions


def _build_insight(**kwargs) -> ManagementInsight:
    insight = ManagementInsight(**kwargs)
    if not insight.message_template:
        insight.message_template = INSIGHT_MESSAGE_TEMPLATES.get(insight.key, '')
    if not insight.actions:
        insight.actions = _default_actions(insight)
    return insight


def build_management_insights() -> List[ManagementInsight]:
    """Rule Engine — تولید پیشنهادهای مدیریتی."""
    insights: List[ManagementInsight] = []

    expired_count, paid_expired = _count_expired_not_renewed()
    if expired_count:
        ctx = f'{paid_expired} نفر از آن‌ها قبلاً حداقل یک بار خرید موفق داشته‌اند.' if paid_expired else ''
        insights.append(_build_insight(
            key='expired_not_renewed',
            title=f'{expired_count} مشتری احتمالاً در حال از دست رفتن هستند',
            what_happened=f'لایسنس {expired_count} نفر تمام شده اما هنوز تمدید نکرده‌اند.',
            importance='احتمال از دست رفتن تمدید و درآمد',
            context=ctx,
            recommendation='یک پیام کوتاه یادآوری تمدید برایشان ارسال کن.',
            severity='critical',
            category='license',
            count=expired_count,
            icon='fa-id-card',
            accent='rose',
            automation_key='expired_renewal_campaign',
            flow_key='license_renewal',
            view_url=reverse('admin_panel_licenses') + '?days=30',
        ))

    pending = _count_pending_orders()
    if pending:
        insights.append(_build_insight(
            key='pending_orders',
            title=f'{pending} سفارش نیمه‌کاره مانده',
            what_happened='این کاربران وارد مسیر خرید شده‌اند ولی پرداخت را کامل نکرده‌اند.',
            importance='از دست رفتن فروش نزدیک به تکمیل',
            context='',
            recommendation='یک پیام بازیابی خرید برایشان بفرست.',
            severity='high',
            category='sales',
            count=pending,
            icon='fa-cart-shopping',
            accent='amber',
            segment_key='pending_orders',
            automation_key='pending_recovery',
            flow_key='pending_recovery',
            view_url=reverse('admin_panel_recovery_center') + '?days=7',
        ))

    expiring_3d = _count_license_expiring(days=3)
    if expiring_3d:
        insights.append(_build_insight(
            key='license_expiring_3d',
            title=f'{expiring_3d} لایسنس تا ۳ روز آینده تمام می‌شود',
            what_happened=f'{expiring_3d} لایسنس فعال تا ۳ روز دیگر منقضی می‌شوند.',
            importance='قطع سرویس و ریزش اگر یادآوری نشود',
            context='',
            recommendation='امروز یادآوری تمدید ارسال کن.',
            severity='high',
            category='license',
            count=expiring_3d,
            icon='fa-hourglass-half',
            accent='amber',
            automation_key='license_expiring_3d',
            flow_key='license_renewal',
            view_url=reverse('admin_panel_licenses') + '?days=30',
        ))

    without_7d = _count_users_without_license_recent(days=7)
    if without_7d:
        insights.append(_build_insight(
            key='users_without_license_7d',
            title=f'{without_7d} کاربر ثبت‌نام کرده‌اند ولی هنوز لایسنس نگرفته‌اند',
            what_happened=f'{without_7d} نفر در ۷ روز اخیر ثبت‌نام کرده‌اند بدون خرید.',
            importance='فرصت تبدیل کاربر جدید به مشتری',
            context='',
            recommendation='پیام معرفی مزیت‌های نسخه کامل برایشان ارسال کن.',
            severity='medium',
            category='users',
            count=without_7d,
            icon='fa-user-plus',
            accent='indigo',
            segment_key='users_without_license',
            automation_key='users_onboarding',
            flow_key='mgmt_users_onboarding',
            view_url=reverse('admin_panel_users') + '?days=7',
        ))

    failed_today = _count_failed_today()
    if failed_today:
        insights.append(_build_insight(
            key='failed_payments_today',
            title=f'{failed_today} پرداخت ناموفق امروز',
            what_happened='کاربر قصد خرید داشته ولی پرداخت موفق نشده است.',
            importance='از دست رفتن فروش در لحظه تصمیم',
            context='',
            recommendation='یک پیام کمک برای تکمیل پرداخت ارسال کن.',
            severity='critical',
            category='sales',
            count=failed_today,
            icon='fa-circle-xmark',
            accent='rose',
            segment_key='failed_orders',
            segment_params={'days_lookback': 1},
            automation_key='failed_payment_followup',
            flow_key='mgmt_failed_payment',
            view_url=reverse('admin_panel_sales') + '?days=1',
        ))

    win_dl = _count_windows_download_no_activate()
    if win_dl:
        insights.append(_build_insight(
            key='windows_download_no_activate',
            title=f'{win_dl} کاربر ویندوز را دانلود کرده ولی فعال نکرده',
            what_happened=f'{win_dl} نفر نسخه ویندوز را دانلود کرده‌اند اما فعال‌سازی نکرده‌اند.',
            importance='کاربر به محصول نزدیک است ولی هنوز استفاده نکرده',
            context='',
            recommendation='ارسال راهنمای فعال‌سازی',
            severity='medium',
            category='windows',
            count=win_dl,
            icon='fa-download',
            accent='cyan',
            automation_key='windows_activation_nudge',
            flow_key='mgmt_windows_activation',
            view_url=reverse('admin_panel_windows') + '?days=30',
        ))

    win_launch = _count_windows_activate_no_launch()
    if win_launch:
        insights.append(_build_insight(
            key='windows_activate_no_launch',
            title=f'{win_launch} کاربر فعال کرده ولی هنوز اجرا نکرده',
            what_happened='برنامه فعال شده اما اولین استفاده ثبت نشده.',
            importance='ریسک عدم Adoption محصول',
            context='',
            recommendation='ارسال آموزش شروع سریع',
            severity='medium',
            category='windows',
            count=win_launch,
            icon='fa-play',
            accent='cyan',
            view_url=reverse('admin_panel_windows') + '?days=30',
            automation_available=False,
        ))

    stale_tickets = _count_stale_tickets(hours=12)
    if stale_tickets:
        insights.append(_build_insight(
            key='stale_tickets',
            title=f'{stale_tickets} تیکت بیش از ۱۲ ساعت بدون پاسخ',
            what_happened=f'{stale_tickets} تیکت باز بیش از ۱۲ ساعت منتظر پاسخ staff هستند.',
            importance='افت رضایت و اعتماد مشتری',
            context='',
            recommendation='مشاهده و پاسخ — معمولاً خودکارسازی توصیه نمی‌شود.',
            severity='critical',
            category='support',
            count=stale_tickets,
            icon='fa-headset',
            accent='rose',
            view_url=reverse('admin_panel_support') + '?days=7',
            automation_available=False,
        ))

    sms = get_sms_balance_snapshot()
    if sms.get('is_low') and sms.get('ok'):
        credit = int(sms.get('credit') or sms.get('sms_count') or 0)
        insights.append(_build_insight(
            key='sms_balance_low',
            title='موجودی پیامک رو به اتمام است',
            what_happened=f'موجودی فعلی حدود {credit:,} تومان است.',
            importance='قطع کمپین‌ها و یادآوری‌ها',
            context='',
            recommendation='موجودی را افزایش دهید — هشدار خودکار زیر آستانه فعال کنید.',
            severity='high',
            category='sms',
            count=1,
            icon='fa-comment-sms',
            accent='amber',
            view_url=reverse('admin_panel_marketing'),
            automation_available=False,
        ))

    cur_rev, prev_rev, rev_delta = _revenue_drop_pct()
    if rev_delta is not None and rev_delta <= -15:
        insights.append(_build_insight(
            key='revenue_drop_7d',
            title='درآمد ۷ روز اخیر کمتر از هفته قبل است',
            what_happened=f'درآمد ۷ روز اخیر {abs(rev_delta):.0f}٪ کمتر از ۷ روز قبل است.',
            importance='سیگnal افت فروش',
            context=f'درآمد فعلی: {cur_rev:,} تومان · دوره قبل: {prev_rev:,} تومان',
            recommendation='قیف فروش را بررسی کن — سفارش‌های نیمه‌کاره و منقضی‌ها را هدف بگیر.',
            severity='medium',
            category='sales',
            count=abs(int(rev_delta)),
            icon='fa-chart-line',
            accent='violet',
            view_url=reverse('admin_panel_sales') + '?days=7',
            automation_available=False,
        ))

    crm_without, crm_total = _count_crm_not_started()
    if crm_total and crm_without:
        pct = round((crm_without / crm_total) * 100)
        if pct >= 40:
            insights.append(_build_insight(
                key='crm_not_started',
                title=f'{pct}٪ کاربران فعال هنوز CRM را شروع نکرده‌اند',
                what_happened=f'{crm_without} کاربر با لایسنس فعال هنوز مشتری CRM ثبت نکرده‌اند.',
                importance='ارزش محصول کامل استفاده نمی‌شود',
                context='',
                recommendation='ارسال آموزش ثبت اولین مشتری',
                severity='opportunity',
                category='crm',
                count=crm_without,
                icon='fa-address-book',
                accent='emerald',
                view_url=reverse('admin_panel_crm') + '?days=30',
                automation_available=False,
            ))

    renewal_hot = _count_high_renewal_chance()
    if renewal_hot:
        insights.append(_build_insight(
            key='high_renewal_chance',
            title=f'{renewal_hot} مشتری با احتمال بالای تمدید',
            what_happened='این کاربران قبلاً خریدار بوده‌اند، لایسنسشان تمام شده و دوباره به سیستم برگشته‌اند.',
            importance='فرصت تمدید با نرخ تبدیل بالا',
            context='',
            recommendation='همین امروز پیام تمدید ارسال کن.',
            severity='high',
            category='license',
            count=renewal_hot,
            icon='fa-fire',
            accent='rose',
            automation_key='expired_renewal_campaign',
            flow_key='license_renewal',
            view_url=reverse('admin_panel_licenses') + '?days=30',
        ))

    insights.sort(key=lambda row: (SEVERITY_ORDER.get(row.severity, 9), -row.count))
    return insights[:7]


def _insight_to_dict(insight: ManagementInsight) -> Dict[str, Any]:
    return {
        'key': insight.key,
        'title': insight.title,
        'what_happened': insight.what_happened,
        'importance': insight.importance,
        'context': insight.context,
        'recommendation': insight.recommendation,
        'severity': insight.severity,
        'severity_label': SEVERITY_LABELS.get(insight.severity, ''),
        'category': insight.category,
        'count': insight.count,
        'icon': insight.icon,
        'accent': insight.accent,
        'segment_key': insight.segment_key,
        'segment_params': insight.segment_params,
        'automation_key': insight.automation_key,
        'flow_key': insight.flow_key,
        'view_url': insight.view_url,
        'message_template': insight.message_template,
        'automation_available': insight.automation_available,
        'actions': [
            {'key': a.key, 'label': a.label, 'style': a.style, 'modal': a.modal}
            for a in insight.actions
        ],
    }


def ensure_automation_rules() -> None:
    """ایجاد/همگام‌سازی قوانین پیش‌فرض."""
    for row in AUTOMATION_RULE_CATALOG:
        defaults = {
            'name': row['name'],
            'is_active': row.get('default_active', False),
            'insight_key': row.get('insight_key', ''),
            'segment_key': row.get('segment_key', ''),
            'cadence': row.get('cadence', 'daily'),
            'action_type': row.get('action_type', 'send_sms'),
            'cooldown_days': row.get('cooldown_days', 7),
            'max_recipients_per_run': row.get('max_recipients_per_run', 50),
            'conditions': {
                'insight_key': row.get('insight_key', ''),
                'flow_key': row.get('flow_key', ''),
            },
        }
        rule, created = ManagementAutomationRule.objects.get_or_create(
            key=row['key'],
            defaults=defaults,
        )
        if not created:
            update_fields = []
            for field, value in (
                ('name', row['name']),
                ('insight_key', row.get('insight_key', '')),
                ('segment_key', row.get('segment_key', '')),
                ('cadence', row.get('cadence', 'daily')),
                ('action_type', row.get('action_type', 'send_sms')),
                ('max_recipients_per_run', row.get('max_recipients_per_run', 50)),
            ):
                if getattr(rule, field) != value:
                    setattr(rule, field, value)
                    update_fields.append(field)
            if update_fields:
                rule.save(update_fields=update_fields + ['updated_at'])


def get_automation_rules() -> List[Dict[str, Any]]:
    ensure_automation_rules()
    db_rules = {r.key: r for r in ManagementAutomationRule.objects.all()}
    rows = []
    for catalog in AUTOMATION_RULE_CATALOG:
        rule = db_rules.get(catalog['key'])
        rows.append({
            'key': catalog['key'],
            'name': catalog['name'],
            'insight_key': catalog.get('insight_key', ''),
            'flow_key': catalog.get('flow_key', ''),
            'condition_label': catalog['condition_label'],
            'audience_label': catalog['audience_label'],
            'action_label': catalog['action_label'],
            'template_label': catalog['template_label'],
            'cooldown_label': catalog['cooldown_label'],
            'is_active': bool(rule and rule.is_active),
            'last_run_at': rule.last_run_at if rule else None,
            'cooldown_days': rule.cooldown_days if rule else 7,
            'cadence': catalog.get('cadence', 'daily'),
            'action_type': catalog.get('action_type', 'send_sms'),
            'is_paused': bool(rule and rule.is_paused),
        })
    return rows


def get_automation_history(limit: int = 30) -> List[Dict[str, Any]]:
    executions = (
        ManagementAutomationExecution.objects.select_related('rule')
        .order_by('-started_at')[:limit]
    )
    history = []
    for ex in executions:
        history.append({
            'id': ex.pk,
            'rule_key': ex.rule.key,
            'title': ex.rule.name,
            'started_at': ex.started_at,
            'finished_at': ex.finished_at,
            'dry_run': ex.dry_run,
            'status': ex.get_status_display(),
            'matched_count': ex.matched_count,
            'success_count': ex.success_count,
            'failed_count': ex.failed_count,
            'skipped_count': ex.skipped_count,
            'sent_count': ex.success_count,
            'converted_count': 0,
        })
    return history


def get_action_results_summary(days: int = 7) -> Dict[str, Any]:
    since = timezone.now() - timedelta(days=days)
    executions = ManagementAutomationExecution.objects.filter(
        started_at__gte=since,
        dry_run=False,
        status=ManagementAutomationExecution.Status.COMPLETED,
    )
    messages = sum(ex.success_count for ex in executions)
    return {
        'days': days,
        'messages_sent': messages,
        'automations_run': executions.count(),
        'purchases': 0,
        'renewals': 0,
    }


def preview_insight_recipients(insight_key: str) -> Dict[str, Any]:
    insights = {i.key: i for i in build_management_insights()}
    insight = insights.get(insight_key)
    if not insight:
        return {'ok': False, 'error': 'پیشنهاد یافت نشد.', 'recipients': [], 'count': 0}

    if insight.segment_key:
        params = dict(insight.segment_params or {})
        preview = preview_segment(insight.segment_key, **params)
        return {
            'ok': True,
            'count': preview.get('count', 0),
            'recipients': preview.get('recipients', [])[:50],
            'sample_message': _sample_message_for_insight(insight, preview.get('recipients', [])),
        }

    return {
        'ok': True,
        'count': insight.count,
        'recipients': [],
        'sample_message': insight.message_template.replace('{link}', _site_link()),
    }


def _sample_message_for_insight(insight: ManagementInsight, recipients: List[Dict[str, Any]]) -> str:
    template = insight.message_template or INSIGHT_MESSAGE_TEMPLATES.get(insight.key, '')
    if not template:
        return ''
    ctx = {
        'name': '',
        'name_part': '',
        'product': 'فایلینگ دیوار',
        'plan': '',
        'amount': '',
        'link': _site_link(),
        'code': '',
    }
    if recipients:
        r0 = recipients[0]
        ctx.update({
            'name': r0.get('name') or '',
            'name_part': r0.get('name_part') or '',
            'product': r0.get('product') or ctx['product'],
            'plan': r0.get('plan') or '',
            'amount': r0.get('amount') or '',
            'link': r0.get('link') or ctx['link'],
            'code': r0.get('code') or '',
        })
    return render_message(template, ctx)


def send_insight_campaign(
    *,
    insight_key: str,
    message_template: str,
    created_by,
    selected_phones: List[str] | None = None,
) -> Dict[str, Any]:
    insights = {i.key: i for i in build_management_insights()}
    insight = insights.get(insight_key)
    if not insight:
        raise MarketingSendError('پیشنهاد نامعتبر است.', code='bad_insight')
    if not insight.segment_key:
        raise MarketingSendError(
            'ارسال خودکار برای این پیشنهاد هنوز پشتیبانی نمی‌شود — از مرکز مربوطه اقدام کنید.',
            code='no_segment',
        )

    params = dict(insight.segment_params or {})
    if selected_phones:
        recipients = build_segment_recipients(insight.segment_key, **params)
        phone_set = {p.strip() for p in selected_phones if p.strip()}
        recipients = [r for r in recipients if r.phone in phone_set]
        if not recipients:
            raise MarketingSendError('گیرنده‌ای انتخاب نشده است.', code='no_recipients')
    else:
        preview = preview_segment(insight.segment_key, **params)
        if not preview.get('count'):
            raise MarketingSendError('گیرنده‌ای یافت نشد.', code='no_recipients')

    template = (message_template or '').strip() or insight.message_template
    campaign = create_campaign_draft(
        name=f'دستیار: {insight.title[:80]}',
        segment_key=insight.segment_key,
        message_template=template,
        discount_mode='none',
        created_by=created_by,
        dedupe_days=7,
        **{k: v for k, v in params.items() if k in ('stale_hours', 'days_lookback', 'product_id')},
    )
    if selected_phones:
        run_campaign_send(campaign, selected_phones=selected_phones)
    else:
        run_campaign_send(campaign)
    return {'ok': True, 'campaign_id': campaign.pk, 'sent': campaign.sent_count}


def toggle_automation_rule(*, rule_key: str, active: bool, user) -> Dict[str, Any]:
    ensure_automation_rules()
    catalog = next((c for c in AUTOMATION_RULE_CATALOG if c['key'] == rule_key), None)
    if not catalog:
        return {'ok': False, 'error': 'قانون نامعتبر است.'}
    rule, _ = ManagementAutomationRule.objects.get_or_create(
        key=rule_key,
        defaults={'name': catalog['name']},
    )
    rule.is_active = active
    if active:
        rule.activated_at = timezone.now()
        rule.activated_by = user
    rule.save(update_fields=['is_active', 'activated_at', 'activated_by', 'updated_at'])
    return {'ok': True, 'key': rule_key, 'is_active': rule.is_active}


def get_assistant_preview() -> Dict[str, Any]:
    """Preview کوچک برای Command Center."""
    insights = build_management_insights()
    severity_counts = {k: 0 for k in SEVERITY_LABELS}
    for ins in insights:
        severity_counts[ins.severity] = severity_counts.get(ins.severity, 0) + 1
    top = insights[:3]
    return {
        'total': len(insights),
        'severity_counts': severity_counts,
        'top_insights': [
            {
                'key': i.key,
                'title': i.title,
                'severity': i.severity,
                'count': i.count,
            }
            for i in top
        ],
    }


def get_management_assistant_context(*, tab: str = 'suggestions') -> Dict[str, Any]:
    ensure_automation_rules()
    insights = build_management_insights()
    severity_counts = {k: 0 for k in SEVERITY_LABELS}
    for ins in insights:
        severity_counts[ins.severity] = severity_counts.get(ins.severity, 0) + 1

    active_automations = sum(1 for r in get_automation_rules() if r['is_active'])

    return {
        'tab': tab if tab in ('suggestions', 'automations', 'history') else 'suggestions',
        'insights': [_insight_to_dict(i) for i in insights],
        'insights_total': len(insights),
        'severity_counts': severity_counts,
        'automation_rules': get_automation_rules(),
        'active_automations_count': active_automations,
        'history': get_automation_history(limit=30),
        'action_results': get_action_results_summary(days=7),
    }
