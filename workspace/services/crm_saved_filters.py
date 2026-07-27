"""فیلترهای ذخیره‌شده CRM — A10."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from django.db import IntegrityError

from workspace.constants import CRM_FILTER_PARAMS, CRM_FILTER_SCOPES
from workspace.models import CRMSavedFilter


def _clean_params(scope: str, params: dict) -> Dict[str, str]:
    allowed = CRM_FILTER_PARAMS.get(scope, set())
    cleaned: Dict[str, str] = {}
    for key, value in (params or {}).items():
        if key not in allowed:
            continue
        text = str(value).strip() if value is not None else ''
        if text:
            cleaned[key] = text
    return cleaned


def list_saved_filters(user, scope: str) -> List[CRMSavedFilter]:
    if scope not in CRM_FILTER_SCOPES:
        return []
    return list(
        CRMSavedFilter.objects.filter(user=user, scope=scope).order_by('-is_pinned', 'name')
    )


def build_filter_url(base_path: str, params: dict, *, view: str = '') -> str:
    qs = params.dict() if hasattr(params, 'dict') else dict(params or {})
    if view:
        qs['view'] = view
    query = urlencode(qs)
    return f'{base_path}?{query}' if query else base_path


def save_filter(user, *, name: str, scope: str, params: dict, is_pinned: bool = False) -> CRMSavedFilter:
    name = (name or '').strip()
    if not name:
        raise ValueError('نام فیلتر الزامی است')
    if len(name) > 120:
        raise ValueError('نام فیلتر خیلی طولانی است')
    if scope not in CRM_FILTER_SCOPES:
        raise ValueError('بخش نامعتبر')
    cleaned = _clean_params(scope, params)
    if not cleaned:
        raise ValueError('حداقل یک معیار فیلتر انتخاب کنید')
    try:
        obj, _created = CRMSavedFilter.objects.update_or_create(
            user=user,
            scope=scope,
            name=name,
            defaults={'params': cleaned, 'is_pinned': is_pinned},
        )
    except IntegrityError as exc:
        raise ValueError('فیلتری با این نام وجود دارد') from exc
    return obj


def delete_filter(user, filter_id: int) -> bool:
    deleted, _ = CRMSavedFilter.objects.filter(user=user, pk=filter_id).delete()
    return bool(deleted)


def toggle_pin(user, filter_id: int) -> CRMSavedFilter:
    obj = CRMSavedFilter.objects.get(user=user, pk=filter_id)
    obj.is_pinned = not obj.is_pinned
    obj.save(update_fields=['is_pinned', 'updated_at'])
    return obj


def serialize_filter(f: CRMSavedFilter, *, new_count: Optional[int] = None) -> Dict[str, Any]:
    data = {
        'id': f.pk,
        'name': f.name,
        'scope': f.scope,
        'entity': f.scope,  # alias برای کلاینت‌های قدیمی
        'params': f.params,
        'payload': f.params,  # alias
        'is_pinned': f.is_pinned,
        'param_count': len(f.params or {}),
        'updated_at': f.updated_at.isoformat() if f.updated_at else None,
    }
    if new_count is not None:
        data['new_count'] = int(new_count)
    return data


def estimate_listings_new_count(user, saved: CRMSavedFilter) -> int:
    """تعداد تقریبی آگهی‌های جدید مطابق فیلتر از زمان آخرین به‌روزرسانی فیلتر."""
    from mobile_api.services.filing_service import filter_listings_queryset, get_dataset
    from workspace.models import Listing
    from workspace.services.filters import parse_filter_params_from_mapping

    params = dict(saved.params or {})
    filters = parse_filter_params_from_mapping(params)
    dataset_id = params.get('dataset_id') or filters.get('dataset_id')
    if not dataset_id:
        return 0
    ds = get_dataset(user, str(dataset_id))
    if not ds:
        return 0
    qs = Listing.objects.filter(dataset=ds)
    qs = filter_listings_queryset(user, qs, filters, dataset=ds)
    if saved.updated_at:
        qs = qs.filter(created_at__gt=saved.updated_at)
    return qs.count()


def current_params_from_request(request, scope: str) -> Dict[str, str]:
    return _clean_params(scope, request.GET.dict())
