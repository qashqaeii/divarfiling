"""زونکن‌های فایل شخصی — دسته‌بندی و فیلتر سریع."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from django.db import IntegrityError
from django.db.models import Count, Max

from workspace.models import CRMProperty, CRMPropertyCabinet, CRMPropertyFolder, CRMPropertyFolderItem

CABINET_NONE = 'none'

FOLDER_COLORS = (
    '#6366f1', '#0ea5e9', '#10b981', '#f59e0b',
    '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6',
)
FOLDER_ICONS = (
    'fa-folder', 'fa-folder-open', 'fa-building', 'fa-city',
    'fa-key', 'fa-star', 'fa-briefcase', 'fa-layer-group',
    'fa-house-chimney', 'fa-landmark',
)
_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')

CabinetFilter = Union[int, str, None]


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


def _cabinet_brief(cabinet: Optional[CRMPropertyCabinet]) -> Optional[Dict[str, Any]]:
    if not cabinet:
        return None
    return {
        'id': cabinet.pk,
        'name': cabinet.name,
        'color': cabinet.color or FOLDER_COLORS[0],
        'icon': cabinet.icon or 'fa-folder',
    }


def _validate_folder_cabinet_user(folder: CRMPropertyFolder, cabinet: CRMPropertyCabinet) -> None:
    if folder.user_id != cabinet.user_id:
        raise ValueError('کمد و زونکن باید متعلق به یک کاربر باشند')


def _apply_cabinet_id(folder: CRMPropertyFolder, user, cabinet_id) -> None:
    if cabinet_id is None or cabinet_id == '' or str(cabinet_id).lower() in ('null', 'none'):
        folder.cabinet = None
        return
    try:
        cid = int(cabinet_id)
    except (TypeError, ValueError) as exc:
        raise ValueError('شناسه کمد نامعتبر است') from exc
    cabinet = CRMPropertyCabinet.objects.filter(user=user, pk=cid).first()
    if not cabinet:
        raise ValueError('کمد یافت نشد')
    _validate_folder_cabinet_user(folder, cabinet)
    folder.cabinet = cabinet


def folder_for_user(user, folder_id: int) -> Optional[CRMPropertyFolder]:
    if not folder_id:
        return None
    return CRMPropertyFolder.objects.filter(user=user, pk=int(folder_id)).select_related('cabinet').first()


def list_property_folders(user, cabinet_id: CabinetFilter = None) -> List[CRMPropertyFolder]:
    qs = CRMPropertyFolder.objects.filter(user=user).select_related('cabinet')
    if cabinet_id is not None and str(cabinet_id).strip() != '':
        if str(cabinet_id).lower() == CABINET_NONE:
            qs = qs.filter(cabinet__isnull=True)
        else:
            try:
                qs = qs.filter(cabinet_id=int(cabinet_id))
            except (TypeError, ValueError):
                pass
    return list(
        qs.annotate(property_count=Count('items', distinct=True))
        .order_by('-is_pinned', 'sort_order', 'name')
    )


def serialize_folder(
    folder: CRMPropertyFolder,
    *,
    property_count: Optional[int] = None,
) -> Dict[str, Any]:
    count = property_count
    if count is None:
        count = getattr(folder, 'property_count', None)
    if count is None:
        count = folder.items.count()
    cabinet = getattr(folder, 'cabinet', None)
    if cabinet is None and folder.cabinet_id:
        cabinet = CRMPropertyCabinet.objects.filter(pk=folder.cabinet_id).first()
    return {
        'id': folder.pk,
        'name': folder.name,
        'description': folder.description or '',
        'color': folder.color or FOLDER_COLORS[0],
        'icon': folder.icon or 'fa-folder',
        'sort_order': folder.sort_order,
        'is_pinned': folder.is_pinned,
        'property_count': int(count or 0),
        'cabinet': _cabinet_brief(cabinet),
        'cabinet_id': folder.cabinet_id,
        'created_at': folder.created_at.isoformat() if folder.created_at else None,
        'updated_at': folder.updated_at.isoformat() if folder.updated_at else None,
    }


def serialize_folder_brief(folder: CRMPropertyFolder) -> Dict[str, Any]:
    return {
        'id': folder.pk,
        'name': folder.name,
        'color': folder.color or FOLDER_COLORS[0],
        'icon': folder.icon or 'fa-folder',
    }


def folders_for_property(prop: CRMProperty) -> List[Dict[str, Any]]:
    cache = getattr(prop, '_prefetched_objects_cache', {}).get('folder_items')
    if cache is not None:
        return [
            serialize_folder_brief(item.folder)
            for item in cache
            if getattr(item, 'folder', None) is not None
        ]
    return [
        serialize_folder_brief(item.folder)
        for item in prop.folder_items.select_related('folder').all()
    ]


def create_property_folder(
    user,
    *,
    name: str,
    description: str = '',
    color: str = '',
    icon: str = '',
    is_pinned: bool = False,
    cabinet_id=None,
) -> CRMPropertyFolder:
    clean_name = (name or '').strip()
    if not clean_name:
        raise ValueError('نام زونکن الزامی است')
    if len(clean_name) > 80:
        raise ValueError('نام زونکن خیلی طولانی است')
    try:
        next_order = (
            CRMPropertyFolder.objects.filter(user=user).aggregate(m=Max('sort_order'))['m'] or 0
        ) + 10
        folder = CRMPropertyFolder(
            user=user,
            name=clean_name,
            description=(description or '').strip()[:240],
            color=_clean_color(color),
            icon=_clean_icon(icon),
            is_pinned=bool(is_pinned),
            sort_order=next_order,
        )
        if cabinet_id is not None:
            _apply_cabinet_id(folder, user, cabinet_id)
        folder.save()
        return CRMPropertyFolder.objects.select_related('cabinet').get(pk=folder.pk)
    except IntegrityError as exc:
        raise ValueError('زونکنی با این نام وجود دارد') from exc


def update_property_folder(user, folder_id: int, data: dict) -> CRMPropertyFolder:
    folder = folder_for_user(user, folder_id)
    if not folder:
        raise ValueError('زونکن یافت نشد')
    if 'name' in data and data.get('name') is not None:
        clean_name = str(data.get('name') or '').strip()
        if not clean_name:
            raise ValueError('نام زونکن الزامی است')
        folder.name = clean_name[:80]
    if 'description' in data and data.get('description') is not None:
        folder.description = str(data.get('description') or '').strip()[:240]
    if 'color' in data and data.get('color') is not None:
        folder.color = _clean_color(str(data.get('color') or ''))
    if 'icon' in data and data.get('icon') is not None:
        folder.icon = _clean_icon(str(data.get('icon') or ''))
    if 'sort_order' in data and data.get('sort_order') is not None:
        try:
            folder.sort_order = max(0, int(data.get('sort_order')))
        except (TypeError, ValueError):
            pass
    if 'is_pinned' in data and data.get('is_pinned') is not None:
        folder.is_pinned = bool(data.get('is_pinned'))
    if 'cabinet_id' in data:
        _apply_cabinet_id(folder, user, data.get('cabinet_id'))
    try:
        folder.save()
    except IntegrityError as exc:
        raise ValueError('زونکنی با این نام وجود دارد') from exc
    return CRMPropertyFolder.objects.select_related('cabinet').get(pk=folder.pk)


def delete_property_folder(user, folder_id: int) -> bool:
    deleted, _ = CRMPropertyFolder.objects.filter(user=user, pk=int(folder_id)).delete()
    return bool(deleted)


def reorder_property_folders(user, folder_ids: List[int]) -> List[CRMPropertyFolder]:
    """به‌روزرسانی ترتیب نمایش زونکن‌ها."""
    ordered: List[int] = []
    seen = set()
    for raw in folder_ids or []:
        try:
            fid = int(raw)
        except (TypeError, ValueError):
            continue
        if fid in seen:
            continue
        seen.add(fid)
        ordered.append(fid)
    valid = set(
        CRMPropertyFolder.objects.filter(user=user, pk__in=ordered).values_list('pk', flat=True)
    )
    ordered = [fid for fid in ordered if fid in valid]
    rest = list(
        CRMPropertyFolder.objects.filter(user=user)
        .exclude(pk__in=ordered)
        .order_by('-is_pinned', 'sort_order', 'name')
        .values_list('pk', flat=True)
    )
    final = ordered + rest
    for idx, fid in enumerate(final):
        CRMPropertyFolder.objects.filter(user=user, pk=fid).update(sort_order=idx * 10)
    return list_property_folders(user)


def add_property_to_folder(user, folder_id: int, property_id: int) -> CRMPropertyFolderItem:
    folder = folder_for_user(user, folder_id)
    if not folder:
        raise ValueError('زونکن یافت نشد')
    prop = CRMProperty.objects.filter(user=user, pk=int(property_id), deleted_at__isnull=True).first()
    if not prop:
        raise ValueError('ملک یافت نشد')
    item, _created = CRMPropertyFolderItem.objects.get_or_create(folder=folder, property=prop)
    return item


def bulk_add_properties_to_folder(user, folder_id: int, property_ids: List[int]) -> Dict[str, Any]:
    """افزودن چند ملک به یک زونکن — بدون حذف عضویت‌های قبلی."""
    folder = folder_for_user(user, folder_id)
    if not folder:
        raise ValueError('زونکن یافت نشد')
    ids: List[int] = []
    for raw in property_ids or []:
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        if pid > 0 and pid not in ids:
            ids.append(pid)
    if not ids:
        raise ValueError('ملکی انتخاب نشده است')
    props = CRMProperty.objects.filter(user=user, pk__in=ids, deleted_at__isnull=True)
    added = 0
    for prop in props:
        _item, created = CRMPropertyFolderItem.objects.get_or_create(folder=folder, property=prop)
        if created:
            added += 1
    folder = folder_for_user(user, folder_id)
    return {
        'added': added,
        'requested': len(ids),
        'matched': props.count(),
        'folder': serialize_folder(folder) if folder else None,
    }


def remove_property_from_folder(user, folder_id: int, property_id: int) -> bool:
    folder = folder_for_user(user, folder_id)
    if not folder:
        raise ValueError('زونکن یافت نشد')
    deleted, _ = CRMPropertyFolderItem.objects.filter(
        folder=folder,
        property_id=int(property_id),
        property__user=user,
    ).delete()
    return bool(deleted)


def set_property_folders(user, property_id: int, folder_ids: List[int]) -> List[int]:
    """جایگزینی کامل زونکن‌های یک ملک."""
    prop = CRMProperty.objects.filter(user=user, pk=int(property_id), deleted_at__isnull=True).first()
    if not prop:
        raise ValueError('ملک یافت نشد')
    valid_ids = list(
        CRMPropertyFolder.objects.filter(user=user, pk__in=folder_ids or []).values_list('pk', flat=True)
    )
    CRMPropertyFolderItem.objects.filter(property=prop).exclude(folder_id__in=valid_ids).delete()
    for fid in valid_ids:
        CRMPropertyFolderItem.objects.get_or_create(folder_id=fid, property=prop)
    return valid_ids
