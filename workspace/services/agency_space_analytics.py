"""Analytics فضای آژانس — Phase 3 (بدون PII)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.db.models import Count, Q
from django.utils import timezone

from workspace.models import AgencySpaceCopy, AgencySpaceItem, CRMAgency
from workspace.services.agency_space_access import can_moderate_agency_space
from workspace.services.crm_scope import agency_members
from workspace.services.user_display import user_display_name


def can_view_space_analytics(user, agency: Optional[CRMAgency] = None) -> bool:
    return can_moderate_agency_space(user, agency)


def get_space_header_kpis(user, agency: CRMAgency) -> Dict[str, int]:
    """KPIهای سبک هدر — بر اساس queryset قابل مشاهده کاربر."""
    from workspace.services.agency_space_query import get_space_items_qs

    base = get_space_items_qs(user, agency=agency, tab='')
    agg = base.aggregate(
        active_properties=Count('pk', filter=Q(property__isnull=False)),
        active_contacts=Count('pk', filter=Q(customer__isnull=False)),
        active_publishers=Count('publisher_id', distinct=True),
    )
    total_copies = AgencySpaceCopy.objects.filter(item__agency=agency).count()
    return {
        'active_properties': int(agg['active_properties'] or 0),
        'active_contacts': int(agg['active_contacts'] or 0),
        'active_publishers': int(agg['active_publishers'] or 0),
        'total_copies': int(total_copies),
    }


def get_space_analytics_payload(agency: CRMAgency) -> Dict[str, Any]:
    week_ago = timezone.now() - timedelta(days=7)
    active = AgencySpaceItem.objects.filter(
        agency=agency,
        status=AgencySpaceItem.STATUS_ACTIVE,
    )
    agg = active.aggregate(
        active_properties=Count('pk', filter=Q(property__isnull=False)),
        active_contacts=Count('pk', filter=Q(customer__isnull=False)),
        active_publishers=Count('publisher_id', distinct=True),
    )
    total_copies = AgencySpaceCopy.objects.filter(item__agency=agency).count()
    copies_7d = AgencySpaceCopy.objects.filter(
        item__agency=agency,
        created_at__gte=week_ago,
    ).count()
    publications_7d = AgencySpaceItem.objects.filter(
        agency=agency,
        published_at__gte=week_ago,
    ).exclude(status=AgencySpaceItem.STATUS_ARCHIVED).count()

    return {
        'active_properties': int(agg['active_properties'] or 0),
        'active_contacts': int(agg['active_contacts'] or 0),
        'active_publishers': int(agg['active_publishers'] or 0),
        'total_copies': int(total_copies),
        'copies_last_7_days': int(copies_7d),
        'publications_last_7_days': int(publications_7d),
    }


def get_contributor_metrics(agency: CRMAgency) -> List[Dict[str, Any]]:
    rows = (
        AgencySpaceItem.objects.filter(agency=agency)
        .exclude(status=AgencySpaceItem.STATUS_ARCHIVED)
        .values('publisher_id')
        .annotate(
            properties_published=Count('pk', filter=Q(property__isnull=False)),
            contacts_published=Count('pk', filter=Q(customer__isnull=False)),
            times_copied=Count('space_copies'),
        )
        .order_by('-properties_published', '-contacts_published')
    )
    members_by_user = {
        m.user_id: m for m in agency_members(agency)
    }
    out: List[Dict[str, Any]] = []
    for row in rows:
        uid = row['publisher_id']
        member = members_by_user.get(uid)
        name = ''
        if member and member.user:
            name = user_display_name(member.user)
        out.append({
            'user_id': uid,
            'name': name,
            'properties_published': int(row['properties_published'] or 0),
            'contacts_published': int(row['contacts_published'] or 0),
            'times_copied': int(row['times_copied'] or 0),
        })
    return out
