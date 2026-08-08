"""ممیزی صحت اعداد قیف جذب — مقایسه داشبورد با خرید/لایسنس واقعی سرنخ‌ها."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum

from accounts.models import (
    CampaignEnrollment,
    LeadAttribution,
    LeadCampaign,
    LeadImportBatch,
    LeadTouchpoint,
    MarketingLead,
)
from accounts.phone_utils import find_user_by_phone, normalize_phone
from accounts.services.lead_funnel import overview_stats
from licenses.models import License
from shop.models import Order

User = get_user_model()

PAID_ORDER_STATUS = 'paid'


@dataclass
class BuyerSample:
    lead_id: int
    phone: str
    lead_status: str
    user_id: int | None
    paid_orders: int
    paid_revenue: int
    plan_names: list[str]
    in_acquisition_enroll: bool
    has_conversion_attr: bool
    has_paid_touchpoint: bool


def _paid_orders_qs():
    return Order.objects.filter(status=PAID_ORDER_STATUS).select_related('plan', 'user')


def _user_ids_with_paid_orders() -> set[int]:
    return set(_paid_orders_qs().values_list('user_id', flat=True))


def _lead_user_id(lead: MarketingLead, paid_users: set[int]) -> int | None:
    if lead.matched_user_id and lead.matched_user_id in paid_users:
        return lead.matched_user_id
    user = find_user_by_phone(lead.phone_normalized)
    if user and user.pk in paid_users:
        return user.pk
    return None


def _orders_for_user(user_id: int) -> list[Order]:
    return list(
        _paid_orders_qs()
        .filter(user_id=user_id)
        .order_by('-paid_at', '-created_at')[:20]
    )


def audit_acquisition_funnel(*, sample_limit: int = 15) -> dict[str, Any]:
    """
    بررسی هم‌خوانی «خرید / لایسنس» داشبورد با واقعیت:
    - LeadAttribution conversion (همان عدد UI)
    - سرنخ‌هایی که شماره/کاربرشان سفارش paid دارد (هر پلن، حتی یک‌هفته‌ای)
    """
    dashboard = overview_stats()

    enrolled_lead_ids = set(
        CampaignEnrollment.objects.filter(
            campaign__kind=LeadCampaign.Kind.ACQUISITION,
        )
        .exclude(status=CampaignEnrollment.Status.HOLD)
        .values_list('lead_id', flat=True)
        .distinct(),
    )

    conversion_qs = LeadAttribution.objects.filter(
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.LAST,
    )
    conversion_enrolled_qs = conversion_qs.filter(lead_id__in=enrolled_lead_ids)

    paid_touch_lead_ids = set(
        LeadTouchpoint.objects.filter(
            event_type__in=(
                LeadTouchpoint.EventType.PAID,
                LeadTouchpoint.EventType.LICENSED,
            ),
        )
        .values_list('lead_id', flat=True)
        .distinct(),
    )

    paid_users = _user_ids_with_paid_orders()
    all_leads = MarketingLead.objects.all().only(
        'id', 'phone_normalized', 'status', 'matched_user_id', 'display_name',
    )

    buyers_all: list[BuyerSample] = []
    buyers_enrolled: list[BuyerSample] = []
    buyers_registered: list[BuyerSample] = []

    conversion_lead_ids = set(conversion_qs.values_list('lead_id', flat=True))

    for lead in all_leads.iterator(chunk_size=500):
        user_id = _lead_user_id(lead, paid_users)
        if not user_id:
            continue
        orders = _orders_for_user(user_id)
        if not orders:
            continue
        revenue = sum(int(o.amount or 0) for o in orders)
        plan_names = list({(o.plan.name if o.plan_id else '—') for o in orders})
        sample = BuyerSample(
            lead_id=lead.pk,
            phone=lead.phone_normalized,
            lead_status=lead.status,
            user_id=user_id,
            paid_orders=len(orders),
            paid_revenue=revenue,
            plan_names=plan_names[:5],
            in_acquisition_enroll=lead.pk in enrolled_lead_ids,
            has_conversion_attr=lead.pk in conversion_lead_ids,
            has_paid_touchpoint=lead.pk in paid_touch_lead_ids,
        )
        buyers_all.append(sample)
        if sample.in_acquisition_enroll:
            buyers_enrolled.append(sample)
        if lead.status == MarketingLead.Status.REGISTERED:
            buyers_registered.append(sample)

    # کاربران paid که اصلاً MarketingLead ندارند (خارج از بانک ۱۰۴۰)
    lead_phones = set(all_leads.values_list('phone_normalized', flat=True))
    paid_users_without_lead = 0
    for uid in paid_users:
        user = User.objects.filter(pk=uid).only('phone').first()
        if not user:
            continue
        phone = normalize_phone(getattr(user, 'phone', '') or '')
        if phone and phone not in lead_phones:
            if not MarketingLead.objects.filter(matched_user_id=uid).exists():
                paid_users_without_lead += 1

    registered_with_acq = LeadAttribution.objects.filter(
        axis=LeadAttribution.Axis.ACQUISITION,
        touch_model=LeadAttribution.TouchModel.LAST,
        campaign__kind=LeadCampaign.Kind.ACQUISITION,
    ).count()

    conversion_total = conversion_qs.count()
    ui_purchases = int(dashboard.get('total_purchases', 0) or 0)

    mismatch = [b for b in buyers_enrolled if not b.has_conversion_attr]
    buyers_all_count = len(buyers_all)

    verdict = 'ok'
    notes: list[str] = []
    if buyers_all_count == 0 and conversion_total == 0:
        notes.append(
            'هیچ یک از سرنخ‌ها (بر اساس تطبیق شماره/کاربر) سفارش paid ندارند — '
            'عدد ۰ خرید در داشبورد درست است.',
        )
    elif buyers_all_count > 0 and conversion_total == 0:
        verdict = 'attribution_gap'
        notes.append(
            f'{buyers_all_count} سرنخ سفارش paid دارند ولی LeadAttribution conversion = 0 — '
            'داشبورد کم‌شمار است؛ backfill لازم است.',
        )
    elif buyers_all_count > conversion_total:
        verdict = 'attribution_gap'
        notes.append(
            f'{buyers_all_count - conversion_total} سرنخ خریدار هنوز conversion ندارند — '
            'python manage.py backfill_acquisition_conversions',
        )
    elif ui_purchases != conversion_total:
        verdict = 'review'
        notes.append(
            f'اختلاف KPI داشبورد ({ui_purchases}) و conversion DB ({conversion_total}) — '
            'cache یا deploy را بررسی کنید.',
        )
    else:
        notes.append(
            f'هم‌خوان: {conversion_total} خرید در بانک سرنخ · '
            f'{conversion_enrolled_qs.count()} نفر enroll کمپین جذب.',
        )

    def _sample_rows(items: list[BuyerSample], limit: int) -> list[dict]:
        rows = []
        for b in items[:limit]:
            rows.append({
                'lead_id': b.lead_id,
                'phone': b.phone,
                'lead_status': b.lead_status,
                'user_id': b.user_id,
                'paid_orders': b.paid_orders,
                'paid_revenue_toman': b.paid_revenue,
                'plans': b.plan_names,
                'enrolled_acquisition': b.in_acquisition_enroll,
                'conversion_attribution': b.has_conversion_attr,
                'paid_touchpoint': b.has_paid_touchpoint,
            })
        return rows

    license_on_lead_users = License.objects.filter(
        order__status=PAID_ORDER_STATUS,
        order__user_id__in=[b.user_id for b in buyers_all if b.user_id],
    ).count() if buyers_all else 0

    return {
        'verdict': verdict,
        'notes': notes,
        'dashboard': {
            'leads_total': dashboard['leads_total'],
            'leads_cold': dashboard['leads_cold'],
            'leads_engaged': dashboard['leads_engaged'],
            'leads_registered': dashboard['leads_registered'],
            'leads_customer': dashboard['leads_customer'],
            'total_clicks': dashboard['total_clicks'],
            'total_purchases_ui': dashboard['total_purchases'],
            'purchase_revenue_ui': dashboard['purchase_revenue'],
            'accepted_sms': dashboard['accepted_sms'],
            'ctr_pct': dashboard['ctr_pct'],
        },
        'attribution': {
            'conversion_last_all_leads': conversion_total,
            'conversion_last_enrolled_acquisition': conversion_enrolled_qs.count(),
            'acquisition_signups_attributed': registered_with_acq,
            'conversion_revenue_all': int(
                conversion_qs.aggregate(s=Sum('revenue_amount'))['s'] or 0,
            ),
            'conversion_revenue_enrolled': int(
                conversion_enrolled_qs.aggregate(s=Sum('revenue_amount'))['s'] or 0,
            ),
        },
        'ground_truth': {
            'paid_orders_site_total': _paid_orders_qs().count(),
            'paid_users_site_total': len(paid_users),
            'paid_users_without_marketing_lead': paid_users_without_lead,
            'leads_with_paid_order_by_phone_or_user': len(buyers_all),
            'enrolled_leads_with_paid_order': len(buyers_enrolled),
            'registered_leads_with_paid_order': len(buyers_registered),
            'leads_with_paid_or_licensed_touchpoint': len(paid_touch_lead_ids),
            'licenses_for_lead_buyers': license_on_lead_users,
            'enrolled_buyers_missing_conversion_attr': len(mismatch),
        },
        'lead_status_breakdown': dict(
            MarketingLead.objects.values('status').annotate(c=Count('id')).values_list('status', 'c'),
        ),
        'batches_committed': LeadImportBatch.objects.filter(
            status=LeadImportBatch.Status.COMMITTED,
        ).count(),
        'samples': {
            'buyers_among_all_leads': _sample_rows(buyers_all, sample_limit),
            'buyers_enrolled_missing_attr': _sample_rows(mismatch, sample_limit),
        },
    }
