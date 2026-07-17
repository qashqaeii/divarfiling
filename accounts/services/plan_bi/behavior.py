"""رفتار پس از خرید + همبستگی Rule-based."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Min

from accounts.services.plan_bi import EMPTY_MSG, MIN_SAMPLE, pct, safe_div
from licenses.models import ClientAppEvent, LicenseActivation
from shop.models import DownloadLog, Order
from workspace.models import CRMDeal, CRMProperty, Customer, Dataset, Reminder


def build_behavior_analytics(*, buyers: dict[str, Any]) -> dict[str, Any]:
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
    launches = set(
        ClientAppEvent.objects.filter(
            user_id__in=user_ids,
            event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
        ).values_list('user_id', flat=True).distinct()
    )
    datasets = dict(
        Dataset.objects.filter(user_id__in=user_ids)
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )
    customers = set(
        Customer.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True).distinct()
    )
    reminders = set(
        Reminder.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True).distinct()
    )
    properties = set(
        CRMProperty.objects.filter(user_id__in=user_ids, deleted_at__isnull=True)
        .values_list('user_id', flat=True).distinct()
    )
    deals = set(
        CRMDeal.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True).distinct()
    )

    return_7d = set()
    return_30d = set()
    upgraded = set()
    same_day_extract = set()
    for uid, fp in first_paid.items():
        # return = any order after first OR any usage after day 1? use order repeat or dataset after
        later_orders = [
            o for o in buyers['orders']
            if o.user_id == uid and o.effective_paid and o.effective_paid > fp
        ]
        if any((o.effective_paid - fp).days <= 7 for o in later_orders):
            return_7d.add(uid)
        if any((o.effective_paid - fp).days <= 30 for o in later_orders):
            return_30d.add(uid)
        # also count usage return
        for ts in (activations.get(uid), datasets.get(uid)):
            if ts and fp < ts <= fp + timedelta(days=7):
                return_7d.add(uid)
            if ts and fp < ts <= fp + timedelta(days=30):
                return_30d.add(uid)

        plans = buyers['plan_types_by_user'].get(uid, [])
        if 'daily' in plans and 'monthly' in plans:
            upgraded.add(uid)

        ds = datasets.get(uid)
        if ds and abs((ds - fp).total_seconds()) <= 86400 and ds >= fp:
            same_day_extract.add(uid)

    def feat(key, label, users_set, available=True, note=''):
        if not available:
            return {
                'key': key, 'label': label, 'available': False,
                'count': None, 'rate': None, 'display': EMPTY_MSG, 'note': note or EMPTY_MSG,
            }
        count = len(users_set & set(user_ids)) if isinstance(users_set, set) else len(users_set)
        return {
            'key': key,
            'label': label,
            'available': True,
            'count': count,
            'rate': pct(count, n, 1),
            'display': pct(count, n, 1),
            'note': note,
        }

    features = [
        feat('download', 'دانلود اپ ویندوز', downloads),
        feat('activated', 'فعال‌سازی لایسنس', set(activations.keys())),
        feat('first_launch', 'اولین اجرای اپ', launches),
        feat('dataset', 'ساخت دیتاست', set(datasets.keys())),
        feat('same_day_extract', 'استخراج همان‌روز خرید', same_day_extract),
        feat('crm', 'استفاده از CRM (مخاطب)', customers),
        feat('property', 'فایل شخصی / ملک', properties),
        feat('deal', 'ثبت معامله', deals),
        feat('reminder', 'ثبت یادآور', reminders),
        feat('return_7d', 'فعال/بازگشت ۷روز', return_7d),
        feat('return_30d', 'فعال/بازگشت ۳۰روز', return_30d),
        feat('upgraded', 'ارتقاء پلن', upgraded),
        feat('market_analysis', 'بازدید تحلیل بازار', set(), available=False),
        feat('sms_campaign', 'ساخت کمپین پیامکی', set(), available=False),
    ]

    # Correlations
    correlations = []
    revenue = buyers['revenue_by_user']
    order_counts = buyers['order_count_by_user']

    def corr(title, with_set: set[int], without_set: set[int] | None = None):
        with_users = with_set & set(user_ids)
        without_users = (set(user_ids) - with_set) if without_set is None else (without_set & set(user_ids))
        if len(with_users) < MIN_SAMPLE or len(without_users) < MIN_SAMPLE:
            return {
                'title': title,
                'available': False,
                'display': EMPTY_MSG,
                'note': f'نمونه کافی نیست (حداقل {MIN_SAMPLE} در هر گروه)',
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
        body = (
            f'LTV تقریبی گروه با سیگنال {with_rev:,} ت در برابر {without_rev:,} ت؛ '
            f'خرید مجدد {with_repeat}٪ در برابر {without_repeat}٪.'
        )
        if ratio and ratio >= 1.5:
            body = f'کاربران این گروه حدوداً {ratio}× درآمد بیشتری دارند. ' + body
        return {
            'title': title,
            'available': True,
            'with_n': len(with_users),
            'without_n': len(without_users),
            'with_ltv': with_rev,
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
        corr('کاربران CRM vs بدون CRM', customers),
        corr('استخراج همان‌روز خرید vs بقیه', same_day_extract),
        corr('کاربران دارای یادآور vs بدون یادآور', reminders),
    ]

    return {
        'available': True,
        'sample_size': n,
        'features': features,
        'correlations': correlations,
    }
