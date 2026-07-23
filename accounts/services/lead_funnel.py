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


def _short_campaign_label(name: str, campaign_id: int, *, max_len: int = 22) -> str:
    text = (name or '').strip() or f'#{campaign_id}'
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + '…'


def acquisition_dashboard_charts(
    campaigns: list[LeadCampaign],
    funnels: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """داده نمودارهای نمای کلی — تجمیع کمپین‌های جذب."""
    agg = {
        'eligible': 0,
        'accepted': 0,
        'clicked': 0,
        'registered': 0,
        'paid': 0,
    }
    variant_totals: Dict[str, Dict[str, int]] = {}

    for row in funnels:
        funnel = row.get('funnel') or {}
        for key in agg:
            agg[key] += int(funnel.get(key, 0) or 0)
        for variant in row.get('variants') or []:
            key = variant.get('key') or '?'
            bucket = variant_totals.setdefault(key, {
                'enrolled': 0,
                'accepted': 0,
                'clicked': 0,
                'registered': 0,
                'paid': 0,
            })
            for field in bucket:
                bucket[field] += int(variant.get(field, 0) or 0)

    status_labels: Dict[str, str] = dict(LeadCampaign.Status.choices)
    status_counts: Dict[str, int] = {code: 0 for code in status_labels}
    for campaign in campaigns:
        status_counts[campaign.status] = status_counts.get(campaign.status, 0) + 1

    top_rows = sorted(
        funnels,
        key=lambda item: int((item.get('funnel') or {}).get('accepted', 0) or 0),
        reverse=True,
    )[:10]

    campaign_rows = []
    for row in top_rows:
        funnel = row.get('funnel') or {}
        campaign_rows.append({
            'id': row.get('campaign_id'),
            'label': _short_campaign_label(row.get('name') or '', row.get('campaign_id') or 0),
            'accepted': int(funnel.get('accepted', 0) or 0),
            'clicked': int(funnel.get('clicked', 0) or 0),
            'registered': int(funnel.get('registered', 0) or 0),
            'paid': int(funnel.get('paid', 0) or 0),
        })

    accepted = agg['accepted']
    clicked = agg['clicked']
    registered = agg['registered']
    paid = agg['paid']

    return {
        'funnel': {
            'labels': ['ارسال پذیرفته', 'کلیک', 'ثبت‌نام', 'خرید'],
            'values': [accepted, clicked, registered, paid],
            'colors': ['#0d9488', '#0891b2', '#6366f1', '#e11d48'],
        },
        'rates': {
            'click_rate': round(100 * clicked / accepted, 1) if accepted else 0,
            'register_rate': round(100 * registered / clicked, 1) if clicked else 0,
            'purchase_rate': round(100 * paid / registered, 1) if registered else 0,
            'overall_conversion': round(100 * paid / accepted, 1) if accepted else 0,
        },
        'status': {
            'labels': [status_labels.get(code, code) for code in status_counts if status_counts[code]],
            'values': [status_counts[code] for code in status_counts if status_counts[code]],
        },
        'campaigns': campaign_rows,
        'variants': {
            'labels': sorted(variant_totals.keys()),
            'accepted': [variant_totals[k]['accepted'] for k in sorted(variant_totals.keys())],
            'clicked': [variant_totals[k]['clicked'] for k in sorted(variant_totals.keys())],
            'registered': [variant_totals[k]['registered'] for k in sorted(variant_totals.keys())],
            'paid': [variant_totals[k]['paid'] for k in sorted(variant_totals.keys())],
        },
        'totals': agg,
    }
