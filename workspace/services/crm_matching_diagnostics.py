"""توضیح نتیجه خالی و آمار عیب‌یابی بدون PII."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import Customer
from workspace.services.crm_matching import (
    _crm_match_candidates_filtered_qs,
    _crm_match_compatible,
    _divar_match_candidates_filtered_qs,
    _is_broad_seeker_profile,
    _is_rent_customer,
    _is_sale_customer,
    is_builder_customer,
)


def _profile_incomplete(customer: Customer) -> bool:
    if is_builder_customer(customer):
        return not (
            customer.builder_buy_budget_min
            or customer.builder_buy_budget_max
            or customer.builder_buy_areas
        )
    if _is_rent_customer(customer):
        return not any([
            customer.deposit_min, customer.deposit_max,
            customer.rent_min, customer.rent_max,
            customer.areas, customer.district, customer.city,
        ])
    if _is_sale_customer(customer):
        return not any([
            customer.budget_min, customer.budget_max,
            customer.areas, customer.district, customer.city,
            customer.property_type,
        ])
    return not (customer.areas or customer.district or customer.city)


def build_empty_match_message(
    customer: Customer,
    user,
    *,
    divar_enabled: bool,
    crm_sql_count: int = 0,
    divar_sql_count: int = 0,
) -> str:
    from workspace.services.crm_contact_archive import is_contact_archived

    if is_contact_archived(customer):
        return 'مخاطب بایگانی است؛ تطبیق خودکار غیرفعال است.'
    if _profile_incomplete(customer):
        return (
            'پروفایل نیاز مشتری ناقص است. بودجه، محله یا شهر را تکمیل کنید '
            'تا پیشنهادهای دقیق‌تری دریافت کنید.'
        )
    if not divar_enabled and divar_sql_count == 0 and crm_sql_count == 0:
        return (
            'فایل سازگار در املاک شخصی پیدا نشد و تطبیق فایلینگ دیوار '
            'به‌دلیل نبود لایسنس فعال در دسترس نیست.'
        )
    if crm_sql_count == 0 and divar_sql_count == 0:
        return (
            'با معیارهای فعلی هیچ کاندیدایی در املاک شخصی یا فایلینگ دیوار '
            'پیدا نشد. انعطاف‌پذیری یا محدوده بودجه/متراژ را بازبینی کنید.'
        )
    if crm_sql_count == 0:
        return 'در املاک شخصی فایل سازگار نیست؛ فقط نتایج فایلینگ دیوار ممکن است موجود باشد.'
    return (
        'فایل‌هایی با معیارهای شما وجود دارد اما امتیاز نهایی آن‌ها از حد کیفیت '
        'پایین‌تر بود یا به‌دلیل سقف اسکن همهٔ موارد امتیازدهی نشدند.'
    )


def compute_match_diagnostics(
    customer: Customer,
    user,
    *,
    divar_enabled: bool,
    dataset_id=None,
) -> Dict[str, Any]:
    """آمار سبک برای مدیر — بدون شماره تماس یا آدرس."""
    crm_qs = _crm_match_candidates_filtered_qs(customer, user)
    crm_sql = crm_qs.count()
    compatible = 0
    for prop in crm_qs.order_by('-updated_at').iterator(chunk_size=500):
        if _crm_match_compatible(customer, prop):
            compatible += 1
        if compatible >= 500:
            break

    divar_sql = 0
    if divar_enabled:
        div_qs = _divar_match_candidates_filtered_qs(
            customer, user,
            dataset_id=dataset_id,
        )
        divar_sql = div_qs.count()

    return {
        'crm_sql_candidates': crm_sql,
        'crm_compatible_deal': compatible,
        'divar_sql_candidates': divar_sql,
        'broad_profile': _is_broad_seeker_profile(customer),
        'divar_enabled': divar_enabled,
    }


def attach_match_guidance(
    payload: Dict[str, Any],
    customer: Customer,
    user,
    *,
    divar_enabled: bool,
    dataset_id=None,
    include_staff_diagnostics: bool = False,
) -> Dict[str, Any]:
    total = int(payload.get('total_count') or 0)
    if total > 0:
        return payload
    diag = compute_match_diagnostics(
        customer, user, divar_enabled=divar_enabled, dataset_id=dataset_id,
    )
    payload['message'] = build_empty_match_message(
        customer,
        user,
        divar_enabled=divar_enabled,
        crm_sql_count=diag['crm_sql_candidates'],
        divar_sql_count=diag['divar_sql_candidates'],
    )
    if include_staff_diagnostics:
        payload['diagnostics'] = diag
    return payload
