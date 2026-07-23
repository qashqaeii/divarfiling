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
    LeadImportBatch,
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


def unicode_sms_parts(text: str) -> int:
    """
    تعداد بخش پیامک برای متن یونیکد (فارسی).
    تک‌بخشی تا ۷۰ کاراکتر؛ چندبخشی هر بخش ۶۷ کاراکتر.
    """
    n = len(text or '')
    if n <= 0:
        return 0
    if n <= 70:
        return 1
    return (n + 66) // 67


def sms_cost_per_part_rial() -> int:
    """تعرفه هر بخش از پنل پیامک (مثال شما: ۷۴۴۰ ریال ÷ ۳ بخش = ۲۴۸۰)."""
    configured = getattr(settings, 'LEAD_SMS_COST_PER_PART_RIAL', None)
    if configured is not None:
        return int(configured or 0)
    # سازگاری با تنظیم قدیمی تومانی
    legacy_toman = int(getattr(settings, 'LEAD_SMS_COST_TOMAN', 0) or 0)
    if legacy_toman:
        return legacy_toman * 10
    return 2480


def estimate_sms_cost_rial(text: str) -> int:
    """هزینه ارسال بر اساس طول متن × تعرفه هر بخش (ریال)."""
    return unicode_sms_parts(text) * sms_cost_per_part_rial()


def sms_unit_cost_toman() -> int:
    """سازگاری قدیمی — ترجیحاً از estimate_sms_cost_rial استفاده شود."""
    return max(1, sms_cost_per_part_rial() // 10)


def send_batch_size() -> int:
    """حداکثر ارسال در یک درخواست HTTP — جلوگیری از timeout گunicorn."""
    raw = getattr(settings, 'LEAD_CAMPAIGN_SEND_BATCH_SIZE', 10)
    try:
        size = int(raw or 10)
    except (TypeError, ValueError):
        size = 10
    return max(1, min(50, size))


def pending_enrollments_for_step(campaign: LeadCampaign, step: CampaignStep):
    """مخاطبان فعال که هنوز پیام موفق این مرحله را نگرفته‌اند."""
    return (
        CampaignEnrollment.objects.filter(
            campaign=campaign,
            status=CampaignEnrollment.Status.ACTIVE,
            assigned_variant__isnull=False,
        )
        .exclude(
            messages__step=step,
            messages__status__in=(
                CampaignMessage.Status.PROVIDER_ACCEPTED,
                CampaignMessage.Status.DELIVERED,
            ),
        )
        .select_related('lead', 'assigned_variant')
        .distinct()
        .order_by('id')
    )


def build_variant_step1_template(variant_a: str, variant_b: str) -> str:
    return f'<<<VARIANT:A>>>\n{variant_a.strip()}\n<<<VARIANT:B>>>\n{variant_b.strip()}'


def pilot_per_variant_for_count(eligible_count: int, *, is_pilot: bool = True) -> int:
    """ظرفیت هر نسخه A/B بر اساس تعداد سرنخ واجد شرایط."""
    if eligible_count <= 0:
        return 1
    if not is_pilot:
        return max(1, min(500, eligible_count))
    # پایلوت: حداکثر ۱۵ در هر نسخه، حداقل ۱
    half = max(1, eligible_count // 2)
    return max(1, min(15, half))


def generate_acquisition_campaign_name(
    *,
    lead_list: LeadList,
    batch_id: Optional[int] = None,
    eligible_count: int = 0,
    is_pilot: bool = True,
) -> str:
    """نام‌گذاری حرفه‌ای کمپین جذب."""
    from django.utils import timezone as tz

    parts: list[str] = ['جذب']
    geo = ' / '.join(
        p for p in (lead_list.city, lead_list.district) if p
    )
    if geo:
        parts.append(geo)
    if lead_list.listing_category:
        parts.append(lead_list.listing_category)
    if is_pilot:
        parts.append('پایلوت A/B')
    if eligible_count:
        parts.append(f'{eligible_count} سرنخ')
    now = tz.localtime()
    parts.append(now.strftime('%Y/%m/%d'))
    if batch_id:
        parts.append(f'فایل #{batch_id}')
    return ' · '.join(parts)


def eligible_count_for_list(lead_list: LeadList) -> int:
    return (
        MarketingLead.objects.filter(
            list_memberships__lead_list=lead_list,
            status__in=(MarketingLead.Status.COLD, MarketingLead.Status.ENGAGED),
        )
        .exclude(
            phone_normalized__in=SuppressionEntry.objects.values_list('phone_normalized', flat=True),
        )
        .distinct()
        .count()
    )


def auto_create_campaign_for_import(
    *,
    lead_list: LeadList,
    batch_id: int,
    eligible_count: int,
    created_by=None,
    landing_url: str = 'https://divarfiling.ir/',
) -> Optional[LeadCampaign]:
    """
    پس از commit فایل، کمپین دو نسخه‌ای می‌سازد — یک کمپین به ازای هر بچ (فایل).
    اگر برای همین بچ قبلاً کمپین ساخته شده باشد، تکرار نمی‌سازد.
    """
    batch = LeadImportBatch.objects.filter(pk=batch_id).first()
    if batch:
        existing_id = (batch.preview_stats or {}).get('campaign_id')
        if existing_id and LeadCampaign.objects.filter(pk=existing_id).exists():
            return LeadCampaign.objects.filter(pk=existing_id).first()

    count = eligible_count
    if count <= 0:
        count = eligible_count_for_list(lead_list)
    if count <= 0:
        return None

    per_variant = pilot_per_variant_for_count(count, is_pilot=True)
    name = generate_acquisition_campaign_name(
        lead_list=lead_list,
        batch_id=batch_id,
        eligible_count=count,
        is_pilot=True,
    )
    campaign = create_acquisition_campaign(
        name=name,
        lead_list=lead_list,
        created_by=created_by,
        landing_url=landing_url,
        is_pilot=True,
        pilot_per_variant=per_variant,
    )
    if batch:
        stats = dict(batch.preview_stats or {})
        stats['campaign_id'] = campaign.pk
        batch.preview_stats = stats
        batch.save(update_fields=['preview_stats'])
    return campaign


def batches_pending_campaign(limit: int = 30) -> list[dict]:
    """بچ‌های commit‌شده که هنوز کمپین ندارند (برای UI و backfill)."""
    rows: list[dict] = []
    for batch in LeadImportBatch.objects.filter(
        status=LeadImportBatch.Status.COMMITTED,
    ).order_by('-committed_at', '-created_at')[: limit * 3]:
        stats = batch.preview_stats or {}
        cid = stats.get('campaign_id')
        if cid and LeadCampaign.objects.filter(pk=cid).exists():
            continue
        list_id = stats.get('list_id')
        if not list_id:
            continue
        lead_list = LeadList.objects.filter(pk=list_id).first()
        if not lead_list:
            continue
        eligible = stats.get('members_added') or stats.get('eligible') or 0
        if not eligible:
            eligible = eligible_count_for_list(lead_list)
        rows.append({
            'batch': batch,
            'list': lead_list,
            'eligible': eligible,
        })
        if len(rows) >= limit:
            break
    return rows


def ensure_campaign_for_batch(
    batch_id: int,
    *,
    created_by=None,
    landing_url: str = 'https://divarfiling.ir/',
) -> Optional[LeadCampaign]:
    """ساخت کمپین برای یک بچ commit‌شده — مخصوص فایل‌های قبلاً واردشده."""
    batch = LeadImportBatch.objects.filter(
        pk=batch_id,
        status=LeadImportBatch.Status.COMMITTED,
    ).first()
    if not batch:
        raise LeadCampaignError('بچ ثبت‌شده یافت نشد.', code='batch_not_found')
    list_id = (batch.preview_stats or {}).get('list_id')
    if not list_id:
        raise LeadCampaignError('لیست سرنخ برای این بچ مشخص نیست.', code='no_list')
    lead_list = LeadList.objects.filter(pk=list_id).first()
    if not lead_list:
        raise LeadCampaignError('لیست سرنخ یافت نشد.', code='list_not_found')
    stats = batch.preview_stats or {}
    eligible = stats.get('members_added') or stats.get('eligible') or 0
    return auto_create_campaign_for_import(
        lead_list=lead_list,
        batch_id=batch.pk,
        eligible_count=eligible,
        created_by=created_by,
        landing_url=landing_url,
    )


def get_step1_variant_templates(campaign: LeadCampaign) -> dict[str, str]:
    step = campaign.steps.filter(step_number=1, is_active=True).first()
    if not step:
        return {'A': DEFAULT_STEP1_A, 'B': DEFAULT_STEP1_B}
    return parse_variant_templates(step.message_template)


@transaction.atomic
def update_acquisition_campaign(
    campaign_id: int,
    *,
    name: Optional[str] = None,
    landing_url: Optional[str] = None,
    pilot_per_variant: Optional[int] = None,
    is_pilot: Optional[bool] = None,
    variant_a_template: Optional[str] = None,
    variant_b_template: Optional[str] = None,
) -> LeadCampaign:
    campaign = LeadCampaign.objects.select_for_update().filter(pk=campaign_id).first()
    if not campaign:
        raise LeadCampaignError('کمپین یافت نشد.', code='not_found')
    if campaign.kind != LeadCampaign.Kind.ACQUISITION:
        raise LeadCampaignError('فقط کمپین جذب قابل ویرایش است.', code='wrong_kind')

    dirty_fields: list[str] = []
    if name is not None:
        campaign.name = name.strip() or campaign.name
        dirty_fields.append('name')
    if landing_url is not None:
        campaign.landing_url = landing_url.strip() or campaign.landing_url
        dirty_fields.append('landing_url')
    if pilot_per_variant is not None:
        campaign.pilot_per_variant = max(1, min(500, int(pilot_per_variant)))
        dirty_fields.append('pilot_per_variant')
    if is_pilot is not None:
        campaign.is_pilot = bool(is_pilot)
        dirty_fields.append('is_pilot')
    if dirty_fields:
        dirty_fields.append('updated_at')
        campaign.save(update_fields=dirty_fields)

    if variant_a_template is not None or variant_b_template is not None:
        step = campaign.steps.filter(step_number=1, is_active=True).first()
        if not step:
            raise LeadCampaignError('مرحله ۱ یافت نشد.', code='no_step')
        current = get_step1_variant_templates(campaign)
        a_text = (variant_a_template if variant_a_template is not None else current['A']).strip()
        b_text = (variant_b_template if variant_b_template is not None else current['B']).strip()
        if not a_text or not b_text:
            raise LeadCampaignError('متن نسخه A و B نمی‌تواند خالی باشد.', code='empty_template')
        step.message_template = build_variant_step1_template(a_text, b_text)
        step.save(update_fields=['message_template'])

    return campaign


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
        # اختلال اپراتور / ارسال ناموفق: اجازه ارسال مجدد با همان مرحله
        if existing.status == CampaignMessage.Status.FAILED:
            existing.idempotency_key = f'{idem}:failed:{existing.pk}'
            existing.skip_reason = ((existing.skip_reason or 'failed') + ';retried')[:200]
            existing.save(update_fields=['idempotency_key', 'skip_reason'])
        else:
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
    cost_rial = estimate_sms_cost_rial(body)

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
            sms_cost_snapshot=cost_rial,
        )
    except IntegrityError:
        existing = CampaignMessage.objects.filter(idempotency_key=idem).first()
        if existing:
            return existing
        raise

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


def send_campaign_step(campaign: LeadCampaign, step_number: int, *, request=None, limit: int | None = None) -> dict:
    step = campaign.steps.filter(step_number=step_number, is_active=True).first()
    if not step:
        raise LeadCampaignError('مرحله یافت نشد.', code='no_step')

    batch_limit = send_batch_size() if limit is None else max(1, min(500, int(limit)))
    pending_qs = pending_enrollments_for_step(campaign, step)
    total_pending = pending_qs.count()
    enrollments = list(pending_qs[:batch_limit])

    stats = {
        'sent': 0,
        'accepted': 0,
        'failed': 0,
        'skipped': 0,
        'idempotent': 0,
        'retried': 0,
        'errors': 0,
        'processed': 0,
        'pending_before': total_pending,
        'remaining': max(0, total_pending - len(enrollments)),
        'batch_limit': batch_limit,
    }
    for enroll in enrollments:
        if not enroll.assigned_variant_id:
            stats['skipped'] += 1
            stats['processed'] += 1
            continue
        idem = generate_idempotency_key(
            enrollment_id=enroll.pk,
            step_number=step.step_number,
            variant_key=enroll.assigned_variant.key,
        )
        before = CampaignMessage.objects.filter(idempotency_key=idem).first()
        was_failed = bool(before and before.status == CampaignMessage.Status.FAILED)
        try:
            msg = send_step_message(enrollment=enroll, step=step, request=request)
        except LeadCampaignError as exc:
            stats['errors'] += 1
            stats['processed'] += 1
            logger.warning(
                'lead campaign step send skipped enrollment=%s err=%s',
                enroll.pk,
                exc.message,
            )
            continue
        except Exception:
            stats['errors'] += 1
            stats['processed'] += 1
            logger.exception('lead campaign step send failed enrollment=%s', enroll.pk)
            continue

        stats['processed'] += 1
        if was_failed:
            stats['retried'] += 1
        elif before and before.pk == msg.pk:
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


@transaction.atomic
def delete_lead_campaign(campaign_id: int, *, confirm: bool = False) -> dict:
    """
    حذف کامل کمپین جذب برای شروع مجدد پس از اختلال ارسال.
    سرنخ‌ها و لیست منطقه باقی می‌مانند.
    """
    if not confirm:
        raise LeadCampaignError('برای حذف، تأیید لازم است.', code='confirm_required')

    campaign = LeadCampaign.objects.select_for_update().filter(pk=campaign_id).first()
    if not campaign:
        raise LeadCampaignError('کمپین یافت نشد.', code='not_found')
    if campaign.kind != LeadCampaign.Kind.ACQUISITION:
        raise LeadCampaignError('فقط کمپین جذب از این مسیر قابل حذف است.', code='wrong_kind')

    # اگر خرید attributed به این کمپین باشد، حذف را سخت‌گیرانه رد می‌کنیم
    from accounts.models import LeadAttribution
    paid = LeadAttribution.objects.filter(
        campaign=campaign,
        axis=LeadAttribution.Axis.CONVERSION,
    ).exists()
    if paid:
        raise LeadCampaignError(
            'این کمپین خرید ثبت‌شده دارد و برای حفظ گزارش قابل حذف نیست.',
            code='has_conversions',
        )

    name = campaign.name
    msg_count = campaign.messages.count()
    enroll_count = campaign.enrollments.count()
    # Enrollment → Variant با PROTECT است؛ اول enrollment/message را پاک می‌کنیم
    CampaignMessage.objects.filter(campaign=campaign).delete()
    CampaignEnrollment.objects.filter(campaign=campaign).delete()
    campaign.delete()
    return {
        'deleted_campaign_id': campaign_id,
        'name': name,
        'messages_removed': msg_count,
        'enrollments_removed': enroll_count,
    }


@transaction.atomic
def reset_campaign_for_retry(campaign_id: int) -> dict:
    """
    بدون حذف کمپین: پیام‌های ناموفق را آزاد می‌کند، enrollmentها را ACTIVE نگه می‌دارد،
    و current_step را صفر می‌کند تا ارسال مرحله ۱ دوباره ممکن شود.
    """
    campaign = LeadCampaign.objects.select_for_update().filter(pk=campaign_id).first()
    if not campaign:
        raise LeadCampaignError('کمپین یافت نشد.', code='not_found')

    failed_qs = CampaignMessage.objects.filter(
        campaign=campaign,
        status=CampaignMessage.Status.FAILED,
    )
    failed_count = failed_qs.count()
    for msg in failed_qs.iterator():
        msg.idempotency_key = f'{msg.idempotency_key}:reset:{msg.pk}'
        msg.save(update_fields=['idempotency_key'])

    # اگر همه پیام‌های مرحله ۱ failed/skipped بودند، step را ریست کن
    active_enrolls = CampaignEnrollment.objects.filter(
        campaign=campaign,
        status__in=(
            CampaignEnrollment.Status.ACTIVE,
            CampaignEnrollment.Status.HOLD,
            CampaignEnrollment.Status.COMPLETED,
        ),
    )
    reset_enrolls = 0
    for enroll in active_enrolls:
        has_success = CampaignMessage.objects.filter(
            enrollment=enroll,
            status__in=(
                CampaignMessage.Status.PROVIDER_ACCEPTED,
                CampaignMessage.Status.DELIVERED,
            ),
        ).exists()
        if not has_success:
            enroll.status = CampaignEnrollment.Status.ACTIVE
            enroll.current_step_number = 0
            enroll.last_message_at = None
            enroll.exited_at = None
            enroll.save(update_fields=[
                'status', 'current_step_number', 'last_message_at', 'exited_at',
            ])
            reset_enrolls += 1

    if campaign.status in (LeadCampaign.Status.COMPLETED, LeadCampaign.Status.ARCHIVED):
        campaign.status = LeadCampaign.Status.PILOT if campaign.is_pilot else LeadCampaign.Status.ACTIVE
        campaign.completed_at = None
        campaign.save(update_fields=['status', 'completed_at', 'updated_at'])

    return {
        'campaign_id': campaign.pk,
        'failed_freed': failed_count,
        'enrollments_reset': reset_enrolls,
    }
