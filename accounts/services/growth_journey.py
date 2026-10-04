"""Orchestrator پایپلاین رشد یکپارچه — transition و backfill."""
from __future__ import annotations

import logging
from typing import Any, Optional

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import GrowthJourney, GrowthJourneyEvent, MarketingLead
from accounts.phone_utils import find_user_by_phone, normalize_phone

logger = logging.getLogger(__name__)

# رتبهٔ مرحله برای جلوگیری از پسرفت ناخواسته (به‌جز suppressed و رویدادهای صریح)
STAGE_RANK = {
    GrowthJourney.Stage.COLD_LEAD: 10,
    GrowthJourney.Stage.ENGAGED: 20,
    GrowthJourney.Stage.REGISTERED: 30,
    GrowthJourney.Stage.ACTIVATED: 35,
    GrowthJourney.Stage.NURTURE_UNPAID: 40,
    GrowthJourney.Stage.PENDING_CHECKOUT: 50,
    GrowthJourney.Stage.CUSTOMER: 60,
    GrowthJourney.Stage.EXPIRING_SOON: 70,
    GrowthJourney.Stage.RENEWED: 65,
    GrowthJourney.Stage.CHURN_RISK: 75,
    GrowthJourney.Stage.SUPPRESSED: 1000,
}

# رویدادهایی که اجازه پسرفت یا پرش دارند
FORCE_EVENTS = frozenset({
    'opt_out',
    'suppressed',
    'paid_licensed',
    'checkout_start',
    'license_expiring',
    'expired_no_renew',
    'repurchase',
    'pause_nurture',
    'resume_nurture',
    'manual_set',
})


def _resolve_phone(*, phone: str = '', user=None, lead: Optional[MarketingLead] = None) -> str:
    if phone:
        return normalize_phone(phone)
    if lead and lead.phone_normalized:
        return normalize_phone(lead.phone_normalized)
    if user is not None:
        return normalize_phone(getattr(user, 'phone', '') or '')
    return ''


def get_or_create_journey(
    *,
    phone: str = '',
    user=None,
    lead: Optional[MarketingLead] = None,
    source: str = GrowthJourney.Source.ACQUISITION,
) -> Optional[GrowthJourney]:
    phone = _resolve_phone(phone=phone, user=user, lead=lead)
    if not phone:
        return None

    defaults = {
        'source': source,
        'stage': GrowthJourney.Stage.COLD_LEAD,
        'last_touch_at': timezone.now(),
    }
    if user is not None:
        defaults['user'] = user
    if lead is not None:
        defaults['lead'] = lead

    journey, created = GrowthJourney.objects.get_or_create(
        phone_normalized=phone,
        defaults=defaults,
    )
    update_fields = []
    if user is not None and journey.user_id != getattr(user, 'pk', None):
        journey.user = user
        update_fields.append('user')
    if lead is not None and journey.lead_id != getattr(lead, 'pk', None):
        journey.lead = lead
        update_fields.append('lead')
    if update_fields:
        update_fields.append('updated_at')
        journey.save(update_fields=update_fields)
    return journey


@transaction.atomic
def transition(
    *,
    event_type: str,
    phone: str = '',
    user=None,
    lead: Optional[MarketingLead] = None,
    stage: Optional[str] = None,
    source: Optional[str] = None,
    ref_model: str = '',
    ref_id: str = '',
    metadata: Optional[dict] = None,
    allow_regress: bool = False,
) -> Optional[GrowthJourney]:
    """تنها نقطهٔ تغییر stage در پایپلاین رشد."""
    phone = _resolve_phone(phone=phone, user=user, lead=lead)
    if not phone:
        return None

    if stage is None:
        stage = _infer_stage(event_type)
    if not stage:
        logger.warning('growth_journey: no stage for event=%s', event_type)
        return None

    journey = get_or_create_journey(phone=phone, user=user, lead=lead, source=source or GrowthJourney.Source.ACQUISITION)
    if not journey:
        return None

    journey = GrowthJourney.objects.select_for_update().get(pk=journey.pk)
    old_stage = journey.stage

    if event_type == 'pause_nurture':
        journey.nurture_paused = True
        journey.save(update_fields=['nurture_paused', 'updated_at'])
        GrowthJourneyEvent.objects.create(
            journey=journey,
            stage_from=old_stage,
            stage_to=old_stage,
            event_type=event_type,
            ref_model=ref_model,
            ref_id=str(ref_id or ''),
            metadata=metadata or {},
        )
        return journey

    if event_type == 'resume_nurture':
        journey.nurture_paused = False
        journey.save(update_fields=['nurture_paused', 'updated_at'])
        GrowthJourneyEvent.objects.create(
            journey=journey,
            stage_from=old_stage,
            stage_to=old_stage,
            event_type=event_type,
            ref_model=ref_model,
            ref_id=str(ref_id or ''),
            metadata=metadata or {},
        )
        return journey

    if stage == GrowthJourney.Stage.SUPPRESSED or event_type in ('opt_out', 'suppressed'):
        journey.stage = GrowthJourney.Stage.SUPPRESSED
        journey.suppressed = True
        journey.stage_entered_at = timezone.now()
        journey.last_touch_at = timezone.now()
        if user is not None:
            journey.user = user
        if lead is not None:
            journey.lead = lead
        journey.save()
        GrowthJourneyEvent.objects.create(
            journey=journey,
            stage_from=old_stage,
            stage_to=journey.stage,
            event_type=event_type,
            ref_model=ref_model,
            ref_id=str(ref_id or ''),
            metadata=metadata or {},
        )
        _exit_active_enrollments(journey, reason=event_type)
        return journey

    force = allow_regress or event_type in FORCE_EVENTS
    old_rank = STAGE_RANK.get(old_stage, 0)
    new_rank = STAGE_RANK.get(stage, 0)
    if not force and new_rank < old_rank:
        # فقط لمس زمانی؛ stage ثابت
        journey.last_touch_at = timezone.now()
        journey.save(update_fields=['last_touch_at', 'updated_at'])
        return journey

    if old_stage == stage and event_type not in FORCE_EVENTS:
        journey.last_touch_at = timezone.now()
        if user is not None and journey.user_id != user.pk:
            journey.user = user
            journey.save(update_fields=['last_touch_at', 'user', 'updated_at'])
        else:
            journey.save(update_fields=['last_touch_at', 'updated_at'])
        return journey

    journey.stage = stage
    journey.stage_entered_at = timezone.now()
    journey.last_touch_at = timezone.now()
    if source:
        journey.source = source
    if user is not None:
        journey.user = user
    if lead is not None:
        journey.lead = lead
    if stage == GrowthJourney.Stage.CUSTOMER:
        journey.suppressed = False
    journey.save()

    GrowthJourneyEvent.objects.create(
        journey=journey,
        stage_from=old_stage,
        stage_to=stage,
        event_type=event_type,
        ref_model=ref_model,
        ref_id=str(ref_id or ''),
        metadata=metadata or {},
    )
    return journey


def _infer_stage(event_type: str) -> Optional[str]:
    mapping = {
        'lead_imported': GrowthJourney.Stage.COLD_LEAD,
        'click_landing': GrowthJourney.Stage.ENGAGED,
        'signup': GrowthJourney.Stage.REGISTERED,
        'signup_complete': GrowthJourney.Stage.REGISTERED,
        'workspace_login': GrowthJourney.Stage.ACTIVATED,
        'checkout_start': GrowthJourney.Stage.PENDING_CHECKOUT,
        'no_purchase_window': GrowthJourney.Stage.NURTURE_UNPAID,
        'paid_licensed': GrowthJourney.Stage.CUSTOMER,
        'license_expiring': GrowthJourney.Stage.EXPIRING_SOON,
        'repurchase': GrowthJourney.Stage.RENEWED,
        'expired_no_renew': GrowthJourney.Stage.CHURN_RISK,
        'opt_out': GrowthJourney.Stage.SUPPRESSED,
        'suppressed': GrowthJourney.Stage.SUPPRESSED,
    }
    return mapping.get(event_type)


def _exit_active_enrollments(journey: GrowthJourney, *, reason: str) -> None:
    from accounts.models import CampaignEnrollment, LeadCampaign
    if not journey.lead_id:
        return
    status = (
        CampaignEnrollment.Status.EXITED_OPT_OUT
        if reason in ('opt_out', 'suppressed')
        else CampaignEnrollment.Status.EXITED_SUPPRESSED
    )
    now = timezone.now()
    CampaignEnrollment.objects.filter(
        lead_id=journey.lead_id,
        status=CampaignEnrollment.Status.ACTIVE,
        campaign__kind__in=(LeadCampaign.Kind.ACQUISITION, LeadCampaign.Kind.ACTIVATION),
    ).update(status=status, exited_at=now)


def lead_status_to_stage(status: str) -> str:
    return {
        MarketingLead.Status.COLD: GrowthJourney.Stage.COLD_LEAD,
        MarketingLead.Status.ENGAGED: GrowthJourney.Stage.ENGAGED,
        MarketingLead.Status.REGISTERED: GrowthJourney.Stage.REGISTERED,
        MarketingLead.Status.CUSTOMER: GrowthJourney.Stage.CUSTOMER,
        MarketingLead.Status.SUPPRESSED: GrowthJourney.Stage.SUPPRESSED,
        MarketingLead.Status.EXISTING_USER: GrowthJourney.Stage.REGISTERED,
    }.get(status, GrowthJourney.Stage.COLD_LEAD)


def backfill_journeys(*, limit: int = 5000) -> dict[str, int]:
    """ساخت/به‌روزرسانی Journey از MarketingLead و کاربران دارای سفارش/لایسنس."""
    from django.contrib.auth import get_user_model
    from licenses.models import License
    from shop.models import Order

    User = get_user_model()
    stats = {'leads': 0, 'users': 0, 'updated': 0, 'created': 0}

    for lead in MarketingLead.objects.order_by('-updated_at')[:limit]:
        journey = get_or_create_journey(
            phone=lead.phone_normalized,
            lead=lead,
            user=lead.matched_user,
            source=(
                GrowthJourney.Source.EXISTING_USER
                if lead.status == MarketingLead.Status.EXISTING_USER
                else GrowthJourney.Source.ACQUISITION
            ),
        )
        if not journey:
            continue
        target = lead_status_to_stage(lead.status)
        created = journey.events.count() == 0 and journey.stage == GrowthJourney.Stage.COLD_LEAD
        if journey.stage != target:
            transition(
                phone=lead.phone_normalized,
                lead=lead,
                user=lead.matched_user,
                event_type='manual_set',
                stage=target,
                allow_regress=True,
                metadata={'backfill': True, 'from_lead_status': lead.status},
            )
            stats['updated'] += 1
        elif created:
            stats['created'] += 1
        stats['leads'] += 1

    # کاربران با سفارش معلق
    pending_user_ids = (
        Order.objects.filter(status__in=('pending', 'pending_verification'))
        .values_list('user_id', flat=True)
        .distinct()[:limit]
    )
    for user in User.objects.filter(pk__in=pending_user_ids).exclude(phone=''):
        phone = normalize_phone(user.phone or '')
        if not phone:
            continue
        transition(
            phone=phone,
            user=user,
            event_type='checkout_start',
            stage=GrowthJourney.Stage.PENDING_CHECKOUT,
            source=GrowthJourney.Source.ORGANIC,
            allow_regress=True,
            metadata={'backfill': True},
        )
        stats['users'] += 1

    # مشتریان با لایسنس فعال
    active_lic_user_ids = (
        License.objects.filter(order__status='paid', status='active')
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        .values_list('order__user_id', flat=True)
        .distinct()[:limit]
    )
    for user in User.objects.filter(pk__in=active_lic_user_ids).exclude(phone=''):
        phone = normalize_phone(user.phone or '')
        if not phone:
            continue
        journey = GrowthJourney.objects.filter(phone_normalized=phone).first()
        if journey and journey.stage in (
            GrowthJourney.Stage.EXPIRING_SOON,
            GrowthJourney.Stage.CHURN_RISK,
            GrowthJourney.Stage.RENEWED,
        ):
            continue
        transition(
            phone=phone,
            user=user,
            event_type='paid_licensed',
            stage=GrowthJourney.Stage.CUSTOMER,
            source=GrowthJourney.Source.ORGANIC,
            allow_regress=True,
            metadata={'backfill': True},
        )
        stats['users'] += 1

    return stats


def pipeline_overview() -> dict[str, Any]:
    """شاخص‌های داشبورد پایپلاین رشد — با توضیح کاربردی برای ادمین."""
    counts = {
        row['stage']: row['c']
        for row in GrowthJourney.objects.values('stage').annotate(c=Count('id'))
    }

    # ترتیب مسیر واقعی کسب‌وکار (نه الفبایی)
    stage_guide = [
        {
            'key': GrowthJourney.Stage.COLD_LEAD,
            'label': 'سرنخ سرد',
            'meaning': 'پیامک معرفی خورده یا در صف است؛ هنوز لینک را باز نکرده.',
            'next_action': 'کرون بعد از ۲ روز یادآوری (مرحله ۲) می‌فرستد.',
            'you_do': 'کاری لازم نیست.',
        },
        {
            'key': GrowthJourney.Stage.ENGAGED,
            'label': 'لینک را باز کرده',
            'meaning': 'روی لینک پیامک کلیک کرده / لندینگ دیده؛ هنوز ثبت‌نام نکرده.',
            'next_action': 'کرون یادآوری می‌فرستد؛ بعد از چند روز پیام گرم‌تر (مرحله ۳).',
            'you_do': 'کاری لازم نیست.',
        },
        {
            'key': GrowthJourney.Stage.REGISTERED,
            'label': 'ثبت‌نام کرده',
            'meaning': 'حساب ساخته؛ هنوز خرید/لایسنس فعال ندارد.',
            'next_action': 'پیام خوش‌آمد Activation و یادآوری خرید خودکار می‌رود.',
            'you_do': 'کاری لازم نیست مگر بخواهید دستی تخفیف بدهید.',
        },
        {
            'key': GrowthJourney.Stage.ACTIVATED,
            'label': 'وارد میزکار شده',
            'meaning': 'حداقل یک‌بار وارد داشبورد شده؛ هنوز مشتری پولی نیست.',
            'next_action': 'یادآوری خرید ادامه دارد تا بخرد یا سبد بسازد.',
            'you_do': 'کاری لازم نیست.',
        },
        {
            'key': GrowthJourney.Stage.NURTURE_UNPAID,
            'label': 'پیگیری بدون خرید',
            'meaning': 'ثبت‌نام کرده و چند یادآوری خریده؛ هنوز پول نداده.',
            'next_action': 'یادآوری‌های Activation ادامه می‌یابد (با سقف مراحل).',
            'you_do': 'اختیاری: از مرکز مارکتینگ کمپین دستی بفرستید.',
        },
        {
            'key': GrowthJourney.Stage.PENDING_CHECKOUT,
            'label': 'سفارش پرداخت‌نشده',
            'meaning': 'سفارش ساخته ولی پرداخت نکرده (سبد معلق).',
            'next_action': 'کرون Recovery پیام بازیابی می‌فرستد (جدا از جذب).',
            'you_do': 'کاری لازم نیست اگر recovery-cron روشن است.',
        },
        {
            'key': GrowthJourney.Stage.CUSTOMER,
            'label': 'مشتری (خرید کرده)',
            'meaning': 'پرداخت موفق / لایسنس فعال دارد.',
            'next_action': 'پیام فروش متوقف می‌شود؛ نزدیک انقضا تمدید می‌آید.',
            'you_do': 'کاری لازم نیست.',
        },
        {
            'key': GrowthJourney.Stage.EXPIRING_SOON,
            'label': 'لایسنس رو به انقضا',
            'meaning': 'لایسنس تا چند روز دیگر تمام می‌شود.',
            'next_action': 'با --renewal-live پیام تمدید می‌رود (فعلاً اگر در کرون باشد).',
            'you_do': 'اگر می‌خواهید تمدید خودکار SMS شود، فلگ renewal-live را در کرون بگذارید.',
        },
        {
            'key': GrowthJourney.Stage.RENEWED,
            'label': 'تمدید کرده',
            'meaning': 'دوباره خرید/تمدید کرده.',
            'next_action': 'مثل مشتری عادی می‌ماند.',
            'you_do': 'کاری لازم نیست.',
        },
        {
            'key': GrowthJourney.Stage.CHURN_RISK,
            'label': 'منقضی بدون تمدید',
            'meaning': 'لایسنس تمام شده و هنوز تمدید نکرده.',
            'next_action': 'پیام بازگشت/تمدید (اگر renewal-live روشن باشد).',
            'you_do': 'اختیاری: پیگیری دستی مشتریان مهم.',
        },
        {
            'key': GrowthJourney.Stage.SUPPRESSED,
            'label': 'مسدود / لغو دریافت',
            'meaning': 'دیگر پیام بازاریابی نباید بگیرد.',
            'next_action': 'هیچ SMS خودکاری نمی‌رود.',
            'you_do': 'فقط اگر اشتباه مسدود شده، از لیست suppression خارج کنید.',
        },
    ]

    stages = []
    for item in stage_guide:
        key = item['key']
        stages.append({
            **item,
            'count': int(counts.get(key, 0) or 0),
        })

    total = sum(s['count'] for s in stages)
    paused = GrowthJourney.objects.filter(nurture_paused=True).count()
    suppressed = GrowthJourney.objects.filter(
        Q(suppressed=True) | Q(stage=GrowthJourney.Stage.SUPPRESSED)
    ).count()

    # خلاصه عملی برای داشبورد بالا
    cold = int(counts.get(GrowthJourney.Stage.COLD_LEAD, 0) or 0)
    engaged = int(counts.get(GrowthJourney.Stage.ENGAGED, 0) or 0)
    registered = int(counts.get(GrowthJourney.Stage.REGISTERED, 0) or 0)
    activated = int(counts.get(GrowthJourney.Stage.ACTIVATED, 0) or 0)
    nurture = int(counts.get(GrowthJourney.Stage.NURTURE_UNPAID, 0) or 0)
    pending = int(counts.get(GrowthJourney.Stage.PENDING_CHECKOUT, 0) or 0)
    customers = int(counts.get(GrowthJourney.Stage.CUSTOMER, 0) or 0)
    waiting_purchase = registered + activated + nurture

    recent = list(
        GrowthJourneyEvent.objects.select_related('journey')
        .order_by('-created_at')[:20]
        .values(
            'event_type', 'stage_from', 'stage_to', 'created_at',
            'journey__phone_normalized', 'journey_id',
        )
    )

    return {
        'total': total,
        'paused': paused,
        'suppressed': suppressed,
        'stages': stages,
        'recent_events': recent,
        'summary': {
            'cold_or_engaged': cold + engaged,
            'waiting_purchase': waiting_purchase,
            'pending_checkout': pending,
            'customers': customers,
            'cold': cold,
            'engaged': engaged,
            'registered': registered,
            'activated': activated,
            'nurture': nurture,
            'expiring': int(counts.get(GrowthJourney.Stage.EXPIRING_SOON, 0) or 0),
            'churn': int(counts.get(GrowthJourney.Stage.CHURN_RISK, 0) or 0),
            'renewed': int(counts.get(GrowthJourney.Stage.RENEWED, 0) or 0),
        },
        'charts': build_pipeline_charts(counts=counts, summary={
            'cold': cold,
            'engaged': engaged,
            'registered': registered,
            'activated': activated,
            'nurture': nurture,
            'pending': pending,
            'customers': customers,
        }),
    }


def build_pipeline_charts(*, counts: dict, summary: dict) -> dict[str, Any]:
    """داده نمودارهای داشبورد پایپلاین رشد."""
    import jdatetime
    from datetime import timedelta
    from django.db.models.functions import TruncDate

    funnel_labels = [
        'سرد', 'تعامل', 'ثبت‌نام', 'فعال', 'بدون خرید', 'سبد معلق', 'مشتری',
    ]
    funnel_values = [
        summary.get('cold', 0),
        summary.get('engaged', 0),
        summary.get('registered', 0),
        summary.get('activated', 0),
        summary.get('nurture', 0),
        summary.get('pending', 0),
        summary.get('customers', 0),
    ]

    # توزیع مرحله برای دونات (فقط stageهای با count>0)
    stage_order = [
        GrowthJourney.Stage.COLD_LEAD,
        GrowthJourney.Stage.ENGAGED,
        GrowthJourney.Stage.REGISTERED,
        GrowthJourney.Stage.ACTIVATED,
        GrowthJourney.Stage.NURTURE_UNPAID,
        GrowthJourney.Stage.PENDING_CHECKOUT,
        GrowthJourney.Stage.CUSTOMER,
        GrowthJourney.Stage.EXPIRING_SOON,
        GrowthJourney.Stage.RENEWED,
        GrowthJourney.Stage.CHURN_RISK,
        GrowthJourney.Stage.SUPPRESSED,
    ]
    labels_map = dict(GrowthJourney.Stage.choices)
    dist_labels, dist_values, dist_keys = [], [], []
    for key in stage_order:
        c = int(counts.get(key, 0) or 0)
        if c <= 0:
            continue
        dist_keys.append(key)
        dist_labels.append(labels_map.get(key, key))
        dist_values.append(c)

    # روند ۱۴ روزه رویدادها
    now = timezone.now()
    since = now - timedelta(days=13)
    day_counts = {
        row['day'].date() if hasattr(row['day'], 'date') else row['day']: row['c']
        for row in (
            GrowthJourneyEvent.objects.filter(created_at__gte=since)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(c=Count('id'))
        )
        if row['day']
    }
    trend_labels, trend_values = [], []
    for i in range(13, -1, -1):
        day = timezone.localtime(now - timedelta(days=i)).date()
        jday = jdatetime.date.fromgregorian(date=day)
        trend_labels.append(jday.strftime('%m/%d'))
        trend_values.append(int(day_counts.get(day, 0) or 0))

    # رویدادها بر اساس نوع (۱۴ روز)
    event_type_rows = (
        GrowthJourneyEvent.objects.filter(created_at__gte=since)
        .values('event_type')
        .annotate(c=Count('id'))
        .order_by('-c')[:8]
    )
    event_label_map = {
        'lead_imported': 'ورود سرنخ',
        'click_landing': 'کلیک',
        'signup': 'ثبت‌نام',
        'workspace_login': 'ورود میزکار',
        'checkout_start': 'سبد',
        'no_purchase_window': 'پیگیری خرید',
        'paid_licensed': 'خرید',
        'license_expiring': 'نزدیک انقضا',
        'expired_no_renew': 'ریسک ریزش',
        'manual_set': 'همگام‌سازی',
        'opt_out': 'لغو',
    }
    event_labels = [
        event_label_map.get(r['event_type'], r['event_type']) for r in event_type_rows
    ]
    event_values = [int(r['c'] or 0) for r in event_type_rows]

    # نرخ تبدیل تقریبی نسبت به کل
    total = max(1, sum(int(v or 0) for v in counts.values()))
    cold_eng = summary.get('cold', 0) + summary.get('engaged', 0)
    rates = {
        'click_rate': round(100.0 * summary.get('engaged', 0) / max(1, cold_eng), 1) if cold_eng else 0,
        'reg_rate': round(
            100.0 * summary.get('registered', 0) / max(1, summary.get('engaged', 0) or cold_eng),
            1,
        ),
        'pay_rate': round(
            100.0 * summary.get('customers', 0) / max(
                1,
                summary.get('registered', 0)
                + summary.get('activated', 0)
                + summary.get('nurture', 0)
                + summary.get('customers', 0),
            ),
            1,
        ),
        'customer_share': round(100.0 * summary.get('customers', 0) / total, 1),
    }

    source_rows = (
        GrowthJourney.objects.values('source')
        .annotate(c=Count('id'))
        .order_by('-c')
    )
    source_map = dict(GrowthJourney.Source.choices)
    source_labels = [source_map.get(r['source'], r['source']) for r in source_rows]
    source_values = [int(r['c'] or 0) for r in source_rows]

    return {
        'funnel': {'labels': funnel_labels, 'values': funnel_values},
        'distribution': {
            'labels': dist_labels,
            'values': dist_values,
            'keys': dist_keys,
        },
        'trend': {'labels': trend_labels, 'values': trend_values},
        'events': {'labels': event_labels, 'values': event_values},
        'sources': {'labels': source_labels, 'values': source_values},
        'rates': rates,
    }


def _parse_run_timestamp(value):
    """ISO string یا datetime → datetime aware برای نمایش شمسی."""
    if value is None or value == '':
        return None
    if hasattr(value, 'strftime'):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        from django.utils.dateparse import parse_datetime
        dt = parse_datetime(text.replace('Z', '+00:00'))
        if dt is None:
            from datetime import datetime
            dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except Exception:
        return None


def summarize_last_run(last_run: Optional[dict] = None) -> dict[str, Any]:
    """خلاصه فارسی و قابل‌فهم از خروجی run_growth_pipeline."""
    last_run = last_run or {}
    parts = last_run.get('parts') or {}
    lines = []
    sms_sent = 0
    sms_failed = 0

    acq = parts.get('acquisition') or {}
    for camp in acq.get('campaigns') or []:
        for step_no, st in (camp.get('steps') or {}).items():
            accepted = int(st.get('accepted') or 0)
            failed = int(st.get('failed') or 0)
            due = int(st.get('due') or 0)
            sms_sent += accepted
            sms_failed += failed
            if accepted or due:
                lines.append(
                    f'جذب کمپین #{camp.get("campaign_id")} مرحله {step_no}: '
                    f'{accepted} پیامک ارسال · {due} در صف'
                )

    act = parts.get('activation') or {}
    for camp in act.get('campaigns') or []:
        for step_no, st in (camp.get('steps') or {}).items():
            accepted = int(st.get('accepted') or 0)
            failed = int(st.get('failed') or 0)
            due = int(st.get('due') or 0)
            sms_sent += accepted
            sms_failed += failed
            if accepted or due:
                lines.append(
                    f'فعال‌سازی مرحله {step_no}: {accepted} پیامک · {due} در صف'
                )

    backfill = parts.get('backfill')
    if backfill:
        lines.append(
            f'همگام‌سازی اولیه: {backfill.get("leads", 0)} سرنخ بررسی · '
            f'{backfill.get("created", 0)} پرونده جدید · {backfill.get("updated", 0)} به‌روز'
        )

    recovery = parts.get('recovery')
    if recovery and not recovery.get('error'):
        would = recovery.get('would_send') or recovery.get('recovery_stats', {}).get('would_send')
        if would is not None:
            lines.append(f'بازیابی سبد (شبیه‌سازی/اجرا): would_send≈{would}')

    renewal = parts.get('license_renewal') or {}
    if renewal:
        lines.append(
            f'تمدید لایسنس: بررسی {renewal.get("examined", 0)} · '
            f'would_send {renewal.get("would_send", 0)} · ارسال واقعی {renewal.get("sent", 0)}'
        )

    if not lines:
        lines.append('در این اجرا پیامکی due نبود (یا هنوز کرون اجرا نشده).')

    return {
        'sms_sent': sms_sent,
        'sms_failed': sms_failed,
        'lines': lines,
        'started_at': _parse_run_timestamp(last_run.get('started_at')),
        'finished_at': _parse_run_timestamp(last_run.get('finished_at')),
        'has_data': bool(last_run),
    }


def journeys_for_stage(stage: str, *, limit: int = 100):
    return (
        GrowthJourney.objects.filter(stage=stage)
        .select_related('user', 'lead')
        .order_by('-stage_entered_at')[:limit]
    )


def journey_display_name(journey: GrowthJourney) -> str:
    """نام مشاور یا آژانس برای گزارش و خروجی — اولویت با دادهٔ سرنخ جذب."""
    lead = journey.lead
    if lead and (lead.display_name or '').strip():
        return lead.display_name.strip()
    user = journey.user
    if user:
        ws = getattr(user, 'workspace_settings', None)
        agency = (getattr(ws, 'agency_name', None) or '').strip() if ws else ''
        if agency:
            return agency
        full = (user.get_full_name() or '').strip()
        if full:
            return full
    return ''


def journey_extraction_district(journey: GrowthJourney) -> str:
    """منطقهٔ استخراج سرنخ — همان منطق نمایش در پیامک، بدون placeholder بازاریابی."""
    lead = journey.lead
    if not lead:
        return ''
    from accounts.services.lead_import import display_district_for_lead

    label = (display_district_for_lead(lead) or '').strip()
    if label == 'منطقه شما':
        return ''
    return label


def on_lead_imported(lead: MarketingLead) -> Optional[GrowthJourney]:
    if lead.status == MarketingLead.Status.EXISTING_USER:
        return transition(
            phone=lead.phone_normalized,
            lead=lead,
            user=lead.matched_user,
            event_type='manual_set',
            stage=GrowthJourney.Stage.REGISTERED,
            source=GrowthJourney.Source.EXISTING_USER,
            allow_regress=True,
            metadata={'existing_user': True},
        )
    return transition(
        phone=lead.phone_normalized,
        lead=lead,
        user=lead.matched_user,
        event_type='lead_imported',
        stage=GrowthJourney.Stage.COLD_LEAD,
        source=GrowthJourney.Source.ACQUISITION,
    )


def on_click_landing(*, lead: MarketingLead, message=None) -> Optional[GrowthJourney]:
    return transition(
        phone=lead.phone_normalized,
        lead=lead,
        event_type='click_landing',
        stage=GrowthJourney.Stage.ENGAGED,
        source=GrowthJourney.Source.ACQUISITION,
        ref_model='CampaignMessage',
        ref_id=getattr(message, 'pk', '') or '',
    )


def on_signup(*, user, lead: Optional[MarketingLead] = None) -> Optional[GrowthJourney]:
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    if lead is None and phone:
        lead = MarketingLead.objects.filter(phone_normalized=phone).first()
    return transition(
        phone=phone,
        user=user,
        lead=lead,
        event_type='signup',
        stage=GrowthJourney.Stage.REGISTERED,
        source=GrowthJourney.Source.ACQUISITION if lead else GrowthJourney.Source.ORGANIC,
        ref_model='User',
        ref_id=user.pk,
        allow_regress=True,
    )


def on_workspace_login(*, user) -> Optional[GrowthJourney]:
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    if not phone:
        return None
    journey = GrowthJourney.objects.filter(phone_normalized=phone).first()
    if journey and journey.stage in (
        GrowthJourney.Stage.CUSTOMER,
        GrowthJourney.Stage.PENDING_CHECKOUT,
        GrowthJourney.Stage.EXPIRING_SOON,
        GrowthJourney.Stage.CHURN_RISK,
        GrowthJourney.Stage.RENEWED,
        GrowthJourney.Stage.SUPPRESSED,
    ):
        journey.last_touch_at = timezone.now()
        journey.save(update_fields=['last_touch_at', 'updated_at'])
        return journey
    return transition(
        phone=phone,
        user=user,
        event_type='workspace_login',
        stage=GrowthJourney.Stage.ACTIVATED,
        allow_regress=False,
        ref_model='User',
        ref_id=user.pk,
    )


def on_checkout_start(*, user, order=None) -> Optional[GrowthJourney]:
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    if not phone:
        return None
    return transition(
        phone=phone,
        user=user,
        event_type='checkout_start',
        stage=GrowthJourney.Stage.PENDING_CHECKOUT,
        allow_regress=True,
        ref_model='Order' if order is not None else '',
        ref_id=str(getattr(order, 'pk', '') or ''),
    )


def on_purchase(*, user, order=None, lead: Optional[MarketingLead] = None) -> Optional[GrowthJourney]:
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    if lead is None and phone:
        lead = MarketingLead.objects.filter(phone_normalized=phone).first()
    return transition(
        phone=phone,
        user=user,
        lead=lead,
        event_type='paid_licensed',
        stage=GrowthJourney.Stage.CUSTOMER,
        allow_regress=True,
        ref_model='Order' if order is not None else '',
        ref_id=str(getattr(order, 'pk', '') or ''),
    )
