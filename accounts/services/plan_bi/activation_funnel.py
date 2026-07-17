"""قیف فعال‌سازی واقعی پس از خرید."""
from __future__ import annotations

from datetime import timedelta
from statistics import mean, median
from typing import Any

from django.db.models import Min, Q
from django.utils import timezone

from accounts.services.plan_bi import EMPTY_MSG, MIN_SAMPLE, pct, safe_div
from licenses.models import ClientAppEvent, LicenseActivation
from shop.models import DownloadLog, Order
from workspace.models import Customer, Dataset, Reminder


def _hours_between(start, end) -> float | None:
    if not start or not end:
        return None
    return max((end - start).total_seconds() / 3600, 0)


def _stage(
    *,
    key: str,
    label: str,
    count: int,
    base: int,
    prev_count: int | None,
    times_hours: list[float],
    available: bool = True,
    note: str = '',
) -> dict[str, Any]:
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
            'display': EMPTY_MSG,
            'note': note or EMPTY_MSG,
        }

    conv_prev = pct(count, prev_count, 1) if prev_count else (100.0 if count else 0.0)
    drop_prev = pct(max((prev_count or 0) - count, 0), prev_count, 1) if prev_count else 0.0
    conv_base = pct(count, base, 1) if base else 0.0
    avg_h = round(mean(times_hours), 1) if times_hours else None
    med_h = round(median(times_hours), 1) if times_hours else None
    return {
        'key': key,
        'label': label,
        'available': True,
        'count': count,
        'conversion_from_prev': conv_prev,
        'dropoff_from_prev': drop_prev,
        'conversion_from_base': conv_base,
        'avg_hours': avg_h,
        'median_hours': med_h,
        'display': count,
        'note': note,
    }


def build_activation_funnel(
    *,
    buyers: dict[str, Any],
    pricing_views: int,
    checkout_views: int,
    failed_payments: int,
    pending_orders: int,
) -> dict[str, Any]:
    """قیف کامل: قیمت → checkout → پرداخت → فعال‌سازی → دیتاست → CRM → یادآور → ارتقا."""
    user_ids = buyers['user_ids']
    first_paid = buyers['first_paid']
    base = len(user_ids)
    paid_count = buyers['paid_count']

    # Top-of-funnel (visitors)
    top_stages = [
        _stage(
            key='pricing_view',
            label='بازدید صفحه قیمت',
            count=pricing_views,
            base=max(pricing_views, 1),
            prev_count=None,
            times_hours=[],
            available=pricing_views > 0 or paid_count > 0,
            note='' if pricing_views > 0 else 'ردیابی بازدید پس از deploy فعال است',
        ),
        _stage(
            key='checkout_view',
            label='شروع Checkout',
            count=checkout_views,
            base=max(pricing_views, 1),
            prev_count=pricing_views or None,
            times_hours=[],
            available=checkout_views > 0 or paid_count > 0,
        ),
        _stage(
            key='paid',
            label='پرداخت موفق',
            count=paid_count,
            base=max(pricing_views, paid_count, 1),
            prev_count=checkout_views or paid_count or None,
            times_hours=[],
            available=True,
        ),
    ]

    if not user_ids:
        empty_post = [
            _stage(key=k, label=lbl, count=0, base=0, prev_count=None, times_hours=[], available=False)
            for k, lbl in [
                ('license_activated', 'فعال‌سازی لایسنس'),
                ('first_dataset', 'ساخت دیتاست / استخراج'),
                ('first_crm', 'اولین استفاده CRM'),
                ('first_reminder', 'ثبت اولین یادآور'),
                ('upgraded', 'ارتقاء پلن'),
            ]
        ]
        return {
            'stages': top_stages + empty_post,
            'failed_payments': failed_payments,
            'pending_checkouts': pending_orders,
            'checkout_abandon_estimate': pending_orders,
            'market_analysis': {'available': False, 'display': EMPTY_MSG},
            'sms_campaign': {'available': False, 'display': EMPTY_MSG},
            'base_buyers': 0,
        }

    # Bulk first-event maps after purchase
    activations = dict(
        LicenseActivation.objects.filter(license__order__user_id__in=user_ids)
        .values('license__order__user_id')
        .annotate(first_at=Min('activated_at'))
        .values_list('license__order__user_id', 'first_at')
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

    # Upgrades: daily then monthly after first paid
    upgraded_users: set[int] = set()
    upgrade_times: list[float] = []
    for uid, fp in first_paid.items():
        plans = buyers['plan_types_by_user'].get(uid, [])
        if 'daily' not in plans:
            continue
        monthly = (
            Order.objects.filter(user_id=uid, status='paid', plan__plan_type='monthly')
            .annotate(effective_paid=Min('paid_at'))  # wrong - need Coalesce
        )
        # simpler: from orders list
        for o in buyers['orders']:
            if o.user_id == uid and o.plan and o.plan.plan_type == 'monthly' and o.effective_paid and o.effective_paid > fp:
                if (o.effective_paid - fp) <= timedelta(days=7):
                    upgraded_users.add(uid)
                    h = _hours_between(fp, o.effective_paid)
                    if h is not None:
                        upgrade_times.append(h)
                break

    def collect(stage_map: dict, after_purchase_only: bool = True):
        count = 0
        times = []
        for uid, fp in first_paid.items():
            ts = stage_map.get(uid)
            if not ts:
                continue
            if after_purchase_only and ts < fp:
                # still count if they had activity after? Prefer after purchase
                continue
            count += 1
            h = _hours_between(fp, ts)
            if h is not None:
                times.append(h)
        return count, times

    act_count, act_times = collect(activations)
    ds_count, ds_times = collect(datasets)
    crm_count, crm_times = collect(customers)
    rem_count, rem_times = collect(reminders)

    post_stages = [
        _stage(
            key='license_activated',
            label='فعال‌سازی لایسنس',
            count=act_count,
            base=base,
            prev_count=base,
            times_hours=act_times,
            available=base >= 1,
        ),
        _stage(
            key='first_dataset',
            label='ساخت دیتاست / استخراج',
            count=ds_count,
            base=base,
            prev_count=act_count or base,
            times_hours=ds_times,
            available=base >= 1,
        ),
        _stage(
            key='first_crm',
            label='اولین استفاده CRM',
            count=crm_count,
            base=base,
            prev_count=ds_count or act_count or base,
            times_hours=crm_times,
            available=base >= 1,
        ),
        _stage(
            key='first_reminder',
            label='ثبت اولین یادآور',
            count=rem_count,
            base=base,
            prev_count=crm_count or base,
            times_hours=rem_times,
            available=base >= 1,
        ),
        _stage(
            key='upgraded',
            label='ارتقاء پلن (۷روز)',
            count=len(upgraded_users),
            base=base,
            prev_count=base,
            times_hours=upgrade_times,
            available=base >= MIN_SAMPLE or len(upgraded_users) > 0,
        ),
    ]

    # Biggest dropoff among sequential post stages
    biggest_drop = None
    for s in top_stages[1:] + post_stages:
        if not s['available'] or s['dropoff_from_prev'] is None:
            continue
        if biggest_drop is None or s['dropoff_from_prev'] > biggest_drop['dropoff_from_prev']:
            biggest_drop = s

    return {
        'stages': top_stages + post_stages,
        'failed_payments': failed_payments,
        'pending_checkouts': pending_orders,
        'checkout_abandon_estimate': pending_orders,
        'biggest_dropoff': {
            'key': biggest_drop['key'],
            'label': biggest_drop['label'],
            'dropoff': biggest_drop['dropoff_from_prev'],
        } if biggest_drop else None,
        'market_analysis': {'available': False, 'display': EMPTY_MSG},
        'sms_campaign': {'available': False, 'display': EMPTY_MSG},
        'base_buyers': base,
    }
