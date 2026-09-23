"""Resolve مخاطب CRM از نام استخراج‌شده توسط LLM."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q

from workspace.services.crm_scope import customers_qs


def resolve_contact_by_name(user, name: Optional[str], limit: int = 8) -> Tuple[Optional[int], List[Dict[str, Any]], str]:
    """
    برگشت: (contact_id اگر یکتا، candidates، ambiguity_code)
    ambiguity_code: '' | 'none' | 'multiple'
    """
    clean = (name or '').strip()
    if not clean:
        return None, [], ''

    qs = customers_qs(user).filter(
        Q(name__icontains=clean) | Q(company_name__icontains=clean)
    ).order_by('-updated_at')[:limit]
    matches = list(qs)
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
