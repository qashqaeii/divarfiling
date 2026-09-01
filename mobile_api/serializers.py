"""سریالایزرهای dict برای API موبایل."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from mobile_api.activity_types import workspace_type_to_api
from workspace.models import (
    CRMDeal, CRMProperty, Customer, CustomerActivity, CustomerDocument,
    CustomerListing, Dataset, Listing, PropertyContact, Reminder,
)
from workspace.services.features import (
    extract_listing_features,
    parse_rooms_from_text,
    parse_rooms_value,
)
from workspace.services.listing_features import build_listing_feature_profile, feature_highlights_for_listing
from workspace.services.crm_match_notifications import is_match_eligible
from workspace.services.advertiser_signal import (
    advertiser_signal_label,
    listing_advertiser_display,
    listing_advertiser_signal,
)
from workspace.services.listing_edit import (
    address_from_listing,
    district_from_listing,
    feature_fields_for_edit,
    listing_is_vacant,
    vacancy_date_from_listing,
    owner_name_from_listing,
    owner_phone_from_listing,
    tenant_name_from_listing,
    tenant_phone_from_listing,
)
from workspace.services.columns import _parse_images
from workspace.services.property_images import deduplicate_divar_image_urls, normalize_external_image_url

_FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
_EMPTY_DATA_VALUES = frozenset({'', '-', '—', 'nan', 'none', 'null'})


def _data_value(data: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text.lower() in _EMPTY_DATA_VALUES:
            continue
        return text
    return None


def _rooms_to_api_int(rooms: Optional[str]) -> Optional[int]:
    if not rooms:
        return None
    normalized = parse_rooms_value(rooms)
    if normalized == 'بدون اتاق':
        return 0
    if normalized.isdigit():
        return int(normalized)
    return None


def _parse_floor_from_text(text: str) -> str:
    if not text:
        return ''
    translated = text.translate(_FA_DIGITS)
    match = re.search(r'طبقه\s*(\d+)', translated)
    if match:
        return match.group(1)
    match = re.search(r'(\d+)\s*از\s*(\d+)', translated)
    if match:
        return match.group(1)
    return ''


def _non_empty_spec(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _EMPTY_DATA_VALUES:
        return None
    return text.translate(_FA_DIGITS)


def _listing_specs(lst: Listing) -> Dict[str, Any]:
    """اتاق، طبقه، سال ساخت — با fallback از data، عنوان و توضیحات."""
    data = lst.data or {}
    feat = extract_listing_features(lst)

    rooms_raw = (
        parse_rooms_value(lst.rooms)
        or _non_empty_spec(feat.get('rooms'))
        or _data_value(data, 'اتاق', 'تعداد اتاق', 'rooms')
        or parse_rooms_from_text(lst.title or '')
        or parse_rooms_from_text(lst.description or '')
        or parse_rooms_from_text(_data_value(data, 'توضیحات', 'description') or '')
        or parse_rooms_from_text(_data_value(data, 'زیرعنوان') or '')
    )

    floor = (
        _non_empty_spec(feat.get('floor'))
        or _data_value(data, 'طبقه', 'floor')
        or _parse_floor_from_text(lst.title or '')
        or _parse_floor_from_text(lst.description or '')
        or _parse_floor_from_text(_data_value(data, 'توضیحات', 'description') or '')
        or _parse_floor_from_text(_data_value(data, 'زیرعنوان') or '')
    )
    if floor:
        floor = floor.translate(_FA_DIGITS)

    total_floors = _data_value(data, 'تعداد کل طبقات ساختمان', 'total_floors')
    if not total_floors:
        combined = ' '.join(filter(None, [
            _data_value(data, 'زیرعنوان') or '',
            lst.description or '',
        ]))
        match = re.search(r'(\d+)\s*از\s*(\d+)', combined.translate(_FA_DIGITS))
        if match:
            total_floors = match.group(2)
    if total_floors:
        total_floors = total_floors.translate(_FA_DIGITS)

    build_year = feat.get('build_year')
    year_built = (
        str(build_year) if build_year else None
    ) or _data_value(data, 'سال ساخت', 'ساخت', 'year_built', 'construction_year')

    return {
        'rooms_val': _rooms_to_api_int(rooms_raw),
        'floor': floor or None,
        'total_floors': total_floors or None,
        'year_built': year_built,
    }


_CORE_AMENITY_API_KEYS = {
    'پارکینگ': 'has_parking',
    'انباری': 'has_storage',
    'آسانسور': 'has_elevator',
}

_EXTRA_AMENITY_FEAT_KEYS = (
    ('balcony', 'has_balcony'),
    ('lobby', 'has_lobby'),
    ('pool', 'has_pool'),
    ('roof_garden', 'has_roof_garden'),
    ('jacuzzi', 'has_jacuzzi'),
    ('gym', 'has_gym'),
)


def _listing_amenity_fields(lst: Listing) -> Dict[str, Any]:
    """وضعیت واحد و امکانات اصلی — همان منطق پلتفرم وب."""
    feat = extract_listing_features(lst)
    profile = build_listing_feature_profile(lst, base_feat=feat)
    data = lst.data or {}
    result: Dict[str, Any] = {
        'has_parking': None,
        'has_storage': None,
        'has_elevator': None,
        'has_balcony': feat.get('balcony'),
        'has_lobby': feat.get('lobby'),
        'has_pool': feat.get('pool'),
        'has_roof_garden': feat.get('roof_garden'),
        'has_jacuzzi': feat.get('jacuzzi'),
        'has_gym': feat.get('gym'),
        'unit_status': _data_value(data, 'وضعیت واحد', 'وضعیت سکونت'),
    }
    for item in profile.get('core') or []:
        api_key = _CORE_AMENITY_API_KEYS.get(str(item.get('key') or '').strip())
        if not api_key:
            continue
        state = item.get('state') or 'unknown'
        if state == 'yes':
            result[api_key] = True
        elif state == 'no':
            result[api_key] = False
    for feat_key, api_key in _EXTRA_AMENITY_FEAT_KEYS:
        if result.get(api_key) is None:
            result[api_key] = feat.get(feat_key)
    return result


def _listing_image_urls(lst: Listing) -> List[str]:
    images: List[str] = []
    for img in (lst.images or []):
        url = normalize_external_image_url(img if isinstance(img, str) else str(img))
        if url:
            images.append(url)
    if not images:
        data = lst.data or {}
        for key in ('رسانه_تصاویر', 'images', 'تصاویر'):
            raw = data.get(key)
            if raw:
                images = _parse_images(raw)
                break
    return deduplicate_divar_image_urls(images)


def _absolute_media_url(url: str, request=None) -> str:
    """تبدیل /media/... به URL مطلق برای کلاینت موبایل."""
    value = str(url or '').strip()
    if not value:
        return ''
    if value.startswith('/media/'):
        if request is not None:
            try:
                return request.build_absolute_uri(value)
            except Exception:
                pass
        return f'https://divarfiling.ir{value}'
    return value


def _property_image_urls(raw_images, *, request=None, limit=None):
    urls: List[str] = []
    for img in raw_images or []:
        url = normalize_external_image_url(img if isinstance(img, str) else str(img))
        if not url:
            continue
        url = _absolute_media_url(url, request=request)
        if url:
            urls.append(url)
    urls = deduplicate_divar_image_urls(urls)
    if limit is not None:
        return urls[: max(0, int(limit))]
    return urls


def _dataset_cover_urls(ds: Dataset, *, limit: int = 8) -> List[str]:
    return resolve_dataset_covers_batch([ds.pk], limit_per_dataset=limit).get(ds.pk, [])


def _dataset_thumbnail(ds: Dataset) -> str:
    urls = _dataset_cover_urls(ds, limit=1)
    return urls[0] if urls else ''


def resolve_dataset_covers_batch(
    dataset_ids: List[int],
    *,
    limit_per_dataset: int = 8,
) -> Dict[int, List[str]]:
    """اولین URL تصویر از چند آگهی مختلف هر دیتاست — برای fallback وقتی لینک دیوار منقضی شده."""
    ids = [int(i) for i in dataset_ids if i]
    if not ids:
        return {}

    covers: Dict[int, List[str]] = {did: [] for did in ids}
    seen: Dict[int, set] = {did: set() for did in ids}

    rows = (
        Listing.objects.filter(dataset_id__in=ids)
        .order_by('dataset_id', 'id')
        .only('dataset_id', 'images', 'data')
    )
    for lst in rows:
        did = lst.dataset_id
        if did not in covers or len(covers[did]) >= limit_per_dataset:
            continue
        listing_urls = _listing_image_urls(lst)
        if not listing_urls:
            continue
        first = listing_urls[0]
        dedupe_key = first.split('?', 1)[0].rstrip('/')
        if dedupe_key in seen[did]:
            continue
        seen[did].add(dedupe_key)
        covers[did].append(first)

    return covers


def user_to_dict(user, request=None) -> Dict[str, Any]:
    agency_name = ''
    avatar_url = ''
    profile = getattr(user, 'profile', None)
    if profile is not None:
        agency_name = getattr(profile, 'company_name', '') or ''
        avatar = getattr(profile, 'avatar', None)
        if avatar:
            try:
                url = avatar.url
                avatar_url = request.build_absolute_uri(url) if request else url
            except Exception:
                avatar_url = ''
    full_name = user.get_full_name() or user.username or ''
    return {
        'id': user.pk,
        'full_name': full_name.strip() or str(user.phone or user.username),
        'phone': user.phone or '',
        'agency_name': agency_name,
        'phone_verified': bool(getattr(user, 'phone_verified', False)),
        'avatar_url': avatar_url,
    }


def contact_to_dict(c: Customer) -> Dict[str, Any]:
    budget = c.budget_max or c.budget_min
    return {
        'id': c.pk,
        'full_name': c.name,
        'phone': c.phone or '',
        'customer_type': c.customer_type,
        'status': c.status,
        'source': c.source or '',
        'priority': c.priority,
        'budget': budget,
        'budget_min': c.budget_min,
        'budget_max': c.budget_max,
        'deposit_min': c.deposit_min,
        'deposit_max': c.deposit_max,
        'rent_min': c.rent_min,
        'rent_max': c.rent_max,
        'property_type': c.property_type or '',
        'min_area': c.min_area,
        'max_area': c.max_area,
        'rooms': c.rooms or '',
        'rooms_min': c.rooms_min,
        'rooms_max': c.rooms_max,
        'year_min': c.year_min,
        'year_max': c.year_max,
        'floor_min': c.floor_min,
        'floor_max': c.floor_max,
        'want_parking': bool(c.want_parking),
        'want_storage': bool(c.want_storage),
        'want_elevator': bool(c.want_elevator),
        'areas': c.areas or '',
        'notes': c.notes or '',
        'address': c.city or '',
        'city': c.city or '',
        'district': c.district or '',
        'phone_alt': c.phone_alt or '',
        'email': getattr(c, 'email', '') or '',
        'job': getattr(c, 'job', '') or '',
        'company_name': getattr(c, 'company_name', '') or '',
        'national_id': getattr(c, 'national_id', '') or '',
        'lease_deadline': c.lease_deadline.isoformat() if getattr(c, 'lease_deadline', None) else None,
        'latitude': None,
        'longitude': None,
        'next_follow_up_at': c.next_follow_up.isoformat() if c.next_follow_up else None,
        'updated_at': c.updated_at.isoformat() if c.updated_at else None,
        'created_at': c.created_at.isoformat() if c.created_at else None,
        'match_eligible': is_match_eligible(c),
        'builder_buy_property_types': c.builder_buy_property_types or '',
        'builder_buy_budget_min': c.builder_buy_budget_min,
        'builder_buy_budget_max': c.builder_buy_budget_max,
        'builder_buy_areas': c.builder_buy_areas or '',
        'builder_buy_min_area': c.builder_buy_min_area,
        'builder_buy_max_area': c.builder_buy_max_area,
        'is_builder': c.customer_type == 'سازنده',
        'social_links': getattr(c, 'social_links', None) or {},
        'active_channels': getattr(c, 'active_channels', None) or [],
        'matching_tolerance_percent': c.matching_tolerance_percent,
    }


def dataset_to_dict(
    ds: Dataset,
    *,
    cover_urls: Optional[List[str]] = None,
    include_stats: bool = False,
) -> Dict[str, Any]:
    source = (ds.metadata or {}).get('source', 'windows')
    if (ds.metadata or {}).get('mobile_extraction'):
        source = 'mobile'
    meta = ds.metadata or {}
    filters = meta.get('filters') if isinstance(meta.get('filters'), dict) else {}
    category = str(
        filters.get('category_name') or filters.get('category') or meta.get('category') or ''
    ).strip()
    thumb_urls = cover_urls if cover_urls is not None else _dataset_cover_urls(ds)
    item_count = ds.listings.count() if include_stats else (ds.row_count if ds.row_count is not None else 0)
    payload: Dict[str, Any] = {
        'id': str(ds.pk),
        'name': ds.name,
        'source': source,
        'transaction_type': ds.transaction_type or '',
        'subcategory': ds.subcategory or '',
        'category': category,
        'city': ds.city or '',
        'district': ds.district or '',
        'item_count': item_count,
        'thumbnail_url': thumb_urls[0] if thumb_urls else '',
        'thumbnail_urls': thumb_urls,
        'created_at': ds.created_at.isoformat() if ds.created_at else None,
        'updated_at': ds.updated_at.isoformat() if ds.updated_at else None,
        'last_opened_at': ds.last_opened_at.isoformat() if ds.last_opened_at else None,
        'original_filename': ds.original_filename or '',
        'file_format': ds.file_format or '',
    }
    if include_stats:
        from workspace.services.advertiser_signal import count_listings_by_advertiser_display

        adv_counts = count_listings_by_advertiser_display(ds.listings.all())
        payload.update({
            'genuine_personal_count': adv_counts['genuine_personal'],
            'disguised_consultant_count': adv_counts['disguised_consultant'],
            'consultant_count': adv_counts['consultant'],
            'personal_other_count': adv_counts['personal_other'],
        })
    return payload


def listing_to_dict(lst: Listing, *, personal_status: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    image_urls = _listing_image_urls(lst)
    thumb = image_urls[0] if image_urls else ''
    adv_display = listing_advertiser_display(lst)
    adv = adv_display['label']
    signal = listing_advertiser_signal(lst)
    specs = _listing_specs(lst)
    transaction_type = 'اجاره' if (lst.rent or lst.deposit) else ('فروش' if lst.price else '')

    payload = {
        'token': lst.token,
        'title': lst.title or '',
        'price': lst.price,
        'deposit': lst.deposit,
        'rent': lst.rent,
        'area': int(lst.area) if lst.area else None,
        'rooms': specs['rooms_val'],
        'district': lst.neighborhood or '',
        'city': lst.city or '',
        'latitude': lst.latitude,
        'longitude': lst.longitude,
        'thumbnail_url': thumb,
        'share_link': lst.link or '',
        'advertiser_type': adv,
        'advertiser_signal': signal,
        'advertiser_signal_label': advertiser_signal_label(signal),
        'business_type': lst.business_type or '',
        'scraped_at': lst.created_at.isoformat() if lst.created_at else None,
        'dataset_id': str(lst.dataset_id) if lst.dataset_id else None,
        'price_per_sqm': _calc_price_per_sqm(lst),
        'year_built': specs['year_built'],
        'floor': specs['floor'],
        'transaction_type': transaction_type,
        'feature_highlights': feature_highlights_for_listing(lst, limit=5),
        **_listing_amenity_fields(lst),
    }
    if personal_status is not None:
        payload.update(personal_status)
    return payload


def _finite_number(value: Any) -> Optional[float]:
    if value is None or value == '':
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _listing_market_to_dict(lst: Listing) -> Optional[Dict[str, Any]]:
    """مقایسه قیمت آگهی با میانه فایل — همان منطق صفحه جزئیات میزکار."""
    dataset = getattr(lst, 'dataset', None)
    if dataset is None:
        return None
    try:
        from workspace.services.analyzer import benchmark_listing, listings_to_dataframe
        from workspace.services.display import market_tier_from_score
        from workspace.services.formatting import format_toman

        listings_qs = dataset.listings.all()
        if listings_qs.count() < 2:
            return None
        df = listings_to_dataframe(listings_qs)
        if df is None or len(df) < 2:
            return None
        bench = benchmark_listing(lst, df, dataset.transaction_type or '')
        listing_metric = _finite_number(bench.get('listing_metric'))
        market_median = _finite_number(bench.get('market_median'))
        score = _finite_number(bench.get('value_score'))
        if score is None and listing_metric is not None and market_median not in (None, 0):
            score = round((listing_metric - market_median) / market_median * 100, 1)
        if score is None and listing_metric is None and market_median is None:
            return None
        tier = bench.get('market_tier') or ''
        if tier in ('', 'unknown') or score is not None:
            computed = market_tier_from_score(score)
            if computed != 'unknown':
                tier = computed
        short = {
            'under': 'زیر بازار',
            'over': 'بالای بازار',
            'fair': 'متعادل',
        }.get(tier, '')
        if not short:
            return None
        diff_amount = _finite_number(bench.get('diff_amount'))
        if diff_amount is None and listing_metric is not None and market_median is not None:
            diff_amount = listing_metric - market_median
        per_sqm = (bench.get('metric') or 'price_per_sqm') == 'price_per_sqm'
        diff_amount_fmt = bench.get('diff_amount_fmt') or ''
        if not diff_amount_fmt and diff_amount is not None:
            diff_amount_fmt = format_toman(abs(diff_amount), per_sqm=per_sqm)
        return {
            'value_score': score,
            'market_tier': tier,
            'short_verdict': short,
            'verdict': bench.get('verdict') or short,
            'label': bench.get('label') or '',
            'metric': bench.get('metric') or '',
            'listing_metric': listing_metric,
            'listing_metric_fmt': bench.get('price_per_sqm_fmt') or '',
            'market_median': market_median,
            'market_median_fmt': bench.get('market_median_fmt') or '',
            'diff_pct': score,
            'diff_amount': round(diff_amount, 0) if diff_amount is not None else None,
            'diff_amount_fmt': diff_amount_fmt,
            'sample_count': int(bench.get('sample_count') or len(df)),
            'note': bench.get('note') or '',
        }
    except Exception:
        logger.exception('listing market benchmark failed token=%s', getattr(lst, 'token', ''))
        return None


def listing_detail_to_dict(lst: Listing, *, user=None, request=None, personal_status: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = listing_to_dict(lst, personal_status=personal_status)
    data = lst.data or {}
    images = _listing_image_urls(lst)
    specs = _listing_specs(lst)
    feat = extract_listing_features(lst)
    feature_profile = build_listing_feature_profile(lst, base_feat=feat)
    listing_highlights = feature_highlights_for_listing(lst, limit=12)

    base.update({
        'description': lst.description or _data_value(data, 'توضیحات', 'description') or '',
        'images': images,
        'year_built': specs['year_built'],
        'floor': specs['floor'],
        'total_floors': specs['total_floors'],
        'business_type': lst.business_type or '',
        'owner_phone': owner_phone_from_listing(lst),
        'owner_name': owner_name_from_listing(lst),
        'tenant_phone': tenant_phone_from_listing(lst),
        'tenant_name': tenant_name_from_listing(lst),
        'vacancy_date': vacancy_date_from_listing(lst),
        'is_vacant': listing_is_vacant(lst),
        'address': address_from_listing(lst),
        'neighborhood': lst.neighborhood or '',
        'region': district_from_listing(lst),
        'link': lst.link or '',
        'published_at': lst.published_at.isoformat() if lst.published_at else None,
        'expires_at': lst.expires_at.isoformat() if lst.expires_at else None,
        'is_expired': lst.is_expired,
        'price_per_sqm': _calc_price_per_sqm(lst),
        'feature_profile': feature_profile,
        'listing_highlights': listing_highlights,
        'feature_fields': feature_fields_for_edit(lst),
        **_listing_amenity_fields(lst),
    })
    market = _listing_market_to_dict(lst)
    if market:
        base['market'] = market
        base['value_score'] = market.get('value_score')
        base['market_tier'] = market.get('market_tier')
        base['verdict'] = market.get('short_verdict')
    if user is not None:
        from workspace.services.listing_public_share import (
            get_listing_share,
            listing_public_share_to_dict,
        )
        share = get_listing_share(user, lst)
        base['public_share'] = listing_public_share_to_dict(share, request) if share else None
        base['meta'] = listing_meta_to_dict(user, lst.token)
        base['linked_contacts'] = listing_linked_contacts_to_dict(user, lst.token, listing=lst)
    else:
        from workspace.constants import LISTING_TAGS
        base['meta'] = {
            'note': '',
            'tag': '',
            'is_favorite': False,
            'updated_at': None,
            'tag_options': [tag for tag in LISTING_TAGS if tag],
        }
        base['linked_contacts'] = []
    return base


def listing_meta_to_dict(user, token: str) -> Dict[str, Any]:
    from workspace.constants import LISTING_TAGS
    from workspace.models import ListingMeta

    meta = ListingMeta.objects.filter(user=user, token=token).first()
    return {
        'note': (meta.note if meta else '') or '',
        'tag': (meta.tag if meta else '') or '',
        'is_favorite': bool(meta.is_favorite) if meta else False,
        'updated_at': meta.updated_at.isoformat() if meta and meta.updated_at else None,
        'tag_options': [tag for tag in LISTING_TAGS if tag],
    }


def listing_linked_contacts_to_dict(user, token: str, listing: Optional[Listing] = None) -> List[Dict[str, Any]]:
    from accounts.phone_utils import normalize_phone
    from workspace.services.crm import customers_linked_to_token

    owner_phone = normalize_phone(owner_phone_from_listing(listing)) if listing is not None else ''
    tenant_phone = normalize_phone(tenant_phone_from_listing(listing)) if listing is not None else ''
    vacant = listing_is_vacant(listing) if listing is not None else False

    rows: List[Dict[str, Any]] = []
    for link in customers_linked_to_token(user, token):
        customer = link.customer
        phone = customer.phone or ''
        phone_key = normalize_phone(phone)
        role = link.role or ''
        if owner_phone and phone_key == owner_phone:
            role = 'مالک'
        elif tenant_phone and not vacant and phone_key == tenant_phone:
            role = 'مستاجر'
        rows.append({
            'id': link.pk,
            'customer_id': customer.pk,
            'full_name': customer.name or '',
            'phone': phone,
            'role': role,
            'deal_type': link.deal_type or '',
            'notes': link.notes or '',
            'status': customer.status or '',
            'updated_at': link.updated_at.isoformat() if link.updated_at else None,
        })
    return rows


def _calc_price_per_sqm(lst: Listing) -> Optional[int]:
    if lst.price and lst.area and lst.area > 0:
        return int(lst.price / lst.area)
    return None


def activity_to_dict(a: CustomerActivity) -> Dict[str, Any]:
    data = {
        'id': a.pk,
        'activity_type': workspace_type_to_api(a.activity_type),
        'activity_type_label': a.activity_type,
        'title': a.title or '',
        'content': a.content or '',
        'token': a.token or '',
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }
    customer = getattr(a, 'customer', None)
    if customer is not None:
        data['customer_id'] = customer.pk
        data['customer_name'] = customer.name or ''
    return data


def reminder_to_dict(r: Reminder) -> Dict[str, Any]:
    contact_name = ''
    if r.customer_id and getattr(r, 'customer', None) is not None:
        contact_name = getattr(r.customer, 'name', '') or ''
    return {
        'id': r.pk,
        'title': r.title,
        'note': r.note or '',
        'contact_id': r.customer_id,
        'contact_name': contact_name,
        'due_at': r.due_at.isoformat() if r.due_at else None,
        'done': r.is_done,
        'token': r.token or '',
        'recurrence': r.recurrence or '',
        'series_id': r.series_id,
    }


def linked_listing_to_dict(cl: CustomerListing) -> Dict[str, Any]:
    return {
        'id': cl.pk,
        'token': cl.token,
        'title': cl.title or '',
        'price': cl.price or '',
        'area': cl.area or '',
        'link': cl.link or '',
        'role': cl.role,
        'deal_type': cl.deal_type,
        'notes': cl.notes or '',
        'created_at': cl.created_at.isoformat() if cl.created_at else None,
    }


def document_to_dict(doc: CustomerDocument, *, request=None) -> Dict[str, Any]:
    file_url = ''
    if doc.file:
        try:
            file_url = request.build_absolute_uri(doc.file.url) if request else doc.file.url
        except Exception:
            file_url = doc.file.url or ''
    return {
        'id': doc.pk,
        'title': doc.title,
        'doc_type': doc.doc_type or '',
        'file_url': file_url,
        'uploaded_at': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
    }


def deal_to_dict(d: CRMDeal, *, detailed: bool = False, stage_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from workspace.services.crm_deals import deal_stage_age_days, is_deal_stale

    meta = stage_meta if stage_meta is not None else None
    if meta is None:
        from workspace.services.crm_deal_stages import stage_def_for
        meta = stage_def_for(d.user, d.stage) or {}
    days_in_stage = deal_stage_age_days(d)
    from workspace.services.crm_deal_finance import serialize_deal_finance

    finance = serialize_deal_finance(d)
    data = {
        'id': d.pk,
        'title': d.title,
        'stage': d.stage,
        'amount': d.value,
        'listing_token': d.listing_token or '',
        'property_id': d.property_id,
        'customer_id': d.customer_id,
        'probability': d.probability,
        'commission_rate': finance['commission_rate'],
        'commission_amount': finance['commission_amount'],
        'deal_kind': finance['deal_kind'],
        'deal_kind_label': finance['deal_kind_label'],
        'commission_mode': finance['commission_mode'],
        'buyer_commission_rate': finance['buyer_commission_rate'],
        'seller_commission_rate': finance['seller_commission_rate'],
        'buyer_commission_amount': finance['buyer_commission_amount'],
        'seller_commission_amount': finance['seller_commission_amount'],
        'advisor_share_percent': finance['advisor_share_percent'],
        'agency_share_percent': finance['agency_share_percent'],
        'advisor_commission': finance['advisor_commission'],
        'agency_commission': finance['agency_commission'],
        'deal_costs': finance['deal_costs'],
        'received_amount': finance['received_amount'],
        'outstanding': finance['outstanding'],
        'net_advisor': finance['net_advisor'],
        'payout_status': finance['payout_status'],
        'payout_status_label': finance['payout_status_label'],
        'payout_notes': finance['payout_notes'],
        'notes': d.notes or '',
        'updated_at': d.updated_at.isoformat() if d.updated_at else None,
        'customer_name': d.customer.name if getattr(d, 'customer', None) else '',
        'property_title': d.property.title if getattr(d, 'property', None) else '',
        'expected_close_date': d.expected_close_date.isoformat() if d.expected_close_date else None,
        'is_stale': is_deal_stale(d, meta),
        'days_in_stage': days_in_stage,
        'stage_color': meta.get('color') or '',
        'stage_bg': meta.get('bg') or '',
        'stage_icon': meta.get('icon') or '',
        'rot_days': int(meta.get('rot_days') or 0),
    }
    if detailed:
        data.update({
            'checklist': d.checklist or [],
            'lost_reason': d.lost_reason or '',
            'contract_number': d.contract_number or '',
            'contract_amount': d.contract_amount,
            'stage_description': meta.get('description') or '',
            'stage_changed_at': d.stage_changed_at.isoformat() if d.stage_changed_at else None,
        })
    return data


def property_to_dict(p: CRMProperty, *, detailed: bool = False, request=None) -> Dict[str, Any]:
    # لیست موبایل هم باید کاور داشته باشد؛ قبلاً فقط detailed تصاویر می‌فرستاد.
    images = _property_image_urls(
        p.images or [],
        request=request,
        limit=None if detailed else 6,
    )
    data = {
        'id': p.pk,
        'title': p.title,
        'deal_mode': p.deal_mode,
        'transaction_status': p.transaction_status,
        'property_type': p.property_type,
        'publish_status': p.publish_status,
        'city': p.city or '',
        'district': p.district or '',
        'neighborhood': p.neighborhood or '',
        'sale_price': p.sale_price,
        'rent': p.monthly_rent,
        'deposit': p.deposit,
        'area': p.area,
        'rooms': p.rooms or '',
        'token': p.token or '',
        'link': p.link or '',
        'phone': p.phone or '',
        'owner_name': p.owner_name or '',
        'business_type': p.business_type or '',
        'images': images,
        'thumbnail_url': images[0] if images else '',
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None,
    }
    from workspace.services.crm_property_folders import folders_for_property
    data['folders'] = folders_for_property(p)
    if detailed:
        from workspace.services.property_features import vacancy_date_from_property
        data.update({
            'address': p.address or '',
            'floor': p.floor,
            'total_floors': p.total_floors,
            'build_year': p.build_year,
            'has_parking': p.has_parking,
            'has_storage': p.has_storage,
            'has_elevator': p.has_elevator,
            'is_vacant': p.is_vacant,
            'tenant_name': p.tenant_name or '',
            'tenant_phone': p.tenant_phone or '',
            'vacancy_date': vacancy_date_from_property(p),
            'amenities': p.amenities or '',
            'notes': p.notes or '',
            'latitude': p.latitude,
            'longitude': p.longitude,
            'feature_data': dict(p.feature_data or {}),
        })
    return data


def property_contact_to_dict(link: PropertyContact) -> Dict[str, Any]:
    customer = link.customer
    return {
        'id': link.pk,
        'customer_id': customer.pk,
        'customer_name': customer.name or '',
        'phone': customer.phone or '',
        'status': customer.status or '',
        'role': link.role or '',
        'deal_type': link.deal_type or '',
        'interest_level': link.interest_level or '',
        'is_primary': link.is_primary,
        'notes': link.notes or '',
        'created_at': link.created_at.isoformat() if link.created_at else None,
    }


def property_detail_to_dict(
    prop: CRMProperty,
    *,
    contacts: Optional[List[PropertyContact]] = None,
    activities: Optional[List[CustomerActivity]] = None,
    documents: Optional[List[CustomerDocument]] = None,
    feature_profile: Optional[Dict[str, Any]] = None,
    listing_highlights: Optional[List[str]] = None,
    can_edit: bool = True,
    mask_sensitive: bool = False,
    request=None,
) -> Dict[str, Any]:
    property_data = property_to_dict(prop, detailed=True, request=request)
    if mask_sensitive:
        property_data['address'] = ''
        property_data['notes'] = ''
        property_data['neighborhood'] = ''
    from workspace.services.listing_map import parse_map_coordinates
    from workspace.services.nearby_pois import nearby_pois_page_context
    from workspace.services.public_share_common import build_map_navigation

    lat, lng, _ = parse_map_coordinates(prop.latitude, prop.longitude)
    map_navigation = build_map_navigation(lat, lng) if lat is not None and lng is not None else None
    return {
        'property': property_data,
        'contacts': [] if mask_sensitive else [property_contact_to_dict(c) for c in (contacts or [])],
        'activities': [] if mask_sensitive else [activity_to_dict(a) for a in (activities or [])],
        'documents': [] if mask_sensitive else [document_to_dict(d, request=request) for d in (documents or [])],
        'feature_profile': feature_profile or {'has_details': False, 'core': [], 'groups': []},
        'listing_highlights': listing_highlights or [],
        'can_edit': can_edit,
        'mask_sensitive': mask_sensitive,
        'contact_count': 0 if mask_sensitive else len(contacts or []),
        'map_navigation': map_navigation,
        'nearby_pois_ctx': nearby_pois_page_context(prop),
    }


def contact_detail_to_dict(
    c: Customer,
    *,
    activities: Optional[List[CustomerActivity]] = None,
    reminders: Optional[List[Reminder]] = None,
    linked_listings: Optional[List[CustomerListing]] = None,
    deals: Optional[List[CRMDeal]] = None,
    properties: Optional[List[CRMProperty]] = None,
    documents: Optional[List[CustomerDocument]] = None,
    request=None,
) -> Dict[str, Any]:
    return {
        'contact': contact_to_dict(c),
        'activities': [activity_to_dict(a) for a in (activities or [])],
        'reminders': [reminder_to_dict(r) for r in (reminders or [])],
        'linked_listings': [linked_listing_to_dict(cl) for cl in (linked_listings or [])],
        'deals': [deal_to_dict(d) for d in (deals or [])],
        'properties': [property_to_dict(p) for p in (properties or [])],
        'documents': [document_to_dict(d, request=request) for d in (documents or [])],
    }


def schedule_to_dict(s) -> Dict[str, Any]:
    return {
        'id': s.pk,
        'title': s.title,
        'is_enabled': s.is_enabled,
        'interval_hours': s.interval_hours,
        'filters': s.filters or {},
        'max_items': s.max_items,
        'next_run_at': s.next_run_at.isoformat() if s.next_run_at else None,
        'last_run_at': s.last_run_at.isoformat() if s.last_run_at else None,
        'last_status': s.last_status,
        'last_error': s.last_error or '',
        'last_dataset_id': str(s.last_dataset_id) if s.last_dataset_id else '',
        'run_count': s.run_count,
        'consecutive_failures': s.consecutive_failures,
        'primary_device_id': s.primary_device_id or '',
        'created_at': s.created_at.isoformat() if s.created_at else None,
        'updated_at': s.updated_at.isoformat() if s.updated_at else None,
    }


def run_to_dict(r) -> Dict[str, Any]:
    return {
        'id': r.pk,
        'schedule_id': r.schedule_id,
        'status': r.status,
        'trigger': r.trigger,
        'filters': r.filters_snapshot or {},
        'dataset_id': str(r.dataset_id) if r.dataset_id else '',
        'ingested_count': r.ingested_count,
        'created_count': r.created_count,
        'updated_count': r.updated_count,
        'skipped_count': r.skipped_count,
        'error': r.error or '',
        'started_at': r.started_at.isoformat() if r.started_at else None,
        'finished_at': r.finished_at.isoformat() if r.finished_at else None,
    }
