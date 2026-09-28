"""کپی فایل شخصی CRM — ملک مستقل با مشخصات مشابه."""
from __future__ import annotations

import copy
from typing import List

from django.db import transaction

from workspace.models import CRMProperty, CRMPropertyFolderItem
from workspace.services.crm_scope import can_edit_property, get_agency, property_for_user

COPY_SUFFIX = ' - کپی'

PROPERTY_DUPLICATE_SCALAR_FIELDS: List[str] = [
    'property_type',
    'deal_mode',
    'transaction_status',
    'publish_status',
    'address',
    'city',
    'district',
    'neighborhood',
    'postal_code',
    'latitude',
    'longitude',
    'area',
    'land_area',
    'frontage_width',
    'rooms',
    'floor',
    'total_floors',
    'has_parking',
    'has_storage',
    'has_elevator',
    'has_wardrobe',
    'has_two_corner',
    'has_two_access',
    'has_wallpaper',
    'has_knauf',
    'has_lighting',
    'is_vacant',
    'build_year',
    'sale_price',
    'deposit',
    'monthly_rent',
    'amenities',
    'link',
    'business_type',
    'phone',
    'owner_name',
    'tenant_phone',
    'tenant_name',
    'notes',
]

JSON_LIST_FIELDS = ('images', 'videos')
JSON_DICT_FIELDS = ('feature_data', 'nearby_pois')

# فیلدهای تماس/یادداشت داخلی — در کپی از فضای آژانس منتقل نمی‌شوند
PROPERTY_SPACE_COPY_EXCLUDED_SCALAR_FIELDS = frozenset({
    'phone',
    'owner_name',
    'tenant_phone',
    'tenant_name',
    'notes',
})


def duplicated_title(title: str) -> str:
    base = (title or '').strip()
    if not base:
        return ''
    max_len = CRMProperty._meta.get_field('title').max_length
    candidate = f'{base}{COPY_SUFFIX}'
    if len(candidate) <= max_len:
        return candidate
    trimmed = base[: max_len - len(COPY_SUFFIX)].rstrip()
    return f'{trimmed}{COPY_SUFFIX}'


def create_property_copy_from_source(
    source: CRMProperty,
    user,
    agency,
    *,
    title: str | None = None,
) -> CRMProperty:
    """کپی مستقل ملک برای کاربر/آژانس مشخص — بدون زونکن و بدون تغییر منبع."""
    if source.deleted_at:
        raise ValueError('ملک حذف‌شده قابل کپی نیست')

    data = {field: getattr(source, field) for field in PROPERTY_DUPLICATE_SCALAR_FIELDS}
    data['user'] = user
    data['agency'] = agency
    data['title'] = (title if title is not None else (source.title or '')).strip()
    data['token'] = ''
    data['source_platform'] = ''
    data['source_external_id'] = ''
    data['deleted_at'] = None
    data['pipeline_order'] = 0
    data['next_follow_up'] = None

    for field in JSON_LIST_FIELDS:
        raw = getattr(source, field) or []
        data[field] = copy.deepcopy(list(raw))
    for field in JSON_DICT_FIELDS:
        raw = getattr(source, field) or {}
        data[field] = copy.deepcopy(dict(raw))

    return CRMProperty.objects.create(**data)


def create_property_copy_from_space_source(
    source: CRMProperty,
    user,
    agency,
) -> CRMProperty:
    """کپی فضای آژانس — بدون اطلاعات تماس مالک/مستأجر و یادداشت داخلی."""
    if source.deleted_at:
        raise ValueError('ملک حذف‌شده قابل کپی نیست')

    fields = [
        f for f in PROPERTY_DUPLICATE_SCALAR_FIELDS
        if f not in PROPERTY_SPACE_COPY_EXCLUDED_SCALAR_FIELDS
    ]
    data = {field: getattr(source, field) for field in fields}
    data['user'] = user
    data['agency'] = agency
    data['title'] = (source.title or '').strip()
    data['phone'] = ''
    data['owner_name'] = ''
    data['tenant_phone'] = ''
    data['tenant_name'] = ''
    data['notes'] = ''
    data['token'] = ''
    data['source_platform'] = ''
    data['source_external_id'] = ''
    data['deleted_at'] = None
    data['pipeline_order'] = 0
    data['next_follow_up'] = None

    for field in JSON_LIST_FIELDS:
        raw = getattr(source, field) or []
        data[field] = copy.deepcopy(list(raw))
    for field in JSON_DICT_FIELDS:
        raw = getattr(source, field) or {}
        data[field] = copy.deepcopy(dict(raw))

    return CRMProperty.objects.create(**data)


@transaction.atomic
def duplicate_property(user, property_id: int) -> CRMProperty:
    source = property_for_user(user, property_id)
    if not source:
        raise ValueError('ملک یافت نشد')
    if source.deleted_at:
        raise ValueError('ملک حذف‌شده قابل کپی نیست')
    if not can_edit_property(user, source):
        raise PermissionError('دسترسی ندارید')

    new_prop = create_property_copy_from_source(
        source,
        source.user,
        source.agency or get_agency(user),
        title=duplicated_title(source.title),
    )

    folder_ids = list(
        CRMPropertyFolderItem.objects.filter(property=source).values_list('folder_id', flat=True)
    )
    if folder_ids:
        CRMPropertyFolderItem.objects.bulk_create(
            [CRMPropertyFolderItem(folder_id=fid, property=new_prop) for fid in folder_ids],
            ignore_conflicts=True,
        )

    return new_prop
