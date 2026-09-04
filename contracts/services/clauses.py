"""موتور بندها و قواعد حقوقی."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from django.db import models
from django.utils import timezone

from contracts.constants import CLAUSE_REVIEW_REVIEWED, CONTRACT_TYPE_LEASE
from contracts.models import ContractClauseDefinition, ContractLegalRule


def _eval_condition(expr: Dict[str, Any], context: Dict[str, Any]) -> bool:
    if not expr:
        return True
    for key, expected in expr.items():
        actual = context.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif isinstance(expected, bool):
            if bool(actual) != expected:
                return False
        elif actual != expected:
            return False
    return True


def allow_pending_clauses(*, user=None) -> bool:
    """بندهای review_pending فقط در DEBUG، staff یا LEGAL_REVIEW_PREVIEW."""
    from django.conf import settings
    if getattr(settings, 'DEBUG', False):
        return True
    if getattr(settings, 'LEGAL_REVIEW_PREVIEW', False):
        return True
    if user and getattr(user, 'is_staff', False):
        return True
    return False


def get_applicable_clauses(
    contract_type: str,
    context: Optional[Dict[str, Any]] = None,
    *,
    include_pending: bool = True,
    user=None,
    as_of: Optional[date] = None,
    reviewed_only: bool = False,
) -> List[ContractClauseDefinition]:
    """بندهای فعال — review_status دیگر access control نیست (مگر reviewed_only=True)."""
    ref = as_of or timezone.localdate()
    qs = ContractClauseDefinition.objects.filter(
        contract_type=contract_type, is_active=True,
    )
    if reviewed_only:
        qs = qs.filter(review_status=CLAUSE_REVIEW_REVIEWED)
    elif not include_pending and not allow_pending_clauses(user=user):
        qs = qs.filter(review_status=CLAUSE_REVIEW_REVIEWED)
    clauses = []
    ctx = context or {}
    for c in qs.select_related('legal_source'):
        if c.effective_from and ref < c.effective_from:
            continue
        if c.effective_to and ref > c.effective_to:
            continue
        if _eval_condition(c.condition_expression or {}, ctx):
            clauses.append(c)
    return clauses


def render_clause_body(defn: ContractClauseDefinition, inline_values: Optional[Dict] = None) -> str:
    text = defn.body_template
    values = inline_values or {}
    for key, val in values.items():
        text = text.replace(f'{{{{{key}}}}}', str(val))
    return text


def get_active_legal_rules(
    contract_type: str = '',
    as_of: Optional[date] = None,
) -> List[ContractLegalRule]:
    ref = as_of or timezone.localdate()
    qs = ContractLegalRule.objects.filter(status='active')
    if contract_type:
        qs = qs.filter(models.Q(contract_type='') | models.Q(contract_type=contract_type))
    rules = []
    for r in qs:
        if r.effective_from and ref < r.effective_from:
            continue
        if r.effective_to and ref > r.effective_to:
            continue
        rules.append(r)
    return rules


def get_legal_warnings(contract_type: str, context: Optional[Dict] = None) -> List[Dict[str, str]]:
    from contracts.constants import (
        CONTRACT_TYPE_JV,
        CONTRACT_TYPE_SALE,
        JV_WARNING,
        WARNING_LEVEL_CRITICAL,
        WARNING_LEVEL_INFO,
        WARNING_LEVEL_WARNING,
    )

    warnings = [
        {
            'level': WARNING_LEVEL_INFO,
            'message': 'شناسه ایجادشده شناسه داخلی فایلینگ دیوار است.',
        },
        {
            'level': WARNING_LEVEL_WARNING,
            'message': 'این قرارداد دارای کد رهگیری رسمی نیست.',
        },
    ]
    if contract_type == CONTRACT_TYPE_SALE:
        warnings.append({
            'level': WARNING_LEVEL_WARNING,
            'message': 'تأیید این قرارداد در فایلینگ دیوار به معنای انتقال رسمی مالکیت نیست.',
        })
    if contract_type == CONTRACT_TYPE_JV:
        warnings.append({
            'level': WARNING_LEVEL_CRITICAL,
            'message': JV_WARNING,
        })

    for rule in get_active_legal_rules(contract_type):
        if rule.warning_message:
            warnings.append({
                'level': rule.warning_level or WARNING_LEVEL_INFO,
                'message': rule.warning_message,
            })
    return warnings
