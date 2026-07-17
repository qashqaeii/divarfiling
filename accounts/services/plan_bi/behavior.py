"""رفتار پس از خرید + همبستگی Rule-based (مشاهده‌ای، نه علّی)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Min

from accounts.services.plan_bi import (
    CORR_MIN_GROUP,
    CORR_MIN_TOTAL,
    EMPTY_MSG,
    pct,
    safe_div,
)
from licenses.models import ClientAppEvent, LicenseActivation
from shop.models import DownloadLog
from workspace.models import CRMDeal, CRMProperty, Customer, Dataset, Reminder

# Activityهای معتبر برای Return (خرید/صدور لایسنس/سیستم خودکار مستثنی‌اند)
VALID_RETURN_ACTIVITIES = (
    'dataset_created',
    'crm_customer_created',
    'reminder_created',
    'crm_property_created',
    'crm_deal_created',
    'app_first_launch',
    'app_client_event',
)


def build_behavior_analytics(*, buyers: dict[str, Any], first_launch_dq: dict | None = None) -> dict[str, Any]:
    user_ids = buyers['user_ids']
    first_paid = buyers['first_paid']
    n = len(user_ids)
    if n < 1:
        return {
            'available': False,
            'display': EMPTY_MSG,
            'sample_size': 0,
            'features': [],
            'correlations': [],
            'valid_return_activities': list(VALID_RETURN_ACTIVITIES),
        }

    downloads = set(
        DownloadLog.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True).distinct()
    )
    activations = dict(
        LicenseActivation.objects.filter(license__order__user_id__in=user_ids)
        .values('license__order__user_id')
        .annotate(first_at=Min('activated_at'))
        .values_list('license__order__user_id', 'first_at')
    )
    launch_times = dict(
        ClientAppEvent.objects.filter(
            user_id__in=user_ids,
            event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
        )
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )
    # سایر ClientAppEvent بعد از خرید (غیر از صدور خودکار)
    other_app_events = dict(
        ClientAppEvent.objects.filter(user_id__in=user_ids)
        .exclude(event_type=ClientAppEvent.EventType.FIRST_LAUNCH)
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )
    datasets = dict(
        Dataset.objects.filter(user_id__in=user_ids)
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )
    customers = dict(
        Customer.objects.filter(user_id__in=user_ids)
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )
    reminders = dict(
        Reminder.objects.filter(user_id__in=user_ids)
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )
    properties = dict(
        CRMProperty.objects.filter(user_id__in=user_ids, deleted_at__isnull=True)
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )
    deals = dict(
        CRMDeal.objects.filter(user_id__in=user_ids)
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )

    return_7d = set()
    return_30d = set()
    upgraded = set()
    same_day_extract = set()

    def activity_timestamps(uid):
        """Activity معتبر بعد از خرید — بدون خرید مجدد و بدون فقط activation."""
        items = []
        for ts in (
            datasets.get(uid),
            customers.get(uid),
            reminders.get(uid),
            properties.get(uid),
            deals.get(uid),
            launch_times.get(uid),
            other_app_events.get(uid),
        ):
            if ts:
                items.append(ts)
        return items

    for uid, fp in first_paid.items():
        # Return 7d: activity در روز ۲ تا ۷ (نه روز ۰/۱ خرید)
        start_7 = fp + timedelta(days=1)
        end_7 = fp + timedelta(days=7)
        # Return 30d: activity در روز ۸ تا ۳۰
        start_30 = fp + timedelta(days=7)
        end_30 = fp + timedelta(days=30)

        for ts in activity_timestamps(uid):
            if ts < fp:
                continue
            if start_7 < ts <= end_7:
                return_7d.add(uid)
            if start_30 < ts <= end_30:
                return_30d.add(uid)

        plans = buyers['plan_types_by_user'].get(uid, [])
        if 'daily' in plans and 'monthly' in plans:
            upgraded.add(uid)

        ds = datasets.get(uid)
        if ds and ds >= fp and (ds - fp).total_seconds() <= 86400:
            same_day_extract.add(uid)

    fl_available = True
    fl_note = ''
    if first_launch_dq and first_launch_dq.get('status') in ('insufficient', 'broken', 'partial'):
        if first_launch_dq.get('status') == 'insufficient':
            fl_available = False
            fl_note = first_launch_dq.get('detail') or 'پوشش Event اولین اجرا ناکافی است.'

    def feat(key, label, users_set, available=True, note=''):
        if not available:
            return {
                'key': key, 'label': label, 'available': False,
                'count': None, 'rate': None, 'display': EMPTY_MSG, 'note': note or EMPTY_MSG,
            }
        count = len(set(users_set) & set(user_ids))
        return {
            'key': key,
            'label': label,
            'available': True,
            'count': count,
            'rate': pct(count, n, 1),
            'display': pct(count, n, 1),
            'note': note,
        }

    activated_after = {
        uid for uid, ts in activations.items()
        if uid in first_paid and ts and ts >= first_paid[uid]
    }
    launches_after = {
        uid for uid, ts in launch_times.items()
        if uid in first_paid and ts and ts >= first_paid[uid]
    }

    features = [
        feat('download', 'دانلود اپ ویندوز', downloads),
        feat('activated', 'فعال‌سازی لایسنس', activated_after),
        feat('first_launch', 'اولین اجرای اپ', launches_after, available=fl_available, note=fl_note),
        feat('dataset', 'ساخت دیتاست', set(datasets.keys())),
        feat('same_day_extract', 'استخراج همان‌روز خرید', same_day_extract),
        feat('crm', 'استفاده از CRM (مخاطب)', set(customers.keys())),
        feat('property', 'فایل شخصی / ملک', set(properties.keys())),
        feat('deal', 'ثبت معامله', set(deals.keys())),
        feat('reminder', 'ثبت یادآور', set(reminders.keys())),
        feat(
            'return_7d',
            'بازگشت ۷روز (روز۲–۷)',
            return_7d,
            note='Activity معتبر در بازه روز ۲ تا ۷ پس از خرید',
        ),
        feat(
            'return_30d',
            'بازگشت ۳۰روز (روز۸–۳۰)',
            return_30d,
            note='Activity معتبر در بازه روز ۸ تا ۳۰ پس از خرید',
        ),
        feat('upgraded', 'ارتقاء پلن (Outcome)', upgraded),
        feat('market_analysis', 'بازدید تحلیل بازار', set(), available=False),
        feat('sms_campaign', 'ساخت کمپین پیامکی', set(), available=False),
    ]

    revenue = buyers['revenue_by_user']
    order_counts = buyers['order_count_by_user']

    def corr(title, with_set: set[int]):
        with_users = with_set & set(user_ids)
        without_users = set(user_ids) - with_set
        sample_ok = (
            n >= CORR_MIN_TOTAL
            and len(with_users) >= CORR_MIN_GROUP
            and len(without_users) >= CORR_MIN_GROUP
        )
        if not sample_ok:
            conf = 'low'
            if n >= CORR_MIN_TOTAL and (len(with_users) >= 5 or len(without_users) >= 5):
                conf = 'medium'
            return {
                'title': title,
                'available': False,
                'display': 'نمونه برای نتیجه‌گیری کافی نیست',
                'note': (
                    f'حداقل {CORR_MIN_GROUP} در هر گروه و {CORR_MIN_TOTAL} کل نمونه لازم است '
                    f'(with={len(with_users)}, without={len(without_users)}, total={n})'
                ),
                'with_n': len(with_users),
                'without_n': len(without_users),
                'sample_size': n,
                'confidence': conf,
            }

        with_rev = safe_div(sum(revenue.get(u, 0) for u in with_users), len(with_users))
        without_rev = safe_div(sum(revenue.get(u, 0) for u in without_users), len(without_users))
        with_repeat = pct(
            sum(1 for u in with_users if order_counts.get(u, 0) > 1),
            len(with_users), 1,
        )
        without_repeat = pct(
            sum(1 for u in without_users if order_counts.get(u, 0) > 1),
            len(without_users), 1,
        )
        with_up = pct(len(with_users & upgraded), len(with_users), 1)
        without_up = pct(len(without_users & upgraded), len(without_users), 1)
        ratio = safe_div(with_rev, without_rev, 2) if without_rev else None
        # مشاهده‌ای — نه علّی
        body = (
            f'مشاهده: ارزش محقق‌شده گروه با سیگنال {with_rev:,} ت در برابر {without_rev:,} ت؛ '
            f'خرید مجدد {with_repeat}٪ در برابر {without_repeat}٪. '
            f'این همبستگی است، نه رابطه علّی.'
        )
        return {
            'title': title,
            'available': True,
            'with_n': len(with_users),
            'without_n': len(without_users),
            'sample_size': n,
            'confidence': 'sufficient',
            'with_observed_value': with_rev,
            'without_observed_value': without_rev,
            'with_ltv': with_rev,  # alias
            'without_ltv': without_rev,
            'with_repeat_rate': with_repeat,
            'without_repeat_rate': without_repeat,
            'with_upgrade_rate': with_up,
            'without_upgrade_rate': without_up,
            'ltv_ratio': ratio,
            'body': body,
            'display': body,
        }

    correlations = [
        corr('کاربران دارای دیتاست vs بدون دیتاست', set(datasets.keys())),
        corr('کاربران CRM vs بدون CRM', set(customers.keys())),
        corr('استخراج همان‌روز خرید vs بقیه', same_day_extract),
        corr('کاربران دارای یادآور vs بدون یادآور', set(reminders.keys())),
    ]

    return {
        'available': True,
        'sample_size': n,
        'features': features,
        'correlations': correlations,
        'valid_return_activities': list(VALID_RETURN_ACTIVITIES),
    }
