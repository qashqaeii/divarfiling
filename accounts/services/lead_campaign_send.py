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
    LeadAcquisitionMessageDefaults,
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


# قالب‌های سراسری جذب — کوتاه (≈۲ بخش یونیکد)، شخصی‌سازی با منطقه، CTA واضح
DEFAULT_STEP1_A = (
    'مشاور املاک {district}؛ فایلینگ دیوار: فایل مناسب منطقه + پیگیری منظم مشتری. '
    'معرفی کوتاه: {link}'
)
DEFAULT_STEP1_B = (
    'مشاور املاک {district}؛ پیدا کردن فایل مناسب وقت‌گیر شده؟ '
    'فایلینگ دیوار مسیر کار را کوتاه می‌کند: {link}'
)
DEFAULT_STEP2 = (
    'یادآوری: فایلینگ دیوار میزکار مشاور است؛ فایل، مشتری و پیگیری یکجا. '
    'لایسنس یک‌روزه را امتحان کنید: {link}'
)
DEFAULT_STEP3 = (
    'اگر هنوز امتحان نکرده‌اید: لایسنس یک‌روزه فایلینگ دیوار '
    'برای سنجش واقعی در کار مشاور: {link}'
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
    """
    مخاطبان فعال که هنوز برای این مرحله ارسال نشده‌اند.
    مرحله ۲/۳ فقط بعد از تکمیل مرحله قبل (بدون الزام delay) — مناسب ارسال دستی.
    """
    handled = CampaignMessage.objects.filter(
        campaign=campaign,
        step=step,
        status__in=(
            CampaignMessage.Status.PROVIDER_ACCEPTED,
            CampaignMessage.Status.DELIVERED,
            CampaignMessage.Status.SKIPPED,
            CampaignMessage.Status.FAILED,
        ),
    ).values('enrollment_id')
    qs = CampaignEnrollment.objects.filter(
        campaign=campaign,
        status=CampaignEnrollment.Status.ACTIVE,
        assigned_variant__isnull=False,
    ).exclude(pk__in=handled)
    if step.step_number >= 2:
        qs = qs.filter(current_step_number=step.step_number - 1)
    return qs.select_related('lead', 'assigned_variant').order_by('id')


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


def get_global_message_templates() -> dict[str, str]:
    """قالب سراسری مراحل ۱–۳ — منبع پیش‌فرض برای کمپین‌های جدید و ویرایش همگانی."""
    try:
        row = LeadAcquisitionMessageDefaults.load()
        a = (row.variant_a or '').strip() or DEFAULT_STEP1_A
        b = (row.variant_b or '').strip() or DEFAULT_STEP1_B
        s2 = (row.step_2 or '').strip() or DEFAULT_STEP2
        s3 = (row.step_3 or '').strip() or DEFAULT_STEP3
        return {'A': a, 'B': b, 'step_2': s2, 'step_3': s3}
    except Exception:
        logger.exception('failed to load global lead message templates')
        return {
            'A': DEFAULT_STEP1_A,
            'B': DEFAULT_STEP1_B,
            'step_2': DEFAULT_STEP2,
            'step_3': DEFAULT_STEP3,
        }


def get_global_variant_templates() -> dict[str, str]:
    """سازگاری با کد قدیمی — فقط A/B مرحله ۱."""
    tpl = get_global_message_templates()
    return {'A': tpl['A'], 'B': tpl['B']}


def _require_link_templates(**named: str) -> None:
    for label, text in named.items():
        if not (text or '').strip():
            raise LeadCampaignError(f'متن {label} نمی‌تواند خالی باشد.', code='empty_template')
        if '{link}' not in text:
            raise LeadCampaignError(f'{label} باید شامل {{link}} باشد.', code='missing_link')


def save_global_variant_templates(
    variant_a: str,
    variant_b: str,
    *,
    step_2: str = '',
    step_3: str = '',
    user=None,
    apply_to_all: bool = True,
) -> dict:
    """ذخیره قالب سراسری مراحل ۱–۳ و در صورت نیاز اعمال روی همه کمپین‌های جذب."""
    global_now = get_global_message_templates()
    a_text = (variant_a or '').strip() or global_now['A']
    b_text = (variant_b or '').strip() or global_now['B']
    s2_text = (step_2 or '').strip() or global_now['step_2']
    s3_text = (step_3 or '').strip() or global_now['step_3']
    _require_link_templates(
        **{'نسخه A': a_text, 'نسخه B': b_text, 'مرحله ۲': s2_text, 'مرحله ۳': s3_text},
    )

    row = LeadAcquisitionMessageDefaults.load()
    row.variant_a = a_text
    row.variant_b = b_text
    row.step_2 = s2_text
    row.step_3 = s3_text
    if user is not None and getattr(user, 'is_authenticated', False):
        row.updated_by = user
    row.save()

    result = {
        'saved': True,
        'variant_a': a_text,
        'variant_b': b_text,
        'step_2': s2_text,
        'step_3': s3_text,
        'updated': [],
        'updated_count': 0,
        'errors': [],
    }
    if apply_to_all:
        ids = list(
            LeadCampaign.objects.filter(kind=LeadCampaign.Kind.ACQUISITION)
            .order_by('-created_at')
            .values_list('pk', flat=True)
        )
        bulk = bulk_update_message_templates(
            ids,
            variant_a=a_text,
            variant_b=b_text,
            step_2=s2_text,
            step_3=s3_text,
        )
        result.update(bulk)
    return result


def get_step1_variant_templates(campaign: LeadCampaign) -> dict[str, str]:
    step = campaign.steps.filter(step_number=1, is_active=True).first()
    if not step:
        return get_global_variant_templates()
    return parse_variant_templates(step.message_template)


def get_campaign_step_templates(campaign: LeadCampaign) -> dict[str, str]:
    """قالب‌های مراحل ۱–۳ یک کمپین (A/B + step_2 + step_3)."""
    global_tpl = get_global_message_templates()
    variants = get_step1_variant_templates(campaign)
    step2 = campaign.steps.filter(step_number=2, is_active=True).first()
    step3 = campaign.steps.filter(step_number=3, is_active=True).first()
    return {
        'A': variants.get('A') or global_tpl['A'],
        'B': variants.get('B') or global_tpl['B'],
        'step_2': ((step2.message_template if step2 else '') or global_tpl['step_2']).strip(),
        'step_3': ((step3.message_template if step3 else '') or global_tpl['step_3']).strip(),
    }


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
    step_2_template: Optional[str] = None,
    step_3_template: Optional[str] = None,
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
        if '{link}' not in a_text or '{link}' not in b_text:
            raise LeadCampaignError('نسخه A و B باید شامل {link} باشند.', code='missing_link')
        step.message_template = build_variant_step1_template(a_text, b_text)
        step.save(update_fields=['message_template'])

    for step_no, tpl in ((2, step_2_template), (3, step_3_template)):
        if tpl is None:
            continue
        text = tpl.strip()
        if not text:
            raise LeadCampaignError(f'متن مرحله {step_no} نمی‌تواند خالی باشد.', code='empty_template')
        if '{link}' not in text:
            raise LeadCampaignError(f'مرحله {step_no} باید شامل {{link}} باشد.', code='missing_link')
        step = campaign.steps.filter(step_number=step_no, is_active=True).first()
        if not step:
            raise LeadCampaignError(f'مرحله {step_no} یافت نشد.', code='no_step')
        step.message_template = text
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

    # {district}/{link}/{name} تا لحظهٔ ارسال جایگزین می‌شوند — اینجا bake نکن
    global_tpl = get_global_message_templates()
    t_a = (variant_a_template or global_tpl['A']).strip()
    t_b = (variant_b_template or global_tpl['B']).strip()
    t_2 = global_tpl['step_2']
    t_3 = global_tpl['step_3']

    CampaignStep.objects.create(
        campaign=campaign,
        step_number=1,
        name='معرفی',
        delay_days=0,
        audience=CampaignStep.Audience.ALL_ELIGIBLE,
        message_template=build_variant_step1_template(t_a, t_b),
    )
    CampaignStep.objects.create(
        campaign=campaign,
        step_number=2,
        name='یادآوری',
        delay_days=2,
        audience=CampaignStep.Audience.NOT_REGISTERED,
        message_template=t_2,
    )
    CampaignStep.objects.create(
        campaign=campaign,
        step_number=3,
        name='تبدیل گرم',
        delay_days=6,
        audience=CampaignStep.Audience.ENGAGED_NOT_REGISTERED,
        message_template=t_3,
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


@transaction.atomic
def enroll_all_eligible(campaign: LeadCampaign) -> dict:
    """
    ثبت همه سرنخ‌های واجد شرایط در کمپین — بدون سقف پایلوت.
    enrollmentهای HOLD موجود را ACTIVE می‌کند.
    """
    if not campaign.lead_list_id:
        raise LeadCampaignError('لیست سرنخ برای کمپین مشخص نیست.', code='no_list')
    variants = list(campaign.variants.filter(is_active=True).order_by('key'))
    if len(variants) < 1:
        raise LeadCampaignError('حداقل یک Variant لازم است.', code='no_variant')

    leads = list(eligible_leads_for_list(campaign.lead_list))
    enrolled = 0
    activated = 0
    skipped_other_campaign = 0

    for lead in leads:
        if find_user_by_phone(lead.phone_normalized):
            if lead.status != MarketingLead.Status.EXISTING_USER:
                lead.status = MarketingLead.Status.EXISTING_USER
                lead.save(update_fields=['status', 'updated_at'])
            continue

        if CampaignEnrollment.objects.filter(
            lead=lead,
            status=CampaignEnrollment.Status.ACTIVE,
            campaign__kind=LeadCampaign.Kind.ACQUISITION,
        ).exclude(campaign=campaign).exists():
            skipped_other_campaign += 1
            continue

        variant = pick_stable_variant(variants, lead_id=lead.pk)
        enroll, created = CampaignEnrollment.objects.get_or_create(
            campaign=campaign,
            lead=lead,
            defaults={
                'assigned_variant': variant,
                'status': CampaignEnrollment.Status.ACTIVE,
                'current_step_number': 0,
            },
        )
        if created:
            enrolled += 1
            continue
        dirty = False
        if not enroll.assigned_variant_id:
            enroll.assigned_variant = variant
            dirty = True
        if enroll.status != CampaignEnrollment.Status.ACTIVE:
            enroll.status = CampaignEnrollment.Status.ACTIVE
            dirty = True
        if dirty:
            enroll.save(update_fields=['assigned_variant', 'status'])
            activated += 1

    campaign.status = LeadCampaign.Status.ACTIVE
    campaign.started_at = campaign.started_at or timezone.now()
    campaign.save(update_fields=['status', 'started_at', 'updated_at'])
    return {
        'enrolled': enrolled,
        'activated': activated,
        'skipped_other_campaign': skipped_other_campaign,
        'total_active': CampaignEnrollment.objects.filter(
            campaign=campaign,
            status=CampaignEnrollment.Status.ACTIVE,
        ).count(),
    }


def enroll_campaigns_for_full_send(campaign_ids: list[int]) -> dict:
    """قبل از ارسال کامل: همه سرنخ‌های واجد شرایط را ثبت می‌کند."""
    summary = {
        'campaigns': 0,
        'enrolled': 0,
        'activated': 0,
        'errors': [],
    }
    for cid in campaign_ids:
        campaign = LeadCampaign.objects.filter(pk=cid).first()
        if not campaign:
            summary['errors'].append({'campaign_id': cid, 'message': 'کمپین یافت نشد'})
            continue
        try:
            result = enroll_all_eligible(campaign)
        except LeadCampaignError as exc:
            summary['errors'].append({'campaign_id': cid, 'message': exc.message})
            continue
        summary['campaigns'] += 1
        summary['enrolled'] += result['enrolled']
        summary['activated'] += result['activated']
    return summary


@transaction.atomic
def bulk_update_message_templates(
    campaign_ids: list[int],
    *,
    variant_a: str,
    variant_b: str,
    step_2: str = '',
    step_3: str = '',
) -> dict:
    """اعمال قالب مراحل ۱–۳ روی چند کمپین."""
    a_text = (variant_a or '').strip()
    b_text = (variant_b or '').strip()
    s2_text = (step_2 or '').strip()
    s3_text = (step_3 or '').strip()
    if not a_text or not b_text:
        raise LeadCampaignError('متن نسخه A و B نمی‌تواند خالی باشد.', code='empty_template')
    updated: list[int] = []
    errors: list[dict] = []
    for cid in campaign_ids:
        try:
            update_acquisition_campaign(
                cid,
                variant_a_template=a_text,
                variant_b_template=b_text,
                step_2_template=s2_text or None,
                step_3_template=s3_text or None,
            )
            updated.append(cid)
        except LeadCampaignError as exc:
            errors.append({'campaign_id': cid, 'message': exc.message})
    return {'updated': updated, 'updated_count': len(updated), 'errors': errors}


@transaction.atomic
def bulk_update_variant_templates(
    campaign_ids: list[int],
    *,
    variant_a: str,
    variant_b: str,
) -> dict:
    """سازگاری با کد قدیمی — فقط A/B مرحله ۱."""
    return bulk_update_message_templates(
        campaign_ids,
        variant_a=variant_a,
        variant_b=variant_b,
    )


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
    from accounts.models import LeadCampaign
    from accounts.services.growth_suppression import (
        PURPOSE_ACQUISITION,
        PURPOSE_ACTIVATION,
        is_send_allowed,
    )

    campaign = enrollment.campaign
    is_activation = campaign.kind == LeadCampaign.Kind.ACTIVATION
    purpose = PURPOSE_ACTIVATION if is_activation else PURPOSE_ACQUISITION

    if lead.status == MarketingLead.Status.SUPPRESSED:
        return False
    if SuppressionEntry.objects.filter(phone_normalized=lead.phone_normalized).exists():
        return False
    if not is_send_allowed(
        lead.phone_normalized,
        purpose=purpose,
        user=enrollment.user,
    ):
        return False

    if is_activation:
        # فقط ثبت‌نام‌شدهٔ بدون خرید/لایسنس فعال
        if lead.status != MarketingLead.Status.REGISTERED:
            return False
        if lead.status == MarketingLead.Status.CUSTOMER:
            return False
        user = enrollment.user or find_user_by_phone(lead.phone_normalized)
        if not user:
            return False
        from django.db.models import Q
        from licenses.models import License
        has_license = License.objects.filter(
            order__user=user,
            order__status='paid',
            status='active',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).exists()
        return not has_license

    if lead.status in (
        MarketingLead.Status.REGISTERED,
        MarketingLead.Status.CUSTOMER,
        MarketingLead.Status.EXISTING_USER,
    ):
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


def pending_totals_for_campaigns(campaign_ids: list[int], step_number: int) -> dict:
    """تعداد مخاطبان در صف ارسال برای هر کمپین."""
    per_campaign: dict[int, int] = {}
    total = 0
    for cid in campaign_ids:
        campaign = LeadCampaign.objects.filter(pk=cid).first()
        if not campaign:
            per_campaign[cid] = 0
            continue
        step = campaign.steps.filter(step_number=step_number, is_active=True).first()
        if not step:
            per_campaign[cid] = 0
            continue
        n = pending_enrollments_for_step(campaign, step).count()
        per_campaign[cid] = n
        total += n
    return {
        'total_pending': total,
        'per_campaign': per_campaign,
        'campaign_count': len(campaign_ids),
    }


def send_campaigns_step_chunk(
    campaign_ids: list[int],
    step_number: int,
    *,
    request=None,
    limit: int | None = None,
) -> dict:
    """
    یک chunk از ارسال مرحله را روی چند کمپین انجام می‌دهد.
    خطای تک‌پیام باعث توقف کل chunk نمی‌شود؛ idempotency ارسال مجدد را امن می‌کند.
    """
    batch_limit = send_batch_size() if limit is None else max(1, min(500, int(limit)))
    agg = {
        'accepted': 0,
        'failed': 0,
        'skipped': 0,
        'idempotent': 0,
        'retried': 0,
        'errors': 0,
        'processed': 0,
        'sent': 0,
        'campaigns_touched': 0,
    }
    remaining_limit = batch_limit

    for cid in campaign_ids:
        if remaining_limit <= 0:
            break
        campaign = LeadCampaign.objects.filter(pk=cid).first()
        if not campaign:
            continue
        step = campaign.steps.filter(step_number=step_number, is_active=True).first()
        if not step:
            continue
        if pending_enrollments_for_step(campaign, step).count() <= 0:
            continue
        stats = send_campaign_step(
            campaign,
            step_number,
            request=request,
            limit=remaining_limit,
        )
        agg['campaigns_touched'] += 1
        for key in agg:
            if key == 'campaigns_touched':
                continue
            agg[key] += int(stats.get(key, 0) or 0)
        remaining_limit -= int(stats.get('processed', 0) or 0)

    totals = pending_totals_for_campaigns(campaign_ids, step_number)
    total_pending = totals['total_pending']
    if agg['processed'] <= 0 and total_pending > 0:
        # اگر به‌دلیل race یا پیام قبلی chunk خالی شد، یک بار دیگر تلاش می‌کنیم
        for cid in campaign_ids:
            campaign = LeadCampaign.objects.filter(pk=cid).first()
            if not campaign:
                continue
            step = campaign.steps.filter(step_number=step_number, is_active=True).first()
            if not step:
                continue
            enroll = pending_enrollments_for_step(campaign, step).first()
            if not enroll:
                continue
            try:
                msg = send_step_message(enrollment=enroll, step=step, request=request)
            except Exception:  # noqa: BLE001
                logger.exception('lead campaign fallback send failed enrollment=%s', enroll.pk)
                agg['errors'] += 1
                agg['processed'] += 1
                break
            agg['processed'] += 1
            if msg.status == CampaignMessage.Status.PROVIDER_ACCEPTED:
                agg['accepted'] += 1
                agg['sent'] += 1
            elif msg.status == CampaignMessage.Status.FAILED:
                agg['failed'] += 1
                agg['sent'] += 1
            elif msg.status == CampaignMessage.Status.SKIPPED:
                agg['skipped'] += 1
            else:
                agg['sent'] += 1
            totals = pending_totals_for_campaigns(campaign_ids, step_number)
            total_pending = totals['total_pending']
            break

    return {
        **agg,
        **totals,
        'batch_limit': batch_limit,
        'done': total_pending == 0,
        'step_number': step_number,
    }


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
    failed_qs.delete()

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
