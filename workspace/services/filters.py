"""فیلتر پیشرفته جدول آگهی‌ها."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Case, Count, IntegerField, Q, QuerySet, Value, When

from workspace.services.columns import consultant_q

from workspace.models import ListingMeta
from workspace.services.features import extract_listing_features, parse_build_year


def _normalize_numeric_str(val: str) -> str:
    s = (val or '').strip()
    for i, d in enumerate('۰۱۲۳۴۵۶۷۸۹'):
        s = s.replace(d, str(i))
    for ch in (',', '،', '\u066c', ' ', '\u00a0', '\u200c'):
        s = s.replace(ch, '')
    return s


def _int_param(val: str) -> Optional[int]:
    try:
        s = _normalize_numeric_str(val)
        return int(float(s)) if s else None
    except (ValueError, TypeError):
        return None


def _float_param(val: str) -> Optional[float]:
    try:
        s = _normalize_numeric_str(val)
        return float(s) if s else None
    except (ValueError, TypeError):
        return None


def parse_filter_params(request) -> Dict[str, Any]:
    g = request.GET
    return {
        'q': g.get('q', '').strip(),
        'token': g.get('token', '').strip(),
        'desc': g.get('desc', '').strip(),
        'neighborhood': g.get('neighborhood', '').strip(),
        'rooms': g.get('rooms', '').strip(),
        'tag': g.get('tag', ''),
        'consultant': g.get('consultant', ''),
        'favorites': g.get('favorites', ''),
        'duplicates': g.get('duplicates', ''),
        'elevator': g.get('elevator', ''),
        'parking': g.get('parking', ''),
        'storage': g.get('storage', ''),
        'has_geo': g.get('has_geo', ''),
        'value': g.get('value', ''),
        'area_min': _float_param(g.get('area_min', '')),
        'area_max': _float_param(g.get('area_max', '')),
        'price_min': _int_param(g.get('price_min', '')),
        'price_max': _int_param(g.get('price_max', '')),
        'deposit_min': _int_param(g.get('deposit_min', '')),
        'deposit_max': _int_param(g.get('deposit_max', '')),
        'rent_min': _int_param(g.get('rent_min', '')),
        'rent_max': _int_param(g.get('rent_max', '')),
        'year_min': _int_param(g.get('year_min', '')),
        'year_max': _int_param(g.get('year_max', '')),
        'sort': g.get('sort', ''),
    }


def apply_listing_filters(qs: QuerySet, filters: Dict, user) -> QuerySet:
    if filters.get('q'):
        qs = qs.filter(title__icontains=filters['q'])
    if filters.get('token'):
        qs = qs.filter(token__icontains=filters['token'])
    if filters.get('desc'):
        qs = qs.filter(description__icontains=filters['desc'])
    if filters.get('neighborhood'):
        qs = qs.filter(neighborhood__icontains=filters['neighborhood'])
    if filters.get('rooms'):
        qs = qs.filter(rooms__icontains=filters['rooms'])

    if filters.get('area_min') is not None:
        qs = qs.filter(area__gte=filters['area_min'])
    if filters.get('area_max') is not None:
        qs = qs.filter(area__lte=filters['area_max'])
    if filters.get('price_min') is not None:
        qs = qs.filter(price__gte=filters['price_min'])
    if filters.get('price_max') is not None:
        qs = qs.filter(price__lte=filters['price_max'])
    if filters.get('deposit_min') is not None:
        qs = qs.filter(deposit__gte=filters['deposit_min'])
    if filters.get('deposit_max') is not None:
        qs = qs.filter(deposit__lte=filters['deposit_max'])
    if filters.get('rent_min') is not None:
        qs = qs.filter(rent__gte=filters['rent_min'])
    if filters.get('rent_max') is not None:
        qs = qs.filter(rent__lte=filters['rent_max'])

    if filters.get('consultant') == '1':
        qs = consultant_q(qs)
    elif filters.get('consultant') == '0':
        qs = qs.exclude(
            Q(business_type__icontains='مشاور')
            | Q(business_type__icontains='business')
            | Q(business_type__icontains='agency')
        )

    if filters.get('favorites') == '1':
        fav_tokens = ListingMeta.objects.filter(
            user=user, is_favorite=True,
        ).values_list('token', flat=True)
        qs = qs.filter(token__in=fav_tokens)

    if filters.get('tag'):
        tagged = ListingMeta.objects.filter(
            user=user, tag=filters['tag'],
        ).values_list('token', flat=True)
        qs = qs.filter(token__in=tagged)

    if filters.get('has_geo') == '1':
        qs = qs.exclude(latitude__isnull=True).exclude(longitude__isnull=True)

    return qs


def apply_amenity_filters(listings: List, filters: Dict) -> List:
    """فیلتر امکانات و سال ساخت (از data JSON)."""
    result = list(listings)
    for key in ('elevator', 'parking', 'storage'):
        want = filters.get(key)
        if want not in ('1', '0'):
            continue
        want_bool = want == '1'
        result = [
            lst for lst in result
            if extract_listing_features(lst).get(key) == want_bool
        ]

    y_min, y_max = filters.get('year_min'), filters.get('year_max')
    if y_min is not None or y_max is not None:
        filtered = []
        for lst in result:
            y = extract_listing_features(lst).get('build_year')
            if y is None:
                continue
            if y_min is not None and y < y_min:
                continue
            if y_max is not None and y > y_max:
                continue
            filtered.append(lst)
        result = filtered

    return result


def apply_value_filter(listings: List, value_map: Dict[int, Optional[float]], value: str) -> List:
    if value not in ('below', 'fair', 'above'):
        return listings
    out = []
    for lst in listings:
        score = value_map.get(lst.pk)
        if score is None:
            continue
        if value == 'below' and score < -12:
            out.append(lst)
        elif value == 'fair' and -12 <= score <= 12:
            out.append(lst)
        elif value == 'above' and score > 12:
            out.append(lst)
    return out


def get_neighborhoods(dataset) -> List[str]:
    return get_neighborhoods_qs(dataset.listings.all())


def get_neighborhoods_qs(listings_qs: QuerySet) -> List[str]:
    return list(
        listings_qs.exclude(neighborhood='')
        .values_list('neighborhood', flat=True)
        .distinct()
        .order_by('neighborhood')[:80]
    )


_CONSULTANT_FILTER_Q = (
    Q(business_type__icontains='مشاور')
    | Q(business_type__icontains='business')
    | Q(business_type__icontains='agency')
)


def _advertiser_rank_annotation():
    """۰ = شخصی/خالی، ۱ = مشاور — برای اولویت نمایش شخصی‌ها."""
    return Case(
        When(_CONSULTANT_FILTER_Q, then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )


def sort_queryset(qs: QuerySet, sort: str, default: str) -> QuerySet:
    allowed = {
        'price', '-price', 'deposit', '-deposit', 'rent', '-rent',
        'area', '-area', 'title', '-title', 'neighborhood', '-neighborhood',
        'rooms', '-rooms', 'business_type', '-business_type',
        'created_at', '-created_at',
    }
    if sort not in allowed:
        sort = default

    qs = qs.annotate(_advertiser_rank=_advertiser_rank_annotation())
    field = sort.lstrip('-')
    if field == 'business_type':
        if sort == 'business_type':
            return qs.order_by('_advertiser_rank', default)
        return qs.order_by('-_advertiser_rank', default)
    return qs.order_by('_advertiser_rank', sort)


def build_sort_url(base_params: Dict, field: str, current_sort: str) -> str:
    from urllib.parse import urlencode
    new_sort = field if current_sort != field else f'-{field}'
    if current_sort == f'-{field}':
        new_sort = field
    elif current_sort == field:
        new_sort = f'-{field}'
    params = {**base_params, 'sort': new_sort}
    return '?' + urlencode({k: v for k, v in params.items() if v not in ('', None)})


def active_filter_count(filters: Dict) -> int:
    skip = {'sort', 'page', 'filters_open'}
    n = 0
    for k, v in filters.items():
        if k in skip:
            continue
        if v not in ('', None, False):
            n += 1
    return n


_BASIC_FILTER_KEYS = frozenset({'q', 'neighborhood', 'consultant', 'sort', 'page', 'filters_open'})


def advanced_filter_count(filters: Dict) -> int:
    """تعداد فیلترهای داخل پنل بازشونده (غیر از جستجو و محله و آگهی‌دهنده)."""
    n = 0
    for k, v in filters.items():
        if k in _BASIC_FILTER_KEYS:
            continue
        if v not in ('', None, False):
            n += 1
    return n
