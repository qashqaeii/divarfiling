"""اعتبارسنجی اعداد مالی پاسخ LLM در برابر محاسبه قطعی فروشگاه."""
from __future__ import annotations

import re
from decimal import Decimal

from public_assistant.services.plan_advisor import compose_subscription_answer
from public_assistant.services.plan_intent import SubscriptionQueryContext
from public_assistant.services.public_plans import (
    PublicPlanCatalog,
    agency_quantity_status,
    compare_personal_duration_savings,
    public_plan_quote,
)
from shop.services.plan_pricing import get_agency_bulk_discount_percent

_PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
_ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_MONEY_HINTS = ('تومان', 'میلیون', 'میلیارد', 'هزار', 'قیمت', 'جمع', 'مبلغ', 'هزینه', 'تخفیف')
_SCALE_HINTS = {'میلیون': 1_000_000, 'هزار': 1_000, 'میلیارد': 1_000_000_000}
_PERCENT_RE = re.compile(r'(\d{1,2})\s*(?:٪|%)')
_DIGIT_RE = re.compile(r'\d[\d,٬.\s]*\d|\d+')
_NON_MONEY_SMALL = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 25, 30, 90, 365})


def _ascii_digits(text: str) -> str:
    return text.translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)


def _parse_numeric_token(token: str) -> float | None:
    t = _ascii_digits(token).replace(',', '').replace('٬', '').replace(' ', '').strip()
    if not t or not re.fullmatch(r'\d+(\.\d+)?', t):
        return None
    return float(t)


def _scale_amount(val: float, hint: str) -> int:
    factor = _SCALE_HINTS.get(hint)
    if not factor:
        return int(val)
    if hint == 'میلیون' and val < 1000:
        return int(val * factor)
    if hint == 'هزار' and val < factor * 50:
        return int(val * factor)
    if hint == 'میلیارد' and val < 50:
        return int(val * factor)
    return int(val)


def _amounts_near_money_hints(text: str) -> set[int]:
    """فقط اعداد نزدیک واژه‌های مالی — نه «۷ روز» یا «۲ دستگاه»."""
    norm = _ascii_digits(text or '')
    amounts: set[int] = set()
    for hint in _MONEY_HINTS:
        idx = 0
        while True:
            pos = norm.find(hint, idx)
            if pos < 0:
                break
            start = max(0, pos - 56)
            end = min(len(norm), pos + len(hint) + 56)
            window = norm[start:end]
            window_has_thousand = 'هزار' in window
            window_has_million = 'میلیون' in window
            for m in _DIGIT_RE.findall(window):
                val = _parse_numeric_token(m)
                if val is None:
                    continue
                scaled = _scale_amount(val, hint)
                if hint == 'تومان' and scaled < 10_000:
                    if window_has_thousand and val < 10_000:
                        scaled = int(val * 1_000)
                    elif window_has_million and val < 1_000:
                        scaled = int(val * 1_000_000)
                    elif scaled < 10_000:
                        continue
                if scaled in _NON_MONEY_SMALL and hint not in (
                    'تومان',
                    'میلیون',
                    'میلیارد',
                    'هزار',
                    'قیمت',
                    'جمع',
                    'مبلغ',
                    'هزینه',
                ):
                    continue
                if scaled >= 10_000 or hint in (
                    'تومان',
                    'میلیون',
                    'میلیارد',
                    'هزار',
                    'قیمت',
                    'جمع',
                    'مبلغ',
                    'هزینه',
                ):
                    amounts.add(scaled)
                elif hint in ('قیمت', 'جمع', 'مبلغ', 'هزینه') and scaled >= 100:
                    amounts.add(scaled)
            idx = pos + len(hint)
    return amounts


def extract_money_amounts(text: str) -> set[int]:
    """مبالغ اشتراک — اعداد کوچک مدت/دستگاه حذف می‌شوند."""
    return {a for a in _amounts_near_money_hints(text) if a >= 100_000}


def extract_percentages(text: str) -> set[int]:
    norm = _ascii_digits(text or '')
    return {int(m.group(1)) for m in _PERCENT_RE.finditer(norm)}


def _add_decimal(amounts: set[int], value: Decimal | int | None) -> None:
    if value is None:
        return
    amounts.add(int(value))


def _canonical_facts(
    ctx: SubscriptionQueryContext,
    catalog: PublicPlanCatalog,
) -> tuple[set[int], set[int]]:
    """مبالغ و درصدها از موتور قیمت — نه از متن فرمت‌شده."""
    amounts: set[int] = set()
    pcts: set[int] = set()
    if ctx.is_property_listing or ctx.needs_team_count:
        return amounts, pcts

    if ctx.wants_welcome_gift and not (ctx.team_size and ctx.team_size >= 2):
        if catalog.trial:
            _add_decimal(amounts, catalog.trial.price)
        return amounts, pcts

    team = ctx.team_size
    if (ctx.agency_context or (team and team >= 2)) and team and team >= 2:
        duration = ctx.duration or 'quarterly'
        plan = catalog.agency_by_type(duration) or (catalog.agency[0] if catalog.agency else None)
        if plan and agency_quantity_status(plan, team) == 'ok':
            quote = public_plan_quote(catalog, plan, quantity=team, strict=True)
            if quote:
                _add_decimal(amounts, quote.get('final_price'))
                _add_decimal(amounts, quote.get('effective_unit_price'))
                _add_decimal(amounts, quote.get('base_unit_price'))
                pcts.add(int(get_agency_bulk_discount_percent(team)))
        return amounts, pcts

    if ctx.wants_trial_info or ctx.duration == 'daily':
        if catalog.trial:
            _add_decimal(amounts, catalog.trial.price)
        return amounts, pcts

    monthly = catalog.personal_by_type('monthly')
    if ctx.wants_comparison and monthly:
        quarterly = catalog.personal_by_type('quarterly')
        yearly = catalog.personal_by_type('yearly')
        if quarterly:
            _add_decimal(amounts, quarterly.price)
            _add_decimal(amounts, monthly.price * 3)
            savings = monthly.price * 3 - quarterly.price
            if savings > 0:
                _add_decimal(amounts, savings)
        if yearly:
            _add_decimal(amounts, yearly.price)
            _add_decimal(amounts, monthly.price * 12)
        for item in compare_personal_duration_savings(catalog):
            _add_decimal(amounts, item.get('baseline_total'))
            _add_decimal(amounts, item.get('bundle_price'))
            _add_decimal(amounts, item.get('savings'))
        _add_decimal(amounts, monthly.price)
        return amounts, pcts

    duration = ctx.duration or 'monthly'
    if duration == 'quarterly' and monthly:
        quarterly = catalog.personal_by_type('quarterly')
        if quarterly:
            _add_decimal(amounts, quarterly.price)
            _add_decimal(amounts, monthly.price * 3)
            savings = monthly.price * 3 - quarterly.price
            if savings > 0:
                _add_decimal(amounts, savings)
        return amounts, pcts

    if duration == 'yearly' and monthly:
        yearly = catalog.personal_by_type('yearly')
        if yearly:
            _add_decimal(amounts, yearly.price)
            _add_decimal(amounts, monthly.price * 12)
        return amounts, pcts

    plan = catalog.personal_by_type(duration) or monthly
    if plan:
        _add_decimal(amounts, plan.price)
        if plan.compare_at_price:
            _add_decimal(amounts, plan.compare_at_price)
    quarterly = catalog.personal_by_type('quarterly')
    if monthly and quarterly and (ctx.newbie or ctx.wants_recommendation):
        _add_decimal(amounts, monthly.price)
        _add_decimal(amounts, quarterly.price)
    return amounts, pcts


def _mentions_money(text: str) -> bool:
    norm = (text or '').lower()
    return any(h in norm for h in _MONEY_HINTS) or bool(extract_money_amounts(text))


def _amounts_conflict(llm_amounts: set[int], canonical: set[int]) -> bool:
    if not llm_amounts or not canonical:
        return False
    for a in llm_amounts:
        if a not in canonical:
            return True
    return False


def _percents_conflict(llm_pcts: set[int], canonical: set[int]) -> bool:
    if not llm_pcts:
        return False
    if not canonical:
        return True
    return not llm_pcts.issubset(canonical)


def should_replace_llm_financials(
    llm_text: str,
    ctx: SubscriptionQueryContext,
    catalog: PublicPlanCatalog | None,
) -> bool:
    if not catalog or not llm_text or not ctx.is_subscription:
        return False
    if ctx.wants_welcome_gift and not (ctx.team_size and ctx.team_size >= 2):
        llm_amounts = extract_money_amounts(llm_text)
        canonical_amounts, _ = _canonical_facts(ctx, catalog)
        if llm_amounts and canonical_amounts and _amounts_conflict(llm_amounts, canonical_amounts):
            return True
        if llm_amounts and len(llm_amounts) > 1:
            return True
        agency_noise = any(
            w in llm_text for w in ('مشاور', 'لایسنس پس از تخفیف', 'تخفیف حجمی آژانس', 'جمع مبلغ پایه')
        )
        if agency_noise:
            return True
        return False
    if not (ctx.wants_price or ctx.team_size or ctx.wants_comparison or ctx.agency_context):
        return False
    canonical_amounts, canonical_pcts = _canonical_facts(ctx, catalog)
    if not canonical_amounts and not canonical_pcts:
        return False
    llm_amounts = extract_money_amounts(llm_text)
    llm_pcts = extract_percentages(llm_text)
    if _amounts_conflict(llm_amounts, canonical_amounts):
        return True
    if llm_pcts and _percents_conflict(llm_pcts, canonical_pcts):
        return True
    if _mentions_money(llm_text) and canonical_amounts and not llm_amounts:
        return True
    return False


def reconcile_subscription_answer(
    llm_text: str | None,
    ctx: SubscriptionQueryContext,
    catalog: PublicPlanCatalog | None,
) -> str:
    canonical = compose_subscription_answer(ctx, catalog) if catalog else ''
    if not llm_text or not llm_text.strip():
        return canonical or ''
    if catalog and should_replace_llm_financials(llm_text, ctx, catalog):
        return canonical or llm_text
    return llm_text


def strip_unverified_subscription_prices(
    text: str,
    ctx: SubscriptionQueryContext,
    catalog: PublicPlanCatalog | None,
) -> str:
    if not ctx.is_subscription or catalog:
        return text
    if not text or not _mentions_money(text):
        return text
    from public_assistant.services.plan_advisor import compose_no_catalog_answer

    return compose_no_catalog_answer()
