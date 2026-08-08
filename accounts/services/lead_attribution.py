"""Attribution جذب و تبدیل برای Lead Acquisition."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from accounts.models import (
    CampaignEnrollment,
    CampaignMessage,
    LeadAttribution,
    LeadCampaign,
    LeadTouchpoint,
    MarketingLead,
)
from accounts.phone_utils import normalize_phone
from accounts.services.lead_tokens import COOKIE_NAME
from accounts.services.user_activation import enroll_user_in_activation_campaign


ACQUISITION_WINDOW_DAYS = 7
CONVERSION_WINDOW_DAYS = 30


def _message_from_cookie_token(token: str) -> Optional[CampaignMessage]:
    token = (token or '').strip()
    if not token:
        return None
    return (
        CampaignMessage.objects.select_related(
            'lead', 'campaign', 'variant', 'step', 'enrollment',
        )
        .filter(click_token=token)
        .first()
    )


def record_touchpoint(
    *,
    lead: MarketingLead,
    event_type: str,
    message: Optional[CampaignMessage] = None,
    user=None,
    ip_hash: str = '',
    user_agent: str = '',
    metadata: Optional[dict] = None,
) -> LeadTouchpoint:
    tp = LeadTouchpoint.objects.create(
        lead=lead,
        message=message,
        campaign=message.campaign if message else None,
        variant=message.variant if message else None,
        step=message.step if message else None,
        user=user,
        event_type=event_type,
        ip_hash=ip_hash or '',
        user_agent=user_agent or '',
        metadata=metadata or {},
    )
    if event_type in (LeadTouchpoint.EventType.CLICK, LeadTouchpoint.EventType.LANDING_VIEW):
        if lead.status == MarketingLead.Status.COLD:
            lead.status = MarketingLead.Status.ENGAGED
            lead.save(update_fields=['status', 'updated_at'])
        try:
            from accounts.services.growth_journey import on_click_landing
            on_click_landing(lead=lead, message=message)
        except Exception:
            pass
    return tp


def _find_last_accepted_message(
    lead: MarketingLead,
    *,
    kind: str,
    within_days: int | None = None,
) -> Optional[CampaignMessage]:
    qs = CampaignMessage.objects.filter(
        lead=lead,
        status__in=(
            CampaignMessage.Status.PROVIDER_ACCEPTED,
            CampaignMessage.Status.DELIVERED,
        ),
    ).select_related('campaign', 'variant', 'step', 'enrollment')
    if kind == LeadCampaign.Kind.ACQUISITION:
        qs = qs.filter(campaign__kind=LeadCampaign.Kind.ACQUISITION)
    elif kind == LeadCampaign.Kind.ACTIVATION:
        qs = qs.filter(campaign__kind=LeadCampaign.Kind.ACTIVATION)
    if within_days is not None:
        qs = qs.filter(requested_at__gte=timezone.now() - timedelta(days=within_days))
    return qs.order_by('-requested_at').first()


def _find_phone_matched_message(
    lead: MarketingLead,
    *,
    kind: str,
    within_days: int,
) -> Optional[CampaignMessage]:
    return _find_last_accepted_message(lead, kind=kind, within_days=within_days)


def _acquisition_campaign_for_lead(lead: MarketingLead) -> Optional[LeadCampaign]:
    enroll = (
        CampaignEnrollment.objects.filter(
            lead=lead,
            campaign__kind=LeadCampaign.Kind.ACQUISITION,
        )
        .select_related('campaign')
        .order_by('-enrolled_at')
        .first()
    )
    if enroll:
        return enroll.campaign
    attr = (
        LeadAttribution.objects.filter(
            lead=lead,
            axis=LeadAttribution.Axis.ACQUISITION,
            touch_model=LeadAttribution.TouchModel.LAST,
        )
        .select_related('campaign')
        .first()
    )
    return attr.campaign if attr and attr.campaign_id else None


def _resolve_conversion_message(
    lead: MarketingLead,
    *,
    cookie_message: Optional[CampaignMessage] = None,
) -> tuple[Optional[CampaignMessage], str]:
    """پیام مرجع conversion — پنجره کوتاه، سپس هر پیام جذب/فعال‌سازی."""
    if cookie_message and cookie_message.lead_id == lead.pk:
        if cookie_message.campaign.kind == LeadCampaign.Kind.ACTIVATION:
            return cookie_message, LeadAttribution.Kind.DIRECT
        return cookie_message, LeadAttribution.Kind.MATCHED

    act = _find_last_accepted_message(
        lead, kind=LeadCampaign.Kind.ACTIVATION, within_days=CONVERSION_WINDOW_DAYS,
    )
    if act:
        return act, LeadAttribution.Kind.MATCHED

    acq = _find_last_accepted_message(
        lead, kind=LeadCampaign.Kind.ACQUISITION, within_days=CONVERSION_WINDOW_DAYS,
    )
    if acq:
        return acq, LeadAttribution.Kind.MATCHED

    acq_attr = (
        LeadAttribution.objects.filter(
            lead=lead,
            axis=LeadAttribution.Axis.ACQUISITION,
            touch_model=LeadAttribution.TouchModel.LAST,
        )
        .select_related('message', 'message__campaign', 'campaign')
        .first()
    )
    if acq_attr and acq_attr.message_id:
        return acq_attr.message, LeadAttribution.Kind.MATCHED

    acq_any = _find_last_accepted_message(lead, kind=LeadCampaign.Kind.ACQUISITION, within_days=None)
    if acq_any:
        return acq_any, LeadAttribution.Kind.MATCHED

    act_any = _find_last_accepted_message(lead, kind=LeadCampaign.Kind.ACTIVATION, within_days=None)
    if act_any:
        return act_any, LeadAttribution.Kind.MATCHED

    return None, LeadAttribution.Kind.MATCHED


def _upsert_attribution(
    *,
    axis: str,
    touch_model: str,
    attribution_kind: str,
    lead: MarketingLead,
    user,
    message: Optional[CampaignMessage],
    order=None,
    revenue_amount: Optional[int] = None,
    registered_at=None,
    converted_at=None,
    metadata: Optional[dict] = None,
    campaign: Optional[LeadCampaign] = None,
) -> LeadAttribution:
    camp = campaign or (message.campaign if message else None)
    defaults = {
        'attribution_kind': attribution_kind,
        'campaign': camp,
        'message': message,
        'variant': message.variant if message else None,
        'step': message.step if message else None,
        'order': order,
        'revenue_amount': revenue_amount,
        'registered_at': registered_at,
        'converted_at': converted_at,
        'metadata': metadata or {},
    }
    obj, created = LeadAttribution.objects.update_or_create(
        lead=lead,
        user=user,
        axis=axis,
        touch_model=touch_model,
        defaults=defaults,
    )
    if not created and attribution_kind == LeadAttribution.Kind.DIRECT:
        # direct بر matched اولویت دارد
        if obj.attribution_kind != LeadAttribution.Kind.DIRECT:
            for k, v in defaults.items():
                setattr(obj, k, v)
            obj.save()
    return obj


@transaction.atomic
def attribute_signup(
    *,
    user,
    request=None,
    cookie_token: str = '',
) -> Optional[LeadAttribution]:
    """ثبت‌نام → Acquisition Attribution + خروج از کمپین جذب + ورود به Activation."""
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    if not phone:
        return None

    lead = MarketingLead.objects.filter(phone_normalized=phone).first()
    token = cookie_token
    if request is not None and not token:
        token = request.COOKIES.get(COOKIE_NAME, '')

    message = _message_from_cookie_token(token)
    kind = LeadAttribution.Kind.DIRECT
    if message and message.lead_id != (lead.pk if lead else None):
        # توکن به سرنخ دیگری اشاره دارد — نادیده بگیر مگر شماره یکی باشد
        if not lead or message.lead.phone_normalized != phone:
            message = None

    if message and not lead:
        lead = message.lead

    if not lead:
        # ثبت‌نام ارگانیک — سرنخ بساز تا Activation و Journey کار کنند
        lead = MarketingLead.objects.create(
            phone_normalized=phone,
            status=MarketingLead.Status.REGISTERED,
            matched_user=user,
            source='organic_signup',
            display_name=(getattr(user, 'first_name', '') or '')[:255],
        )
        _finalize_signup_journey(user=user, lead=lead)
        enroll_user_in_activation_campaign(user=user, lead=lead)
        return None

    if not message:
        message = _find_phone_matched_message(
            lead, kind=LeadCampaign.Kind.ACQUISITION, within_days=ACQUISITION_WINDOW_DAYS,
        )
        kind = LeadAttribution.Kind.MATCHED if message else LeadAttribution.Kind.MATCHED

    if not message:
        # بدون پیام در پنجره — فقط وضعیت lead را به‌روز کن
        lead.status = MarketingLead.Status.REGISTERED
        lead.matched_user = user
        lead.save(update_fields=['status', 'matched_user', 'updated_at'])
        _exit_acquisition_enrollments(lead, user, status=CampaignEnrollment.Status.EXITED_REGISTERED)
        _finalize_signup_journey(user=user, lead=lead)
        enroll_user_in_activation_campaign(user=user, lead=lead)
        return None

    now = timezone.now()
    record_touchpoint(
        lead=lead,
        event_type=LeadTouchpoint.EventType.SIGNUP_COMPLETE,
        message=message,
        user=user,
    )

    # first-touch: اولین پیام کمپین جذب در پنجره
    first_msg = (
        CampaignMessage.objects.filter(
            lead=lead,
            campaign__kind=LeadCampaign.Kind.ACQUISITION,
            status__in=(
                CampaignMessage.Status.PROVIDER_ACCEPTED,
                CampaignMessage.Status.DELIVERED,
            ),
            requested_at__gte=now - timedelta(days=ACQUISITION_WINDOW_DAYS),
        )
        .order_by('requested_at')
        .select_related('campaign', 'variant', 'step')
        .first()
    ) or message

    last_msg = message
    attr_kind_last = kind
    if kind != LeadAttribution.Kind.DIRECT:
        # last از phone match؛ first هم matched
        attr_kind_first = LeadAttribution.Kind.MATCHED
    else:
        attr_kind_first = (
            LeadAttribution.Kind.DIRECT
            if first_msg and first_msg.click_token == last_msg.click_token
            else LeadAttribution.Kind.MATCHED
        )
        # اگر first همان last با cookie است direct؛ وگرنه first را matched نگه می‌داریم مگر کلیک روی first بوده
        if first_msg and first_msg.pk != last_msg.pk:
            has_click = LeadTouchpoint.objects.filter(
                message=first_msg,
                event_type=LeadTouchpoint.EventType.CLICK,
            ).exists()
            attr_kind_first = (
                LeadAttribution.Kind.DIRECT if has_click else LeadAttribution.Kind.MATCHED
            )
        else:
            attr_kind_first = LeadAttribution.Kind.DIRECT

    _upsert_attribution(
        axis=LeadAttribution.Axis.ACQUISITION,
        touch_model=LeadAttribution.TouchModel.FIRST,
        attribution_kind=attr_kind_first,
        lead=lead,
        user=user,
        message=first_msg,
        registered_at=now,
        metadata={'phone_matched': attr_kind_first == LeadAttribution.Kind.MATCHED},
    )
    last_attr = _upsert_attribution(
        axis=LeadAttribution.Axis.ACQUISITION,
        touch_model=LeadAttribution.TouchModel.LAST,
        attribution_kind=attr_kind_last,
        lead=lead,
        user=user,
        message=last_msg,
        registered_at=now,
        metadata={
            'phone_matched': attr_kind_last == LeadAttribution.Kind.MATCHED,
            'label': (
                'phone_matched'
                if attr_kind_last == LeadAttribution.Kind.MATCHED
                else 'direct'
            ),
        },
    )

    lead.status = MarketingLead.Status.REGISTERED
    lead.matched_user = user
    lead.save(update_fields=['status', 'matched_user', 'updated_at'])
    _exit_acquisition_enrollments(lead, user, status=CampaignEnrollment.Status.EXITED_REGISTERED)
    _finalize_signup_journey(user=user, lead=lead)
    enroll_user_in_activation_campaign(user=user, lead=lead)
    return last_attr


def _finalize_signup_journey(*, user, lead: MarketingLead) -> None:
    try:
        from accounts.services.growth_journey import on_signup
        on_signup(user=user, lead=lead)
    except Exception:
        pass


def _exit_acquisition_enrollments(lead: MarketingLead, user, *, status: str) -> None:
    now = timezone.now()
    qs = CampaignEnrollment.objects.filter(
        lead=lead,
        status=CampaignEnrollment.Status.ACTIVE,
        campaign__kind=LeadCampaign.Kind.ACQUISITION,
    )
    for enroll in qs:
        enroll.status = status
        enroll.exited_at = now
        enroll.user = user
        enroll.save(update_fields=['status', 'exited_at', 'user'])


def _finalize_purchase_side_effects(*, lead: MarketingLead, user, order) -> None:
    now = timezone.now()
    lead.status = MarketingLead.Status.CUSTOMER
    lead.matched_user = user
    lead.save(update_fields=['status', 'matched_user', 'updated_at'])

    CampaignEnrollment.objects.filter(
        lead=lead,
        status=CampaignEnrollment.Status.ACTIVE,
    ).update(
        status=CampaignEnrollment.Status.EXITED_PURCHASED,
        exited_at=now,
        user=user,
    )
    try:
        from accounts.services.growth_journey import on_purchase
        from accounts.services.user_activation import exit_activation_on_purchase

        on_purchase(user=user, order=order, lead=lead)
        exit_activation_on_purchase(lead=lead, user=user)
    except Exception:
        pass


def _write_conversion_attribution(
    *,
    lead: MarketingLead,
    user,
    order,
    message: Optional[CampaignMessage],
    kind: str,
    campaign: Optional[LeadCampaign] = None,
) -> LeadAttribution:
    converted_at = getattr(order, 'paid_at', None) or timezone.now()
    revenue = int(getattr(order, 'amount', 0) or 0)
    meta_base = {
        'phone_matched': kind == LeadAttribution.Kind.MATCHED,
        'label': 'phone_matched' if kind == LeadAttribution.Kind.MATCHED else 'direct',
    }

    record_touchpoint(
        lead=lead,
        event_type=LeadTouchpoint.EventType.PAID,
        message=message,
        user=user,
        metadata={'order_id': str(order.pk)},
    )
    record_touchpoint(
        lead=lead,
        event_type=LeadTouchpoint.EventType.LICENSED,
        message=message,
        user=user,
        metadata={'order_id': str(order.pk)},
    )

    first_msg = message
    if message and message.campaign.kind == LeadCampaign.Kind.ACTIVATION:
        first_msg = (
            _find_last_accepted_message(
                lead,
                kind=LeadCampaign.Kind.ACTIVATION,
                within_days=CONVERSION_WINDOW_DAYS,
            )
            or message
        )
    elif not message:
        first_msg = None

    _upsert_attribution(
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.FIRST,
        attribution_kind=(
            LeadAttribution.Kind.DIRECT
            if first_msg and message and first_msg.pk == message.pk and kind == LeadAttribution.Kind.DIRECT
            else LeadAttribution.Kind.MATCHED
        ),
        lead=lead,
        user=user,
        message=first_msg,
        order=order,
        revenue_amount=revenue,
        converted_at=converted_at,
        metadata=meta_base,
        campaign=campaign or (first_msg.campaign if first_msg else None),
    )
    return _upsert_attribution(
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.LAST,
        attribution_kind=kind,
        lead=lead,
        user=user,
        message=message,
        order=order,
        revenue_amount=revenue,
        converted_at=converted_at,
        metadata=meta_base,
        campaign=campaign or (message.campaign if message else None),
    )


@transaction.atomic
def attribute_purchase(*, order, request=None, cookie_token: str = '') -> Optional[LeadAttribution]:
    """پرداخت موفق → Conversion Attribution؛ Acquisition دست‌نخورده می‌ماند."""
    user = getattr(order, 'user', None)
    if not user:
        return None
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    lead = MarketingLead.objects.filter(phone_normalized=phone).first() if phone else None
    if not lead and user:
        lead = MarketingLead.objects.filter(matched_user=user).first()
    if not lead:
        try:
            from accounts.services.growth_journey import on_purchase
            on_purchase(user=user, order=order, lead=None)
        except Exception:
            pass
        return None

    existing = LeadAttribution.objects.filter(
        lead=lead,
        user=user,
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.LAST,
    ).first()
    if existing and existing.order_id:
        _finalize_purchase_side_effects(lead=lead, user=user, order=order)
        return existing

    token = cookie_token
    if request is not None and not token:
        token = request.COOKIES.get(COOKIE_NAME, '')

    cookie_message = _message_from_cookie_token(token)
    if cookie_message and cookie_message.lead_id != lead.pk:
        cookie_message = None

    message, kind = _resolve_conversion_message(lead, cookie_message=cookie_message)
    fallback_campaign = None
    if not message:
        fallback_campaign = _acquisition_campaign_for_lead(lead)

    if kind == LeadAttribution.Kind.DIRECT and message and message.campaign.kind == LeadCampaign.Kind.ACTIVATION:
        pass
    elif message and message.campaign.kind == LeadCampaign.Kind.ACTIVATION and kind != LeadAttribution.Kind.DIRECT:
        kind = LeadAttribution.Kind.MATCHED

    last_attr = _write_conversion_attribution(
        lead=lead,
        user=user,
        order=order,
        message=message,
        kind=kind,
        campaign=fallback_campaign,
    )
    _finalize_purchase_side_effects(lead=lead, user=user, order=order)
    return last_attr


def backfill_conversion_attributions(*, dry_run: bool = False, limit: int = 0) -> dict[str, int]:
    """Conversion گم‌شده برای سرنخ‌هایی که سفارش paid دارند."""
    from shop.models import Order

    stats = {
        'candidates': 0,
        'created': 0,
        'skipped_has_conversion': 0,
        'skipped_no_lead': 0,
        'errors': 0,
    }
    converted_leads = set(
        LeadAttribution.objects.filter(
            axis=LeadAttribution.Axis.CONVERSION,
            touch_model=LeadAttribution.TouchModel.LAST,
        ).values_list('lead_id', flat=True),
    )

    seen_leads: set[int] = set()
    orders = (
        Order.objects.filter(status='paid')
        .select_related('user')
        .order_by('-paid_at', '-created_at')
    )
    if limit > 0:
        orders = orders[:limit]

    for order in orders.iterator(chunk_size=200):
        user = order.user
        if not user:
            continue
        phone = normalize_phone(getattr(user, 'phone', '') or '')
        lead = MarketingLead.objects.filter(phone_normalized=phone).first() if phone else None
        if not lead:
            lead = MarketingLead.objects.filter(matched_user=user).first()
        if not lead:
            stats['skipped_no_lead'] += 1
            continue
        if lead.pk in converted_leads or lead.pk in seen_leads:
            stats['skipped_has_conversion'] += 1
            continue
        stats['candidates'] += 1
        seen_leads.add(lead.pk)
        if dry_run:
            continue
        try:
            attribute_purchase(order=order)
            stats['created'] += 1
            converted_leads.add(lead.pk)
        except Exception:
            stats['errors'] += 1

    return stats
