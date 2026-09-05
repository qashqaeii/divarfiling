"""Single source of truth for contract document display (web + PDF)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from contracts.models import Contract, ContractVersion
from contracts.services.contract_renderer import render_contract_document
from contracts.services.review_context import build_review_context
from contracts.services.version_copy import version_display_snapshot


def build_contract_display(
    contract: Contract,
    version: Optional[ContractVersion] = None,
) -> Dict[str, Any]:
    """
    Unified payload for public final view and PDF generation.
    Legal text comes from version snapshot / render_contract_document only.
    """
    version = version or contract.current_version
    if not version:
        return {
            'document_sections': [],
            'parties': [],
            'witnesses': [],
            'property': {},
            'financial_summary': {},
            'payment_schedule': {'rows': [], 'has_rows': False},
            'important_dates': [],
            'penalty_summary': [],
            'costs_summary': [],
            'custom_agreements': [],
            'contract_meta': {},
            'verify_url': '',
            'content_hash': '',
            'content_hash_short': '',
        }

    review = build_review_context(contract, version=version)
    snap = version_display_snapshot(version)
    content_hash = version.content_hash or ''

    return {
        'document_sections': render_contract_document(contract, version),
        'parties': review['parties'],
        'witnesses': review['witnesses'],
        'property': review['property'],
        'financial_summary': review['financial_summary'],
        'payment_schedule': review['payment_schedule'],
        'important_dates': review['important_dates'],
        'penalty_summary': review['penalty_summary'],
        'costs_summary': review['costs_summary'],
        'custom_agreements': review['custom_agreements'],
        'contract_meta': {
            **review['contract_meta'],
            'finalized_at': contract.finalized_at,
            'content_hash': content_hash,
        },
        'verify_url': (snap or {}).get('public_verification_url', '') if isinstance(snap, dict) else '',
        'content_hash': content_hash,
        'content_hash_short': (content_hash[:12] + '…') if len(content_hash) > 12 else content_hash,
    }
