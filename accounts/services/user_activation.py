"""کمپین جداگانه User Activation / Purchase Conversion."""
from __future__ import annotations

import logging
from typing import Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import (
    CampaignEnrollment,
    CampaignStep,
    CampaignVariant,
    LeadCampaign,
    MarketingLead,
)

logger = logging.getLogger(__name__)

DEFAULT_ACTIVATION_NAME = 'User Activation / Purchase Conversion'
DEFAULT_ACTIVATION_STEP1 = (
    'حساب شما در فایلینگ دیوار آماده است. برای شروع کار و دریافت لایسنس یک‌روزه '
    'از این لینک وارد شوید: {link}'
)
DEFAULT_ACTIVATION_STEP2 = (
    'هنوز لایسنس فعال ندارید. امکانات میزکار آماده است — '
    'با این لینک ادامه دهید: {link}'
)
DEFAULT_ACTIVATION_STEP3 = (
    'آخرین یادآوری: برای فعال‌سازی کامل فایلینگ دیوار همین حالا اقدام کنید: {link}'
)


def get_or_create_default_activation_campaign(*, created_by=None) -> LeadCampaign:
    campaign = (
        LeadCampaign.objects.filter(
            kind=LeadCampaign.Kind.ACTIVATION,
            status__in=(
                LeadCampaign.Status.ACTIVE,
                LeadCampaign.Status.DRAFT,
                LeadCampaign.Status.PILOT,
            ),
        )
        .order_by('-created_at')
        .first()
    )
    if campaign:
        if campaign.status == LeadCampaign.Status.DRAFT:
            campaign.status = LeadCampaign.Status.ACTIVE
            campaign.started_at = campaign.started_at or timezone.now()
            campaign.save(update_fields=['status', 'started_at', 'updated_at'])
        _ensure_activation_steps(campaign)
        return campaign

    campaign = LeadCampaign.objects.create(
        name=DEFAULT_ACTIVATION_NAME,
        kind=LeadCampaign.Kind.ACTIVATION,
        status=LeadCampaign.Status.ACTIVE,
        landing_url='https://divarfiling.ir/accounts/dashboard/',
        created_by=created_by,
        started_at=timezone.now(),
    )
    CampaignVariant.objects.create(campaign=campaign, key='A', name='Default', weight=1)
    _ensure_activation_steps(campaign)
    return campaign


def _ensure_activation_steps(campaign: LeadCampaign) -> None:
    """توالی ۳ مرحله‌ای: روز ۰ خوش‌آمد، روز ۲ یادآوری، روز ۵ آخرین تلاش."""
    specs = [
        (1, 'خوش‌آمد و فعال‌سازی', 0, DEFAULT_ACTIVATION_STEP1),
        (2, 'یادآوری بدون خرید', 2, DEFAULT_ACTIVATION_STEP2),
        (3, 'آخرین تلاش خرید', 5, DEFAULT_ACTIVATION_STEP3),
    ]
    existing = {s.step_number: s for s in campaign.steps.all()}
    for number, name, delay, template in specs:
        step = existing.get(number)
        if step:
            continue
        CampaignStep.objects.create(
            campaign=campaign,
            step_number=number,
            name=name,
            delay_days=delay,
            audience=CampaignStep.Audience.ALL_ELIGIBLE,
            message_template=template,
            is_active=True,
        )


def _user_has_active_license(user) -> bool:
    if not user:
        return False
    from licenses.models import License
    return License.objects.filter(
        order__user=user,
        order__status='paid',
        status='active',
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).exists()


@transaction.atomic
def enroll_user_in_activation_campaign(
    *,
    user,
    lead: Optional[MarketingLead] = None,
    send_welcome: bool = True,
) -> Optional[CampaignEnrollment]:
    """پس از ثبت‌نام، کاربر وارد کمپین Activation می‌شود و پیام خوش‌آمد ارسال می‌گردد."""
    if lead is None:
        from accounts.phone_utils import normalize_phone
        phone = normalize_phone(getattr(user, 'phone', '') or '')
        lead = MarketingLead.objects.filter(phone_normalized=phone).first() if phone else None
    if not lead:
        return None

    if _user_has_active_license(user):
        return None

    campaign = get_or_create_default_activation_campaign()
    variant = campaign.variants.filter(is_active=True).order_by('key').first()
    if not variant:
        variant = CampaignVariant.objects.create(
            campaign=campaign, key='A', name='Default', weight=1,
        )

    existing = CampaignEnrollment.objects.filter(
        campaign=campaign,
        lead=lead,
        status=CampaignEnrollment.Status.ACTIVE,
    ).first()
    if existing:
        if not existing.user_id:
            existing.user = user
            existing.save(update_fields=['user'])
        enroll = existing
    else:
        enroll, created = CampaignEnrollment.objects.get_or_create(
            campaign=campaign,
            lead=lead,
            defaults={
                'user': user,
                'assigned_variant': variant,
                'status': CampaignEnrollment.Status.ACTIVE,
                'current_step_number': 0,
            },
        )
        if not created and enroll.status != CampaignEnrollment.Status.ACTIVE:
            enroll.status = CampaignEnrollment.Status.ACTIVE
            enroll.user = user
            enroll.assigned_variant = enroll.assigned_variant or variant
            enroll.exited_at = None
            enroll.current_step_number = 0
            enroll.save()

    if send_welcome and enroll and enroll.current_step_number == 0:
        try:
            send_activation_step1_now(enroll)
        except Exception:
            logger.exception('activation welcome SMS failed enrollment=%s', enroll.pk)

    return enroll


def send_activation_step1_now(enrollment: CampaignEnrollment, *, request=None):
    """ارسال فوری مرحله ۱ Activation (delay=0)."""
    from accounts.services.lead_campaign_send import send_step_message

    step = enrollment.campaign.steps.filter(step_number=1, is_active=True).first()
    if not step:
        return None
    return send_step_message(enrollment=enrollment, step=step, request=request)


def exit_activation_on_purchase(*, lead: MarketingLead, user=None) -> int:
    now = timezone.now()
    qs = CampaignEnrollment.objects.filter(
        lead=lead,
        status=CampaignEnrollment.Status.ACTIVE,
        campaign__kind=LeadCampaign.Kind.ACTIVATION,
    )
    count = 0
    for enroll in qs:
        enroll.status = CampaignEnrollment.Status.EXITED_PURCHASED
        enroll.exited_at = now
        if user is not None:
            enroll.user = user
        enroll.save(update_fields=['status', 'exited_at', 'user'] if user else ['status', 'exited_at'])
        count += 1
    return count
