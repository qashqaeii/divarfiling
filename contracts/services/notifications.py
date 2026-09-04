"""اعلان‌های پنل CRM برای رویدادهای قرارداد."""
from __future__ import annotations

from django.urls import reverse

from contracts.models import Contract
from workspace.models import CRMAgencyPanelNotification
from workspace.services.crm_scope import get_agency


def notify_contract_event(contract: Contract, event: str, *, user=None, party_name: str = '') -> None:
    agency = contract.agency or get_agency(contract.user)
    if not agency:
        return
    titles = {
        'viewed': 'طرف قرارداد مشاهده کرد',
        'accepted': f'{party_name or "طرف"} قرارداد را تأیید کرد',
        'fully_accepted': 'همه طرفین قرارداد را تأیید کردند',
        'sent': 'قرارداد برای طرفین ارسال شد',
        'finalized': 'قرارداد نهایی شد',
    }
    title = titles.get(event, 'به‌روزرسانی قرارداد')
    link = reverse('workspace:contract_manage', kwargs={
        'deal_id': contract.deal_id,
        'contract_id': contract.pk,
    })
    CRMAgencyPanelNotification.objects.create(
        agency=agency,
        user=contract.user,
        kind='contract',
        title=title,
        body=f'{contract.internal_number} — {contract.get_contract_type_display()}',
        link=link,
    )
