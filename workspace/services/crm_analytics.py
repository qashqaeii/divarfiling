"""تحلیل و گزارش CRM — فاز ۳."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.db.models import Max
from django.utils import timezone

from workspace.constants import DEFAULT_STAGNANT_DAYS, FUNNEL_STAGES
from workspace.models import CRMDeal, Customer, CustomerActivity, PropertyVisit
from workspace.services.crm_scope import customers_qs, deals_qs


def get_conversion_funnel(user) -> Dict[str, Any]:
    """قیف تبدیل: سرنخ → پیگیری → بازدید → قرارداد."""
    customers = customers_qs(user)
    total = customers.count() or 1

    stage_map = {
        'سرنخ': customers.filter(status='جدید').count(),
        'پیگیری': customers.filter(status='در حال پیگیری').count(),
        'بازدید': customers.filter(status='بازدید انجام شد').count(),
        'قرارداد': customers.filter(status='قرارداد').count(),
    }
    deal_won = deals_qs(user).filter(stage__in=['قرارداد', 'بسته‌شده']).count()

    stages = []
    prev = total
    for name in FUNNEL_STAGES:
        count = stage_map.get(name, 0)
        if name == 'قرارداد' and deal_won > count:
            count = max(count, deal_won)
        pct_of_total = round(count / total * 100) if total else 0
        conv = round(count / prev * 100) if prev else 0
        stages.append({
            'stage': name,
            'count': count,
            'pct_of_total': pct_of_total,
            'conversion_from_prev': conv if stages else 100,
        })
        prev = count or prev

    return {
        'stages': stages,
        'total_contacts': total,
        'visit_records': PropertyVisit.objects.filter(user=user).count(),
        'active_deals': deals_qs(user).exclude(
            stage__in=['بسته‌شده', 'از دست رفته'],
        ).count(),
    }


def get_stagnant_contacts(user, days: int = DEFAULT_STAGNANT_DAYS, limit: int = 12):
    """مخاطبین بدون فعالیت اخیر."""
    cutoff = timezone.now() - timedelta(days=days)
    active_statuses = ['جدید', 'در حال پیگیری', 'بازدید انجام شد']
    rows = []

    for c in customers_qs(user).filter(status__in=active_statuses).order_by('updated_at'):
        last_act = (
            CustomerActivity.objects.filter(customer=c)
            .aggregate(m=Max('created_at'))['m']
        )
        last_touch = c.updated_at
        if last_act and last_act > last_touch:
            last_touch = last_act
        if last_touch >= cutoff:
            continue
        idle_days = (timezone.now() - last_touch).days
        rows.append({'customer': c, 'idle_days': idle_days, 'last_touch': last_touch})
        if len(rows) >= limit:
            break

    return rows


def stagnant_count(user, days: int = DEFAULT_STAGNANT_DAYS) -> int:
    cutoff = timezone.now() - timedelta(days=days)
    active_statuses = ['جدید', 'در حال پیگیری', 'بازدید انجام شد']
    count = 0
    for c in customers_qs(user).filter(status__in=active_statuses).only('id', 'updated_at'):
        last_act = (
            CustomerActivity.objects.filter(customer=c)
            .aggregate(m=Max('created_at'))['m']
        )
        last_touch = c.updated_at
        if last_act and last_act > last_touch:
            last_touch = last_act
        if last_touch < cutoff:
            count += 1
    return count
