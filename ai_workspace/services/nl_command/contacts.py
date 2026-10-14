"""Resolve مخاطب CRM از نام استخراج‌شده توسط LLM."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q

from workspace.services.crm_merge import normalize_contact_name
from workspace.services.crm_scope import customers_qs

# پیشوندهای رایج در گفتار طبیعی («فردا به آقای سعادت زنگ بزنم»)
_HONORIFIC_PREFIX = re.compile(
    r'^(?:'
    r'سرکار\s*خانم|سرکار|'
    r'آقای|خانم|آقا|خانوم|'
    r'جناب|'
    r'دکتر|دكتر|'
    r'مهندس|استاد|'
    r'حاج\s*آقا|حاجی|حاج'
    r')\s+',
    re.UNICODE,
)

_MIN_TERM_LEN = 2
_MAX_REVERSE_SCAN = 400


def strip_contact_honorifics(name: str) -> str:
    """حذف پیشوند محترمانه برای جستجوی مخاطب."""
    s = normalize_contact_name(name)
    while s:
        m = _HONORIFIC_PREFIX.match(s)
        if not m:
            break
        s = s[m.end() :].strip()
    return s


def _search_terms(raw: str) -> List[str]:
    clean = normalize_contact_name(raw)
    if not clean:
        return []
    terms: List[str] = [clean]
    stripped = strip_contact_honorifics(clean)
    if stripped and stripped not in terms:
        terms.append(stripped)
    for token in re.split(r'\s+', stripped or clean):
        token = token.strip()
        if len(token) >= _MIN_TERM_LEN and token not in terms:
            terms.append(token)
    return terms


def _query_by_terms(user, terms: List[str], limit: int) -> List[Any]:
    terms = [t for t in dict.fromkeys(terms) if t and len(t) >= _MIN_TERM_LEN]
    if not terms:
        return []
    clause = Q()
    for term in terms:
        clause |= Q(name__icontains=term) | Q(company_name__icontains=term)
    return list(customers_qs(user).filter(clause).order_by('-updated_at')[:limit])


def _reverse_substring_matches(user, query: str, limit: int) -> List[Any]:
    """
    وقتی نام CRM کوتاه‌تر است («سعادت») ولی LLM «آقای سعادت» برگردانده —
    نام ذخیره‌شده زیررشتهٔ عبارت جستجو باشد.
    """
    haystack = strip_contact_honorifics(query).casefold()
    if len(haystack) < _MIN_TERM_LEN:
        return []
    found: List[Any] = []
    qs = (
        customers_qs(user)
        .exclude(name='')
        .only('id', 'name', 'phone', 'updated_at')
        .order_by('-updated_at')[:_MAX_REVERSE_SCAN]
    )
    for customer in qs:
        needle = normalize_contact_name(customer.name).casefold()
        if len(needle) < _MIN_TERM_LEN:
            continue
        if needle in haystack:
            found.append(customer)
            if len(found) >= limit:
                break
    return found


def _contact_names_similar_for_duplicate_hint(input_name: str, stored_name: str) -> bool:
    """
    آیا دو نام برای هشدار «مشابه» در ثبت مخاطب جدید کافی‌شبیه‌اند؟
    پیشوند مشترک داخل یک توکن (مثل سلیمان در سلیمانی) کافی نیست.
    """
    a = normalize_contact_name(input_name).casefold()
    b = normalize_contact_name(stored_name).casefold()
    if not a or not b:
        return False
    if a == b:
        return True
    a_tokens = [t for t in strip_contact_honorifics(input_name).casefold().split() if len(t) >= _MIN_TERM_LEN]
    b_tokens = [t for t in strip_contact_honorifics(stored_name).casefold().split() if len(t) >= _MIN_TERM_LEN]
    if a_tokens and b_tokens and set(a_tokens) & set(b_tokens):
        return True
    return False


def find_similar_contacts_by_name(user, name: Optional[str], limit: int = 5) -> List[Any]:
    """مخاطبین با نام واقعاً مشابه — برای هشدار ثبت مخاطب جدید (نه resolve یادآوری)."""
    clean = normalize_contact_name(name or '')
    if not clean:
        return []
    found: List[Any] = []
    for customer in (
        customers_qs(user)
        .exclude(name='')
        .only('id', 'name', 'phone', 'updated_at')
        .order_by('-updated_at')[:400]
    ):
        if _contact_names_similar_for_duplicate_hint(clean, customer.name):
            found.append(customer)
            if len(found) >= limit:
                break
    return found


def resolve_contact_by_name(
    user,
    name: Optional[str],
    limit: int = 8,
) -> Tuple[Optional[int], List[Dict[str, Any]], str]:
    """
    برگشت: (contact_id اگر یکتا، candidates، ambiguity_code)
    ambiguity_code: '' | 'none' | 'multiple'
    """
    clean = normalize_contact_name(name or '')
    if not clean:
        return None, [], ''

    matches = _query_by_terms(user, _search_terms(clean), limit)
    if not matches:
        matches = _reverse_substring_matches(user, clean, limit)

    if not matches:
        return None, [], 'none'

    candidates = [
        {
            'id': c.pk,
            'name': c.name,
            'phone': (c.phone or '')[:4] + '…' if c.phone and len(c.phone) > 4 else (c.phone or ''),
        }
        for c in matches
    ]
    if len(matches) == 1:
        return matches[0].pk, candidates, ''
    return None, candidates, 'multiple'
