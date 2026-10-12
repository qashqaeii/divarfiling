"""قراردادهای دیجیتال — adapter API موبایل (/api/mobile/v1/contracts/)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, When
from django.utils import timezone

from contracts.constants import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    CONTRACT_STATUS_CANCELLED,
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_EXPIRED,
    CONTRACT_STATUS_FINALIZED,
    CONTRACT_STATUS_READY,
    CONTRACT_STATUS_SENT,
    CONTRACT_STATUS_READY,
    CONTRACT_TYPES,
    MAX_ATTACHMENT_SIZE,
)
from contracts.models import Contract, ContractAttachment
from contracts.services.audit import build_audit_timeline
from contracts.services.attachments import attachment_for_user, save_contract_attachment, validate_upload_file
from contracts.services.contract_display import build_contract_display
from contracts.services.dashboard import ACTION_STATUSES, contract_acceptance_progress, contract_dashboard_stats, filter_contracts
from contracts.services.license_gate import LICENSE_REQUIRED_MSG, user_has_contract_license
from contracts.services.lifecycle import ContractError, create_contract
from contracts.services.scope import can_edit_contract
from contracts.services.routing import (
    contract_manage_url,
    contract_wizard_url,
    handover_create_url,
    handover_wizard_url,
)
from contracts.services.scope import contract_for_user
from workspace.services.crm_scope import deal_for_user


ROLE_LABELS = {
    'landlord': 'موجر',
    'tenant': 'مستأجر',
    'seller': 'فروشنده',
    'buyer': 'خریدار',
    'owner': 'مالک',
    'builder': 'سازنده',
    'witness': 'شاهد',
    'other': 'سایر',
}



def assert_mobile_contract_license(user) -> None:
    if not user_has_contract_license(user):
        raise ValueError(LICENSE_REQUIRED_MSG)


def workspace_paths(contract: Contract) -> Dict[str, str]:
    return {
        'wizard': contract_wizard_url(contract),
        'manage': contract_manage_url(contract),
    }


def _contract_title(contract: Contract) -> str:
    if (contract.title or '').strip():
        return contract.title.strip()
    if contract.deal_id and contract.deal:
        if (contract.deal.title or '').strip():
            return contract.deal.title.strip()
        if contract.deal.property_id and contract.deal.property:
            return (contract.deal.property.title or '').strip() or '—'
    wizard = contract.wizard_data or {}
    prop = wizard.get('property') or {}
    if isinstance(prop, dict):
        return (prop.get('title') or prop.get('address') or '').strip() or '—'
    version = contract.current_version
    if version and getattr(version, 'property_snapshot', None):
        snap = version.property_snapshot
        if snap:
            return (getattr(snap, 'title', None) or getattr(snap, 'address', None) or '').strip() or '—'
    return '—'


def _party_summary(contract: Contract) -> List[str]:
    version = contract.current_version
    if version:
        names = []
        for p in version.parties.all()[:4]:
            label = (getattr(p, 'display_name', None) or f'{p.first_name} {p.last_name}'.strip()).strip()
            if label:
                names.append(label)
        return names
    wizard = contract.wizard_data or {}
    parties = wizard.get('parties') or []
    names = []
    for p in parties[:4]:
        if isinstance(p, dict):
            label = (p.get('display_name') or p.get('full_name') or p.get('name') or '').strip()
            if label:
                names.append(label)
    return names


def _signature_label(contract: Contract) -> str:
    progress = contract_acceptance_progress(contract)
    total = progress.get('total') or 0
    accepted = progress.get('accepted') or 0
    if contract.status == CONTRACT_STATUS_FINALIZED:
        return 'نهایی شده'
    if total and accepted >= total:
        return 'امضا کامل'
    if accepted:
        return f'{accepted} از {total} امضا'
    if contract.status in ACTION_STATUSES or contract.status == CONTRACT_STATUS_READY:
        return 'در انتظار امضا'
    return '—'


def _handover_label(contract: Contract) -> str:
    ho = contract.handovers.order_by('-updated_at').first()
    if not ho:
        return '—'
    return ho.get_status_display()


def _contract_cta(contract: Contract) -> str:
    if contract.status == CONTRACT_STATUS_DRAFT:
        return 'continue_wizard'
    if contract.status == CONTRACT_STATUS_FINALIZED:
        return 'view_contract'
    if contract.status in ACTION_STATUSES or contract.status == CONTRACT_STATUS_READY:
        return 'view_signature'
    return 'view_contract'


def _handover_cta(contract: Contract) -> Optional[Dict[str, Any]]:
    ho = contract.handovers.order_by('-updated_at').first()
    if not ho:
        if contract.status == CONTRACT_STATUS_FINALIZED:
            return {
                'label': 'شروع تحویل',
                'action': 'OPEN_HANDOVER_CREATE',
                'web_path': handover_create_url(contract),
                'native_target': 'handover_create',
            }
        return None
    if ho.status == 'finalized':
        return {
            'label': 'مشاهده تحویل',
            'action': 'OPEN_HANDOVER',
            'web_path': handover_wizard_url(contract, ho),
            'native_target': 'handover_wizard',
            'handover_id': ho.pk,
        }
    return {
        'label': 'ادامه تحویل',
        'action': 'OPEN_HANDOVER',
        'web_path': handover_wizard_url(contract, ho),
        'native_target': 'handover_wizard',
        'handover_id': ho.pk,
    }


def build_contract_next_action(contract: Contract) -> Dict[str, Any]:
    paths = workspace_paths(contract)
    handover = _handover_cta(contract)
    if contract.status == CONTRACT_STATUS_DRAFT:
        return {
            'label': 'تکمیل قرارداد',
            'action': 'OPEN_WIZARD',
            'web_path': paths['wizard'],
            'native_target': 'wizard',
        }
    if contract.status in ACTION_STATUSES or contract.status == CONTRACT_STATUS_READY:
        return {
            'label': 'مشاهده وضعیت تأیید',
            'action': 'OPEN_ACCEPTANCE',
            'web_path': paths['manage'],
            'native_target': 'bridge',
        }
    if contract.status == CONTRACT_STATUS_FINALIZED:
        if handover and handover['action'] != 'OPEN_HANDOVER':
            return {**handover, 'native_target': 'bridge'}
        return {
            'label': 'مشاهده PDF نهایی',
            'action': 'OPEN_PDF',
            'web_path': '',
            'native_target': 'pdf',
        }
    if handover:
        return {**handover, 'native_target': 'bridge'}
    return {
        'label': 'ادامه فرایند',
        'action': 'OPEN_MANAGE',
        'web_path': paths['manage'],
        'native_target': 'bridge',
    }


def serialize_contract(contract: Contract, *, include_next_action: bool = True) -> Dict[str, Any]:
    primary_party = _party_summary(contract)
    version = contract.current_version
    payload: Dict[str, Any] = {
        'id': contract.pk,
        'title': _contract_title(contract),
        'contract_type': contract.contract_type,
        'contract_type_label': contract.get_contract_type_display(),
        'internal_number': contract.internal_number or '',
        'status': contract.status,
        'status_label': contract.get_status_display(),
        'current_version_number': version.version_number if version else 0,
        'wizard_step': contract.wizard_step if contract.status == CONTRACT_STATUS_DRAFT else '',
        'parties': primary_party,
        'primary_party': primary_party[0] if primary_party else '',
        'signature_status': _signature_label(contract),
        'handover_status': _handover_label(contract),
        'deal_id': contract.deal_id,
        'deal_title': (contract.deal.title if contract.deal_id and contract.deal else '') or '',
        'property_title': _contract_title(contract),
        'created_at': contract.created_at.isoformat() if contract.created_at else None,
        'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
        'cta': _contract_cta(contract),
        'workspace_paths': workspace_paths(contract),
    }
    if include_next_action:
        payload['next_action'] = build_contract_next_action(contract)
    return payload


def contracts_list_stats(user) -> Dict[str, int]:
    raw = contract_dashboard_stats(user)
    return {
        'all': raw.get('total') or 0,
        'draft': raw.get('draft') or 0,
        'needs_action': raw.get('needs_action') or 0,
        'awaiting_acceptance': raw.get('pending') or 0,
        'finalized': raw.get('finalized') or 0,
    }


def _parse_date(value: str):
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _apply_mobile_filters(qs, params: Dict[str, Any]):
    linked = (params.get('deal_linked') or '').strip().lower()
    if linked in ('1', 'true', 'yes'):
        qs = qs.filter(deal_id__isnull=False)
    elif linked in ('0', 'false', 'no'):
        qs = qs.filter(deal__isnull=True)
    date_from = _parse_date(params.get('date_from') or '')
    if date_from:
        qs = qs.filter(updated_at__date__gte=date_from)
    date_to = _parse_date(params.get('date_to') or '')
    if date_to:
        qs = qs.filter(updated_at__date__lte=date_to)
    needs = (params.get('needs_action') or '').strip().lower()
    if needs in ('1', 'true', 'yes'):
        qs = qs.filter(status__in=ACTION_STATUSES)
    sort = (params.get('sort') or 'updated').strip()
    if sort == 'created':
        return qs.order_by('-created_at')
    if sort == 'needs_action':
        return qs.annotate(
            _prio=Case(
                When(status__in=ACTION_STATUSES, then=0),
                When(status=CONTRACT_STATUS_DRAFT, then=1),
                default=2,
                output_field=IntegerField(),
            )
        ).order_by('_prio', '-updated_at')
    return qs.order_by('-updated_at')


def list_contracts_paginated(
    user,
    *,
    page: int = 1,
    page_size: int = 20,
    query: Optional[Dict[str, Any]] = None,
) -> Tuple[List[dict], dict, dict]:
    assert_mobile_contract_license(user)
    params = dict(query or {})
    qs = filter_contracts(user, params)
    qs = _apply_mobile_filters(qs, params)
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items = [serialize_contract(c) for c in page_obj.object_list]
    meta = {'page': page, 'page_size': page_size, 'total': paginator.count}
    stats = contracts_list_stats(user)
    return items, meta, stats


def create_contract_mobile(
    user,
    *,
    contract_type: str,
    deal_id: Optional[int] = None,
) -> Dict[str, Any]:
    assert_mobile_contract_license(user)
    ctype = (contract_type or 'sale').strip()
    if ctype not in {t[0] for t in CONTRACT_TYPES}:
        raise ValueError('نوع قرارداد نامعتبر است.')
    if deal_id:
        if not deal_for_user(user, deal_id):
            raise ValueError('معامله یافت نشد.')
    try:
        contract = create_contract(user, ctype, deal_id=deal_id)
    except ContractError as exc:
        raise ValueError(str(exc)) from exc
    return serialize_contract(contract)


def _party_invitation_status(contract: Contract, version, party, invitation) -> str:
    if contract.status == CONTRACT_STATUS_EXPIRED:
        return 'expired'
    if invitation and invitation.is_revoked:
        return 'invalid'
    if invitation and invitation.expires_at and invitation.expires_at < timezone.now():
        return 'expired'
    if version:
        accepted = version.acceptances.filter(party_id=party.pk).exists() if hasattr(party, 'pk') else False
        if accepted:
            return 'accepted'
    if invitation:
        if invitation.viewed_at or invitation.opened_at:
            return 'viewed'
        if invitation.last_sent_at or invitation.sms_sent_at:
            return 'sent'
    if contract.status in (CONTRACT_STATUS_SENT, CONTRACT_STATUS_READY) or invitation:
        return 'sent'
    return 'not_sent'


def build_party_signatures(contract: Contract) -> List[Dict[str, Any]]:
    version = contract.current_version
    rows: List[Dict[str, Any]] = []
    if version:
        accepted_ids = set(version.acceptances.filter(party_id__isnull=False).values_list('party_id', flat=True))
        for party in version.parties.order_by('sort_order', 'pk'):
            inv = contract.invitations.filter(version=version, party=party, is_revoked=False).order_by('-created_at').first()
            status = _party_invitation_status(contract, version, party, inv)
            if party.pk in accepted_ids:
                status = 'accepted'
            can_resend = bool(
                inv
                and party.pk not in accepted_ids
                and status not in ('accepted',)
                and contract.status not in (CONTRACT_STATUS_FINALIZED, CONTRACT_STATUS_CANCELLED)
            )
            rows.append({
                'kind': 'party',
                'role': party.role,
                'role_label': ROLE_LABELS.get(party.role, party.role),
                'name': party.display_name,
                'status': status,
                'status_label': _status_label(status),
                'accepted': party.pk in accepted_ids,
                'invitation_id': inv.pk if inv else None,
                'can_resend': can_resend,
            })
        accepted_w = set(version.acceptances.filter(witness_id__isnull=False).values_list('witness_id', flat=True))
        for witness in version.witnesses.order_by('witness_number'):
            inv = contract.invitations.filter(version=version, witness=witness, is_revoked=False).order_by('-created_at').first()
            status = _party_invitation_status(contract, version, witness, inv)
            if witness.pk in accepted_w:
                status = 'accepted'
            can_resend = bool(
                inv
                and witness.pk not in accepted_w
                and status not in ('accepted',)
                and contract.status not in (CONTRACT_STATUS_FINALIZED, CONTRACT_STATUS_CANCELLED)
            )
            rows.append({
                'kind': 'witness',
                'role': 'witness',
                'role_label': witness.witness_role or f'شاهد {witness.witness_number}',
                'name': f'{witness.first_name} {witness.last_name}'.strip(),
                'status': status,
                'status_label': _status_label(status),
                'accepted': witness.pk in accepted_w,
                'invitation_id': inv.pk if inv else None,
                'can_resend': can_resend,
            })
    else:
        wizard = contract.wizard_data or {}
        for party in wizard.get('parties') or []:
            if not isinstance(party, dict):
                continue
            role = party.get('role') or ''
            name = (party.get('display_name') or party.get('name') or '').strip()
            rows.append({
                'kind': 'party',
                'role': role,
                'role_label': ROLE_LABELS.get(role, role),
                'name': name or '—',
                'status': 'not_sent',
                'status_label': _status_label('not_sent'),
                'accepted': False,
            })
    return rows


def _status_label(status: str) -> str:
    return {
        'not_sent': 'ارسال نشده',
        'sent': 'ارسال شده',
        'viewed': 'مشاهده شده',
        'accepted': 'تأیید شده',
        'signed': 'امضا شده',
        'expired': 'منقضی',
        'invalid': 'نامعتبر',
    }.get(status, status)


def _clause_summary(contract: Contract) -> List[Dict[str, str]]:
    display = build_contract_display(contract)
    sections = display.get('document_sections') or []
    out = []
    for sec in sections[:30]:
        if not isinstance(sec, dict):
            continue
        title = (sec.get('title') or sec.get('heading') or '').strip()
        if title:
            out.append({'title': title})
    if out:
        return out
    review = build_contract_display(contract)
    for item in (review.get('custom_agreements') or [])[:10]:
        if isinstance(item, dict) and item.get('title'):
            out.append({'title': str(item['title'])})
    return out


def _financial_mobile_summary(contract: Contract) -> Dict[str, Any]:
    display = build_contract_display(contract)
    fin = display.get('financial_summary') or {}
    if not fin:
        return {}
    simplified = {}
    for key, val in fin.items():
        if isinstance(val, dict) and 'toman' in val:
            simplified[key] = val.get('toman') or val.get('label') or ''
        elif isinstance(val, (str, int, float)):
            simplified[key] = val
    return simplified


def handover_summary(contract: Contract) -> Dict[str, Any]:
    ho = contract.handovers.order_by('-updated_at').first()
    if not ho:
        return {
            'exists': False,
            'status': '',
            'status_label': '',
            'handover_date': None,
            'summary': '',
            'next_action': _handover_cta(contract),
        }
    snap = ho.snapshot_json or {}
    summary_bits = []
    if ho.handover_date:
        summary_bits.append(f'تاریخ {ho.handover_date.isoformat()}')
    if snap.get('keys_count') is not None:
        summary_bits.append(f"کلید: {snap.get('keys_count')}")
    return {
        'exists': True,
        'id': ho.pk,
        'status': ho.status,
        'status_label': ho.get_status_display(),
        'handover_type': ho.handover_type,
        'handover_type_label': ho.get_handover_type_display(),
        'handover_date': ho.handover_date.isoformat() if ho.handover_date else None,
        'summary': ' · '.join(summary_bits),
        'next_action': _handover_cta(contract),
    }


def contract_detail_payload(user, contract_id: int) -> Optional[Dict[str, Any]]:
    assert_mobile_contract_license(user)
    contract = contract_for_user(user, contract_id)
    if not contract:
        return None
    display = build_contract_display(contract)
    base = serialize_contract(contract)
    base.update({
        'summary': {
            'acceptance_progress': contract_acceptance_progress(contract),
            'important_dates': display.get('important_dates') or [],
            'contract_meta': display.get('contract_meta') or {},
        },
        'parties_detail': display.get('parties') or [],
        'witnesses': display.get('witnesses') or [],
        'property': display.get('property') or {},
        'financial': _financial_mobile_summary(contract),
        'clauses': _clause_summary(contract),
        'clauses_edit_path': workspace_paths(contract)['wizard'],
        'signatures': build_party_signatures(contract),
        'handover': handover_summary(contract),
        'attachments_meta': {
            'max_size_bytes': MAX_ATTACHMENT_SIZE,
            'allowed_extensions': list(ALLOWED_ATTACHMENT_EXTENSIONS),
        },
        'can_edit_clauses': contract.is_editable,
        'can_cancel': contract.status not in (
            CONTRACT_STATUS_FINALIZED,
            CONTRACT_STATUS_CANCELLED,
        ),
        'can_copy': True,
        'can_new_version': can_edit_contract(user, contract) and contract.status not in (
            CONTRACT_STATUS_CANCELLED,
        ),
        'current_version_number': (contract.current_version.version_number if contract.current_version else 0),
        'versions': _contract_versions_summary(contract),
    })
    return base


def _contract_versions_summary(contract: Contract) -> List[Dict[str, Any]]:
    rows = []
    for version in contract.versions.order_by('-version_number')[:20]:
        rows.append({
            'id': version.pk,
            'version_number': version.version_number,
            'is_current': contract.current_version_id == version.pk,
            'is_locked': bool(version.is_locked),
            'created_at': version.created_at.isoformat() if version.created_at else None,
            'status_label': 'قفل‌شده' if version.is_locked else 'پیش‌نویس',
        })
    return rows


def contract_timeline_payload(user, contract_id: int) -> Optional[List[Dict[str, Any]]]:
    assert_mobile_contract_license(user)
    contract = contract_for_user(user, contract_id)
    if not contract:
        return None
    events = contract.audit_events.select_related('party', 'actor_user', 'version').order_by('-created_at')[:80]
    timeline = build_audit_timeline(events)
    out = []
    for row in timeline:
        created = row.get('created_at')
        out.append({
            'id': row['id'],
            'event_type': row['event_type'],
            'label': row['label'],
            'detail': row['detail'],
            'created_at': created.isoformat() if created else None,
        })
    return out


def serialize_attachment(att: ContractAttachment) -> Dict[str, Any]:
    return {
        'id': att.pk,
        'title': att.title or '',
        'attachment_type': att.attachment_type,
        'mime_type': att.mime_type or '',
        'file_size': att.file_size or 0,
        'created_at': att.created_at.isoformat() if att.created_at else None,
        'can_delete': False,
    }


def list_attachments_payload(user, contract_id: int) -> Optional[List[Dict[str, Any]]]:
    assert_mobile_contract_license(user)
    contract = contract_for_user(user, contract_id)
    if not contract:
        return None
    atts = contract.attachments.filter(handover__isnull=True).order_by('-created_at')[:100]
    return [serialize_attachment(a) for a in atts]


def upload_attachment_payload(
    user,
    contract_id: int,
    uploaded,
    *,
    title: str = '',
    attachment_type: str = 'other',
    handover_id: Optional[int] = None,
):
    assert_mobile_contract_license(user)
    contract = contract_for_user(user, contract_id)
    if not contract:
        raise ValueError('قرارداد یافت نشد.')
    version = contract.current_version
    if not version:
        raise ValueError('نسخه قرارداد آماده نیست.')
    handover = None
    if handover_id:
        handover = contract.handovers.filter(pk=handover_id).first()
        if not handover:
            raise ValueError('صورت‌جلسه یافت نشد.')
        if handover.status not in ('draft', 'pending'):
            raise ValueError('این صورت‌جلسه قابل ویرایش نیست.')
    try:
        validate_upload_file(uploaded)
        att = save_contract_attachment(
            contract=contract,
            version=version,
            uploaded=uploaded,
            attachment_type=attachment_type or 'other',
            title=title,
            user=user,
            handover=handover,
        )
    except ValidationError as exc:
        msg = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
        raise ValueError(msg) from exc
    return serialize_attachment(att)


def get_contract_for_pdf(user, contract_id: int) -> Optional[Contract]:
    assert_mobile_contract_license(user)
    return contract_for_user(user, contract_id)
