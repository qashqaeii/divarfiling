"""لاگ ممیزی قرارداد."""
from __future__ import annotations

from typing import Any, Optional

from contracts.models import Contract, ContractAuditEvent, ContractParty, ContractVersion

_SENSITIVE_KEYS = frozenset({
    'otp', 'otp_code', 'code', 'token', 'raw_token', 'national_id',
    'signature', 'signature_image', 'phone', 'mobile',
})


def _sanitize_metadata(metadata: Optional[dict]) -> dict:
    if not metadata:
        return {}
    clean = {}
    for key, value in metadata.items():
        lk = str(key).lower()
        if lk in _SENSITIVE_KEYS or 'token' in lk or 'otp' in lk:
            continue
        if lk == 'national_id' or lk.endswith('_national_id'):
            continue
        clean[key] = value
    return clean


def log_audit_event(
    contract: Contract,
    event_type: str,
    *,
    version: Optional[ContractVersion] = None,
    actor_user=None,
    party: Optional[ContractParty] = None,
    metadata: Optional[dict] = None,
    request=None,
) -> ContractAuditEvent:
    ip = ''
    ua = ''
    if request is not None:
        forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
        ip = forwarded or (request.META.get('REMOTE_ADDR') or '')
        ua = (request.META.get('HTTP_USER_AGENT') or '')[:500]
    return ContractAuditEvent.objects.create(
        contract=contract,
        version=version,
        event_type=event_type,
        actor_user=actor_user,
        party=party,
        metadata=_sanitize_metadata(metadata),
        ip_address=ip or None,
        user_agent=ua,
    )
