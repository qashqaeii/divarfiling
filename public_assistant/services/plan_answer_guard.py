"""اعتبارسنجی اعداد مالی پاسخ LLM در برابر محاسبه قطعی فروشگاه."""
from __future__ import annotations

import re
from decimal import Decimal

from public_assistant.services.plan_advisor import compose_subscription_answer
from public_assistant.services.plan_intent import SubscriptionQueryContext
from public_assistant.services.public_plans import (
    PublicPlanCatalog,
    agency_quantity_status,
    public_plan_quote,
)
from shop.services.plan_pricing import get_agency_bulk_discount_percent

_PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
_MONEY_HINTS = ('تومان', 'میلیون', 'میلیارد', 'هزار', 'قیمت', 'جمع', 'مبلغ', 'هزینه', 'تخفیف')
_SCALE_HINTS = {'میلیون': 1_000_000, 'هزار': 1_000, 'میلیارد': 1_000_000_000}
_PERCENT_RE = re.compile(r'(\d{1,2})\s*(?:٪|%)')
_DIGIT_RE = re.compile(r'\d[\d,٬.]*')
_NON_MONEY_SMALL = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 25, 30, 90, 365})


def _ascii_digits(text: str) -> str:
    return text.translate(_PERSIAN_DIGITS)


def _parse_int_token(token: str) -> int | None:
    t = _ascii_digits(token).replace(',', '').replace('٬', '').strip()
    if not t or not re.fullmatch(r'\d+(\.\d+)?', t):
        return None
    if '.' in t:
        return int(float(t))
    return int(t)


def _scale_amount(val: int, hint: str) -> int:
    factor = _SCALE_HINTS.get(hint)
    if factor and val < factor * 50:
        return val * factor
    return val


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
            start = max(0, pos - 48)
            end = min(len(norm), pos + len(hint) + 48)
            window = norm[start:end]
            for m in _DIGIT_RE.findall(window):
                val = _parse_int_token(m)
                if val is None:
                    continue
                scaled = _scale_amount(val, hint)
                if scaled in _NON_MONEY_SMALL and hint not in (
                    'قیمت',
                    'جمع',
                    'مبلغ',
                    'هزینه',
                    'تومان',
                    'میلیون',
                    'میلیارد',
                    'هزار',
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
    return _amounts_near_money_hints(text)


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

    duration = ctx.duration or 'monthly'
    monthly = catalog.personal_by_type('monthly')
    if duration == 'quarterly' and monthly:
        quarterly = catalog.personal_by_type('quarterly')
        if quarterly:
            _add_decimal(amounts, quarterly.price)
            _add_decimal(amounts, monthly.price * 3)
        if ctx.wants_comparison:
            pcts.update(extract_percentages(compose_subscription_answer(ctx, catalog) or ''))
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
    return amounts, pcts


def _mentions_money(text: str) -> bool:
    norm = (text or '').lower()
    return any(h in norm for h in _MONEY_HINTS) or bool(extract_money_amounts(text))


def _close_enough(a: int, b: int) -> bool:
    lo, hi = min(a, b), max(a, b)
    if hi >= 50_000 and lo < max(hi // 50, 1000):
        return False
    return abs(a - b) <= max(1000, int(b * 0.02))


def _amounts_conflict(llm_amounts: set[int], canonical: set[int]) -> bool:
    if not llm_amounts or not canonical:
        return False
    for a in llm_amounts:
        if not any(_close_enough(a, c) for c in canonical):
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
