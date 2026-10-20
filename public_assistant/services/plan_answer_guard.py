"""اعتبارسنجی اعداد مالی پاسخ LLM در برابر محاسبه قطعی فروشگاه."""
from __future__ import annotations

import re

from public_assistant.services.plan_advisor import compose_subscription_answer
from public_assistant.services.plan_intent import SubscriptionQueryContext
from public_assistant.services.public_plans import (
    PublicPlanCatalog,
    agency_quantity_status,
    public_plan_quote,
)

_PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
_MONEY_HINTS = ('تومان', 'میلیون', 'میلیارد', 'هزار', 'قیمت', 'جمع', 'مبلغ', 'هزینه')
_PERCENT_RE = re.compile(r'(\d{1,2})\s*(?:٪|%)')
_DIGIT_RE = re.compile(r'\d[\d,٬]*')


def _ascii_digits(text: str) -> str:
    return text.translate(_PERSIAN_DIGITS)


def _parse_int_token(token: str) -> int | None:
    t = _ascii_digits(token).replace(',', '').replace('٬', '').strip()
    if not t.isdigit():
        return None
    return int(t)


def extract_money_amounts(text: str) -> set[int]:
    """اعداد بزرگ احتمالاً مبلغ — از متن فارسی/انگلیسی."""
    norm = _ascii_digits(text or '')
    amounts: set[int] = set()
    for m in _DIGIT_RE.findall(norm):
        val = _parse_int_token(m)
        if val is not None and val >= 10_000:
            amounts.add(val)
    return amounts


def extract_percentages(text: str) -> set[int]:
    norm = _ascii_digits(text or '')
    return {int(m.group(1)) for m in _PERCENT_RE.finditer(norm)}


def _canonical_facts(ctx: SubscriptionQueryContext, catalog: PublicPlanCatalog) -> tuple[set[int], set[int]]:
    amounts: set[int] = set()
    percents: set[int] = set()
    answer = compose_subscription_answer(ctx, catalog)
    if answer:
        amounts |= extract_money_amounts(answer)
        percents |= extract_percentages(answer)

    if ctx.team_size and ctx.agency_context:
        duration = ctx.duration or 'quarterly'
        plan = catalog.agency_by_type(duration)
        if plan and agency_quantity_status(plan, ctx.team_size) == 'ok':
            quote = public_plan_quote(catalog, plan, quantity=ctx.team_size, strict=True)
            if quote:
                for key in ('base_unit_price', 'effective_unit_price', 'final_price', 'original_price'):
                    amounts.add(int(quote[key]))
                from shop.services.plan_pricing import get_agency_bulk_discount_percent

                pct = int(get_agency_bulk_discount_percent(ctx.team_size))
                if pct:
                    percents.add(pct)

    monthly = catalog.personal_by_type('monthly')
    if monthly:
        amounts.add(monthly.price)
    quarterly = catalog.personal_by_type('quarterly')
    if quarterly:
        amounts.add(quarterly.price)
    return amounts, percents


def _mentions_money(text: str) -> bool:
    norm = (text or '').lower()
    return any(h in norm for h in _MONEY_HINTS) or bool(extract_money_amounts(text))


def _amounts_conflict(llm_amounts: set[int], canonical: set[int]) -> bool:
    if not llm_amounts or not canonical:
        return False
    for a in llm_amounts:
        if not any(abs(a - c) <= max(1000, int(c * 0.02)) for c in canonical):
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
    if not catalog or not llm_text:
        return False
    if not ctx.is_subscription:
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
    """پاسخ نهایی — در تعارض مالی، نسخه قطعی جایگزین می‌شود."""
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
    """بدون کاتالوگ زنده، اعداد قیمتی از پاسخ حذف و به صفحه خرید ارجاع می‌شود."""
    if not ctx.is_subscription or catalog:
        return text
    if not text or not _mentions_money(text):
        return text
    from public_assistant.services.plan_advisor import compose_no_catalog_answer

    return compose_no_catalog_answer()
