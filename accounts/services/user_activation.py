"""کمپین جداگانه User Activation / Purchase Conversion."""
from __future__ import annotations

import logging
from typing import Optional

from django.db import transaction
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
DEFAULT_ACTIVATION_STEP_TEMPLATE = (
    'حساب شما در فایلینگ دیوار آماده است. برای امتحان امکانات با لایسنس یک‌روزه '
    'از این لینک وارد شوید: {link}'
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
        landing_url='https://divarfiling.ir/accounts/register/',
        created_by=created_by,
        started_at=timezone.now(),
    )
    CampaignVariant.objects.create(campaign=campaign, key='A', name='Default', weight=1)
    _ensure_activation_steps(campaign)
    return campaign


def _ensure_activation_steps(campaign: LeadCampaign) -> None:
    if campaign.steps.exists():
        return
    CampaignStep.objects.create(
        campaign=campaign,
        step_number=1,
        name='فعال‌سازی و خرید',
        delay_days=0,
        audience=CampaignStep.Audience.ALL_ELIGIBLE,
        message_template=DEFAULT_ACTIVATION_STEP_TEMPLATE,
    )


@transaction.atomic
def enroll_user_in_activation_campaign(
    *,
    user,
    lead: Optional[MarketingLead] = None,
) -> Optional[CampaignEnrollment]:
    """پس از ثبت‌نام از مسیر جذب، کاربر وارد کمپین Activation می‌شود."""
    if lead is None:
        from accounts.phone_utils import normalize_phone
        phone = normalize_phone(getattr(user, 'phone', '') or '')
        lead = MarketingLead.objects.filter(phone_normalized=phone).first() if phone else None
    if not lead:
        return None

    campaign = get_or_create_default_activation_campaign()
    variant = campaign.variants.filter(is_active=True).order_by('key').first()
    if not variant:
        variant = CampaignVariant.objects.create(
            campaign=campaign, key='A', name='Default', weight=1,
        )

    # جلوگیری از enrollment تکراری فعال
    existing = CampaignEnrollment.objects.filter(
        campaign=campaign,
        lead=lead,
        status=CampaignEnrollment.Status.ACTIVE,
    ).first()
    if existing:
        if not existing.user_id:
            existing.user = user
            existing.save(update_fields=['user'])
        return existing

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
    return enroll
