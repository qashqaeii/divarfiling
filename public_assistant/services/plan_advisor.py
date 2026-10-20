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
from public_assistant.services.public_links import (
    LINK_STYLE_PROMPT,
    contact_link,
    license_guide_link,
    plan_purchase_markdown,
    workspace_link,
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
""" + LINK_STYLE_PROMPT


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

    norm = normalize_persian(ctx.raw_message)

    if ctx.team_size == 1 and ctx.agency_context:
        return _agency_single_advisor_note(catalog)

    if ctx.needs_team_count:
        return _ask_agency_team_count(catalog, ctx)

    if ctx.wants_welcome_gift or (
        ctx.wants_trial_info and any(w in norm for w in ('هدیه', 'رایگان', 'خوش'))
    ):
        return _welcome_gift_and_trial_answer(catalog, ctx)

    if ctx.agency_context or (ctx.team_size and ctx.team_size >= 2):
        agency_ans = _answer_agency(catalog, ctx)
        if agency_ans:
            return agency_ans

    if ctx.wants_features and not ctx.wants_comparison:
        return _features_same_across_plans(catalog)

    multi_duration_compare = ctx.wants_comparison and (
        ('سال' in norm or 'yearly' in norm)
        and ('سه' in norm or 'quarterly' in norm)
        and ('ماه' in norm or 'monthly' in norm or 'یک‌ماه' in norm or 'یک ماه' in norm)
    )
    if multi_duration_compare:
        cmp_ans = _compare_personal_all_durations(catalog)
        if cmp_ans:
            return cmp_ans

    duration_compare = ctx.wants_comparison and (
        ctx.duration in ('monthly', 'quarterly')
        or ('ماهانه' in norm and 'سه' in norm and 'ماه' in norm)
    )
    if duration_compare:
        cmp_ans = _compare_personal_durations(catalog, ctx.duration)
        if cmp_ans:
            return cmp_ans

    if (ctx.wants_recommendation or ctx.newbie or ctx.solo_advisor) and not (
        ctx.agency_context or (ctx.team_size and ctx.team_size >= 2)
    ):
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
    from public_assistant.services.public_copy import finalize_public_answer

    return finalize_public_answer(
        'الان نتوانستم قیمت به‌روز پلن‌ها را از فروشگاه بخوانم. '
        f'{plan_purchase_markdown(None, None, inline=True)} '
        f'یا از {contact_link()} راهنمایی بگیرید.'
    )


def _buy_line(plan: PublicPlanInfo | None, catalog: PublicPlanCatalog) -> str:
    return plan_purchase_markdown(plan, catalog, inline=True)


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
        f'{plan_purchase_markdown(plan, catalog, inline=True)}'
    )


def _agency_over_capacity(catalog: PublicPlanCatalog, team_size: int, plan: PublicPlanInfo) -> str:
    _, max_q = agency_plan_limits(plan)
    return (
        f'برای **{team_size} مشاور**، خرید آنلاین این پلن حداکثر **{max_q} لایسنس** در یک سفارش دارد. '
        f'برای تعداد بیشتر {contact_link(inline=True)}.\n\n'
        f'{plan_purchase_markdown(plan, catalog, inline=True)}'
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

    if ctx.newbie or ctx.solo_advisor:
        lines.append(
            'برای **مشاور مستقل** (به‌ویژه تازه‌کار)، پلن‌های **شخصی** مناسب‌تر از آژانس چندلایسنس است؛ '
            'می‌توانید با یک ماه کار عملی شروع کنید یا قبلش امکانات را با پلن آزمایشی خریدنی بسنجید.'
        )
    else:
        lines.append('برای کار **تک‌نفره**، پلن شخصی پیشنهاد می‌شود.')

    if monthly:
        lines.append(f'- پلن **یک‌ماهه شخصی**: **{format_price(monthly.price)}**')
    if quarterly:
        lines.append(f'- پلن **سه‌ماهه شخصی**: **{format_price(quarterly.price)}** (برای ادامه بعد از ماه اول)')
    if catalog.trial:
        lines.append(
            f'- **پلن آزمایشی خریدنی**: {format_price(catalog.trial.price)} — {catalog.trial.duration_label} '
            '(متفاوت از **هدیه ۷روزه ثبت‌نام** در صورت واجد شرایط بودن)'
        )
    lines.append(
        'امکانات اصلی (CRM، استخراج، فایلینگ) بین مدت‌های شخصی یکسان است؛ تفاوت در مدت و هزینه کل است.'
    )
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
        plan_purchase_markdown(None, catalog, inline=True),
    ]
    if savings:
        best = max((s for s in savings if s['savings_positive']), key=lambda x: x['savings'], default=None)
        if best:
            lines.append(
                f'برای استفاده بلندمدت، {best["label"]} نسبت به چند بار خرید ماهانه معمولاً به‌صرفه‌تر است.'
            )
    return '\n\n'.join(lines)


def _compare_personal_all_durations(catalog: PublicPlanCatalog) -> str | None:
    monthly = catalog.personal_by_type('monthly')
    quarterly = catalog.personal_by_type('quarterly')
    yearly = catalog.personal_by_type('yearly')
    if not monthly or not quarterly or not yearly:
        return None
    baseline_3 = monthly.price * 3
    baseline_12 = monthly.price * 12
    savings_3 = baseline_3 - quarterly.price
    lines = [
        '**امکانات اصلی یکسان است**؛ تفاوت فقط در **مدت** و **هزینه کل** است.',
        '',
        f'- **یک‌ماهه شخصی**: {format_price(monthly.price)}',
        f'- **سه‌ماهه شخصی**: {format_price(quarterly.price)}',
        f'- **یک‌ساله شخصی**: {format_price(yearly.price)}',
        '',
        'اگر حداقل **۳ ماه** استفاده می‌کنید:',
        f'- خرید ۳× ماهانه: **{format_price(baseline_3)}**',
        f'- پلن سه‌ماهه: **{format_price(quarterly.price)}**',
    ]
    if savings_3 > 0:
        lines.append(f'- پلن سه‌ماهه **{format_price(savings_3)}** ارزان‌تر از ۳× ماهانه است.')
    lines.append(_buy_line(quarterly, catalog))
    return '\n'.join(lines)


def _welcome_gift_and_trial_answer(
    catalog: PublicPlanCatalog,
    ctx: SubscriptionQueryContext,
) -> str:
    trial_line = ''
    if catalog.trial:
        trial_line = (
            f'\n\n**پلن آزمایشی خریدنی** ({catalog.trial.duration_label}): '
            f'**{format_price(catalog.trial.price)}** — پس از پرداخت فعال می‌شود.\n'
            f'{_buy_line(catalog.trial, catalog)}'
        )
    return (
        '**هدیه ۷روزه خوش‌آمدگویی** (پس از ثبت‌نام و تأیید موبایل، برای حساب‌های واجد شرایط) '
        'طرح جداگانه‌ای است و برای همه تضمین نمی‌شود. '
        f'{workspace_link(inline=True)} وضعیت لایسنس را در حساب خود ببینید؛ '
        f'راهنما: {license_guide_link()}.\n\n'
        '**پلن آزمایشی خریدنی** با هدیه یکی نیست: هر کسی می‌تواند آن را بخرد، مدت و قیمت مشخص دارد '
        'و مستقل از شرایط هدیه ثبت‌نام است.'
        + trial_line
    )
