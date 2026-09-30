"""نمای کلی فضای آژانس — KPI، آخرین‌ها، فعالیت."""
from __future__ import annotations

from typing import Any, Dict, List

from workspace.models import AgencyActivityEvent, CRMAgency
from workspace.services.agency_activity import EVENT_TYPE_LABELS, EVENT_SPACE_ITEM_PUBLISHED
from workspace.services.agency_space_analytics import get_contributor_metrics, get_space_header_kpis
from workspace.services.agency_space_query import get_space_items_qs
from workspace.services.agency_space_serialize import serialize_space_item
from workspace.services.user_display import user_display_name


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
    contributors = get_contributor_metrics(agency)[:5]

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
            'created_at': ev.created_at.isoformat() if ev.created_at else '',
        })

    return {
        'kpis': kpis,
        'recent_properties': recent_properties,
        'recent_contacts': recent_contacts,
        'contributors': contributors,
        'activity': activity_rows,
    }
