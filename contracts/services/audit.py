"""لاگ ممیزی قرارداد."""
from __future__ import annotations

from typing import Any, Optional

from contracts.models import Contract, ContractAuditEvent, ContractParty, ContractVersion
from contracts.constants import AUDIT_EVENT_LABELS, WIZARD_STEP_LABELS

_ROLE_LABELS = {
    'landlord': 'موجر', 'tenant': 'مستأجر', 'seller': 'فروشنده', 'buyer': 'خریدار',
    'owner': 'مالک', 'builder': 'سازنده', 'witness': 'شاهد',
}

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


def audit_event_label(event_type: str) -> str:
    return AUDIT_EVENT_LABELS.get(event_type, event_type.replace('_', ' ').title())


def audit_event_detail(event: ContractAuditEvent) -> str:
    meta = event.metadata or {}
    parts = []
    if event.event_type == 'CONTRACT_UPDATED' and meta.get('step'):
        step_label = WIZARD_STEP_LABELS.get(meta['step'], meta['step'])
        parts.append(f'مرحله {step_label}')
    if event.party_id and event.party:
        name = f'{event.party.first_name} {event.party.last_name}'.strip()
        role = _ROLE_LABELS.get(event.party.role, event.party.role)
        parts.append(f'{role}' + (f' ({name})' if name else ''))
    elif event.actor_user_id and event.actor_user:
        actor = event.actor_user.get_full_name() or event.actor_user.username
        if actor:
            parts.append(f'توسط {actor}')
    if event.event_type == 'SMS_SENT' and meta.get('resend'):
        parts.append('ارسال مجدد')
    if event.event_type == 'CONTRACT_CANCELLED' and meta.get('reason'):
        parts.append(meta['reason'])
    if event.version_id and event.version:
        parts.append(f'نسخه {event.version.version_number}')
    return ' · '.join(parts)


def build_audit_timeline(events) -> list:
    """Return display dicts for manage-page timeline."""
    out = []
    for ev in events:
        out.append({
            'id': ev.pk,
            'created_at': ev.created_at,
            'label': audit_event_label(ev.event_type),
            'detail': audit_event_detail(ev),
            'event_type': ev.event_type,
        })
    return out
