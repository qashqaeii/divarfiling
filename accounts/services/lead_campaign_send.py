"""ایجاد کمپین، enroll با Variant ثابت، و ارسال پیام با click_token."""
from __future__ import annotations

import logging
import random
from typing import Iterable, List, Optional

from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    CampaignEnrollment,
    CampaignMessage,
    CampaignStep,
    CampaignVariant,
    LeadCampaign,
    LeadList,
    LeadListMember,
    MarketingLead,
    SuppressionEntry,
)
from accounts.phone_utils import find_user_by_phone, is_valid_iran_mobile
from accounts.services.lead_tokens import generate_click_token, generate_idempotency_key
from accounts.services.notifications import notify_marketing

logger = logging.getLogger(__name__)


class LeadCampaignError(Exception):
    def __init__(self, message: str, *, code: str = 'campaign_error'):
        self.message = message
        self.code = code
        super().__init__(message)


DEFAULT_STEP1_A = (
    'مشاور املاک {district} هستید؟ فایلینگ دیوار کمک می‌کند فایل‌های مناسب منطقه را '
    'سریع‌تر پیدا و مشتری‌ها را منظم پیگیری کنید. معرفی کوتاه: {link}'
)
DEFAULT_STEP1_B = (
    'هنوز برای پیدا کردن فایل مناسب بین آگهی‌ها زمان زیادی می‌گذارید؟ '
    'فایلینگ دیوار برای سریع‌تر شدن کار مشاوران املاک ساخته شده. ببینید چطور: {link}'
)
DEFAULT_STEP2 = (
    'از جست‌وجوی فایل تا ثبت مشتری و یادآوری پیگیری؛ همه در یک میزکار مخصوص مشاور املاک. '
    'لایسنس یک‌روزه فایلینگ دیوار را امتحان کنید: {link}'
)
DEFAULT_STEP3 = (
    'اگر هنوز فایلینگ دیوار را امتحان نکرده‌اید، با لایسنس یک‌روزه می‌توانید امکاناتش را '
    'در کار واقعی خودتان بسنجید: {link}'
)


def sms_unit_cost_toman() -> int:
    return int(getattr(settings, 'LEAD_SMS_COST_TOMAN', 300) or 300)


def absolute_click_url(request, click_token: str) -> str:
    # مسیر کوتاه عمومی طبق پلن: /s/t/<click_token>/
    try:
        path = reverse('lead_click_redirect_root', kwargs={'click_token': click_token})
    except Exception:
        path = reverse('lead_click_redirect', kwargs={'click_token': click_token})
    if request is not None:
        return request.build_absolute_uri(path)
    base = getattr(settings, 'SITE_URL', 'https://divarfiling.ir').rstrip('/')
    return f'{base}{path}'


def create_acquisition_campaign(
    *,
    name: str,
    lead_list: LeadList,
    created_by=None,
    landing_url: str = 'https://divarfiling.ir/',
    is_pilot: bool = True,
    pilot_per_variant: int = 15,
    variant_a_template: str = '',
    variant_b_template: str = '',
) -> LeadCampaign:
    district = lead_list.district or 'منطقه شما'
    campaign = LeadCampaign.objects.create(
        name=name,
        kind=LeadCampaign.Kind.ACQUISITION,
        status=LeadCampaign.Status.DRAFT,
        lead_list=lead_list,
        landing_url=landing_url,
        is_pilot=is_pilot,
        pilot_per_variant=pilot_per_variant,
        created_by=created_by,
    )
    CampaignVariant.objects.create(campaign=campaign, key='A', name='نسخه A', weight=1)
    CampaignVariant.objects.create(campaign=campaign, key='B', name='نسخه B', weight=1)

    t_a = (variant_a_template or DEFAULT_STEP1_A).replace('{district}', district)
    t_b = (variant_b_template or DEFAULT_STEP1_B).replace('{district}', district)

    CampaignStep.objects.create(
        campaign=campaign,
        step_number=1,
        name='معرفی',
        delay_days=0,
        audience=CampaignStep.Audience.ALL_ELIGIBLE,
        message_template=f'<<<VARIANT:A>>>\n{t_a}\n<<<VARIANT:B>>>\n{t_b}',
    )
    CampaignStep.objects.create(
        campaign=campaign,
        step_number=2,
        name='یادآوری',
        delay_days=2,
        audience=CampaignStep.Audience.NOT_REGISTERED,
        message_template=DEFAULT_STEP2,
    )
    CampaignStep.objects.create(
        campaign=campaign,
        step_number=3,
        name='تبدیل گرم',
        delay_days=6,
        audience=CampaignStep.Audience.ENGAGED_NOT_REGISTERED,
        message_template=DEFAULT_STEP3,
    )
    return campaign


def parse_variant_templates(step1_template: str) -> dict:
    text = step1_template or ''
    if '<<<VARIANT:A>>>' in text and '<<<VARIANT:B>>>' in text:
        _, rest = text.split('<<<VARIANT:A>>>', 1)
        a_part, b_part = rest.split('<<<VARIANT:B>>>', 1)
        return {'A': a_part.strip(), 'B': b_part.strip()}
    return {'A': text, 'B': text}


def pick_stable_variant(variants: List[CampaignVariant], *, lead_id: int) -> CampaignVariant:
    """تخصیص شبه‌تصادفی پایدار بر اساس lead_id — اجرای مجدد عوض نمی‌کند."""
    active = [v for v in variants if v.is_active]
    if not active:
        raise LeadCampaignError('نسخه فعالی وجود ندارد.', code='no_variant')
    active = sorted(active, key=lambda v: v.key)
    idx = lead_id % len(active)
    return active[idx]


def eligible_leads_for_list(lead_list: LeadList) -> Iterable[MarketingLead]:
    return (
        MarketingLead.objects.filter(
            list_memberships__lead_list=lead_list,
            status__in=(MarketingLead.Status.COLD, MarketingLead.Status.ENGAGED),
        )
        .exclude(
            phone_normalized__in=SuppressionEntry.objects.values_list('phone_normalized', flat=True),
        )
        .distinct()
        .order_by('id')
    )


@transaction.atomic
def enroll_pilot(
    campaign: LeadCampaign,
    *,
    per_variant: Optional[int] = None,
) -> dict:
    if not campaign.lead_list_id:
        raise LeadCampaignError('لیست سرنخ برای کمپین مشخص نیست.', code='no_list')
    per = per_variant if per_variant is not None else campaign.pilot_per_variant
    variants = list(campaign.variants.filter(is_active=True).order_by('key'))
    if len(variants) < 1:
        raise LeadCampaignError('حداقل یک Variant لازم است.', code='no_variant')

    leads = list(eligible_leads_for_list(campaign.lead_list))
    # فیلتر کاربر موجود
    filtered = []
    for lead in leads:
        if find_user_by_phone(lead.phone_normalized):
            if lead.status != MarketingLead.Status.EXISTING_USER:
                lead.status = MarketingLead.Status.EXISTING_USER
                lead.save(update_fields=['status', 'updated_at'])
            continue
        filtered.append(lead)

    random.Random(campaign.pk).shuffle(filtered)
    counts = {v.key: 0 for v in variants}
    enrolled = 0
    held = 0

    for lead in filtered:
        # یک enrollment فعال جذب در کل سیستم
        if CampaignEnrollment.objects.filter(
            lead=lead,
            status=CampaignEnrollment.Status.ACTIVE,
            campaign__kind=LeadCampaign.Kind.ACQUISITION,
        ).exclude(campaign=campaign).exists():
            continue

        variant = pick_stable_variant(variants, lead_id=lead.pk)
        if campaign.is_pilot and counts[variant.key] >= per:
            CampaignEnrollment.objects.get_or_create(
                campaign=campaign,
                lead=lead,
                defaults={
                    'assigned_variant': variant,
                    'status': CampaignEnrollment.Status.HOLD,
                },
            )
            held += 1
            continue

        enroll, created = CampaignEnrollment.objects.get_or_create(
            campaign=campaign,
            lead=lead,
            defaults={
                'assigned_variant': variant,
                'status': CampaignEnrollment.Status.ACTIVE,
                'current_step_number': 0,
            },
        )
        if not created:
            continue
        # Variant ثابت از لحظه create
        counts[variant.key] = counts.get(variant.key, 0) + 1
        enrolled += 1

    campaign.status = LeadCampaign.Status.PILOT if campaign.is_pilot else LeadCampaign.Status.ACTIVE
    campaign.started_at = timezone.now()
    campaign.save(update_fields=['status', 'started_at', 'updated_at'])
    return {'enrolled': enrolled, 'held': held, 'per_variant': counts}


def render_step_body(*, step: CampaignStep, variant: CampaignVariant, link: str, lead: MarketingLead) -> str:
    template = step.message_template
    if step.step_number == 1:
        templates = parse_variant_templates(step.message_template)
        template = templates.get(variant.key) or templates.get('A') or step.message_template
    body = template.replace('{link}', link)
    body = body.replace('{district}', lead.district or lead.city or 'منطقه شما')
    body = body.replace('{name}', lead.display_name or '')
    return body.strip()


def audience_allows(*, step: CampaignStep, lead: MarketingLead, enrollment: CampaignEnrollment) -> bool:
    if lead.status in (
        MarketingLead.Status.REGISTERED,
        MarketingLead.Status.CUSTOMER,
        MarketingLead.Status.SUPPRESSED,
        MarketingLead.Status.EXISTING_USER,
    ):
        return False
    if SuppressionEntry.objects.filter(phone_normalized=lead.phone_normalized).exists():
        return False
    if find_user_by_phone(lead.phone_normalized):
        return False

    if step.audience == CampaignStep.Audience.ALL_ELIGIBLE:
        return True
    if step.audience == CampaignStep.Audience.NOT_REGISTERED:
        return lead.status in (MarketingLead.Status.COLD, MarketingLead.Status.ENGAGED)
    if step.audience == CampaignStep.Audience.ENGAGED_NOT_REGISTERED:
        from accounts.models import LeadTouchpoint
        engaged = LeadTouchpoint.objects.filter(
            lead=lead,
            event_type__in=(
                LeadTouchpoint.EventType.CLICK,
                LeadTouchpoint.EventType.LANDING_VIEW,
            ),
        ).exists()
        return engaged and lead.status in (
            MarketingLead.Status.COLD,
            MarketingLead.Status.ENGAGED,
        )
    return False


@transaction.atomic
def send_step_message(
    *,
    enrollment: CampaignEnrollment,
    step: CampaignStep,
    request=None,
    force: bool = False,
) -> CampaignMessage:
    enrollment = (
        CampaignEnrollment.objects.select_for_update()
        .select_related('lead', 'assigned_variant', 'campaign')
        .get(pk=enrollment.pk)
    )
    lead = enrollment.lead
    variant = enrollment.assigned_variant

    if enrollment.status != CampaignEnrollment.Status.ACTIVE and not force:
        raise LeadCampaignError('Enrollment فعال نیست.', code='inactive_enrollment')

    idem = generate_idempotency_key(
        enrollment_id=enrollment.pk,
        step_number=step.step_number,
        variant_key=variant.key,
    )
    existing = CampaignMessage.objects.filter(idempotency_key=idem).first()
    if existing:
        return existing

    if not audience_allows(step=step, lead=lead, enrollment=enrollment):
        msg = CampaignMessage.objects.create(
            enrollment=enrollment,
            campaign=enrollment.campaign,
            variant=variant,
            step=step,
            lead=lead,
            click_token=generate_click_token(),
            idempotency_key=idem,
            status=CampaignMessage.Status.SKIPPED,
            skip_reason='audience_or_suppression',
            sms_cost_snapshot=0,
        )
        return msg

    if not is_valid_iran_mobile(lead.phone_normalized):
        return CampaignMessage.objects.create(
            enrollment=enrollment,
            campaign=enrollment.campaign,
            variant=variant,
            step=step,
            lead=lead,
            click_token=generate_click_token(),
            idempotency_key=idem,
            status=CampaignMessage.Status.SKIPPED,
            skip_reason='invalid_phone',
            sms_cost_snapshot=0,
        )

    click_token = generate_click_token()
    link = absolute_click_url(request, click_token)
    body = render_step_body(step=step, variant=variant, link=link, lead=lead)

    try:
        msg = CampaignMessage.objects.create(
            enrollment=enrollment,
            campaign=enrollment.campaign,
            variant=variant,
            step=step,
            lead=lead,
            click_token=click_token,
            idempotency_key=idem,
            body_rendered=body,
            status=CampaignMessage.Status.REQUESTED,
            sms_cost_snapshot=sms_unit_cost_toman(),
        )
    except IntegrityError:
        return CampaignMessage.objects.get(idempotency_key=idem)

    ok, sms_log = notify_marketing(phone=lead.phone_normalized, text=body)
    # purpose در notify_marketing فعلاً marketing است؛ برای گزارش lead از CampaignMessage استفاده می‌کنیم
    msg.sms_log = sms_log
    msg.provider_message_id = getattr(sms_log, 'provider_message_id', '') or ''
    if ok:
        msg.status = CampaignMessage.Status.PROVIDER_ACCEPTED
        msg.accepted_at = timezone.now()
        enrollment.current_step_number = max(enrollment.current_step_number, step.step_number)
        enrollment.last_message_at = timezone.now()
        enrollment.save(update_fields=['current_step_number', 'last_message_at'])
    else:
        msg.status = CampaignMessage.Status.FAILED
        msg.failed_at = timezone.now()
        msg.skip_reason = (getattr(sms_log, 'error_message', '') or 'send_failed')[:200]
    msg.save()
    return msg


def send_campaign_step(campaign: LeadCampaign, step_number: int, *, request=None, limit: int = 500) -> dict:
    step = campaign.steps.filter(step_number=step_number, is_active=True).first()
    if not step:
        raise LeadCampaignError('مرحله یافت نشد.', code='no_step')

    enrollments = (
        CampaignEnrollment.objects.filter(
            campaign=campaign,
            status=CampaignEnrollment.Status.ACTIVE,
        )
        .select_related('lead', 'assigned_variant')
        .order_by('id')[:limit]
    )
    stats = {'sent': 0, 'accepted': 0, 'failed': 0, 'skipped': 0, 'idempotent': 0}
    for enroll in enrollments:
        before = CampaignMessage.objects.filter(
            idempotency_key=generate_idempotency_key(
                enrollment_id=enroll.pk,
                step_number=step.step_number,
                variant_key=enroll.assigned_variant.key,
            )
        ).first()
        msg = send_step_message(enrollment=enroll, step=step, request=request)
        if before and before.pk == msg.pk:
            stats['idempotent'] += 1
        if msg.status == CampaignMessage.Status.PROVIDER_ACCEPTED:
            stats['accepted'] += 1
            stats['sent'] += 1
        elif msg.status == CampaignMessage.Status.FAILED:
            stats['failed'] += 1
            stats['sent'] += 1
        elif msg.status == CampaignMessage.Status.SKIPPED:
            stats['skipped'] += 1
        else:
            stats['sent'] += 1
    return stats
