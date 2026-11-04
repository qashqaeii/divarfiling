"""تشخیص intent معامله — سازگار در Divar، CRM، reverse و audit."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from django.db.models import Q, QuerySet

from workspace.constants import LEAD_TYPES
from workspace.services.crm_matching_prefilter import (
    apply_int_max_prefilter,
    apply_int_min_prefilter,
)


def profile_has_sale_criteria(profile) -> bool:
    return (
        getattr(profile, 'budget_min', None) is not None
        or getattr(profile, 'budget_max', None) is not None
    )


def profile_has_rent_criteria(profile) -> bool:
    return any(
        getattr(profile, field, None) is not None
        for field in ('deposit_min', 'deposit_max', 'rent_min', 'rent_max')
    )


@dataclass(frozen=True)
class CustomerDealIntent:
    sale: bool
    rent: bool
    unknown: bool


def customer_deal_intent(profile) -> CustomerDealIntent:
    """
    سرنخ: فقط از فیلدهای مالی — بدون استنتاج اجاره از بودجه خرید یا برعکس.
    انواع typed: intent از customer_type (نه از بودجه طرف مقابل).
    """
    sale = profile_has_sale_criteria(profile)
    rent = profile_has_rent_criteria(profile)
    ctype = (getattr(profile, 'customer_type', None) or '').strip()
    if ctype in {'خریدار', 'متقاضی خرید', 'سرمایه‌گذار', 'فروشنده', 'فروشنده ملک'}:
        sale = True
    elif ctype in {'مستاجر', 'متقاضی اجاره', 'موجر'}:
        rent = True
    elif ctype == 'سرنخ':
        return CustomerDealIntent(sale=sale, rent=rent, unknown=not sale and not rent)
    return CustomerDealIntent(sale=sale, rent=rent, unknown=False)


def property_matches_customer_deal_intent(
    profile,
    *,
    is_rent_listing: bool,
    is_sale_listing: bool,
) -> bool:
    ctype = (getattr(profile, 'customer_type', None) or '').strip()
    if ctype in {'مستاجر', 'متقاضی اجاره', 'موجر'}:
        return is_rent_listing
    if ctype in {'خریدار', 'متقاضی خرید', 'فروشنده', 'فروشنده ملک', 'سرمایه‌گذار'}:
        return is_sale_listing

    if ctype not in LEAD_TYPES and ctype != 'سرنخ':
        return is_rent_listing or is_sale_listing

    intent = customer_deal_intent(profile)
    rent_only = is_rent_listing and not is_sale_listing
    sale_only = is_sale_listing and not is_rent_listing

    if intent.unknown:
        return is_rent_listing or is_sale_listing
    if rent_only:
        return intent.rent
    if sale_only:
        return intent.sale
    if is_rent_listing and is_sale_listing:
        return intent.rent or intent.sale
    return False


def resolve_listing_scoring_deal(
    profile,
    *,
    is_rent_listing: bool,
    is_sale_listing: bool,
) -> Optional[str]:
    """
    'rent' | 'sale' | None — None یعنی ناسازگار با intent (رد قطعی).
    """
    if not property_matches_customer_deal_intent(
        profile,
        is_rent_listing=is_rent_listing,
        is_sale_listing=is_sale_listing,
    ):
        return None
    rent_only = is_rent_listing and not is_sale_listing
    sale_only = is_sale_listing and not is_rent_listing
    intent = customer_deal_intent(profile)
    if rent_only:
        return 'rent' if intent.rent or intent.unknown else None
    if sale_only:
        return 'sale' if intent.sale or intent.unknown else None
    if is_rent_listing and is_sale_listing:
        if intent.rent and not intent.sale:
            return 'rent'
        if intent.sale and not intent.rent:
            return 'sale'
        return 'sale'
    return None


def deal_prevents_strong_tier(
    profile,
    dims: Any,
    *,
    is_rent_deal: bool,
    is_rent_listing: bool,
    is_sale_listing: bool,
) -> bool:
    from workspace.services.crm_matching_eval import _deal_criteria

    intent = customer_deal_intent(profile)
    rent_only = is_rent_listing and not is_sale_listing
    sale_only = is_sale_listing and not is_rent_listing

    if rent_only and intent.sale and not intent.rent:
        return True
    if sale_only and intent.rent and not intent.sale:
        return True

    if _deal_criteria(profile, is_rent_deal=is_rent_deal) and dims.price_s <= 0.2:
        return True

    if intent.unknown and dims.price_s <= 0.5:
        has_financial = profile_has_sale_criteria(profile) or profile_has_rent_criteria(profile)
        if not has_financial and (dims.hood_s >= 0.9 or dims.area_s >= 0.99):
            return True
    return False


def apply_lead_deal_intent_crm_sql(qs: QuerySet, customer, *, tol: float) -> QuerySet:
    from workspace.services.crm_matching import _budget_sql_bounds, _deposit_rent_sql_bounds

    intent = customer_deal_intent(customer)
    if intent.unknown:
        return qs.filter(
            Q(deal_mode__in=['فروش', 'پیش‌فروش'], sale_price__gt=0)
            | Q(deal_mode__in=['رهن و اجاره', 'اجاره'], deposit__gt=0)
            | Q(deal_mode__in=['رهن و اجاره', 'اجاره'], monthly_rent__gt=0)
        )
    if intent.sale and not intent.rent:
        qs = qs.filter(deal_mode__in=['فروش', 'پیش‌فروش']).filter(sale_price__gt=0)
        sql_lo, sql_hi = _budget_sql_bounds(customer, tolerance=tol)
        if sql_lo is not None:
            qs = qs.filter(sale_price__gte=sql_lo)
        if sql_hi is not None:
            qs = qs.filter(sale_price__lte=sql_hi)
        return qs
    if intent.rent and not intent.sale:
        qs = qs.filter(deal_mode__in=['رهن و اجاره', 'اجاره']).filter(
            Q(deposit__gt=0) | Q(monthly_rent__gt=0),
        )
        bounds = _deposit_rent_sql_bounds(customer, tolerance=tol)
        qs = apply_int_min_prefilter(qs, 'deposit', bounds['deposit_lo'])
        qs = apply_int_max_prefilter(qs, 'deposit', bounds['deposit_hi'])
        qs = apply_int_min_prefilter(qs, 'monthly_rent', bounds['rent_lo'])
        qs = apply_int_max_prefilter(qs, 'monthly_rent', bounds['rent_hi'])
        return qs
    return qs.filter(
        Q(deal_mode__in=['فروش', 'پیش‌فروش'], sale_price__gt=0)
        | Q(deal_mode__in=['رهن و اجاره', 'اجاره'], deposit__gt=0)
        | Q(deal_mode__in=['رهن و اجاره', 'اجاره'], monthly_rent__gt=0)
    )


def apply_lead_deal_intent_divar_sql(qs: QuerySet, customer, *, tol: float) -> QuerySet:
    from workspace.services.crm_matching import _budget_sql_bounds, _deposit_rent_sql_bounds

    intent = customer_deal_intent(customer)
    if intent.unknown:
        return qs.filter(Q(price__gt=0) | Q(deposit__gt=0) | Q(rent__gt=0))
    if intent.sale and not intent.rent:
        qs = qs.filter(price__gt=0).filter(
            Q(deposit__isnull=True) | Q(deposit=0),
        ).filter(
            Q(rent__isnull=True) | Q(rent=0),
        )
        sql_lo, sql_hi = _budget_sql_bounds(customer, tolerance=tol)
        if sql_lo is not None:
            qs = qs.filter(price__gte=sql_lo)
        if sql_hi is not None:
            qs = qs.filter(price__lte=sql_hi)
        return qs
    if intent.rent and not intent.sale:
        qs = qs.filter(Q(deposit__gt=0) | Q(rent__gt=0))
        bounds = _deposit_rent_sql_bounds(customer, tolerance=tol)
        qs = apply_int_min_prefilter(qs, 'deposit', bounds['deposit_lo'])
        qs = apply_int_max_prefilter(qs, 'deposit', bounds['deposit_hi'])
        qs = apply_int_min_prefilter(qs, 'rent', bounds['rent_lo'])
        qs = apply_int_max_prefilter(qs, 'rent', bounds['rent_hi'])
        return qs
    return qs.filter(Q(price__gt=0) | Q(deposit__gt=0) | Q(rent__gt=0))
