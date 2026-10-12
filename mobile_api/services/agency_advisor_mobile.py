"""Advisor 360 workspace payloads for mobile — reuses agency_data_scope."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.core.paginator import Paginator

from workspace.services.agency_activity import EVENT_TYPE_LABELS
from workspace.services.agency_data_scope import (
    AgencyDataScopeError,
    get_member_activity_qs,
    get_member_contacts_qs,
    get_member_contracts_qs,
    get_member_deals_qs,
    get_member_filing_qs,
    get_member_listings_qs,
    get_member_overview_kpis,
    get_member_properties_qs,
    resolve_visible_agency_member,
)
from workspace.services.display import to_jalali_display

PAGE_SIZE = 25

WORKSPACE_TABS = (
    'overview',
    'contacts',
    'properties',
    'filing',
    'deals',
    'contracts',
    'activities',
)


def _dt_label(dt) -> str:
    if not dt:
        return ''
    return to_jalali_display(dt) or ''


def _iso(dt) -> str:
    if not dt:
        return ''
    return dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)


def _contact_item(row) -> Dict[str, Any]:
    return {
        'id': row.pk,
        'name': row.name or '',
        'phone': row.phone or '',
        'status': row.status or '',
        'next_follow_up': _iso(row.next_follow_up),
        'next_follow_up_display': _dt_label(row.next_follow_up),
        'created_at': _iso(row.created_at),
        'created_at_display': _dt_label(row.created_at),
    }


def _property_item(row) -> Dict[str, Any]:
    region = ' · '.join(p for p in (row.neighborhood, row.district, row.city) if p)
    return {
        'id': row.pk,
        'title': row.title or '',
        'region': region,
        'transaction_status': row.transaction_status or '',
        'deal_mode': row.deal_mode or '',
        'property_type': row.property_type or '',
        'updated_at_display': _dt_label(row.updated_at),
    }


def _dataset_item(row) -> Dict[str, Any]:
    return {
        'id': str(row.pk),
        'name': row.name or '',
        'listing_count': int(getattr(row, 'listing_count', 0) or 0),
        'updated_at_display': _dt_label(row.updated_at),
    }


def _listing_item(row) -> Dict[str, Any]:
    return {
        'id': row.pk,
        'token': row.token or '',
        'title': row.title or '',
        'district': row.district or '',
        'price_label': (row.price or '') if hasattr(row, 'price') else '',
        'created_at_display': _dt_label(row.created_at),
        'dataset_id': str(row.dataset_id) if row.dataset_id else '',
        'dataset_name': row.dataset.name if row.dataset_id else '',
    }


def _deal_item(row) -> Dict[str, Any]:
    return {
        'id': row.pk,
        'title': row.title or '',
        'stage': row.stage or '',
        'customer_name': row.customer.name if row.customer_id else '',
        'property_title': row.property.title if row.property_id else '',
        'updated_at_display': _dt_label(row.updated_at),
    }


def _contract_item(row) -> Dict[str, Any]:
    version = row.current_version
    return {
        'id': row.pk,
        'internal_number': row.internal_number or '',
        'status': row.get_status_display() if row.status else '',
        'title': row.title or '',
        'deal_title': row.deal.title if row.deal_id else '',
        'version': version.version_number if version else None,
        'updated_at_display': _dt_label(row.updated_at),
    }


def _activity_item(row: Dict[str, Any]) -> Dict[str, Any]:
    at = row.get('at')
    label = row.get('label') or ''
    if row.get('type') == 'agency_event':
        label = EVENT_TYPE_LABELS.get(label, label.replace('_', ' '))
    return {
        'type': row.get('type') or '',
        'label': label,
        'title': row.get('title') or '',
        'detail': row.get('detail') or '',
        'created_at': _iso(at),
        'created_at_display': _dt_label(at),
    }


def _paginate(qs, page: int) -> Dict[str, Any]:
    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(page)
    return {
        'total': paginator.count,
        'page': page_obj.number,
        'num_pages': paginator.num_pages,
        'page_obj': page_obj,
    }


def _serialize_kpis(kpis: Dict[str, Any]) -> Dict[str, Any]:
    last = kpis.get('last_activity')
    return {
        'period_days': kpis.get('period_days', 30),
        'contacts': kpis.get('contacts') or {},
        'properties': kpis.get('properties') or {},
        'datasets': kpis.get('datasets') or {},
        'deals_active': kpis.get('deals_active', 0),
        'deals_closed': kpis.get('deals_closed', 0),
        'contracts': kpis.get('contracts', 0),
        'open_tasks': kpis.get('open_tasks', 0),
        'last_activity': _iso(last),
        'last_activity_display': _dt_label(last),
    }


def advisor_workspace_for_user(
    user,
    member_id: int,
    *,
    tab: str = 'overview',
    page: int = 1,
    q: str = '',
    status: str = '',
    stage: str = '',
    dataset_id: Optional[str] = None,
    period: int = 30,
) -> Optional[Dict[str, Any]]:
    try:
        member = resolve_visible_agency_member(user, member_id)
    except AgencyDataScopeError:
        return None

    tab = (tab or 'overview').strip()
    if tab not in WORKSPACE_TABS:
        tab = 'overview'
    if period not in (7, 30, 90):
        period = 30
    page = max(1, int(page or 1))

    base: Dict[str, Any] = {
        'tab': tab,
        'member_id': member.pk,
        'period_days': period,
    }

    if tab == 'overview':
        kpis = get_member_overview_kpis(user, member, days=period)
        base['overview'] = _serialize_kpis(kpis)
        base['counts'] = {
            'contacts': kpis['contacts']['total'],
            'properties': kpis['properties']['total'],
            'datasets': kpis['datasets']['total'],
            'deals_active': kpis['deals_active'],
            'contracts': kpis['contracts'],
        }
        return base

    if tab == 'contacts':
        qs = get_member_contacts_qs(user, member, search=q, status=status)
        meta = _paginate(qs, page)
        base.update({
            'total': meta['total'],
            'page': meta['page'],
            'num_pages': meta['num_pages'],
            'items': [_contact_item(r) for r in meta['page_obj']],
        })
        return base

    if tab == 'properties':
        qs = get_member_properties_qs(user, member, search=q, transaction_status=status)
        meta = _paginate(qs, page)
        base.update({
            'total': meta['total'],
            'page': meta['page'],
            'num_pages': meta['num_pages'],
            'items': [_property_item(r) for r in meta['page_obj']],
        })
        return base

    if tab == 'filing':
        if dataset_id:
            qs = get_member_listings_qs(user, member, dataset_id=dataset_id)
            meta = _paginate(qs, page)
            base['dataset_id'] = dataset_id
            base.update({
                'total': meta['total'],
                'page': meta['page'],
                'num_pages': meta['num_pages'],
                'listings': [_listing_item(r) for r in meta['page_obj']],
            })
        else:
            qs = get_member_filing_qs(user, member)
            meta = _paginate(qs, page)
            base.update({
                'total': meta['total'],
                'page': meta['page'],
                'num_pages': meta['num_pages'],
                'datasets': [_dataset_item(r) for r in meta['page_obj']],
            })
        return base

    if tab == 'deals':
        qs = get_member_deals_qs(user, member, search=q, stage=stage)
        meta = _paginate(qs, page)
        base.update({
            'total': meta['total'],
            'page': meta['page'],
            'num_pages': meta['num_pages'],
            'items': [_deal_item(r) for r in meta['page_obj']],
        })
        return base

    if tab == 'contracts':
        qs = get_member_contracts_qs(user, member)
        meta = _paginate(qs, page)
        base.update({
            'total': meta['total'],
            'page': meta['page'],
            'num_pages': meta['num_pages'],
            'items': [_contract_item(r) for r in meta['page_obj']],
        })
        return base

    if tab == 'activities':
        events = get_member_activity_qs(user, member, limit=80)
        base['items'] = [_activity_item(ev) for ev in events]
        base['total'] = len(events)
        return base

    return base


def advisor_section_counts(user, member_id: int) -> Optional[Dict[str, int]]:
    try:
        member = resolve_visible_agency_member(user, member_id)
    except AgencyDataScopeError:
        return None
    return {
        'contacts': get_member_contacts_qs(user, member).count(),
        'properties': get_member_properties_qs(user, member).count(),
        'datasets': get_member_filing_qs(user, member).count(),
        'deals': get_member_deals_qs(user, member).count(),
        'contracts': get_member_contracts_qs(user, member).count(),
    }
