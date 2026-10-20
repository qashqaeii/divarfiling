"""مشاوره خرید و انتخاب پلن — پاسخ قطعی و زمینه برای LLM."""
from __future__ import annotations

from public_assistant.services.persian_text import normalize_persian
from public_assistant.services.plan_intent import SubscriptionQueryContext
from public_assistant.services.public_plans import (
    PublicPlanCatalog,
    PublicPlanInfo,
    agency_bulk_note,
    agency_plan_limits,
    agency_quantity_status,
    catalog_context_for_llm,
    compare_personal_duration_savings,
    format_price,
    load_public_plan_catalog,
    public_plan_quote,
)
from shop.services.plan_pricing import get_agency_bulk_discount_percent

AGENCY_TEAM_COUNT_QUESTION = 'چند مشاور قرار است از اشتراک استفاده کنند؟'

PLAN_ADVISOR_SYSTEM_ADDENDUM = """
وقتی بخش «داده فروشگاه زنده» در پیام کاربر آمده، قیمت و مدت پلن‌ها فقط از آن بخش است — نه از حافظه و نه حدس.
هدیه ۷روزه ثبت‌نام (خوش‌آمدگویی) با پلن آزمایشی **خریدنی** یکی نیست؛ هر دو را از منابع دانشنامه تفکیک کن.
بدون ورود کاربر، تخفیف وفاداری، کد تخفیف یا معرف را قطعی اعلام نکن.
لحن: مشاور املاک حرفه‌ای، فارسی روان، بدون اغراق تبلیغاتی.
ساختار: جواب مستقیم → توضیح قیمت/مقایسه → پیشنهاد کوتاه با دلیل → لینک خرید رسمی در صورت نیاز.
برای سؤال ساده قیمت، کوتاه بمان.
"""


def build_plan_advisor_context(
    ctx: SubscriptionQueryContext,
    catalog: PublicPlanCatalog,
) -> str:
    return catalog_context_for_llm(
        catalog,
        team_size=ctx.team_size,
        duration=ctx.duration,
    )


def compose_subscription_answer(
    ctx: SubscriptionQueryContext,
    catalog: PublicPlanCatalog,
) -> str:
    """پاسخ خوانا بدون LLM — fallback و تست."""
    if ctx.is_property_listing:
        return ''

    if ctx.team_size == 1 and ctx.agency_context:
        return _agency_single_advisor_note(catalog)

    if ctx.needs_team_count:
        return _ask_agency_team_count(catalog, ctx)

    if ctx.agency_context or (ctx.team_size and ctx.team_size >= 2):
        agency_ans = _answer_agency(catalog, ctx)
        if agency_ans:
            return agency_ans

    if ctx.wants_welcome_gift and not ctx.wants_price:
        return _welcome_gift_pointer(catalog)

    if ctx.wants_features and not ctx.wants_comparison:
        return _features_same_across_plans(catalog)

    norm = normalize_persian(ctx.raw_message)
    duration_compare = ctx.wants_comparison and (
        ctx.duration in ('monthly', 'quarterly')
        or ('ماهانه' in norm and 'سه' in norm and 'ماه' in norm)
    )
    if duration_compare:
        cmp_ans = _compare_personal_durations(catalog, ctx.duration)
        if cmp_ans:
            return cmp_ans

    if ctx.wants_recommendation or ctx.newbie or ctx.solo_advisor:
        return _recommend_personal(catalog, ctx)

    if ctx.wants_comparison:
        cmp_ans = _compare_personal_durations(catalog, ctx.duration)
        if cmp_ans:
            return cmp_ans

    if ctx.wants_trial_info or (ctx.wants_price and ctx.duration == 'daily'):
        return _trial_paid_info(catalog)

    if ctx.wants_price or ctx.duration:
        return _personal_price_summary(catalog, ctx)

    if ctx.wants_features:
        return _features_same_across_plans(catalog)

    return _overview_short(catalog)


def compose_no_catalog_answer() -> str:
    return (
        'الان نتوانستم قیمت به‌روز پلن‌ها را از فروشگاه بخوانم. '
        'لطفاً مستقیم از صفحه خرید رسمی بررسی کنید: `/products/divar-extraction-bot/buy/` '
        'یا از `/contact/` راهنمایی بگیرید.'
    )


def _buy_line(plan: PublicPlanInfo | None, catalog: PublicPlanCatalog) -> str:
    url = plan.buy_url if plan else catalog.product_buy_url
    return f'خرید رسمی: {url}'


def _agency_single_advisor_note(catalog: PublicPlanCatalog) -> str:
    monthly = catalog.personal_by_type('monthly')
    min_agency = 2
    if catalog.agency:
        min_agency, _ = agency_plan_limits(catalog.agency[0])
    lines = [
        'برای **یک مشاور**، پلن **شخصی** مناسب‌تر از خرید گروهی آژانس است؛ '
        f'خرید آژانس از **{min_agency} لایسنس** به بالا طراحی شده.',
    ]
    if monthly:
        lines.append(f'پلن یک‌ماهه شخصی الان **{format_price(monthly.price)}** است.')
    lines.append(_buy_line(monthly, catalog))
    return '\n\n'.join(lines)


def _ask_agency_team_count(catalog: PublicPlanCatalog, ctx: SubscriptionQueryContext) -> str:
    dur = ctx.duration or 'quarterly'
    plan = catalog.agency_by_type(dur)
    hint = ''
    if plan:
        min_q, max_q = agency_plan_limits(plan)
        hint = f' (خرید آنلاین این پلن معمولاً **{min_q} تا {max_q}** لایسنس است)'
    return (
        f'برای محاسبه **قیمت کل آژانس**، {AGENCY_TEAM_COUNT_QUESTION}{hint}\n\n'
        f'صفحه خرید: {catalog.product_buy_url}'
    )


def _agency_over_capacity(catalog: PublicPlanCatalog, team_size: int, plan: PublicPlanInfo) -> str:
    _, max_q = agency_plan_limits(plan)
    return (
        f'برای **{team_size} مشاور**، خرید آنلاین این پلن حداکثر **{max_q} لایسنس** در یک سفارش دارد. '
        'برای تعداد بیشتر با پشتیبانی هماهنگ کنید: `/contact/`.\n\n'
        f'صفحه خرید آژانس: {catalog.product_buy_url}'
    )


def _answer_agency(catalog: PublicPlanCatalog, ctx: SubscriptionQueryContext) -> str:
    if ctx.team_size is None:
        return ''

    qty = ctx.team_size
    if qty < 2:
        return _agency_single_advisor_note(catalog)

    duration = ctx.duration or 'quarterly'
    plan = catalog.agency_by_type(duration) or (catalog.agency[0] if catalog.agency else None)
    if not plan:
        return compose_no_catalog_answer()

    status = agency_quantity_status(plan, qty)
    if status == 'below_min':
        return _agency_single_advisor_note(catalog)
    if status == 'above_max':
        return _agency_over_capacity(catalog, qty, plan)

    quote = public_plan_quote(catalog, plan, quantity=qty, strict=True)
    if not quote:
        return compose_no_catalog_answer()

    pct = int(get_agency_bulk_discount_percent(qty))
    lines = [
        f'برای **{qty} مشاور** با پلن **{plan.name}** (مدت {plan.duration_label}):',
        f'- قیمت پایه هر لایسنس: **{format_price(quote["base_unit_price"])}**',
        f'- تخفیف حجمی آژانس: **{pct}٪**',
        f'- قیمت هر لایسنس پس از تخفیف: **{format_price(quote["effective_unit_price"])}**',
        f'- **جمع مبلغ پایه سفارش: {format_price(quote["final_price"])}**',
        '',
        agency_bulk_note(),
        '',
        _buy_line(plan, catalog),
    ]
    return '\n'.join(lines)


def _compare_personal_durations(catalog: PublicPlanCatalog, focus: str | None) -> str | None:
    monthly = catalog.personal_by_type('monthly')
    if not monthly:
        return None

    if focus == 'yearly':
        yearly = catalog.personal_by_type('yearly')
        if not yearly:
            return None
        baseline = monthly.price * 12
        bundle = yearly.price
        savings = baseline - bundle
        lines = [
            'مقایسه **یک‌ساله** با خرید **۱۲ بار ماهانه** (با قیمت فعلی):',
            f'- ۱۲× ماهانه: **{format_price(baseline)}**',
            f'- پلن سالانه: **{format_price(bundle)}**',
        ]
        if savings > 0:
            lines.append(f'- پلن سالانه حدود **{format_price(savings)}** ارزان‌تر است.')
        else:
            lines.append('- با قیمت فعلی پلن سالانه از نظر جمع هزینه به‌صرفه‌تر نیست؛ مدت و شرایط را در فروشگاه ببینید.')
        target = yearly
    else:
        quarterly = catalog.personal_by_type('quarterly')
        if not quarterly:
            return None
        baseline = monthly.price * 3
        bundle = quarterly.price
        savings = baseline - bundle
        lines = [
            'مقایسه **سه‌ماهه** با خرید **۳ بار ماهانه** (با قیمت فعلی):',
            f'- ۳× ماهانه: **{format_price(baseline)}**',
            f'- پلن سه‌ماهه: **{format_price(bundle)}**',
        ]
        if savings > 0:
            lines.append(f'- پلن سه‌ماهه حدود **{format_price(savings)}** ارزان‌تر است.')
        else:
            lines.append('- با قیمت فعلی پلن سه‌ماهه از نظر جمع هزینه به‌صرفه‌تر نیست.')
        target = quarterly

    lines.append('امکانات اصلی یکسان است؛ تفاوت در **مدت** و **هزینه کل** است.')
    lines.append(_buy_line(target, catalog))
    return '\n\n'.join(lines)


def _recommend_personal(catalog: PublicPlanCatalog, ctx: SubscriptionQueryContext) -> str:
    monthly = catalog.personal_by_type('monthly')
    quarterly = catalog.personal_by_type('quarterly')
    lines: list[str] = []

    if ctx.newbie:
        lines.append(
            'اگر تازه مشاوره املاک را شروع کرده‌اید، منطقی است اول با **پلن یک‌ماهه شخصی** کار کنید '
            'تا استخراج، ثبت فایل و CRM را در عمل ببینید.'
        )
    elif ctx.solo_advisor:
        lines.append('برای **مشاور مستقل**، پلن‌های **شخصی** (نه آژانس چندلایسنس) مناسب‌ترند.')
    else:
        lines.append('برای کار **تک‌نفره**، پلن شخصی پیشنهاد می‌شود.')

    if monthly:
        lines.append(f'هزینه فعلی پلن یک‌ماهه: **{format_price(monthly.price)}**.')
    if catalog.trial:
        lines.append(
            f'اگر قبل از تعهد بلندمدت می‌خواهید امکانات را بسنجید، **پلن آزمایشی خریدنی** '
            f'({format_price(catalog.trial.price)} — {catalog.trial.duration_label}) هم دارید؛ '
            'این با **هدیه ۷روزه ثبت‌نام** (در صورت واجد شرایط بودن) متفاوت است.'
        )
    elif quarterly and ctx.wants_comparison:
        cmp_txt = _compare_personal_durations(catalog, ctx.duration)
        if cmp_txt:
            lines.append(cmp_txt)
    lines.append(_buy_line(monthly, catalog))
    return '\n\n'.join(lines)


def _trial_paid_info(catalog: PublicPlanCatalog) -> str:
    if not catalog.trial:
        return _overview_short(catalog)
    return (
        f'**پلن آزمایشی خریدنی** ({catalog.trial.name}): **{format_price(catalog.trial.price)}** '
        f'برای {catalog.trial.duration_label} دسترسی کامل لایسنس — پس از پرداخت فعال می‌شود.\n\n'
        '**هدیه ۷روزه ثبت‌نام** طرح جداگانه‌ای است که برای حساب‌های واجد شرایط ممکن است رایگان باشد؛ '
        'جایگزین هم نیستند.\n\n'
        + _buy_line(catalog.trial, catalog)
    )


def _personal_price_summary(catalog: PublicPlanCatalog, ctx: SubscriptionQueryContext) -> str:
    if ctx.duration:
        plan = catalog.personal_by_type(ctx.duration)
        if plan:
            return (
                f'**{plan.name}**: **{format_price(plan.price)}** ({plan.duration_label}).\n\n'
                + _buy_line(plan, catalog)
            )
        agency_plan = catalog.agency_by_type(ctx.duration)
        if agency_plan and ctx.team_size and ctx.team_size >= 2:
            ans = _answer_agency(catalog, ctx)
            if ans:
                return ans

    parts = ['**قیمت پلن‌های شخصی (فعلی):**']
    if catalog.trial:
        parts.append(f'- {catalog.trial.name}: {format_price(catalog.trial.price)}')
    for p in catalog.personal:
        parts.append(f'- {p.name}: {format_price(p.price)}')
    parts.append('')
    parts.append(_buy_line(None, catalog))
    return '\n'.join(parts)


def _features_same_across_plans(catalog: PublicPlanCatalog) -> str:
    monthly = catalog.personal_by_type('monthly')
    feat = monthly.feature_texts[:4] if monthly and monthly.feature_texts else []
    lines = [
        'در پلن‌های شخصی با مدت‌های مختلف، **هسته امکانات** (استخراج، فایلینگ، CRM و ابزارهای هوشمند محصول) '
        'معمولاً یکسان است؛ تفاوت اصلی **مدت اشتراک** و **هزینه** است.',
    ]
    if feat:
        lines.append('نمونه امکانات روی کارت پلن: ' + '؛ '.join(feat[:3]) + '.')
    lines.append(_buy_line(monthly, catalog))
    return '\n\n'.join(lines)


def _overview_short(catalog: PublicPlanCatalog) -> str:
    savings = compare_personal_duration_savings(catalog)
    lines = [
        'پلن‌های فعال فایلینگ دیوار شامل **شخصی** (یک مشاور)، **آزمایشی خریدنی** و **آژانس** (۲ تا ۲۵ لایسنس) است.',
        f'صفحه خرید: {catalog.product_buy_url}',
    ]
    if savings:
        best = max((s for s in savings if s['savings_positive']), key=lambda x: x['savings'], default=None)
        if best:
            lines.append(
                f'برای استفاده بلندمدت، {best["label"]} نسبت به چند بار خرید ماهانه معمولاً به‌صرفه‌تر است.'
            )
    return '\n\n'.join(lines)


def _welcome_gift_pointer(catalog: PublicPlanCatalog) -> str:
    trial_line = ''
    if catalog.trial:
        trial_line = (
            f'\n\nپلن آزمایشی **خریدنی** جداگانه: {format_price(catalog.trial.price)} — {catalog.trial.buy_url}'
        )
    return (
        '**هدیه ۷روزه** طرح خوش‌آمدگویی بعد از ثبت‌نام و تأیید موبایل است (برای همه تضمین نیست). '
        'بعد از ورود به میزکار وضعیت لایسنس خود را ببینید؛ راهنما: `/license-guide/`.'
        + trial_line
    )
