"""اعتبارسنجی سرور برای ثبت پیشنهاد ملک به مخاطب."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from workspace.models import CRMProperty, Customer, Listing
from workspace.services.crm_matching import (
    _crm_match_compatible,
    _score_crm_property,
    _score_listing,
)
from workspace.services.crm_matching_access import mask_crm_match_for_viewer
from workspace.services.crm_scope import can_edit_customer, customer_for_user, property_for_user
from workspace.services.formatting import format_toman


def _property_suggestion_eligible(prop: CRMProperty) -> bool:
    if prop.deleted_at:
        return False
    if prop.publish_status == 'بایگانی':
        return False
    if prop.transaction_status not in ('فعال', 'در مذاکره'):
        return False
    return True


def _listing_suggestion_eligible(listing: Listing) -> bool:
    return bool(
        listing
        and listing.dataset.is_active
        and not listing.is_expired
    )


def _server_crm_match_dict(user, customer: Customer, prop: CRMProperty) -> Optional[Dict[str, Any]]:
    scored = _score_crm_property(customer, prop)
    if not scored:
        return None
    return mask_crm_match_for_viewer(user, prop, scored)


def _server_divar_match_dict(customer: Customer, listing: Listing) -> Optional[Dict[str, Any]]:
    return _score_listing(customer, listing)


def resolve_property_suggestion_items(
    user,
    customer: Customer,
    raw_items: List[Dict[str, Any]],
    *,
    divar_enabled: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    ورودی کلاینت را به پیشنهادهای معتبر تبدیل می‌کند.
    برگشت: (موارد معتبر، خطاهای هر آیتم)
    """
    validated: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    if not raw_items:
        return validated, failures

    owner_customer = customer_for_user(user, customer.pk)
    if not owner_customer or not can_edit_customer(user, customer):
        return [], [{'code': 'forbidden', 'message': 'دسترسی به این مخاطب ندارید.'}]

    seen: set[str] = set()
    for index, raw in enumerate(raw_items):
        source = (raw.get('source') or '').strip()
        dedupe_key = ''
        try:
            if source == 'crm':
                try:
                    prop_id = int(raw.get('property_id') or 0)
                except (TypeError, ValueError):
                    failures.append({'index': index, 'code': 'invalid_id', 'message': 'شناسه ملک نامعتبر است.'})
                    continue
                dedupe_key = f'crm:{prop_id}'
                if dedupe_key in seen:
                    continue
                prop = property_for_user(user, prop_id)
                if not prop:
                    failures.append({'index': index, 'code': 'not_found', 'message': 'ملک در دسترس شما نیست.'})
                    continue
                if not _property_suggestion_eligible(prop):
                    failures.append({'index': index, 'code': 'inactive', 'message': 'ملک فعال یا قابل پیشنهاد نیست.'})
                    continue
                if not _crm_match_compatible(customer, prop):
                    failures.append({
                        'index': index,
                        'code': 'incompatible',
                        'message': 'این ملک با نوع معامله یا نیاز مخاطب سازگار نیست.',
                    })
                    continue
                match = _server_crm_match_dict(user, customer, prop)
                if not match:
                    failures.append({
                        'index': index,
                        'code': 'criteria',
                        'message': 'ملک با معیارهای الزامی مخاطب هم‌خوان نیست.',
                    })
                    continue
                seen.add(dedupe_key)
                validated.append(match)

            elif source == 'divar':
                if not divar_enabled:
                    failures.append({
                        'index': index,
                        'code': 'divar_locked',
                        'message': 'پیشنهاد آگهی دیوار نیاز به لایسنس فعال دارد.',
                    })
                    continue
                token = (raw.get('token') or '').strip()
                listing_id = raw.get('listing_id')
                dedupe_key = f'divar:{token or listing_id}'
                if dedupe_key in seen:
                    continue
                qs = Listing.objects.filter(
                    dataset__user=user,
                    dataset__is_active=True,
                    is_expired=False,
                ).select_related('dataset')
                listing = None
                if listing_id:
                    listing = qs.filter(pk=listing_id).first()
                if listing is None and token:
                    listing = qs.filter(token=token).first()
                if not listing or not _listing_suggestion_eligible(listing):
                    failures.append({'index': index, 'code': 'not_found', 'message': 'آگهی دیوار یافت نشد.'})
                    continue
                match = _server_divar_match_dict(customer, listing)
                if not match:
                    failures.append({
                        'index': index,
                        'code': 'criteria',
                        'message': 'آگهی با معیارهای الزامی مخاطب هم‌خوان نیست.',
                    })
                    continue
                seen.add(dedupe_key)
                validated.append(match)
            else:
                failures.append({'index': index, 'code': 'invalid_source', 'message': 'منبع پیشنهاد نامعتبر است.'})
        except Exception:
            failures.append({'index': index, 'code': 'error', 'message': 'ثبت این مورد ممکن نبود.'})

    return validated, failures


def price_label_for_property(prop: CRMProperty) -> str:
    if prop.deal_mode in ('فروش', 'پیش‌فروش') and prop.sale_price:
        return format_toman(prop.sale_price)
    parts = []
    if prop.deposit:
        parts.append(f'رهن {format_toman(prop.deposit)}')
    if prop.monthly_rent:
        parts.append(f'اجاره {format_toman(prop.monthly_rent)}')
    return ' · '.join(parts)
