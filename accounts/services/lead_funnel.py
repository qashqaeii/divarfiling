"""داشبورد قیف Lead Acquisition."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.models import (
    CampaignEnrollment,
    CampaignMessage,
    CampaignVariant,
    LeadAttribution,
    LeadCampaign,
    LeadImportBatch,
    LeadTouchpoint,
    MarketingLead,
)


TEHRAN_TZ = 'Asia/Tehran'

FUNNEL_STEP_DEFS = (
    ('eligible', 'واجد شرایط', '#64748b'),
    ('enrolled', 'ثبت در کمپین', '#475569'),
    ('accepted', 'ارسال پذیرفته', '#0d9488'),
    ('clicked', 'کلیک لندینگ', '#0891b2'),
    ('registered', 'ثبت‌نام', '#6366f1'),
    ('paid', 'خرید / لایسنس', '#e11d48'),
)

STATUS_CHART_COLORS = {
    LeadCampaign.Status.DRAFT: '#94a3b8',
    LeadCampaign.Status.PILOT: '#d97706',
    LeadCampaign.Status.ACTIVE: '#0d9488',
    LeadCampaign.Status.PAUSED: '#64748b',
    LeadCampaign.Status.COMPLETED: '#6366f1',
    LeadCampaign.Status.ARCHIVED: '#cbd5e1',
}


def _rate(part: int | float, whole: int | float, *, digits: int = 1) -> float:
    if not whole:
        return 0.0
    return round(100 * float(part) / float(whole), digits)


def _short_campaign_label(name: str, campaign_id: int, *, max_len: int = 28) -> str:
    text = (name or '').strip() or f'#{campaign_id}'
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + '…'


def _campaign_row_from_funnel(row: Dict[str, Any]) -> Dict[str, Any]:
    funnel = row.get('funnel') or {}
    attr = row.get('attribution') or {}
    accepted = int(funnel.get('accepted', 0) or 0)
    clicked = int(funnel.get('clicked', 0) or 0)
    registered = int(funnel.get('registered', 0) or 0)
    paid = int(funnel.get('paid', 0) or 0)
    revenue = int(attr.get('revenue', 0) or 0)
    sms_cost = int(attr.get('sms_cost', 0) or 0)
    cid = int(row.get('campaign_id') or 0)
    return {
        'id': cid,
        'label': _short_campaign_label(row.get('name') or '', cid),
        'name': row.get('name') or '',
        'status': row.get('status') or '',
        'status_display': row.get('status_display') or '',
        'is_pilot': bool(row.get('is_pilot')),
        'eligible': int(funnel.get('eligible', 0) or 0),
        'enrolled': int(funnel.get('enrolled_total', 0) or 0),
        'accepted': accepted,
        'clicked': clicked,
        'registered': registered,
        'paid': paid,
        'revenue': revenue,
        'sms_cost': sms_cost,
        'cac': attr.get('cac'),
        'roas': attr.get('roas'),
        'ctr': _rate(clicked, accepted),
        'click_to_reg': _rate(registered, clicked),
        'reg_to_paid': _rate(paid, registered),
        'overall_cvr': _rate(paid, accepted),
    }


def _build_funnel_steps(totals: Dict[str, int]) -> list[Dict[str, Any]]:
    steps: list[Dict[str, Any]] = []
    top_value = 0
    prev_value = 0
    for idx, (key, label, color) in enumerate(FUNNEL_STEP_DEFS):
        value = int(totals.get(key, 0) or 0)
        if idx == 0:
            top_value = value or 1
        steps.append({
            'key': key,
            'label': label,
            'value': value,
            'color': color,
            'share_of_top': _rate(value, top_value),
            'step_conversion': _rate(value, prev_value) if idx else 100.0,
            'drop_from_prev': round(100 - _rate(value, prev_value), 1) if idx and prev_value else 0.0,
        })
        if value:
            prev_value = value
    return steps


def campaign_funnel(campaign: LeadCampaign) -> Dict[str, Any]:
    enroll_qs = CampaignEnrollment.objects.filter(campaign=campaign)
    lead_ids = enroll_qs.exclude(
        status=CampaignEnrollment.Status.HOLD,
    ).values_list('lead_id', flat=True)

    leads = MarketingLead.objects.filter(id__in=lead_ids).count()
    eligible = enroll_qs.filter(status=CampaignEnrollment.Status.ACTIVE).count()
    # HOLD هم در پایلوت شمرده می‌شود ولی eligible برای ارسال نیست
    enrolled_total = enroll_qs.count()

    msgs = CampaignMessage.objects.filter(campaign=campaign)
    requested = msgs.exclude(status=CampaignMessage.Status.SKIPPED).count()
    accepted = msgs.filter(
        status__in=(
            CampaignMessage.Status.PROVIDER_ACCEPTED,
            CampaignMessage.Status.DELIVERED,
        )
    ).count()
    delivered = msgs.filter(status=CampaignMessage.Status.DELIVERED).count()

    clicked_leads = (
        LeadTouchpoint.objects.filter(
            campaign=campaign,
            event_type=LeadTouchpoint.EventType.CLICK,
        )
        .values('lead_id')
        .distinct()
        .count()
    )

    acq = LeadAttribution.objects.filter(
        campaign=campaign,
        axis=LeadAttribution.Axis.ACQUISITION,
        touch_model=LeadAttribution.TouchModel.LAST,
    )
    registered = acq.count()
    registered_direct = acq.filter(attribution_kind=LeadAttribution.Kind.DIRECT).count()
    registered_matched = acq.filter(attribution_kind=LeadAttribution.Kind.MATCHED).count()

    # Conversion ممکن است روی کمپین activation باشد؛ برای گزارش کمپین جذب از leadهای همین کمپین
    conv = LeadAttribution.objects.filter(
        lead_id__in=lead_ids,
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.LAST,
    )
    paid = conv.count()
    paid_direct = conv.filter(attribution_kind=LeadAttribution.Kind.DIRECT).count()
    paid_matched = conv.filter(attribution_kind=LeadAttribution.Kind.MATCHED).count()
    revenue = conv.aggregate(s=Sum('revenue_amount'))['s'] or 0

    cost = msgs.filter(
        status__in=(
            CampaignMessage.Status.PROVIDER_ACCEPTED,
            CampaignMessage.Status.DELIVERED,
        )
    ).aggregate(s=Sum('sms_cost_snapshot'))['s'] or 0

    activated = LeadTouchpoint.objects.filter(
        lead_id__in=lead_ids,
        event_type=LeadTouchpoint.EventType.WORKSPACE_LOGIN,
    ).values('lead_id').distinct().count()
    checkout = LeadTouchpoint.objects.filter(
        lead_id__in=lead_ids,
        event_type=LeadTouchpoint.EventType.CHECKOUT_START,
    ).values('lead_id').distinct().count()
    licensed = LeadTouchpoint.objects.filter(
        lead_id__in=lead_ids,
        event_type=LeadTouchpoint.EventType.LICENSED,
    ).values('lead_id').distinct().count()

    cac = int(cost / paid) if paid else None
    roas = float(Decimal(revenue) / Decimal(cost)) if cost and revenue else None

    variant_rows = []
    for variant in campaign.variants.all().order_by('key'):
        v_enrolls = enroll_qs.filter(assigned_variant=variant).exclude(
            status=CampaignEnrollment.Status.HOLD,
        )
        v_lead_ids = list(v_enrolls.values_list('lead_id', flat=True))
        v_accepted = msgs.filter(
            variant=variant,
            status__in=(
                CampaignMessage.Status.PROVIDER_ACCEPTED,
                CampaignMessage.Status.DELIVERED,
            ),
        ).count()
        v_clicks = (
            LeadTouchpoint.objects.filter(
                variant=variant,
                event_type=LeadTouchpoint.EventType.CLICK,
            )
            .values('lead_id')
            .distinct()
            .count()
        )
        v_reg = LeadAttribution.objects.filter(
            variant=variant,
            axis=LeadAttribution.Axis.ACQUISITION,
            touch_model=LeadAttribution.TouchModel.LAST,
        ).count()
        v_paid = LeadAttribution.objects.filter(
            lead_id__in=v_lead_ids,
            axis=LeadAttribution.Axis.CONVERSION,
            touch_model=LeadAttribution.TouchModel.LAST,
        ).count()
        variant_rows.append({
            'key': variant.key,
            'name': variant.name,
            'enrolled': v_enrolls.count(),
            'accepted': v_accepted,
            'clicked': v_clicks,
            'registered': v_reg,
            'paid': v_paid,
        })

    return {
        'campaign_id': campaign.pk,
        'name': campaign.name,
        'kind': campaign.kind,
        'kind_display': campaign.get_kind_display(),
        'status': campaign.status,
        'status_display': campaign.get_status_display(),
        'is_pilot': campaign.is_pilot,
        'pilot_label': 'نتیجه پایلوت' if campaign.is_pilot else 'نتیجه کمپین',
        'funnel': {
            'leads': leads,
            'enrolled_total': enrolled_total,
            'eligible': eligible,
            'requested': requested,
            'accepted': accepted,  # Estimated Reach
            'estimated_reach': accepted,
            'delivered': delivered,  # فقط اگر DLR واقعی
            'clicked': clicked_leads,
            'registered': registered,
            'activated': activated,
            'checkout': checkout,
            'paid': paid,
            'licensed': licensed,
        },
        'attribution': {
            'acquisition_direct': registered_direct,
            'acquisition_phone_matched': registered_matched,
            'conversion_direct': paid_direct,
            'conversion_phone_matched': paid_matched,
            'revenue': revenue,
            'sms_cost': cost,
            'cac': cac,
            'roas': roas,
        },
        'variants': variant_rows,
        'winner_note': (
            'این نتیجه پایلوت فنی است؛ انتخاب نسخه برنده آماری نیازمند تجمیع چند منطقه یا چند بچ است.'
            if campaign.is_pilot
            else ''
        ),
    }


def overview_stats() -> Dict[str, Any]:
    acq_lead_ids = CampaignEnrollment.objects.filter(
        campaign__kind=LeadCampaign.Kind.ACQUISITION,
    ).values_list('lead_id', flat=True).distinct()

    accepted_sms = CampaignMessage.objects.filter(
        campaign__kind=LeadCampaign.Kind.ACQUISITION,
        status__in=(
            CampaignMessage.Status.PROVIDER_ACCEPTED,
            CampaignMessage.Status.DELIVERED,
        ),
    ).count()

    total_clicks = LeadTouchpoint.objects.filter(
        campaign__kind=LeadCampaign.Kind.ACQUISITION,
        event_type=LeadTouchpoint.EventType.CLICK,
    ).values('lead_id').distinct().count()

    purchases_qs = LeadAttribution.objects.filter(
        lead_id__in=acq_lead_ids,
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.LAST,
    )
    total_purchases = purchases_qs.count()
    purchase_revenue = purchases_qs.aggregate(s=Sum('revenue_amount'))['s'] or 0

    ctr_pct = round(100 * total_clicks / accepted_sms, 1) if accepted_sms else None
    purchase_rate_pct = None
    registered_leads = MarketingLead.objects.filter(status=MarketingLead.Status.REGISTERED).count()
    if registered_leads:
        purchase_rate_pct = round(100 * total_purchases / registered_leads, 1)

    return {
        'leads_total': MarketingLead.objects.count(),
        'leads_cold': MarketingLead.objects.filter(status=MarketingLead.Status.COLD).count(),
        'leads_engaged': MarketingLead.objects.filter(status=MarketingLead.Status.ENGAGED).count(),
        'leads_registered': MarketingLead.objects.filter(status=MarketingLead.Status.REGISTERED).count(),
        'leads_customer': MarketingLead.objects.filter(status=MarketingLead.Status.CUSTOMER).count(),
        'batches': LeadImportBatch.objects.filter(status=LeadImportBatch.Status.COMMITTED).count(),
        'campaigns_active': LeadCampaign.objects.filter(
            status__in=(LeadCampaign.Status.PILOT, LeadCampaign.Status.ACTIVE),
        ).count(),
        'total_clicks': total_clicks,
        'total_purchases': total_purchases,
        'purchase_revenue': int(purchase_revenue),
        'accepted_sms': accepted_sms,
        'ctr_pct': ctr_pct,
        'purchase_rate_pct': purchase_rate_pct,
        'now_utc': timezone.now().isoformat(),
    }


def acquisition_dashboard_charts(
    campaigns: list[LeadCampaign],
    funnels: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """داده کامل نمودارها و جدول دقیق — تجمیع کمپین‌های جذب."""
    totals = {
        'eligible': 0,
        'enrolled': 0,
        'accepted': 0,
        'clicked': 0,
        'registered': 0,
        'paid': 0,
        'revenue': 0,
        'sms_cost': 0,
    }
    variant_items: Dict[str, Dict[str, Any]] = {}

    for row in funnels:
        funnel = row.get('funnel') or {}
        attr = row.get('attribution') or {}
        totals['eligible'] += int(funnel.get('eligible', 0) or 0)
        totals['enrolled'] += int(funnel.get('enrolled_total', 0) or 0)
        totals['accepted'] += int(funnel.get('accepted', 0) or 0)
        totals['clicked'] += int(funnel.get('clicked', 0) or 0)
        totals['registered'] += int(funnel.get('registered', 0) or 0)
        totals['paid'] += int(funnel.get('paid', 0) or 0)
        totals['revenue'] += int(attr.get('revenue', 0) or 0)
        totals['sms_cost'] += int(attr.get('sms_cost', 0) or 0)

        for variant in row.get('variants') or []:
            key = variant.get('key') or '?'
            bucket = variant_items.setdefault(key, {
                'key': key,
                'name': variant.get('name') or f'نسخه {key}',
                'enrolled': 0,
                'accepted': 0,
                'clicked': 0,
                'registered': 0,
                'paid': 0,
            })
            for field in ('enrolled', 'accepted', 'clicked', 'registered', 'paid'):
                bucket[field] += int(variant.get(field, 0) or 0)

    status_labels: Dict[str, str] = dict(LeadCampaign.Status.choices)
    status_items = []
    for code, label in LeadCampaign.Status.choices:
        count = sum(1 for c in campaigns if c.status == code)
        if count:
            status_items.append({
                'code': code,
                'label': label,
                'value': count,
                'color': STATUS_CHART_COLORS.get(code, '#94a3b8'),
            })

    campaign_rows = [_campaign_row_from_funnel(row) for row in funnels]
    campaign_rows.sort(key=lambda item: item['accepted'], reverse=True)

    chart_campaigns = campaign_rows[:8]

    variant_list = []
    for key in sorted(variant_items.keys()):
        item = variant_items[key]
        accepted = item['accepted']
        clicked = item['clicked']
        registered = item['registered']
        paid = item['paid']
        variant_list.append({
            **item,
            'ctr': _rate(clicked, accepted),
            'click_to_reg': _rate(registered, clicked),
            'reg_to_paid': _rate(paid, registered),
            'overall_cvr': _rate(paid, accepted),
        })

    winner_key = None
    if len(variant_list) >= 2:
        winner_key = max(variant_list, key=lambda v: (v['paid'], v['registered'], v['clicked'])).get('key')

    funnel_steps = _build_funnel_steps(totals)
    accepted = totals['accepted']
    clicked = totals['clicked']
    registered = totals['registered']
    paid = totals['paid']
    sms_cost = totals['sms_cost']
    revenue = totals['revenue']

    return {
        'meta': {
            'campaign_count': len(campaigns),
            'reported_campaigns': len(funnels),
            'generated_at': timezone.now().isoformat(),
        },
        'summary': {
            **totals,
            'cac': int(sms_cost / paid) if paid else None,
            'roas': round(float(Decimal(revenue) / Decimal(sms_cost)), 2) if sms_cost and revenue else None,
            'ctr': _rate(clicked, accepted),
            'click_to_reg': _rate(registered, clicked),
            'reg_to_paid': _rate(paid, registered),
            'overall_cvr': _rate(paid, accepted),
        },
        'funnel_steps': funnel_steps,
        'funnel': {
            'labels': [step['label'] for step in funnel_steps],
            'values': [step['value'] for step in funnel_steps],
            'colors': [step['color'] for step in funnel_steps],
        },
        'conversion_series': {
            'labels': [step['label'] for step in funnel_steps[1:]],
            'step_rates': [step['step_conversion'] for step in funnel_steps[1:]],
            'share_rates': [step['share_of_top'] for step in funnel_steps],
        },
        'rates': {
            'click_rate': _rate(clicked, accepted),
            'register_rate': _rate(registered, clicked),
            'purchase_rate': _rate(paid, registered),
            'overall_conversion': _rate(paid, accepted),
        },
        'status': {
            'labels': [item['label'] for item in status_items],
            'values': [item['value'] for item in status_items],
            'colors': [item['color'] for item in status_items],
            'items': status_items,
            'total': len(campaigns),
        },
        'campaigns': chart_campaigns,
        'campaign_table': campaign_rows,
        'variants': {
            'items': variant_list,
            'winner': winner_key,
            'labels': [item['key'] for item in variant_list],
            'accepted': [item['accepted'] for item in variant_list],
            'clicked': [item['clicked'] for item in variant_list],
            'registered': [item['registered'] for item in variant_list],
            'paid': [item['paid'] for item in variant_list],
        },
        'totals': totals,
    }
