"""URLهای کاننیکال قرارداد — با و بدون معامله."""
from __future__ import annotations

from django.urls import reverse


def _deal_kw(contract) -> dict:
    if contract.deal_id:
        return {'deal_id': contract.deal_id, 'contract_id': contract.pk}
    return {'contract_id': contract.pk}


def contract_wizard_url(contract) -> str:
    if contract.deal_id:
        return reverse('workspace:contract_wizard', kwargs=_deal_kw(contract))
    return reverse('workspace:contract_wizard_standalone', kwargs={'contract_id': contract.pk})


def contract_manage_url(contract) -> str:
    if contract.deal_id:
        return reverse('workspace:contract_manage', kwargs=_deal_kw(contract))
    return reverse('workspace:contract_manage_standalone', kwargs={'contract_id': contract.pk})


def contract_delete_draft_url(contract) -> str:
    if contract.deal_id:
        return reverse('workspace:contract_delete_draft', kwargs=_deal_kw(contract))
    return reverse('workspace:contract_delete_draft_standalone', kwargs={'contract_id': contract.pk})


def contract_pdf_url(contract) -> str:
    if contract.deal_id:
        return reverse('workspace:contract_pdf', kwargs=_deal_kw(contract))
    return reverse('workspace:contract_pdf_standalone', kwargs={'contract_id': contract.pk})


def contract_pdf_preview_url(contract) -> str:
    if contract.deal_id:
        return reverse('workspace:contract_pdf_preview', kwargs=_deal_kw(contract))
    return reverse('workspace:contract_pdf_preview_standalone', kwargs={'contract_id': contract.pk})


def contract_create_url(deal_id: int | None = None) -> str:
    if deal_id:
        return reverse('workspace:contract_create', kwargs={'deal_id': deal_id})
    return reverse('workspace:contract_create_standalone')


def contracts_dashboard_url(**query) -> str:
    from urllib.parse import urlencode
    base = reverse('workspace:contracts_dashboard')
    if query:
        return f'{base}?{urlencode(query)}'
    return base


def handover_public_pdf_url(contract, *, request=None) -> str:
    """Inline PDF صورت‌جلسه — /c/view/<staff-token>/handover/pdf/"""
    if contract.status != 'finalized':
        return ''
    if not contract.handovers.filter(status='finalized').exists():
        return ''
    from contracts.services.invitations import ensure_staff_public_view_url

    version = contract.current_version
    if not version:
        return ''
    base = ensure_staff_public_view_url(contract, version, request=request)
    if not base:
        return ''
    return f'{base.rstrip("/")}/handover/pdf/'


def handover_create_url(contract) -> str:
    if contract.deal_id:
        return reverse('workspace:handover_create', kwargs=_deal_kw(contract))
    return reverse('workspace:handover_create_standalone', kwargs={'contract_id': contract.pk})


def handover_wizard_url(contract, handover, *, step: str = '') -> str:
    kwargs = {'contract_id': contract.pk, 'handover_id': handover.pk}
    if contract.deal_id:
        kwargs['deal_id'] = contract.deal_id
        url = reverse('workspace:handover_wizard', kwargs=kwargs)
    else:
        url = reverse('workspace:handover_wizard_standalone', kwargs=kwargs)
    return f'{url}?step={step}' if step else url


def contract_attachment_download_url(contract, attachment_id, *, inline: bool = False) -> str:
    kwargs = {'contract_id': contract.pk, 'attachment_id': attachment_id}
    if contract.deal_id:
        kwargs['deal_id'] = contract.deal_id
        url = reverse('workspace:contract_attachment_download', kwargs=kwargs)
    else:
        url = reverse('workspace:contract_attachment_download_standalone', kwargs=kwargs)
    return f'{url}?inline=1' if inline else url


def deal_contracts_filter_url(deal_id: int) -> str:
    return contracts_dashboard_url(deal=deal_id)
