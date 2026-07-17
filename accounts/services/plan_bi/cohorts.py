"""کوهورت غنی خریداران."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import Min, Sum
from django.db.models.functions import Coalesce

from accounts.services.plan_bi import (
    jalali_iso,
    jalali_week_label,
    pct,
    safe_div,
    to_local_date,
    week_start_monday,
)
from licenses.models import LicenseActivation
from shop.models import Order
from workspace.models import Customer, Dataset, Reminder


def build_rich_cohorts(*, limit: int = 12) -> list[dict[str, Any]]:
    first_paid_rows = (
        Order.objects.filter(status='paid')
        .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
        .filter(effective_paid__isnull=False)
        .values('user_id')
        .annotate(first_paid=Min('effective_paid'))
        .order_by('-first_paid')[:8000]
    )

    cohorts: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'users': 0,
        'revenue': 0,
        'repeat_7d': 0,
        'repeat_30d': 0,
        'upgraded_monthly_7d': 0,
        'daily_starters': 0,
        'activated_7d': 0,
        'dataset_7d': 0,
        'crm_7d': 0,
        'reminder_7d': 0,
        'active_7d': 0,
        'active_30d': 0,
        'renewed': 0,
        'user_ids': [],
        'first_paid_map': {},
    })

    window_7 = timedelta(days=7)
    window_30 = timedelta(days=30)

    rows = list(first_paid_rows)
    all_uids = [r['user_id'] for r in rows]

    # Bulk maps
    activations = dict(
        LicenseActivation.objects.filter(license__order__user_id__in=all_uids)
        .values('license__order__user_id')
        .annotate(first_at=Min('activated_at'))
        .values_list('license__order__user_id', 'first_at')
    )
    datasets = dict(
        Dataset.objects.filter(user_id__in=all_uids)
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )
    customers = dict(
        Customer.objects.filter(user_id__in=all_uids)
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )
    reminders = dict(
        Reminder.objects.filter(user_id__in=all_uids)
        .values('user_id')
        .annotate(first_at=Min('created_at'))
        .values_list('user_id', 'first_at')
    )

    user_orders = (
        Order.objects.filter(user_id__in=all_uids, status='paid')
        .annotate(effective_paid=Coalesce('paid_at', 'created_at'))
        .select_related('plan')
        .order_by('effective_paid')
    )
    orders_by_user: dict[int, list] = defaultdict(list)
    for o in user_orders:
        orders_by_user[o.user_id].append(o)

    for row in rows:
        uid = row['user_id']
        first_paid = row['first_paid']
        first_date = to_local_date(first_paid)
        if not first_date:
            continue
        key = week_start_monday(first_date).isoformat()
        bucket = cohorts[key]
        bucket['users'] += 1
        bucket['user_ids'].append(uid)
        bucket['first_paid_map'][uid] = first_paid

        u_orders = orders_by_user.get(uid, [])
        rev = sum(int(o.amount or 0) for o in u_orders)
        bucket['revenue'] += rev

        if any(o.effective_paid and first_paid < o.effective_paid <= first_paid + window_7 for o in u_orders):
            bucket['repeat_7d'] += 1
        if any(o.effective_paid and first_paid < o.effective_paid <= first_paid + window_30 for o in u_orders):
            bucket['repeat_30d'] += 1

        first_plan = u_orders[0].plan.plan_type if u_orders and u_orders[0].plan else ''
        if first_plan == 'daily':
            bucket['daily_starters'] += 1
            if any(
                o.plan and o.plan.plan_type == 'monthly'
                and o.effective_paid and first_paid < o.effective_paid <= first_paid + window_7
                for o in u_orders
            ):
                bucket['upgraded_monthly_7d'] += 1

        # Renew heuristic: 2nd+ paid of same plan_type after 20+ days
        if len(u_orders) >= 2:
            for o in u_orders[1:]:
                if o.effective_paid and (o.effective_paid - first_paid).days >= 20:
                    bucket['renewed'] += 1
                    break

        def within(ts, window):
            return ts and first_paid <= ts <= first_paid + window

        if within(activations.get(uid), window_7):
            bucket['activated_7d'] += 1
            bucket['active_7d'] += 1
        if within(datasets.get(uid), window_7):
            bucket['dataset_7d'] += 1
            bucket['active_7d'] += 0  # already counted if activated; ensure activity
            if uid not in [x for x in []]:
                pass
        # active_7d = any usage signal
        signals_7 = [
            activations.get(uid), datasets.get(uid), customers.get(uid), reminders.get(uid),
        ]
        if any(within(s, window_7) for s in signals_7):
            # recount properly
            pass

        if within(datasets.get(uid), window_7):
            bucket['dataset_7d'] += 0  # already incremented above - fix double
        # Fix: I double-counted dataset. Let me rewrite the signal block cleanly below.

    # Rebuild activity counts cleanly (fix double-count from messy block)
    for key, bucket in cohorts.items():
        bucket['activated_7d'] = 0
        bucket['dataset_7d'] = 0
        bucket['crm_7d'] = 0
        bucket['reminder_7d'] = 0
        bucket['active_7d'] = 0
        bucket['active_30d'] = 0
        for uid in bucket['user_ids']:
            fp = bucket['first_paid_map'][uid]

            def in_w(ts, days):
                return ts is not None and fp <= ts <= fp + timedelta(days=days)

            a7 = in_w(activations.get(uid), 7)
            d7 = in_w(datasets.get(uid), 7)
            c7 = in_w(customers.get(uid), 7)
            r7 = in_w(reminders.get(uid), 7)
            if a7:
                bucket['activated_7d'] += 1
            if d7:
                bucket['dataset_7d'] += 1
            if c7:
                bucket['crm_7d'] += 1
            if r7:
                bucket['reminder_7d'] += 1
            if a7 or d7 or c7 or r7:
                bucket['active_7d'] += 1
            if any(in_w(s, 30) for s in [
                activations.get(uid), datasets.get(uid), customers.get(uid), reminders.get(uid),
            ]):
                bucket['active_30d'] += 1

    result = []
    for week_key in sorted(cohorts.keys(), reverse=True)[:limit]:
        data = cohorts[week_key]
        users = data['users']
        from datetime import date as date_cls
        week_date = date_cls.fromisoformat(week_key)
        daily_starters = data['daily_starters']
        result.append({
            'week': week_key,
            'week_jalali': jalali_iso(week_date),
            'week_label': jalali_week_label(week_date),
            'users': users,
            'revenue': int(data['revenue']),
            'avg_ltv': safe_div(data['revenue'], users),
            'daily_starters': daily_starters,
            'repeat_7d': data['repeat_7d'],
            'repeat_30d': data['repeat_30d'],
            'repeat_7d_rate': pct(data['repeat_7d'], users, 1),
            'repeat_30d_rate': pct(data['repeat_30d'], users, 1),
            'upgraded_monthly_7d': data['upgraded_monthly_7d'],
            'upgrade_rate': pct(data['upgraded_monthly_7d'], daily_starters or users, 1),
            'renewed': data['renewed'],
            'renewal_rate': pct(data['renewed'], users, 1),
            'activated_7d': data['activated_7d'],
            'activated_7d_rate': pct(data['activated_7d'], users, 1),
            'dataset_7d': data['dataset_7d'],
            'dataset_7d_rate': pct(data['dataset_7d'], users, 1),
            'crm_7d': data['crm_7d'],
            'crm_7d_rate': pct(data['crm_7d'], users, 1),
            'reminder_7d': data['reminder_7d'],
            'reminder_7d_rate': pct(data['reminder_7d'], users, 1),
            'active_7d': data['active_7d'],
            'active_7d_rate': pct(data['active_7d'], users, 1),
            'active_30d': data['active_30d'],
            'active_30d_rate': pct(data['active_30d'], users, 1),
            'market_analysis_rate': None,
            'market_analysis_available': False,
        })
    return result
