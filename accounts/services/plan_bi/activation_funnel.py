"""قیف خرید و قیف فعال‌سازی — دو آبجکت مستقل."""
from __future__ import annotations

from datetime import timedelta
from statistics import mean, median
from typing import Any

from django.db.models import Min

from accounts.services.plan_bi import (
    EMPTY_MSG,
    MIN_SAMPLE,
    conversion_rate,
    percentile,
)
from licenses.models import ClientAppEvent, LicenseActivation
from workspace.models import Customer, Dataset, Reminder


def _hours_between(start, end) -> float | None:
    if not start or not end:
        return None
    # Event قبل از خرید نادیده
    if end < start:
        return None
    return max((end - start).total_seconds() / 3600, 0)


def _time_stats(times_hours: list[float]) -> dict[str, Any]:
    if not times_hours:
        return {
            'sample_size': 0,
            'avg_hours': None,
            'median_hours': None,
            'p90_hours': None,
        }
    return {
        'sample_size': len(times_hours),
        'avg_hours': round(mean(times_hours), 1),
        'median_hours': round(median(times_hours), 1),
        'p90_hours': percentile(times_hours, 90),
    }


def _stage(
    *,
    key: str,
    label: str,
    count: int | None,
    base: int | None,
    prev_count: int | None,
    times_hours: list[float] | None = None,
    available: bool = True,
    note: str = '',
    conversions_allowed: bool = True,
) -> dict[str, Any]:
    times_hours = times_hours or []
    stats = _time_stats(times_hours)

    if not available:
        return {
            'key': key,
            'label': label,
            'available': False,
            'count': None,
            'conversion_from_prev': None,
            'dropoff_from_prev': None,
            'conversion_from_base': None,
            'avg_hours': None,
            'median_hours': None,
            'p90_hours': None,
            'time_sample_size': 0,
            'display': EMPTY_MSG,
            'note': note or EMPTY_MSG,
        }

    conv_prev = None
    drop_prev = None
    conv_base = None
    if conversions_allowed and prev_count:
        conv_prev = conversion_rate(count or 0, prev_count, 1)
        if conv_prev is not None:
            drop_prev = round(100.0 - conv_prev, 1)
        else:
            drop_prev = None
    if conversions_allowed and base:
        conv_base = conversion_rate(count or 0, base, 1)

    return {
        'key': key,
        'label': label,
        'available': True,
        'count': count,
        'conversion_from_prev': conv_prev,
        'dropoff_from_prev': drop_prev,
        'conversion_from_base': conv_base,
        'avg_hours': stats['avg_hours'],
        'median_hours': stats['median_hours'],
        'p90_hours': stats['p90_hours'],
        'time_sample_size': stats['sample_size'],
        'display': count,
        'note': note,
    }


def build_purchase_funnel(
    *,
    pricing_views: int,
    checkout_views: int,
    paid_count: int,
    unique_buyers: int,
    activated_count: int,
    order_statuses: dict,
    funnel_conversions_available: bool,
    linked_paid_count: int,
) -> dict[str, Any]:
    """قیف خرید: pricing → checkout → payment → license_activated."""
    # برای conversion فقط linked_paid؛ نمایش خام paid جدا
    paid_for_conv = linked_paid_count if funnel_conversions_available else None

    stages = [
        _stage(
            key='pricing_view',
            label='بازدید صفحه قیمت',
            count=pricing_views,
            base=pricing_views or None,
            prev_count=None,
            available=pricing_views > 0,
            conversions_allowed=funnel_conversions_available,
            note='' if pricing_views > 0 else 'ردیابی بازدید هنوز پوشش کافی ندارد',
        ),
        _stage(
            key='checkout_started',
            label='شروع Checkout',
            count=checkout_views,
            base=pricing_views or None,
            prev_count=pricing_views or None,
            available=checkout_views > 0,
            conversions_allowed=funnel_conversions_available,
        ),
        _stage(
            key='payment_success',
            label='پرداخت موفق',
            count=paid_count,
            base=pricing_views or None,
            prev_count=checkout_views if funnel_conversions_available else None,
            available=True,
            conversions_allowed=funnel_conversions_available and paid_for_conv is not None,
            note=(
                f'تعداد خام سفارش: {paid_count}؛ برای Conversion فقط {linked_paid_count} سفارش متصل به Tracking'
                if not funnel_conversions_available
                else ''
            ),
        ),
        _stage(
            key='license_activated',
            label='فعال‌سازی لایسنس',
            count=activated_count,
            base=unique_buyers or None,
            prev_count=unique_buyers or None,
            available=unique_buyers > 0,
            conversions_allowed=True,
            note='نسبت به خریداران یکتا (نه تعداد سفارش)',
        ),
    ]

    # اصلاح conversion مرحله payment با linked count
    if funnel_conversions_available and stages[2]['available']:
        stages[2]['conversion_from_prev'] = conversion_rate(linked_paid_count, checkout_views, 1)
        stages[2]['conversion_from_base'] = conversion_rate(linked_paid_count, pricing_views, 1)
        if stages[2]['conversion_from_prev'] is not None:
            stages[2]['dropoff_from_prev'] = round(100.0 - stages[2]['conversion_from_prev'], 1)

    biggest_drop = None
    for s in stages[1:]:
        if not s['available'] or s['dropoff_from_prev'] is None:
            continue
        if biggest_drop is None or s['dropoff_from_prev'] > biggest_drop['dropoff']:
            biggest_drop = {
                'key': s['key'],
                'label': s['label'],
                'dropoff': s['dropoff_from_prev'],
            }

    return {
        'stages': stages,
        'failed_payments': order_statuses.get('failed', 0),
        'pending_recent': order_statuses.get('pending_recent', 0),
        'pending_stale': order_statuses.get('pending_stale', 0),
        'pending_stale_label': order_statuses.get('pending_stale_label', 'سفارش معلق قدیمی'),
        'abandoned': order_statuses.get('abandoned', 0),
        'abandoned_available': order_statuses.get('abandoned_available', False),
        'abandoned_display': order_statuses.get('abandoned_display', EMPTY_MSG),
        'biggest_dropoff': biggest_drop,
        'conversions_available': funnel_conversions_available,
        'paid_raw_count': paid_count,
        'unique_buyers': unique_buyers,
    }


def build_activation_funnel(*, buyers: dict[str, Any]) -> dict[str, Any]:
    """قیف فعال‌سازی روی unique paid buyers — بدون Upgrade/Renewal."""
    user_ids = buyers['user_ids']
    first_paid = buyers['first_paid']
    base = len(user_ids)

    if base < 1:
        empty_keys = [
            ('paid_buyer', 'خریدار پرداخت‌شده'),
            ('license_activated', 'فعال‌سازی لایسنس'),
            ('app_first_launch', 'اولین اجرای اپ'),
            ('first_extract_or_dataset', 'اولین استخراج/دیتاست'),
            ('first_crm_use', 'اولین استفاده CRM'),
            ('first_reminder', 'اولین یادآور'),
        ]
        return {
            'stages': [
                _stage(key=k, label=lbl, count=0, base=0, prev_count=None, available=False)
                for k, lbl in empty_keys
            ],
            'base_buyers': 0,
            'biggest_dropoff': None,
            'outcomes': {
                'upgrade': {'available': False, 'display': EMPTY_MSG},
                'renewal': {'available': False, 'display': EMPTY_MSG},
            },
        }

    activations = dict(
        LicenseActivation.objects.filter(license__order__user_id__in=user_ids)
        .values('license__order__user_id')
        .annotate(first_at=Min('activated_at'))
        .values_list('license__order__user_id', 'first_at')
    )
    launches = dict(
        ClientAppEvent.objects.filter(
            user_id__in=user_ids,
            event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
        )
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

    def collect(stage_map: dict):
        count = 0
        times = []
        for uid, fp in first_paid.items():
            ts = stage_map.get(uid)
            if not ts or ts < fp:
                continue
            count += 1
            h = _hours_between(fp, ts)
            if h is not None:
                times.append(h)
        return count, times

    act_count, act_times = collect(activations)
    launch_count, launch_times = collect(launches)
    ds_count, ds_times = collect(datasets)
    crm_count, crm_times = collect(customers)
    rem_count, rem_times = collect(reminders)

    stages = [
        _stage(
            key='paid_buyer',
            label='خریدار پرداخت‌شده (یکتا)',
            count=base,
            base=base,
            prev_count=None,
            available=True,
        ),
        _stage(
            key='license_activated',
            label='فعال‌سازی لایسنس',
            count=act_count,
            base=base,
            prev_count=base,
            times_hours=act_times,
            available=True,
        ),
        _stage(
            key='app_first_launch',
            label='اولین اجرای اپ',
            count=launch_count,
            base=base,
            prev_count=act_count or base,
            times_hours=launch_times,
            available=True,
            note='اگر پوشش Event ناکافی باشد در Data Quality اعلام می‌شود',
        ),
        _stage(
            key='first_extract_or_dataset',
            label='اولین استخراج/دیتاست',
            count=ds_count,
            base=base,
            prev_count=launch_count or act_count or base,
            times_hours=ds_times,
            available=True,
        ),
        _stage(
            key='first_crm_use',
            label='اولین استفاده CRM',
            count=crm_count,
            base=base,
            prev_count=ds_count or act_count or base,
            times_hours=crm_times,
            available=True,
        ),
        _stage(
            key='first_reminder',
            label='اولین یادآور',
            count=rem_count,
            base=base,
            prev_count=crm_count or base,
            times_hours=rem_times,
            available=True,
        ),
    ]

    biggest_drop = None
    for s in stages[1:]:
        if s['dropoff_from_prev'] is None:
            continue
        if biggest_drop is None or s['dropoff_from_prev'] > biggest_drop['dropoff']:
            biggest_drop = {
                'key': s['key'],
                'label': s['label'],
                'dropoff': s['dropoff_from_prev'],
            }

    # Outcomes جدا از قیف
    daily_eligible = {
        uid for uid, plans in buyers['plan_types_by_user'].items()
        if 'daily' in (plans or [])
    }
    upgraded = 0
    for uid in daily_eligible:
        fp = first_paid.get(uid)
        if not fp:
            continue
        for o in buyers['orders']:
            if (
                o.user_id == uid
                and o.plan
                and o.plan.plan_type == 'monthly'
                and o.effective_paid
                and o.effective_paid > fp
                and (o.effective_paid - fp) <= timedelta(days=7)
            ):
                upgraded += 1
                break

    daily_n = len(daily_eligible)
    upgrade_rate = conversion_rate(upgraded, daily_n, 1) if daily_n else None

    return {
        'stages': stages,
        'base_buyers': base,
        'biggest_dropoff': biggest_drop,
        'outcomes': {
            'upgrade': {
                'available': daily_n >= MIN_SAMPLE or upgraded > 0,
                'count': upgraded,
                'eligible': daily_n,
                'rate': upgrade_rate,
                'display': f'{upgrade_rate}٪' if upgrade_rate is not None else EMPTY_MSG,
                'note': 'Outcome جدا — جزء قیف فعال‌سازی نیست',
            },
            'renewal': {
                'available': False,
                'display': EMPTY_MSG,
                'note': 'تشخیص تمدید قطعی هنوز پوشش کافی ندارد',
            },
        },
    }
