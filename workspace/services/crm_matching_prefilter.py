"""پیش‌فیلتر SQL تطبیق — باید با ارزیابی Python (_profile_*_eligible) سازگار باشد."""
from __future__ import annotations

from typing import Optional

from django.db.models import Q


def _area_value_unknown_q(field: str = 'area') -> Q:
    """متراژ نامشخص در ارزیابی نهایی رد نمی‌شود."""
    return Q(**{f'{field}__isnull': True}) | Q(**{f'{field}__lte': 0})


def _int_value_unknown_q(field: str) -> Q:
    return Q(**{f'{field}__isnull': True}) | Q(**{field: 0})


def apply_area_min_prefilter(qs, min_area: Optional[float], tolerance: float, *, field: str = 'area'):
    if min_area is None or min_area <= 0:
        return qs
    bound = min_area * (1 - tolerance)
    return qs.filter(_area_value_unknown_q(field) | Q(**{f'{field}__gte': bound}))


def apply_area_max_prefilter(qs, max_area: Optional[float], tolerance: float, *, field: str = 'area'):
    if max_area is None or max_area <= 0:
        return qs
    bound = max_area * (1 + tolerance)
    return qs.filter(_area_value_unknown_q(field) | Q(**{f'{field}__lte': bound}))


def apply_int_min_prefilter(qs, field: str, bound: Optional[int]):
    if bound is None:
        return qs
    return qs.filter(_int_value_unknown_q(field) | Q(**{f'{field}__gte': bound}))


def apply_int_max_prefilter(qs, field: str, bound: Optional[int]):
    if bound is None:
        return qs
    return qs.filter(_int_value_unknown_q(field) | Q(**{f'{field}__lte': bound}))
