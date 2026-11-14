"""داشبورد قیف Lead Acquisition."""
from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from typing import Any, Dict, Optional

from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.services.admin_dashboard import (
    ALL_TIME_DAYS,
    _range_label_fa,
    effective_range_days,
    is_all_time_range,
    _date_range,
)
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
TOMAN_TO_RIAL = 10


def _revenue_toman_to_rial(toman: int | float) -> int:
    return int(toman or 0) * TOMAN_TO_RIAL


def period_start_at(days: int | None = None) -> datetime | None:
    """ابتدای بازهٔ پنل ادمین (تقویم محلی) — None یعنی کل بازه."""
    if days is None or is_all_time_range(int(days)):
        return None
    start_date, _ = _date_range(int(days))
    tz = timezone.get_current_timezone()
    start = datetime.combine(start_date, time.min)
    if timezone.is_naive(start):
        return timezone.make_aware(start, tz)
    return start


def _conversion_time_q(*, since: datetime | None) -> Q:
    if since is None:
        return Q()
    return Q(converted_at__gte=since) | Q(converted_at__isnull=True, created_at__gte=since)


def _registration_time_q(*, since: datetime | None) -> Q:
    if since is None:
        return Q()
    return Q(registered_at__gte=since) | Q(registered_at__isnull=True, created_at__gte=since)


def acquisition_campaigns_for_dashboard(
    *,
    days: int = ALL_TIME_DAYS,
    limit: int = 50,
) -> list[LeadCampaign]:
    """کمپین‌های جذب برای داشبورد — در بازهٔ زمانی، فقط کمپین‌های دارای فعالیت."""
    qs = LeadCampaign.objects.filter(kind=LeadCampaign.Kind.ACQUISITION).select_related(
        'lead_list',
        'created_by',
    )
    since = period_start_at(days)
    if since is None:
        return list(qs.order_by('-created_at')[:limit])
    msg_ids = CampaignMessage.objects.filter(
        campaign__kind=LeadCampaign.Kind.ACQUISITION,
        requested_at__gte=since,
    ).values_list('campaign_id', flat=True)
    tp_ids = LeadTouchpoint.objects.filter(
        campaign__kind=LeadCampaign.Kind.ACQUISITION,
        created_at__gte=since,
    ).values_list('campaign_id', flat=True)
    attr_ids = LeadAttribution.objects.filter(
        campaign__kind=LeadCampaign.Kind.ACQUISITION,
    ).filter(_conversion_time_q(since=since) | _registration_time_q(since=since)).values_list(
        'campaign_id', flat=True,
    )
    enroll_ids = CampaignEnrollment.objects.filter(
        campaign__kind=LeadCampaign.Kind.ACQUISITION,
        enrolled_at__gte=since,
    ).values_list('campaign_id', flat=True)
    active_ids = set(msg_ids) | set(tp_ids) | set(attr_ids) | set(enroll_ids)
    return list(
        qs.filter(Q(pk__in=active_ids) | Q(created_at__gte=since))
        .distinct()
        .order_by('-created_at')[:limit]
    )


def _lead_ids_for_acquisition_campaign(campaign: LeadCampaign) -> set[int]:
    """سرنخ‌های کمپین جذب: ثبت‌نام‌شده + نسبت‌دهی acquisition."""
    enroll_ids = set(
        CampaignEnrollment.objects.filter(campaign=campaign)
        .exclude(status=CampaignEnrollment.Status.HOLD)
        .values_list('lead_id', flat=True)
    )
    acq_ids = set(
        LeadAttribution.objects.filter(
            campaign=campaign,
            axis=LeadAttribution.Axis.ACQUISITION,
            touch_model=LeadAttribution.TouchModel.LAST,
        ).values_list('lead_id', flat=True)
    )
    return enroll_ids | acq_ids


def _bulk_acquisition_campaign_id_for_leads(lead_ids: list[int]) -> dict[int, int]:
    """نقشه lead_id → کمپین جذب (آخرین ثبت‌نام، سپس نسبت acquisition)."""
    if not lead_ids:
        return {}
    mapping: dict[int, int] = {}
    enroll_rows = (
        CampaignEnrollment.objects.filter(
            lead_id__in=lead_ids,
            campaign__kind=LeadCampaign.Kind.ACQUISITION,
        )
        .exclude(status=CampaignEnrollment.Status.HOLD)
        .order_by('lead_id', '-enrolled_at')
        .values_list('lead_id', 'campaign_id')
    )
    for lead_id, campaign_id in enroll_rows:
        if lead_id not in mapping:
            mapping[lead_id] = campaign_id
    missing = [lid for lid in lead_ids if lid not in mapping]
    if missing:
        attr_rows = (
            LeadAttribution.objects.filter(
                lead_id__in=missing,
                axis=LeadAttribution.Axis.ACQUISITION,
                touch_model=LeadAttribution.TouchModel.LAST,
                campaign__kind=LeadCampaign.Kind.ACQUISITION,
            )
            .order_by('lead_id', '-created_at')
            .values_list('lead_id', 'campaign_id')
        )
        for lead_id, campaign_id in attr_rows:
            if lead_id not in mapping and campaign_id:
                mapping[lead_id] = campaign_id
    return mapping


def conversion_stats_by_acquisition_campaign(
    campaign_ids: list[int],
    *,
    days: int = ALL_TIME_DAYS,
) -> dict[int, dict[str, int]]:
    """تعداد خرید و درآمد (ریال) به ازای هر کمپین جذب."""
    cid_set = set(campaign_ids)
    result = {cid: {'paid': 0, 'revenue': 0} for cid in cid_set}
    if not cid_set:
        return result

    convs_qs = LeadAttribution.objects.filter(
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.LAST,
    )
    since = period_start_at(days)
    if since is not None:
        convs_qs = convs_qs.filter(_conversion_time_q(since=since))
    convs = list(convs_qs.values_list('lead_id', 'revenue_amount', 'campaign_id'))
    if not convs:
        return result

    lead_ids = list({row[0] for row in convs})
    lead_to_campaign = _bulk_acquisition_campaign_id_for_leads(lead_ids)
    acq_campaign_ids = set(
        LeadCampaign.objects.filter(
            pk__in={row[2] for row in convs if row[2]},
            kind=LeadCampaign.Kind.ACQUISITION,
        ).values_list('pk', flat=True)
    )

    for lead_id, revenue_toman, conv_campaign_id in convs:
        acq_cid = None
        if conv_campaign_id and conv_campaign_id in acq_campaign_ids:
            acq_cid = conv_campaign_id
        else:
            acq_cid = lead_to_campaign.get(lead_id)
        if acq_cid in cid_set:
            result[acq_cid]['paid'] += 1
            result[acq_cid]['revenue'] += _revenue_toman_to_rial(revenue_toman or 0)
    return result


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
    created_at = row.get('created_at')
    return {
        'id': cid,
        'created_at': created_at,
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


def campaign_funnel(campaign: LeadCampaign, *, days: int = ALL_TIME_DAYS) -> Dict[str, Any]:
    since = period_start_at(days)
    all_campaign_lead_ids = _lead_ids_for_acquisition_campaign(campaign)

    enroll_qs = CampaignEnrollment.objects.filter(campaign=campaign)
    if since is not None:
        enroll_qs = enroll_qs.filter(enrolled_at__gte=since)

    period_lead_ids = all_campaign_lead_ids
    if since is not None:
        period_lead_ids = set(
            enroll_qs.values_list('lead_id', flat=True),
        ) | set(
            CampaignMessage.objects.filter(campaign=campaign, requested_at__gte=since).values_list(
                'lead_id', flat=True,
            ),
        )

    leads = len(period_lead_ids)
    eligible = enroll_qs.filter(status=CampaignEnrollment.Status.ACTIVE).count()
    # HOLD هم در پایلوت شمرده می‌شود ولی eligible برای ارسال نیست
    enrolled_total = enroll_qs.count()

    msgs = CampaignMessage.objects.filter(campaign=campaign)
    if since is not None:
        msgs = msgs.filter(requested_at__gte=since)
    requested = msgs.exclude(status=CampaignMessage.Status.SKIPPED).count()
    accepted = msgs.filter(
        status__in=(
            CampaignMessage.Status.PROVIDER_ACCEPTED,
            CampaignMessage.Status.DELIVERED,
        )
    ).count()
    delivered = msgs.filter(status=CampaignMessage.Status.DELIVERED).count()

    tp_base = LeadTouchpoint.objects.filter(campaign=campaign)
    if since is not None:
        tp_base = tp_base.filter(created_at__gte=since)
    clicked_leads = (
        tp_base.filter(event_type=LeadTouchpoint.EventType.CLICK)
        .values('lead_id')
        .distinct()
        .count()
    )

    acq = LeadAttribution.objects.filter(
        campaign=campaign,
        axis=LeadAttribution.Axis.ACQUISITION,
        touch_model=LeadAttribution.TouchModel.LAST,
    )
    if since is not None:
        acq = acq.filter(_registration_time_q(since=since))
    registered = acq.count()
    registered_direct = acq.filter(attribution_kind=LeadAttribution.Kind.DIRECT).count()
    registered_matched = acq.filter(attribution_kind=LeadAttribution.Kind.MATCHED).count()

    # Conversion ممکن است روی کمپین activation باشد؛ برای گزارش کمپین جذب از leadهای همین کمپین
    conv = LeadAttribution.objects.filter(
        lead_id__in=all_campaign_lead_ids,
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.LAST,
    )
    if since is not None:
        conv = conv.filter(_conversion_time_q(since=since))
    paid = conv.count()
    paid_direct = conv.filter(attribution_kind=LeadAttribution.Kind.DIRECT).count()
    paid_matched = conv.filter(attribution_kind=LeadAttribution.Kind.MATCHED).count()
    revenue_toman = conv.aggregate(s=Sum('revenue_amount'))['s'] or 0
    revenue = _revenue_toman_to_rial(revenue_toman)

    cost = msgs.filter(
        status__in=(
            CampaignMessage.Status.PROVIDER_ACCEPTED,
            CampaignMessage.Status.DELIVERED,
        )
    ).aggregate(s=Sum('sms_cost_snapshot'))['s'] or 0

    tp_lead = LeadTouchpoint.objects.filter(lead_id__in=all_campaign_lead_ids)
    if since is not None:
        tp_lead = tp_lead.filter(created_at__gte=since)
    activated = tp_lead.filter(event_type=LeadTouchpoint.EventType.WORKSPACE_LOGIN).values(
        'lead_id',
    ).distinct().count()
    checkout = tp_lead.filter(event_type=LeadTouchpoint.EventType.CHECKOUT_START).values(
        'lead_id',
    ).distinct().count()
    licensed = tp_lead.filter(event_type=LeadTouchpoint.EventType.LICENSED).values(
        'lead_id',
    ).distinct().count()

    cac = int(cost / paid) if paid else None
    roas = float(Decimal(revenue) / Decimal(cost)) if cost and revenue else None

    variant_rows = []
    for variant in campaign.variants.all().order_by('key'):
        v_enrolls = enroll_qs.filter(assigned_variant=variant).exclude(
            status=CampaignEnrollment.Status.HOLD,
        )
        v_lead_ids = list(v_enrolls.values_list('lead_id', flat=True))
        v_msgs = msgs.filter(variant=variant)
        v_accepted = v_msgs.filter(
            status__in=(
                CampaignMessage.Status.PROVIDER_ACCEPTED,
                CampaignMessage.Status.DELIVERED,
            ),
        ).count()
        v_tp = LeadTouchpoint.objects.filter(
            variant=variant,
            event_type=LeadTouchpoint.EventType.CLICK,
        )
        if since is not None:
            v_tp = v_tp.filter(created_at__gte=since)
        v_clicks = v_tp.values('lead_id').distinct().count()
        v_reg_qs = LeadAttribution.objects.filter(
            variant=variant,
            axis=LeadAttribution.Axis.ACQUISITION,
            touch_model=LeadAttribution.TouchModel.LAST,
        )
        if since is not None:
            v_reg_qs = v_reg_qs.filter(_registration_time_q(since=since))
        v_reg = v_reg_qs.count()
        v_paid_qs = LeadAttribution.objects.filter(
            lead_id__in=v_lead_ids,
            axis=LeadAttribution.Axis.CONVERSION,
            touch_model=LeadAttribution.TouchModel.LAST,
        )
        if since is not None:
            v_paid_qs = v_paid_qs.filter(_conversion_time_q(since=since))
        v_paid = v_paid_qs.count()
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
        'created_at': campaign.created_at.isoformat() if campaign.created_at else None,
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


def overview_stats(*, days: int = ALL_TIME_DAYS) -> Dict[str, Any]:
    since = period_start_at(days)
    msgs_acq = CampaignMessage.objects.filter(campaign__kind=LeadCampaign.Kind.ACQUISITION)
    if since is not None:
        msgs_acq = msgs_acq.filter(requested_at__gte=since)
    accepted_sms = msgs_acq.filter(
        status__in=(
            CampaignMessage.Status.PROVIDER_ACCEPTED,
            CampaignMessage.Status.DELIVERED,
        ),
    ).count()
    sms_requested = msgs_acq.exclude(status=CampaignMessage.Status.SKIPPED).count()
    sms_delivered = msgs_acq.filter(status=CampaignMessage.Status.DELIVERED).count()
    sms_failed = msgs_acq.filter(status=CampaignMessage.Status.FAILED).count()
    sms_pending = msgs_acq.filter(status=CampaignMessage.Status.REQUESTED).count()

    tp_clicks = LeadTouchpoint.objects.filter(
        campaign__kind=LeadCampaign.Kind.ACQUISITION,
        event_type=LeadTouchpoint.EventType.CLICK,
    )
    if since is not None:
        tp_clicks = tp_clicks.filter(created_at__gte=since)
    total_clicks = tp_clicks.values('lead_id').distinct().count()

    purchases_qs = LeadAttribution.objects.filter(
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.LAST,
    )
    if since is not None:
        purchases_qs = purchases_qs.filter(_conversion_time_q(since=since))
    total_purchases = purchases_qs.count()
    purchase_revenue_toman = purchases_qs.aggregate(s=Sum('revenue_amount'))['s'] or 0
    purchase_revenue = _revenue_toman_to_rial(purchase_revenue_toman)

    leads_qs = MarketingLead.objects.all()
    if since is not None:
        leads_qs = leads_qs.filter(created_at__gte=since)
    leads_total = leads_qs.count()
    leads_cold = leads_qs.filter(status=MarketingLead.Status.COLD).count()
    leads_engaged = leads_qs.filter(status=MarketingLead.Status.ENGAGED).count()
    if since is not None:
        leads_registered = LeadAttribution.objects.filter(
            axis=LeadAttribution.Axis.ACQUISITION,
            touch_model=LeadAttribution.TouchModel.LAST,
        ).filter(_registration_time_q(since=since)).values('lead_id').distinct().count()
        leads_customer = purchases_qs.values('lead_id').distinct().count()
    else:
        leads_registered = MarketingLead.objects.filter(status=MarketingLead.Status.REGISTERED).count()
        leads_customer = MarketingLead.objects.filter(status=MarketingLead.Status.CUSTOMER).count()

    ctr_pct = round(100 * total_clicks / accepted_sms, 1) if accepted_sms else None
    registration_rate_pct = round(100 * leads_registered / leads_total, 1) if leads_total else None
    engaged_to_reg_pct = round(100 * leads_registered / leads_engaged, 1) if leads_engaged else None
    sms_accept_rate_pct = round(100 * accepted_sms / sms_requested, 1) if sms_requested else None
    purchase_rate_pct = round(100 * total_purchases / leads_registered, 1) if leads_registered else None

    acq_campaigns = LeadCampaign.objects.filter(kind=LeadCampaign.Kind.ACQUISITION)
    if since is not None:
        acq_campaigns = acq_campaigns.filter(created_at__gte=since)
    campaigns_total = acq_campaigns.count()
    active_qs = LeadCampaign.objects.filter(
        kind=LeadCampaign.Kind.ACQUISITION,
        status__in=(LeadCampaign.Status.PILOT, LeadCampaign.Status.ACTIVE),
    )
    if since is not None:
        active_qs = active_qs.filter(
            Q(created_at__gte=since)
            | Q(messages__requested_at__gte=since)
            | Q(touchpoints__created_at__gte=since)
        ).distinct()
    campaigns_active = active_qs.count()

    batches_qs = LeadImportBatch.objects.filter(status=LeadImportBatch.Status.COMMITTED)
    if since is not None:
        batches_qs = batches_qs.filter(
            Q(committed_at__gte=since) | Q(committed_at__isnull=True, created_at__gte=since),
        )

    return {
        'range_days': days,
        'range_label': _range_label_fa(days),
        'range_days_effective': effective_range_days(days),
        'leads_total': leads_total,
        'leads_cold': leads_cold,
        'leads_engaged': leads_engaged,
        'leads_registered': leads_registered,
        'leads_customer': leads_customer,
        'batches': batches_qs.count(),
        'campaigns_total': campaigns_total,
        'campaigns_active': campaigns_active,
        'total_clicks': total_clicks,
        'total_purchases': total_purchases,
        'purchase_revenue': int(purchase_revenue),
        'purchase_revenue_toman': int(purchase_revenue_toman),
        'accepted_sms': accepted_sms,
        'sms_requested': sms_requested,
        'sms_delivered': sms_delivered,
        'sms_failed': sms_failed,
        'sms_pending': sms_pending,
        'ctr_pct': ctr_pct,
        'registration_rate_pct': registration_rate_pct,
        'engaged_to_reg_pct': engaged_to_reg_pct,
        'sms_accept_rate_pct': sms_accept_rate_pct,
        'purchase_rate_pct': purchase_rate_pct,
        'now_utc': timezone.now().isoformat(),
    }


def acquisition_dashboard_charts(
    campaigns: list[LeadCampaign],
    funnels: list[Dict[str, Any]],
    *,
    days: int = ALL_TIME_DAYS,
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

    campaign_ids = [int(c.pk) for c in campaigns]
    conv_by_campaign = conversion_stats_by_acquisition_campaign(campaign_ids, days=days)

    campaign_rows = []
    for row in funnels:
        item = _campaign_row_from_funnel(row)
        stats = conv_by_campaign.get(item['id'], {})
        if stats:
            item['paid'] = int(stats.get('paid', 0) or 0)
            item['revenue'] = int(stats.get('revenue', 0) or 0)
            sms_cost = int(item.get('sms_cost', 0) or 0)
            paid = item['paid']
            revenue = item['revenue']
            item['cac'] = int(sms_cost / paid) if paid else None
            item['roas'] = (
                round(float(Decimal(revenue) / Decimal(sms_cost)), 2)
                if sms_cost and revenue else None
            )
            item['reg_to_paid'] = _rate(paid, item['registered'])
            item['overall_cvr'] = _rate(paid, item['accepted'])
        campaign_rows.append(item)

    totals['paid'] = sum(int(r.get('paid', 0) or 0) for r in campaign_rows)
    totals['revenue'] = sum(int(r.get('revenue', 0) or 0) for r in campaign_rows)
    campaign_rows.sort(key=lambda item: int(item.get('id') or 0), reverse=True)

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
            'range_days': days,
            'range_label': _range_label_fa(days),
            'range_days_effective': effective_range_days(days),
            'is_all_time': is_all_time_range(days),
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
        'table_totals': {
            'label': 'جمع کل',
            'campaign_count': len(campaign_rows),
            'eligible': totals['eligible'],
            'enrolled': totals['enrolled'],
            'accepted': accepted,
            'clicked': clicked,
            'registered': registered,
            'paid': paid,
            'revenue': revenue,
            'sms_cost': sms_cost,
            'ctr': _rate(clicked, accepted),
            'overall_cvr': _rate(paid, accepted),
            'cac': int(sms_cost / paid) if paid else None,
            'roas': round(float(Decimal(revenue) / Decimal(sms_cost)), 2) if sms_cost and revenue else None,
        },
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


def leads_recent_for_ui(*, limit: int = 40, days: int = ALL_TIME_DAYS) -> dict[str, Any]:
    """سرنخ‌های اخیر برای تب lac-leads — داده غنی و فشرده برای جدول UI."""
    from accounts.services.lead_import import display_district_for_lead, listing_category_display_fa
    qs = MarketingLead.objects.select_related('first_batch', 'matched_user')
    since = period_start_at(days)
    if since is not None:
        qs = qs.filter(Q(updated_at__gte=since) | Q(created_at__gte=since))
    qs = qs.order_by('-updated_at', '-pk')[:limit]
    rows: list[dict[str, Any]] = []
    stats = {
        'agency': 0,
        'consultant': 0,
        'unknown': 0,
        'engaged': 0,
        'filing_user': 0,
    }
    for lead in qs:
        conf = float(lead.classification_confidence or 0)
        if conf >= 0.75:
            conf_tier = 'high'
        elif conf >= 0.45:
            conf_tier = 'mid'
        else:
            conf_tier = 'low'

        if lead.lead_type == MarketingLead.LeadType.AGENCY:
            stats['agency'] += 1
        elif lead.lead_type == MarketingLead.LeadType.CONSULTANT:
            stats['consultant'] += 1
        else:
            stats['unknown'] += 1
        if lead.status == MarketingLead.Status.ENGAGED:
            stats['engaged'] += 1
        if lead.matched_user_id:
            stats['filing_user'] += 1

        district = display_district_for_lead(lead)
        loc_parts = [p.strip() for p in (lead.city or '', district or '') if (p or '').strip()]
        location_label = ' · '.join(loc_parts) if loc_parts else '—'
        category_label = listing_category_display_fa(lead.listing_category)
        extra_districts = len(lead.districts_json or [])
        if district and extra_districts:
            extra_districts = max(0, extra_districts - 1)

        rows.append({
            'lead': lead,
            'confidence_pct': int(round(conf * 100)),
            'confidence_tier': conf_tier,
            'location_label': location_label,
            'category_label': category_label,
            'extra_districts': extra_districts,
            'has_filing_user': bool(lead.matched_user_id),
            'activity_at': lead.last_seen_at or lead.updated_at or lead.created_at,
            'search_blob': ' '.join(
                bit for bit in (
                    lead.phone_normalized,
                    lead.display_name,
                    lead.city,
                    district,
                    category_label,
                ) if bit
            ),
        })

    return {
        'rows': rows,
        'stats': stats,
        'shown': len(rows),
        'range_label': _range_label_fa(days),
    }
