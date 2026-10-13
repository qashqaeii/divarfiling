"""شناسایی مخاطب CRM برای دستیار پس از تماس موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db.models import Q

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from workspace.models import Customer, CustomerActivity
from workspace.services.crm_scope import customers_qs


def _last_follow_up_summary(customer: Customer) -> Optional[Dict[str, Any]]:
    activity = (
        CustomerActivity.objects.filter(customer=customer, activity_type='پیگیری')
        .order_by('-created_at')
        .only('created_at', 'content', 'title')
        .first()
    )
    if activity:
        summary = (activity.content or activity.title or '').strip()
        return {
            'at': activity.created_at.isoformat() if activity.created_at else None,
            'summary': summary[:240] if summary else '',
        }
    follow = getattr(customer, 'next_follow_up', None)
    if follow:
        return {
            'at': follow.isoformat(),
            'summary': 'پیگیری بعدی',
        }
    return None


def _budget_summary(customer: Customer) -> str:
    parts: List[str] = []
    if customer.budget_min:
        parts.append(f"از {customer.budget_min:,}")
    if customer.budget_max:
        parts.append(f"تا {customer.budget_max:,}")
    if not parts:
        return ''
    return 'بودجه: ' + ' '.join(parts)


def _areas_summary(customer: Customer) -> str:
    for value in (customer.areas, customer.district, customer.city):
        text = (value or '').strip()
        if text:
            return text[:200]
    return ''


def _contact_brief(customer: Customer) -> Dict[str, Any]:
    return {
        'id': customer.pk,
        'full_name': customer.name,
        'phone': customer.phone or '',
        'customer_type': customer.customer_type or '',
        'status': customer.status or '',
        'last_follow_up': _last_follow_up_summary(customer),
        'areas_summary': _areas_summary(customer),
        'budget_summary': _budget_summary(customer),
    }


def find_customers_by_phone_in_scope(user, phone: str) -> List[Customer]:
    key = normalize_phone(phone)
    if not key:
        return []
    matches: List[Customer] = []
    qs = customers_qs(user).filter(Q(phone__gt='') | Q(phone_alt__gt='')).only(
        'id',
        'phone',
        'phone_alt',
        'name',
        'customer_type',
        'status',
        'next_follow_up',
        'user_id',
    )
    for customer in qs:
        if normalize_phone(customer.phone) == key or normalize_phone(customer.phone_alt) == key:
            matches.append(customer)
    return matches


def resolve_post_call_phone(user, raw_phone: str) -> Dict[str, Any]:
    normalized = normalize_phone(raw_phone or '')
    if not normalized:
        return {'status': 'invalid_phone', 'phone': '', 'contact': None, 'contacts': []}
    if not is_valid_iran_mobile(normalized):
        return {'status': 'invalid_phone', 'phone': normalized, 'contact': None, 'contacts': []}

    try:
        matches = find_customers_by_phone_in_scope(user, normalized)
    except Exception:
        return {'status': 'error', 'phone': normalized, 'contact': None, 'contacts': []}

    if not matches:
        return {'status': 'new_contact', 'phone': normalized, 'contact': None, 'contacts': []}
    if len(matches) == 1:
        return {
            'status': 'existing_contact',
            'phone': normalized,
            'contact': _contact_brief(matches[0]),
            'contacts': [],
        }
    return {
        'status': 'ambiguous',
        'phone': normalized,
        'contact': None,
        'contacts': [_contact_brief(c) for c in matches],
    }
