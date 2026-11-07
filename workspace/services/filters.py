"""فیلتر پیشرفته جدول آگهی‌ها."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Case, Count, F, IntegerField, Q, QuerySet, Value, When

from workspace.services.advertiser_signal import (
    ADVERTISER_SIGNAL_CONSULTANT,
    ADVERTISER_SIGNAL_DISGUISED,
    ADVERTISER_SIGNAL_GENUINE_PERSONAL,
    listing_advertiser_display,
    listing_advertiser_signal,
)
from workspace.services.columns import consultant_q

from workspace.models import ListingMeta
from workspace.services.features import extract_listing_features, parse_build_year, parse_rooms_value

DEFAULT_LISTING_SORT = '-published_at'


def default_listing_sort() -> str:
    """مرتب‌سازی پیش‌فرض لیست آگهی‌ها — جدیدترین تاریخ ایجاد در دیوار."""
    return DEFAULT_LISTING_SORT


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


_BUILD_YEAR_MIN = 1200
_BUILD_YEAR_MAX = 1500


def _year_param(val: str) -> Optional[int]:
    n = _int_param(val)
    if n is None:
        return None
    if n < _BUILD_YEAR_MIN or n > _BUILD_YEAR_MAX:
        return None
    return n


def parse_filter_params_from_mapping(g) -> Dict[str, Any]:
    """پارس فیلتر از QueryDict / dict — مشترک وب و موبایل."""
    def get(k, default=''):
        if hasattr(g, 'get'):
            val = g.get(k, default)
        elif isinstance(g, dict):
            val = g.get(k, default)
        else:
            val = default
        if val is None:
            return default
        return val

    rooms_raw = get('rooms', '')
    rooms = str(rooms_raw).strip() if rooms_raw != '' else ''
    return {
        'q': str(get('q', '') or '').strip(),
        'token': str(get('token', '') or '').strip(),
        'desc': str(get('desc', '') or '').strip(),
        'neighborhood': str(get('neighborhood', '') or '').strip(),
        'street': str(get('street', '') or '').strip(),
        'rooms': rooms,
        'tag': str(get('tag', '') or ''),
        'consultant': str(get('consultant', '') or ''),
        'favorites': str(get('favorites', '') or ''),
        'duplicates': str(get('duplicates', '') or ''),
        'unique': str(get('unique', '') or ''),
        'new_only': str(get('new_only', '') or ''),
        'elevator': str(get('elevator', '') or ''),
        'parking': str(get('parking', '') or ''),
        'storage': str(get('storage', '') or ''),
        'has_geo': str(get('has_geo', '') or ''),
        'value': str(get('value', '') or ''),
        'area_min': _float_param(str(get('area_min', '') or '')),
        'area_max': _float_param(str(get('area_max', '') or '')),
        'price_min': _int_param(str(get('price_min', '') or '')),
        'price_max': _int_param(str(get('price_max', '') or '')),
        'deposit_min': _int_param(str(get('deposit_min', '') or '')),
        'deposit_max': _int_param(str(get('deposit_max', '') or '')),
        'rent_min': _int_param(str(get('rent_min', '') or '')),
        'rent_max': _int_param(str(get('rent_max', '') or '')),
        'year_min': _year_param(str(get('year_min', '') or '')),
        'year_max': _year_param(str(get('year_max', '') or '')),
        'sort': str(get('sort', '') or ''),
        'dataset_id': str(get('dataset_id', '') or '').strip(),
        'retention_warning': str(get('retention_warning', '') or '').strip(),
    }


def parse_filter_params(request) -> Dict[str, Any]:
    return parse_filter_params_from_mapping(request.GET)


_DIVAR_TOKEN_IN_URL = re.compile(
    r'(?:https?://)?(?:www\.)?divar\.ir/v/([A-Za-z0-9_-]+)',
    re.IGNORECASE,
)
_DIVAR_TOKEN_SHAPE = re.compile(r'^[A-Za-z0-9_-]+$')
_TOKEN_CONFUSION_PAIRS: Tuple[Tuple[str, str], ...] = (
    ('Z', '2'),
    ('z', '2'),
    ('O', '0'),
    ('o', '0'),
    ('l', '1'),
    ('I', '1'),
)


def _normalize_search_text(val: str) -> str:
    """فقط ارقام فارسی/عربی → لاتین؛ فاصله برای جستجوی عنوان/خیابان حفظ می‌شود."""
    s = (val or '').strip()
    for i, d in enumerate('۰۱۲۳۴۵۶۷۸۹'):
        s = s.replace(d, str(i))
    for i, d in enumerate('٠١٢٣٤٥٦٧٨٩'):
        s = s.replace(d, str(i))
    return s


def normalize_listing_search_query(raw: str) -> str:
    """استخراج شناسه دیوار از لینک، یا متن آزاد جستجو (با حفظ فاصله)."""
    q = str(raw or '').strip()
    if not q:
        return ''
    m = _DIVAR_TOKEN_IN_URL.search(q)
    if m:
        return _normalize_numeric_str(m.group(1))
    compact = _normalize_numeric_str(q)
    if _looks_like_divar_token(compact):
        return compact
    return _normalize_search_text(q)


def _looks_like_divar_token(term: str) -> bool:
    return 6 <= len(term) <= 12 and bool(_DIVAR_TOKEN_SHAPE.match(term))


def divar_token_search_variants(term: str, *, max_variants: int = 48) -> frozenset[str]:
    """واریانت‌های رایج اشتباه تایپ/خواندن شناسه (مثلاً Z به‌جای ۲ در فونت کوچک)."""
    base = _normalize_numeric_str((term or '').strip())
    if not base or not _looks_like_divar_token(base):
        return frozenset({base}) if base else frozenset()
    variants = {base}
    queue = [base]
    while queue and len(variants) < max_variants:
        s = queue.pop(0)
        for i, ch in enumerate(s):
            for a, b in _TOKEN_CONFUSION_PAIRS:
                for src, dst in ((a, b), (b, a)):
                    if ch != src:
                        continue
                    candidate = s[:i] + dst + s[i + 1:]
                    if candidate in variants:
                        continue
                    variants.add(candidate)
                    if len(variants) < max_variants:
                        queue.append(candidate)
    return frozenset(variants)


def token_field_search_q(term: str) -> Q:
    q = _normalize_numeric_str((term or '').strip())
    if not q:
        return Q()
    q_obj = Q(token__icontains=q)
    if _looks_like_divar_token(q):
        for variant in divar_token_search_variants(q):
            q_obj |= Q(token__iexact=variant)
    return q_obj


def listing_search_q(term: str) -> Q:
    """جستجوی متن آزاد: عنوان، شناسه، لینک، محله، شهر، خیابان."""
    q = normalize_listing_search_query(term)
    if not q:
        return Q()
    return (
        Q(title__icontains=q)
        | Q(link__icontains=q)
        | Q(neighborhood__icontains=q)
        | Q(city__icontains=q)
        | Q(data__مکان_خیابان__icontains=q)
        | Q(data__خیابان__icontains=q)
        | token_field_search_q(q)
    )


def apply_listing_filters(qs: QuerySet, filters: Dict, user) -> QuerySet:
    if filters.get('q'):
        qs = qs.filter(listing_search_q(filters['q']))
    if filters.get('token'):
        qs = qs.filter(token_field_search_q(filters['token']))
    if filters.get('desc'):
        qs = qs.filter(description__icontains=filters['desc'])
    if filters.get('neighborhood'):
        qs = qs.filter(neighborhood__icontains=filters['neighborhood'])
    # street — در apply_street_filter (نرمال‌سازی مکان_خیابان / خیابان)
    # rooms — در apply_rooms_filter (هم‌راستا با extract_listing_features)

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

    if filters.get('retention_warning') == '1':
        from workspace.services.listing_retention_status import listing_ids_in_retention_warning
        warning_ids = listing_ids_in_retention_warning(user, qs)
        qs = qs.filter(pk__in=warning_ids) if warning_ids else qs.none()

    return qs


def apply_rooms_filter(listings: List, rooms_filter: str) -> List:
    """فیلتر اتاق — از data/عنوان هم می‌خواند، نه فقط ستون rooms."""
    needle = parse_rooms_value(rooms_filter)
    if not needle:
        raw = _normalize_numeric_str(rooms_filter)
        if not raw:
            return listings
        return [
            lst for lst in listings
            if raw in _normalize_numeric_str(extract_listing_features(lst).get('rooms') or '')
            or raw in _normalize_numeric_str(getattr(lst, 'rooms', '') or '')
        ]
    return [
        lst for lst in listings
        if parse_rooms_value(extract_listing_features(lst).get('rooms')) == needle
        or parse_rooms_value(getattr(lst, 'rooms', '') or '') == needle
    ]


def apply_street_filter(listings: List, street: str) -> List:
    """فیلتر خیابان با نرمال‌سازی همان منطق نمایش کارت."""
    from workspace.services.listing_street_data import (
        listing_street_for_display,
        normalize_street_storage_value,
    )

    needle = normalize_street_storage_value(street)
    if not needle:
        return listings
    return [
        lst for lst in listings
        if listing_street_for_display(lst) == needle
    ]


def apply_amenity_filters(listings: List, filters: Dict) -> List:
    """فیلتر امکانات، سال ساخت و اتاق (از data JSON)."""
    result = list(listings)
    if filters.get('street'):
        result = apply_street_filter(result, filters['street'])
    if filters.get('rooms'):
        result = apply_rooms_filter(result, filters['rooms'])
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


def get_streets(dataset) -> List[Dict[str, Any]]:
    return get_streets_qs(dataset.listings.all())


def get_streets_qs(listings_qs: QuerySet, *, limit: int = 80) -> List[Dict[str, Any]]:
    """خیابان‌های یکتا با تعداد آگهی از Listing.data (مکان_خیابان / خیابان)."""
    from workspace.services.listing_street_data import (
        normalize_street_storage_value,
        sync_street_keys_in_listing_data,
    )

    counts: Dict[str, int] = {}
    for data in listings_qs.values_list('data', flat=True).iterator(chunk_size=400):
        if not isinstance(data, dict):
            continue
        synced = sync_street_keys_in_listing_data(data)
        street = normalize_street_storage_value(synced.get('مکان_خیابان'))
        if street:
            counts[street] = counts.get(street, 0) + 1
    items = [
        {'name': name, 'count': count}
        for name, count in counts.items()
    ]
    items.sort(key=lambda row: row['name'])
    return items[:limit]


_LISTING_POST_FILTER_KEYS = frozenset({
    'rooms', 'elevator', 'parking', 'storage', 'year_min', 'year_max', 'value', 'street',
})


def needs_listing_post_filters(filters: Dict) -> bool:
    """آیا بعد از queryset باید فیلتر پایتون (امکانات/خیابان/ارزش/…) اعمال شود؟"""
    return any(filters.get(k) for k in _LISTING_POST_FILTER_KEYS) or needs_advertiser_signal_filter(filters)


def get_user_dataset_neighborhoods(
    user,
    *,
    search: str = '',
    limit: int = 500,
    offset: int = 0,
) -> List[str]:
    """محله/منطقهٔ distinct از فایلینگ فعال و فایل‌های شخصی — با جست‌وجو و صفحه‌بندی."""
    from workspace.models import CRMProperty, Listing

    if not user or not getattr(user, 'pk', None):
        return []

    names: set[str] = set()
    term = (search or '').strip()

    listing_qs = Listing.objects.filter(
        dataset__user=user,
        dataset__is_active=True,
    ).exclude(neighborhood='')
    if term:
        listing_qs = listing_qs.filter(neighborhood__icontains=term)
    names.update(
        n.strip()
        for n in listing_qs.values_list('neighborhood', flat=True).distinct().iterator(chunk_size=500)
        if (n or '').strip()
    )

    prop_qs = CRMProperty.objects.filter(
        user=user,
        deleted_at__isnull=True,
    )
    if term:
        prop_qs = prop_qs.filter(
            Q(neighborhood__icontains=term) | Q(district__icontains=term)
        )
    for neighborhood, district in prop_qs.values_list('neighborhood', 'district').iterator(chunk_size=400):
        for raw in (neighborhood, district):
            value = (raw or '').strip()
            if not value:
                continue
            if term and term.casefold() not in value.casefold():
                continue
            names.add(value)

    ordered = sorted(names)
    return ordered[offset: offset + limit]


def get_user_location_streets(
    user,
    *,
    search: str = '',
    limit: int = 500,
    offset: int = 0,
) -> List[str]:
    """خیابان‌های distinct از فایلینگ فعال و فایل‌های شخصی — با جست‌وجو و صفحه‌بندی."""
    from workspace.models import CRMProperty, Listing
    from workspace.services.listing_street_data import (
        normalize_street_storage_value,
        sync_street_keys_in_listing_data,
    )

    if not user or not getattr(user, 'pk', None):
        return []

    names: set[str] = set()
    term = (search or '').strip()
    term_cf = term.casefold() if term else ''

    def _accept(street: str) -> None:
        if not street:
            return
        if term_cf and term_cf not in street.casefold():
            return
        names.add(street)

    listing_qs = Listing.objects.filter(
        dataset__user=user,
        dataset__is_active=True,
    )
    if term:
        listing_qs = listing_qs.filter(
            Q(data__مکان_خیابان__icontains=term) | Q(data__خیابان__icontains=term)
        )
    for data in listing_qs.values_list('data', flat=True).iterator(chunk_size=400):
        if not isinstance(data, dict):
            continue
        synced = sync_street_keys_in_listing_data(data)
        _accept(normalize_street_storage_value(synced.get('مکان_خیابان')))

    prop_qs = CRMProperty.objects.filter(
        user=user,
        deleted_at__isnull=True,
    )
    for feature_data in prop_qs.values_list('feature_data', flat=True).iterator(chunk_size=400):
        if not isinstance(feature_data, dict):
            continue
        _accept(normalize_street_storage_value(
            feature_data.get('خیابان') or feature_data.get('مکان_خیابان')
        ))

    ordered = sorted(names)
    return ordered[offset: offset + limit]


_CONSULTANT_FILTER_Q = (
    Q(business_type__icontains='مشاور')
    | Q(business_type__icontains='business')
    | Q(business_type__icontains='agency')
)

_ADVERTISER_SIGNAL_FILTER_VALUES = frozenset({
    ADVERTISER_SIGNAL_GENUINE_PERSONAL,
    ADVERTISER_SIGNAL_DISGUISED,
})

_ADVERTISER_SIGNAL_FILTER_ALIASES = {
    'disguised': ADVERTISER_SIGNAL_DISGUISED,
    'مالک واقعی': ADVERTISER_SIGNAL_GENUINE_PERSONAL,
}


def _normalize_consultant_filter(value: str) -> str:
    raw = str(value or '').strip()
    return _ADVERTISER_SIGNAL_FILTER_ALIASES.get(raw, raw)


def needs_advertiser_signal_filter(filters: Dict) -> bool:
    return _normalize_consultant_filter(filters.get('consultant') or '') in _ADVERTISER_SIGNAL_FILTER_VALUES


def apply_advertiser_signal_filter(listings: List, consultant: str) -> List:
    key = _normalize_consultant_filter(consultant)
    if key not in _ADVERTISER_SIGNAL_FILTER_VALUES:
        return listings
    return [
        lst for lst in listings
        if listing_advertiser_signal(lst) == key
    ]


def _advertiser_rank_annotation():
    """۰ = غیرمشاور رسمی، ۱ = مشاور — برای اولویت پیش‌فرض در سایر ستون‌ها."""
    return Case(
        When(advertiser_signal=ADVERTISER_SIGNAL_CONSULTANT, then=Value(1)),
        When(_CONSULTANT_FILTER_Q, then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )


def _advertiser_display_rank_for_listing(listing) -> int:
    """هم‌راستا با برچسب ستون آگهی‌دهنده در جدول."""
    order = {'مالک': 0, 'شخصی': 1, 'مشاور پنهان': 2, 'مشاور': 3}
    short_label = listing_advertiser_display(listing).get('short_label', 'شخصی')
    return order.get(short_label, 1)


def _default_sort_key(listing, default: str):
    field = default.lstrip('-')
    val = getattr(listing, field, None)
    if val is None:
        val = '' if field in ('title', 'neighborhood', 'business_type') else 0
    if default.startswith('-') and isinstance(val, (int, float)):
        return -val
    if isinstance(val, str):
        return val.lower()
    return val


def _sort_queryset_by_advertiser_display(qs: QuerySet, sort: str, default: str) -> QuerySet:
    """مرتب‌سازی با سیگنال محاسبه‌شده از متن — هم‌راستا با نمایش جدول."""
    reverse = sort.startswith('-')
    pks = list(qs.values_list('pk', flat=True))
    if not pks:
        return qs

    rows = list(qs.model.objects.filter(pk__in=pks))

    def sort_key(lst):
        rank = _advertiser_display_rank_for_listing(lst)
        if reverse:
            rank = -rank
        return (rank, _default_sort_key(lst, default), lst.pk)

    rows.sort(key=sort_key)
    whens = [When(pk=row.pk, then=Value(idx)) for idx, row in enumerate(rows)]
    return qs.model.objects.filter(pk__in=[row.pk for row in rows]).annotate(
        _advertiser_display_order=Case(
            *whens,
            default=Value(len(rows)),
            output_field=IntegerField(),
        )
    ).order_by('_advertiser_display_order')


def sort_queryset(qs: QuerySet, sort: str, default: str) -> QuerySet:
    allowed = {
        'price', '-price', 'deposit', '-deposit', 'rent', '-rent',
        'area', '-area', 'title', '-title', 'neighborhood', '-neighborhood',
        'rooms', '-rooms', 'business_type', '-business_type',
        'created_at', '-created_at', 'published_at', '-published_at',
    }
    if sort not in allowed:
        sort = default

    field = sort.lstrip('-')
    if field == 'published_at':
        if sort.startswith('-'):
            return qs.order_by(F('published_at').desc(nulls_last=True), '-pk')
        return qs.order_by(F('published_at').asc(nulls_first=True), 'pk')

    qs = qs.annotate(_advertiser_rank=_advertiser_rank_annotation())
    if field == 'business_type':
        return _sort_queryset_by_advertiser_display(qs, sort, default)
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


_BASIC_FILTER_KEYS = frozenset({
    'q', 'neighborhood', 'street', 'consultant', 'sort', 'page', 'filters_open',
})


def advanced_filter_count(filters: Dict) -> int:
    """تعداد فیلترهای داخل پنل بازشونده (غیر از جستجو و فیلترهای ریل اصلی)."""
    n = 0
    for k, v in filters.items():
        if k in _BASIC_FILTER_KEYS:
            continue
        if v not in ('', None, False):
            n += 1
    return n
