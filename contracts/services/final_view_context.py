"""Context builder for public finalized contract view."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from contracts.constants import LEGAL_DISCLAIMER_FULL
from contracts.models import Contract, ContractAccessToken, ContractVersion
from contracts.services.contract_display import build_contract_display
from contracts.services.handover_wizard import build_handover_public_display

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
        return tok.witness.witness_role or f'شاهد {tok.witness.witness_number}'
    return ''


def build_version_signatories(version: ContractVersion) -> List[Dict[str, Any]]:
    """Public helper — signatories with signature metadata for a published version."""
    return _build_signatories(version)


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


def _qr_data_url(url: str) -> str:
    if not url:
        return ''
    try:
        import base64
        import io

        import qrcode

        qr = qrcode.make(url)
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return ''


def build_final_view_context(
    contract: Contract,
    *,
    access_token: Optional[ContractAccessToken] = None,
    verified: bool = False,
) -> Dict[str, Any]:
    version = contract.current_version
    display = build_contract_display(contract, version) if version else {}
    has_handover = contract.handovers.filter(status='finalized').exists()

    ctx: Dict[str, Any] = {
        'contract': contract,
        'version': version,
        'verified': verified,
        'viewer_role': _viewer_role_label(access_token) if access_token else '',
        'legal_disclaimer': LEGAL_DISCLAIMER_FULL,
        'has_handover': has_handover,
        'contract_meta': {
            'internal_number': contract.internal_number,
            'contract_type_label': contract.get_contract_type_display(),
            'status_label': contract.get_status_display(),
            'version_number': version.version_number if version else 0,
            'finalized_at': contract.finalized_at,
            'content_hash_short': display.get('content_hash_short', ''),
        },
    }

    if verified and version:
        finalized_handover = contract.handovers.filter(status='finalized').order_by('-finalized_at').first()
        handover_display = build_handover_public_display(finalized_handover) if finalized_handover else None
        ctx.update({
            'document_sections': display.get('document_sections', []),
            'parties': display.get('parties', []),
            'witnesses': display.get('witnesses', []),
            'property_info': display.get('property', {}),
            'financial_summary': display.get('financial_summary', {}),
            'payment_schedule': display.get('payment_schedule', {}),
            'important_dates': display.get('important_dates', []),
            'penalty_summary': display.get('penalty_summary', []),
            'costs_summary': display.get('costs_summary', []),
            'custom_agreements': display.get('custom_agreements', []),
            'signatories': _build_signatories(version),
            'verify_url': display.get('verify_url', ''),
            'verify_qr_data_url': _qr_data_url(display.get('verify_url', '')),
            'content_hash': display.get('content_hash', ''),
            'has_pdf': bool(version.pdf_file),
            'handover_display': handover_display,
        })
    else:
        ctx.update({
            'document_sections': [],
            'parties': [],
            'witnesses': [],
            'property_info': {},
            'financial_summary': {},
            'payment_schedule': {},
            'important_dates': [],
            'penalty_summary': [],
            'costs_summary': [],
            'custom_agreements': [],
            'signatories': [],
            'verify_url': '',
            'verify_qr_data_url': '',
            'content_hash': '',
            'has_pdf': False,
            'handover_display': None,
        })

    return ctx
