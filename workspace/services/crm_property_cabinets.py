"""کمدهای فایل شخصی — گروه‌بندی زونکن‌ها."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from django.db import IntegrityError
from django.db.models import Count, Max

from workspace.models import CRMPropertyCabinet, CRMPropertyFolder

FOLDER_COLORS = (
    '#6366f1', '#0ea5e9', '#10b981', '#f59e0b',
    '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6',
)
FOLDER_ICONS = (
    'fa-folder', 'fa-folder-open', 'fa-building', 'fa-city',
    'fa-key', 'fa-star', 'fa-briefcase', 'fa-layer-group',
    'fa-house-chimney', 'fa-landmark',
)

CabinetFilter = Union[int, str, None]

_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
CABINET_NONE = 'none'


def _clean_color(value: str) -> str:
    text = (value or '').strip()
    if _HEX_COLOR_RE.match(text):
        return text.lower()
    return FOLDER_COLORS[0]


def _clean_icon(value: str) -> str:
    text = (value or '').strip()
    if text in FOLDER_ICONS:
        return text
    if text.startswith('fa-') and len(text) <= 40:
        return text
    return 'fa-folder'


def folder_for_user(user, folder_id: int) -> Optional[CRMPropertyFolder]:
    if not folder_id:
        return None
    return CRMPropertyFolder.objects.filter(user=user, pk=int(folder_id)).select_related('cabinet').first()


def cabinet_for_user(user, cabinet_id: int) -> Optional[CRMPropertyCabinet]:
    if not cabinet_id:
        return None
    return CRMPropertyCabinet.objects.filter(user=user, pk=int(cabinet_id)).first()


def _validate_folder_cabinet_user(folder: CRMPropertyFolder, cabinet: CRMPropertyCabinet) -> None:
    if folder.user_id != cabinet.user_id:
        raise ValueError('کمد و زونکن باید متعلق به یک کاربر باشند')


def list_property_cabinets(user) -> List[CRMPropertyCabinet]:
    return list(
        CRMPropertyCabinet.objects.filter(user=user)
        .annotate(
            folder_count=Count('folders', distinct=True),
            property_count=Count('folders__items__property', distinct=True),
        )
        .order_by('-is_pinned', 'sort_order', 'name')
    )


def unassigned_folder_count(user) -> int:
    return CRMPropertyFolder.objects.filter(user=user, cabinet__isnull=True).count()


def serialize_cabinet(
    cabinet: CRMPropertyCabinet,
    *,
    folder_count: Optional[int] = None,
    property_count: Optional[int] = None,
) -> Dict[str, Any]:
    fcount = folder_count
    if fcount is None:
        fcount = getattr(cabinet, 'folder_count', None)
    if fcount is None:
        fcount = cabinet.folders.count()
    pcount = property_count
    if pcount is None:
        pcount = getattr(cabinet, 'property_count', None)
    return {
        'id': cabinet.pk,
        'name': cabinet.name,
        'description': cabinet.description or '',
        'color': cabinet.color or FOLDER_COLORS[0],
        'icon': cabinet.icon or 'fa-folder',
        'sort_order': cabinet.sort_order,
        'is_pinned': cabinet.is_pinned,
        'folder_count': int(fcount or 0),
        'property_count': int(pcount or 0),
        'created_at': cabinet.created_at.isoformat() if cabinet.created_at else None,
        'updated_at': cabinet.updated_at.isoformat() if cabinet.updated_at else None,
    }


def serialize_cabinet_brief(cabinet: CRMPropertyCabinet) -> Dict[str, Any]:
    return {
        'id': cabinet.pk,
        'name': cabinet.name,
        'color': cabinet.color or FOLDER_COLORS[0],
        'icon': cabinet.icon or 'fa-folder',
    }


def create_property_cabinet(
    user,
    *,
    name: str,
    description: str = '',
    color: str = '',
    icon: str = '',
    is_pinned: bool = False,
) -> CRMPropertyCabinet:
    clean_name = (name or '').strip()
    if not clean_name:
        raise ValueError('نام کمد الزامی است')
    if len(clean_name) > 80:
        raise ValueError('نام کمد خیلی طولانی است')
    try:
        next_order = (
            CRMPropertyCabinet.objects.filter(user=user).aggregate(m=Max('sort_order'))['m'] or 0
        ) + 10
        return CRMPropertyCabinet.objects.create(
            user=user,
            name=clean_name,
            description=(description or '').strip()[:240],
            color=_clean_color(color),
            icon=_clean_icon(icon),
            is_pinned=bool(is_pinned),
            sort_order=next_order,
        )
    except IntegrityError as exc:
        raise ValueError('کمدی با این نام وجود دارد') from exc


def update_property_cabinet(user, cabinet_id: int, data: dict) -> CRMPropertyCabinet:
    cabinet = cabinet_for_user(user, cabinet_id)
    if not cabinet:
        raise ValueError('کمد یافت نشد')
    if 'name' in data and data.get('name') is not None:
        clean_name = str(data.get('name') or '').strip()
        if not clean_name:
            raise ValueError('نام کمد الزامی است')
        cabinet.name = clean_name[:80]
    if 'description' in data and data.get('description') is not None:
        cabinet.description = str(data.get('description') or '').strip()[:240]
    if 'color' in data and data.get('color') is not None:
        cabinet.color = _clean_color(str(data.get('color') or ''))
    if 'icon' in data and data.get('icon') is not None:
        cabinet.icon = _clean_icon(str(data.get('icon') or ''))
    if 'sort_order' in data and data.get('sort_order') is not None:
        try:
            cabinet.sort_order = max(0, int(data.get('sort_order')))
        except (TypeError, ValueError):
            pass
    if 'is_pinned' in data and data.get('is_pinned') is not None:
        cabinet.is_pinned = bool(data.get('is_pinned'))
    try:
        cabinet.save()
    except IntegrityError as exc:
        raise ValueError('کمدی با این نام وجود دارد') from exc
    return cabinet


def delete_property_cabinet(user, cabinet_id: int) -> bool:
    cabinet = cabinet_for_user(user, cabinet_id)
    if not cabinet:
        return False
    CRMPropertyFolder.objects.filter(user=user, cabinet=cabinet).update(cabinet=None)
    cabinet.delete()
    return True


def reorder_property_cabinets(user, cabinet_ids: List[int]) -> List[CRMPropertyCabinet]:
    ordered: List[int] = []
    seen = set()
    for raw in cabinet_ids or []:
        try:
            cid = int(raw)
        except (TypeError, ValueError):
            continue
        if cid in seen:
            continue
        seen.add(cid)
        ordered.append(cid)
    valid = set(
        CRMPropertyCabinet.objects.filter(user=user, pk__in=ordered).values_list('pk', flat=True)
    )
    ordered = [cid for cid in ordered if cid in valid]
    rest = list(
        CRMPropertyCabinet.objects.filter(user=user)
        .exclude(pk__in=ordered)
        .order_by('-is_pinned', 'sort_order', 'name')
        .values_list('pk', flat=True)
    )
    final = ordered + rest
    for idx, cid in enumerate(final):
        CRMPropertyCabinet.objects.filter(user=user, pk=cid).update(sort_order=idx * 10)
    return list_property_cabinets(user)


def assign_folder_to_cabinet(user, folder_id: int, cabinet_id: int) -> CRMPropertyFolder:
    folder = folder_for_user(user, folder_id)
    if not folder:
        raise ValueError('زونکن یافت نشد')
    cabinet = cabinet_for_user(user, cabinet_id)
    if not cabinet:
        raise ValueError('کمد یافت نشد')
    _validate_folder_cabinet_user(folder, cabinet)
    folder.cabinet = cabinet
    folder.save(update_fields=['cabinet', 'updated_at'])
    return folder


def remove_folder_from_cabinet(user, folder_id: int) -> CRMPropertyFolder:
    folder = folder_for_user(user, folder_id)
    if not folder:
        raise ValueError('زونکن یافت نشد')
    folder.cabinet = None
    folder.save(update_fields=['cabinet', 'updated_at'])
    return folder
