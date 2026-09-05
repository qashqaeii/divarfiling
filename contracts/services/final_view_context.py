"""Context builder for public finalized contract view."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from contracts.constants import LEGAL_DISCLAIMER_FULL
from contracts.models import Contract, ContractAccessToken, ContractVersion
from contracts.services.contract_renderer import render_contract_document

PARTY_ROLE_LABELS = {
    'landlord': 'موجر',
    'tenant': 'مستأجر',
    'seller': 'فروشنده',
    'buyer': 'خریدار',
    'owner': 'مالک',
    'builder': 'سازنده',
    'witness': 'شاهد',
    'other': 'سایر',
}


def _party_display_name(party) -> str:
    if party.company_name:
        return party.company_name.strip()
    return f'{party.first_name or ""} {party.last_name or ""}'.strip() or '—'


def _viewer_role_label(tok: ContractAccessToken) -> str:
    if tok.party_id and tok.party:
        return PARTY_ROLE_LABELS.get(tok.party.role, tok.party.role)
    if tok.witness_id and tok.witness:
        role = tok.witness.witness_role or f'شاهد {tok.witness.witness_number}'
        return role
    return ''


def _build_signatories(version: ContractVersion) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    acceptances = (
        version.acceptances
        .select_related('party', 'witness', 'signature')
        .order_by('accepted_at', 'pk')
    )
    for acc in acceptances:
        if acc.party_id and acc.party:
            party = acc.party
            rows.append({
                'name': _party_display_name(party),
                'role': PARTY_ROLE_LABELS.get(party.role, party.role),
                'mobile_masked': _mask_mobile(acc.mobile),
                'accepted_at': acc.accepted_at,
                'signature_image_url': _signature_url(acc),
                'signature_type': _signature_type(acc),
                'hash_valid': acc.is_hash_valid(),
            })
        elif acc.witness_id and acc.witness:
            w = acc.witness
            rows.append({
                'name': f'{w.first_name or ""} {w.last_name or ""}'.strip() or '—',
                'role': w.witness_role or f'شاهد {w.witness_number}',
                'mobile_masked': _mask_mobile(acc.mobile),
                'accepted_at': acc.accepted_at,
                'signature_image_url': _signature_url(acc),
                'signature_type': _signature_type(acc),
                'hash_valid': acc.is_hash_valid(),
            })
    return rows


def _mask_mobile(mobile: str) -> str:
    m = (mobile or '').strip()
    if len(m) < 8:
        return m
    return f'{m[:4]}***{m[-4:]}'


def _signature_url(acc) -> str:
    try:
        sig = acc.signature
    except Exception:
        return ''
    if sig and sig.image:
        return sig.image.url
    return ''


def _signature_type(acc) -> str:
    try:
        sig = acc.signature
    except Exception:
        return 'otp_acceptance'
    return sig.signature_type if sig else 'otp_acceptance'


def build_final_view_context(
    contract: Contract,
    *,
    access_token: Optional[ContractAccessToken] = None,
    verified: bool = False,
) -> Dict[str, Any]:
    version = contract.current_version
    ctx: Dict[str, Any] = {
        'contract': contract,
        'version': version,
        'verified': verified,
        'viewer_role': _viewer_role_label(access_token) if access_token else '',
        'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
    }
    if not version:
        ctx.update({
            'document_sections': [],
            'signatories': [],
            'contract_meta': {},
        })
        return ctx

    content_hash = version.content_hash or ''
    ctx_meta = {
        'internal_number': contract.internal_number,
        'contract_type_label': contract.get_contract_type_display(),
        'status_label': contract.get_status_display(),
        'version_number': version.version_number,
        'finalized_at': contract.finalized_at,
        'content_hash_short': (content_hash[:12] + '…') if len(content_hash) > 12 else content_hash,
    }
    ctx['contract_meta'] = ctx_meta

    if verified:
        ctx['document_sections'] = render_contract_document(contract, version)
        ctx['signatories'] = _build_signatories(version)
        ctx['has_pdf'] = bool(version.pdf_file)
    else:
        ctx['document_sections'] = []
        ctx['signatories'] = []
        ctx['has_pdf'] = False

    return ctx
