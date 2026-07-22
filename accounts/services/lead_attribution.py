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
    return tp


def _find_phone_matched_message(
    lead: MarketingLead,
    *,
    kind: str,
    within_days: int,
) -> Optional[CampaignMessage]:
    since = timezone.now() - timedelta(days=within_days)
    qs = (
        CampaignMessage.objects.filter(
            lead=lead,
            status__in=(
                CampaignMessage.Status.PROVIDER_ACCEPTED,
                CampaignMessage.Status.DELIVERED,
            ),
            requested_at__gte=since,
        )
        .select_related('campaign', 'variant', 'step', 'enrollment')
        .order_by('-requested_at')
    )
    if kind == LeadCampaign.Kind.ACQUISITION:
        qs = qs.filter(campaign__kind=LeadCampaign.Kind.ACQUISITION)
    elif kind == LeadCampaign.Kind.ACTIVATION:
        qs = qs.filter(campaign__kind=LeadCampaign.Kind.ACTIVATION)
    return qs.first()


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
) -> LeadAttribution:
    defaults = {
        'attribution_kind': attribution_kind,
        'campaign': message.campaign if message else None,
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
        # سرنخ سرد نبوده — attribution نداریم
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
    enroll_user_in_activation_campaign(user=user, lead=lead)
    return last_attr


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
        return None

    token = cookie_token
    if request is not None and not token:
        token = request.COOKIES.get(COOKIE_NAME, '')

    message = _message_from_cookie_token(token)
    kind = LeadAttribution.Kind.DIRECT
    if message and message.lead_id != lead.pk:
        message = None
    if message and message.campaign.kind != LeadCampaign.Kind.ACTIVATION:
        # کلیک روی پیام جذب برای خرید conversion از activation اولویت ندارد مگر پیام activation نباشد
        pass

    if not message or (message and message.campaign.kind != LeadCampaign.Kind.ACTIVATION):
        act_msg = _find_phone_matched_message(
            lead, kind=LeadCampaign.Kind.ACTIVATION, within_days=CONVERSION_WINDOW_DAYS,
        )
        if act_msg:
            message = act_msg
            kind = LeadAttribution.Kind.MATCHED
        elif message and message.campaign.kind == LeadCampaign.Kind.ACQUISITION:
            # fallback: آخرین پیام جذب در پنجره conversion به‌عنوان matched
            kind = LeadAttribution.Kind.MATCHED
        elif not message:
            message = _find_phone_matched_message(
                lead, kind=LeadCampaign.Kind.ACQUISITION, within_days=CONVERSION_WINDOW_DAYS,
            )
            kind = LeadAttribution.Kind.MATCHED if message else LeadAttribution.Kind.MATCHED

    if not message:
        lead.status = MarketingLead.Status.CUSTOMER
        lead.save(update_fields=['status', 'updated_at'])
        return None

    if kind == LeadAttribution.Kind.DIRECT and message.campaign.kind == LeadCampaign.Kind.ACTIVATION:
        pass
    elif message.campaign.kind == LeadCampaign.Kind.ACTIVATION and kind != LeadAttribution.Kind.DIRECT:
        kind = LeadAttribution.Kind.MATCHED

    now = timezone.now()
    revenue = int(getattr(order, 'amount', 0) or 0)
    record_touchpoint(
        lead=lead,
        event_type=LeadTouchpoint.EventType.PAID,
        message=message,
        user=user,
        metadata={'order_id': order.pk},
    )
    record_touchpoint(
        lead=lead,
        event_type=LeadTouchpoint.EventType.LICENSED,
        message=message,
        user=user,
        metadata={'order_id': order.pk},
    )

    first_act = (
        CampaignMessage.objects.filter(
            lead=lead,
            campaign__kind=LeadCampaign.Kind.ACTIVATION,
            status__in=(
                CampaignMessage.Status.PROVIDER_ACCEPTED,
                CampaignMessage.Status.DELIVERED,
            ),
            requested_at__gte=now - timedelta(days=CONVERSION_WINDOW_DAYS),
        )
        .order_by('requested_at')
        .select_related('campaign', 'variant', 'step')
        .first()
    ) or message

    _upsert_attribution(
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.FIRST,
        attribution_kind=(
            LeadAttribution.Kind.DIRECT
            if first_act.pk == message.pk and kind == LeadAttribution.Kind.DIRECT
            else LeadAttribution.Kind.MATCHED
        ),
        lead=lead,
        user=user,
        message=first_act,
        order=order,
        revenue_amount=revenue,
        converted_at=now,
        metadata={'phone_matched': True} if kind == LeadAttribution.Kind.MATCHED else {},
    )
    last_attr = _upsert_attribution(
        axis=LeadAttribution.Axis.CONVERSION,
        touch_model=LeadAttribution.TouchModel.LAST,
        attribution_kind=kind,
        lead=lead,
        user=user,
        message=message,
        order=order,
        revenue_amount=revenue,
        converted_at=now,
        metadata={
            'phone_matched': kind == LeadAttribution.Kind.MATCHED,
            'label': 'phone_matched' if kind == LeadAttribution.Kind.MATCHED else 'direct',
        },
    )

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
    return last_attr
