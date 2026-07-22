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
        'now_utc': timezone.now().isoformat(),
    }
