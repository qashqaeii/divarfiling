"""نمای کلی فضای آژانس — KPI، آخرین‌ها، فعالیت."""
from __future__ import annotations

from typing import Any, Dict, List

from workspace.models import AgencyActivityEvent, CRMAgency
from workspace.services.agency_activity import EVENT_TYPE_LABELS, EVENT_SPACE_ITEM_PUBLISHED
from workspace.services.agency_space_analytics import get_contributor_metrics, get_space_header_kpis
from workspace.services.agency_space_query import get_space_items_qs
from workspace.services.agency_space_serialize import serialize_space_item
from workspace.services.display import to_jalali_display
from workspace.services.user_display import user_display_name

_ACTIVITY_ICONS = {
    'contact_created': 'fa-user-plus',
    'personal_property_created': 'fa-building',
    'dataset_created': 'fa-database',
    'extraction_completed': 'fa-download',
    'deal_created': 'fa-handshake',
    'deal_stage_changed': 'fa-diagram-project',
    'follow_up': 'fa-arrows-rotate',
    'call': 'fa-phone',
    'visit': 'fa-door-open',
    'contract_created': 'fa-file-signature',
    'license_assigned': 'fa-id-card',
    'license_unassigned': 'fa-id-card-clip',
    'advisor_data_export': 'fa-file-export',
    'space_item_published': 'fa-share-nodes',
}


def _serialize_slice(user, qs, limit: int = 6) -> List[Dict[str, Any]]:
    rows = list(qs[:limit])
    out = []
    for item in rows:
        payload = serialize_space_item(item, user, detail=False)
        if payload:
            out.append(payload)
    return out


def get_space_overview_payload(user, agency: CRMAgency) -> Dict[str, Any]:
    kpis = get_space_header_kpis(user, agency)
    recent_properties = _serialize_slice(
        user,
        get_space_items_qs(user, agency=agency, tab='properties'),
        limit=5,
    )
    recent_contacts = _serialize_slice(
        user,
        get_space_items_qs(user, agency=agency, tab='contacts'),
        limit=5,
    )
    contributors_raw = get_contributor_metrics(agency)[:5]
    max_contrib = 1
    for row in contributors_raw:
        row['score'] = int(row.get('properties_published') or 0) + int(row.get('contacts_published') or 0)
        max_contrib = max(max_contrib, row['score'])
    contributors = []
    for row in contributors_raw:
        score = row['score']
        contributors.append({
            **row,
            'score_percent': int(round(100 * score / max_contrib)) if max_contrib else 0,
        })

    activity_rows = []
    events = (
        AgencyActivityEvent.objects.filter(agency=agency)
        .select_related('actor')
        .order_by('-created_at')[:12]
    )
    for ev in events:
        label = EVENT_TYPE_LABELS.get(ev.event_type, ev.event_type)
        actor_name = user_display_name(ev.actor) if ev.actor else ''
        detail = ''
        if ev.event_type == EVENT_SPACE_ITEM_PUBLISHED:
            kind = (ev.metadata or {}).get('kind_label') or ev.object_type or ''
            detail = kind
        activity_rows.append({
            'event_type': ev.event_type,
            'label': label,
            'actor_name': actor_name,
            'detail': detail,
            'icon': _ACTIVITY_ICONS.get(ev.event_type, 'fa-circle-dot'),
            'created_at': ev.created_at.isoformat() if ev.created_at else '',
            'created_at_display': to_jalali_display(ev.created_at) if ev.created_at else '',
        })

    return {
        'kpis': kpis,
        'recent_properties': recent_properties,
        'recent_contacts': recent_contacts,
        'contributors': contributors,
        'activity': activity_rows,
    }
