"""وارد کردن فایل‌های Excel/CSV/JSON به workspace."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

import pandas as pd
from django.db import transaction
from django.utils import timezone

from workspace.models import Dataset, Listing, PriceHistory
from workspace.services.columns import detect_metadata, row_to_listing_fields
from workspace.services.ingest_mode import resolve_ingest_mode, should_prune_stale_listings
from workspace.services.listing_personal_status import DIVAR_SOURCE_PLATFORM
from workspace.services.listing_suppression import get_suppressed_external_ids
from workspace.services.divar_listing_datetime import (
    has_explicit_publish_in_export_data,
    merge_listing_schedule_data,
)
from workspace.services.price_history import load_latest_snapshots, should_record_price
from workspace.services.folder_import import (
    build_dataset_name, build_file_identity, dataset_path_info_from_record, locations_match,
    merge_path_into_dataset_meta, normalize_file_identity, normalize_source_path,
    parse_tx_subcategory, subcategory_match, transaction_match,
)

BATCH_SIZE = 500


@dataclass
class ImportResult:
    dataset: Dataset
    added_count: int
    updated_count: int
    skipped_count: int
    suppressed_count: int
    is_update: bool
    reactivated: bool
    total_in_file: int


def read_file_to_dataframe(file_path: str, ext: str) -> pd.DataFrame:
    ext = ext.lower()
    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(file_path, engine='openpyxl')
    if ext == '.csv':
        for enc in ('utf-8-sig', 'utf-8', 'cp1256'):
            try:
                return pd.read_csv(file_path, encoding=enc)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(file_path)
    if ext == '.json':
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return pd.DataFrame(data)
        if isinstance(data, dict) and 'items' in data:
            return pd.DataFrame(data['items'])
        return pd.DataFrame([data])
    raise ValueError(f'فرمت پشتیبانی‌نشده: {ext}')


def _norm_identity(val: str) -> str:
    raw = (val or '').strip().lower()
    if not raw:
        return ''
    if '/' in raw:
        return normalize_file_identity(raw)
    return os.path.splitext(raw)[0]


def _identity_lookup_keys(identity: str) -> List[str]:
    norm = _norm_identity(identity)
    keys: Set[str] = set()
    for val in (identity, norm):
        if not val:
            continue
        keys.add(val)
        for ext in ('.xlsx', '.xls', '.csv', '.json'):
            keys.add(f'{val}{ext}')
    return list(keys)


def _norm_loc(val: str) -> str:
    return (val or '').strip().replace('_', ' ')


def _has_folder_path(path_info: dict | None) -> bool:
    return bool(normalize_file_identity((path_info or {}).get('relative_path', '')))


def _filename_tx_matches(ds: Dataset, pi: dict, basename: str) -> bool:
    md = ds.metadata or {}
    return (
        transaction_match(ds.transaction_type, ds.original_filename, pi, basename)
        and subcategory_match(
            getattr(ds, 'subcategory', ''), ds.original_filename, md, pi, basename,
        )
    )


def _bare_upload_location_compatible(ds: Dataset, pi: dict) -> bool:
    """آپلود تکی بدون مسیر پوشه — سازگاری مکان با مجموعهٔ قبلی."""
    pi_dist = _norm_loc(pi.get('district'))
    pi_city = _norm_loc(pi.get('city'))
    ds_dist = _norm_loc(ds.district)
    ds_city = _norm_loc(ds.city)

    if pi_dist and ds_dist:
        return pi_dist == ds_dist
    if pi_dist and not ds_dist:
        return False
    if ds_dist and not pi_dist:
        return False

    if pi_city and ds_city:
        return pi_city == ds_city
    if pi_city and not ds_city:
        return True
    if ds_city and not pi_city:
        return False
    return True


def _bare_reupload_match(
    qs,
    basename: str,
    path_info: dict | None,
) -> Optional[Dataset]:
    """
    آپلود تکی همان نام فایل (بدون مسیر پوشه) — تطبیق با مجموعهٔ قبلی.
    مثال: فایل «اجاره_آپارتمان.xlsx» که قبلاً از مسیر بریانک وارد شده.
    """
    if _has_folder_path(path_info):
        return None

    pi = path_info or {}
    candidates = [
        ds for ds in qs.filter(original_filename=basename)
        if _filename_tx_matches(ds, pi, basename)
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        if _bare_upload_location_compatible(candidates[0], pi):
            return candidates[0]
        return None

    pi_dist = _norm_loc(pi.get('district'))
    pi_city = _norm_loc(pi.get('city'))
    if pi_dist:
        by_dist = [ds for ds in candidates if _norm_loc(ds.district) == pi_dist]
        if len(by_dist) == 1:
            return by_dist[0]

    if pi_city:
        by_city = [ds for ds in candidates if _norm_loc(ds.city) == pi_city]
        if len(by_city) == 1:
            return by_city[0]

    stem = os.path.splitext(basename)[0].lower()
    by_stem: List[Dataset] = []
    for ds in candidates:
        stored = _norm_identity((ds.metadata or {}).get('file_identity', ''))
        if stored == stem or stored.endswith(f'/{stem}'):
            by_stem.append(ds)
    if len(by_stem) == 1:
        return by_stem[0]

    return None


def _preserve_dataset_location_meta(
    meta: dict,
    path_info: dict,
    dataset: Dataset,
) -> dict:
    """در آپلود تکی، مکان و هویت فایل قبلی حفظ شود."""
    if _has_folder_path(path_info):
        return meta

    out = dict(meta or {})
    old_md = dataset.metadata or {}
    for key in ('province', 'city', 'district', 'transaction_type', 'subcategory'):
        if not out.get(key):
            out[key] = old_md.get(key) or getattr(dataset, key, '') or ''
    for key in ('file_identity', 'source_path'):
        if old_md.get(key):
            out[key] = old_md[key]
    return out


def _match_score(ds: Dataset, path_info: dict, basename: str, identity: str) -> int:
    md = ds.metadata or {}
    pi = path_info or {}
    pi_dist = _norm_loc(pi.get('district'))
    ds_dist = _norm_loc(ds.district)
    stored_id = _norm_identity(md.get('file_identity', ''))
    norm_id = _norm_identity(identity)
    if norm_id and stored_id and stored_id == norm_id:
        return 1000

    pi_path = normalize_file_identity((path_info or {}).get('relative_path', ''))
    ds_path = _norm_identity(md.get('source_path', ''))
    if pi_path and ds_path and pi_path == ds_path:
        return 900

    stem = os.path.splitext(basename)[0].lower()
    if norm_id and stored_id and stored_id != norm_id:
        if stored_id.endswith(stem) and norm_id.endswith(stem):
            loc_ok = locations_match(md, ds.city, ds.district, pi)
            if not loc_ok:
                ds_city = _norm_loc(ds.city)
                pi_city = _norm_loc(pi.get('city'))
                loc_ok = (
                    not pi_dist and not ds_dist
                    and ds_city
                    and (ds_city in norm_id or ds_city in stored_id)
                    and (not pi_city or pi_city == ds_city)
                )
            if (
                loc_ok
                and transaction_match(ds.transaction_type, ds.original_filename, pi, basename)
                and subcategory_match(
                    getattr(ds, 'subcategory', ''), ds.original_filename, md, pi, basename,
                )
            ):
                return 950

    if pi_path and ds_path == stem and pi_path.endswith(stem):
        if _norm_loc((path_info or {}).get('city')) == _norm_loc(ds.city):
            if (
                transaction_match(ds.transaction_type, ds.original_filename, path_info, basename)
                and subcategory_match(
                    getattr(ds, 'subcategory', ''), ds.original_filename, md, path_info, basename,
                )
            ):
                return 880

    score = 0
    if pi_dist and ds_dist and pi_dist != ds_dist:
        return 0

    if locations_match(md, ds.city, ds.district, pi):
        score += 100
    else:
        pi_city = _norm_loc(pi.get('city')) or _norm_loc(pi.get('province'))
        if pi_city and pi_city == _norm_loc(ds.city):
            if pi_dist and not ds_dist:
                return 0
            if ds_dist and not pi_dist:
                return 0
            score += 85

    if ds.original_filename == basename:
        score += 15

    if not transaction_match(ds.transaction_type, ds.original_filename, path_info or {}, basename):
        return 0

    if not subcategory_match(
        getattr(ds, 'subcategory', ''), ds.original_filename, md, path_info or {}, basename,
    ):
        return 0

    if score >= 85:
        score += 20
    return score


def find_existing_dataset(
    user,
    original_filename: str,
    path_info: dict | None = None,
    *,
    strict_identity: bool = False,
) -> Tuple[Optional[Dataset], bool]:
    """
    یافتن مجموعه‌داده قبلی — مسیر یکتا، مکان + نوع معامله.
    strict_identity: فقط هویت فایل / نام فایل؛ بدون ادغام فازی بر اساس محله.
    برمی‌گرداند: (dataset, reactivating).
    """
    basename = os.path.basename(original_filename)
    identity = build_file_identity(path_info, basename)
    pi = path_info or {}

    def _lookup(qs, reactivating: bool) -> Optional[Dataset]:
        norm_incoming = _norm_identity(identity)

        for key in _identity_lookup_keys(identity):
            hit = qs.filter(metadata__file_identity=key).order_by('pk').first()
            if hit and _filename_tx_matches(hit, pi, basename):
                return hit

        source_path = normalize_file_identity(pi.get('relative_path', ''))
        if source_path:
            for key in _identity_lookup_keys(source_path):
                hit = qs.filter(metadata__source_path=key).order_by('pk').first()
                if hit and _filename_tx_matches(hit, pi, basename):
                    return hit
            for key in (pi.get('relative_path', ''), normalize_source_path(pi.get('relative_path', ''))):
                if not key:
                    continue
                hit = qs.filter(metadata__source_path=key).order_by('pk').first()
                if hit and _filename_tx_matches(hit, pi, basename):
                    return hit

        bare = _bare_reupload_match(qs, basename, pi)
        if bare:
            return bare

        if strict_identity:
            return None

        seen: Set = set()
        candidates: List[Dataset] = []
        for ds in qs.filter(original_filename=basename):
            if ds.pk not in seen:
                seen.add(ds.pk)
                candidates.append(ds)
        if pi.get('city'):
            for ds in qs.filter(city__iexact=pi['city']):
                if ds.pk not in seen:
                    seen.add(ds.pk)
                    candidates.append(ds)
        if pi.get('district'):
            for ds in qs.filter(district__iexact=pi['district']):
                if ds.pk not in seen:
                    seen.add(ds.pk)
                    candidates.append(ds)

        if norm_incoming:
            for ds in candidates:
                rec_pi = dataset_path_info_from_record(
                    ds.city, ds.district, ds.original_filename, ds.metadata,
                )
                stored_norm = _norm_identity(build_file_identity(rec_pi, ds.original_filename))
                if stored_norm == norm_incoming and _filename_tx_matches(ds, pi, basename):
                    return ds

        best: Optional[Dataset] = None
        best_score = 0
        tied: List[Dataset] = []
        for ds in candidates:
            sc = _match_score(ds, pi, basename, identity)
            if sc > best_score:
                best_score = sc
                best = ds
                tied = [ds]
            elif sc == best_score and sc > 0:
                tied.append(ds)

        if best_score >= 100:
            if len(tied) > 1:
                return None
            return best
        return None

    active = _lookup(Dataset.objects.filter(user=user, is_active=True), False)
    if active:
        return active, False

    return None, False


def _listing_from_fields(dataset: Dataset, fields: dict) -> Listing:
    return Listing(
        dataset=dataset,
        token=fields['token'],
        title=fields['title'],
        price=fields['price'],
        deposit=fields['deposit'],
        rent=fields['rent'],
        area=fields['area'],
        rooms=fields['rooms'],
        neighborhood=fields['neighborhood'],
        city=fields['city'],
        latitude=fields['latitude'],
        longitude=fields['longitude'],
        business_type=fields['business_type'],
        advertiser_signal=fields.get('advertiser_signal') or '',
        description=fields['description'],
        link=fields['link'],
        images=fields['images'],
        published_at=fields['published_at'],
        expires_at=fields['expires_at'],
        data=fields['data'],
    )


_LISTING_SCALAR_FIELDS = (
    'title', 'price', 'deposit', 'rent', 'area', 'rooms',
    'neighborhood', 'city', 'latitude', 'longitude',
    'business_type', 'advertiser_signal', 'description', 'link',
    'published_at', 'expires_at',
)

_MONEY_SCALAR_ATTRS = ('price', 'deposit', 'rent')
_TEXTUAL_MONEY_STATUSES = frozenset({'free', 'negotiable', 'customary', 'full_deposit'})
_MONEY_STATUS_DATA_KEYS = {
    'price': 'مالی_قیمت_کل_وضعیت',
    'deposit': 'اجاره_ودیعه_وضعیت',
    'rent': 'اجاره_ماهانه_وضعیت',
}
_EXPORT_TEXT_MONEY = frozenset({'توافقی', 'متعارف', 'رایگان', 'رهن کامل'})
_MONEY_EXPORT_COLUMN = {'price': 'قیمت', 'deposit': 'ودیعه', 'rent': 'اجاره ماهانه'}


def _incoming_money_is_textual(fields: dict, attr: str) -> bool:
    data = fields.get('data') or {}
    status_key = _MONEY_STATUS_DATA_KEYS.get(attr, '')
    if data.get(status_key) in _TEXTUAL_MONEY_STATUSES:
        return True
    col = _MONEY_EXPORT_COLUMN.get(attr, '')
    raw = data.get(col)
    if raw is not None and str(raw).strip() in _EXPORT_TEXT_MONEY:
        return True
    return False


def _merge_listing_data(old: dict | None, new: dict | None) -> dict:
    merged = dict(old or {})
    for key, val in (new or {}).items():
        if val is None:
            continue
        s = str(val).strip()
        if s in ('', '-', '—', 'nan', 'None'):
            continue
        merged[key] = val
    return merge_listing_schedule_data(old, new)


def _has_explicit_publish_in_data(data: dict | None) -> bool:
    return has_explicit_publish_in_export_data(data)


def _has_explicit_coords_in_data(data: dict | None) -> bool:
    if not data:
        return False
    for key in (
        'عرض جغرافیایی', 'طول جغرافیایی',
        'مکان_مختصات_lat', 'مکان_مختصات_lng',
        'latitude', 'longitude',
    ):
        val = data.get(key)
        if val is None:
            continue
        s = str(val).strip()
        if s and s not in ('-', '—', 'nan', 'None'):
            return True
    return False


def _update_listing_from_fields(listing: Listing, fields: dict) -> bool:
    """به‌روزرسانی آگهی موجود — ادغام ویژگی‌های جدید اکسل در data."""
    changed = False
    for money_attr in _MONEY_SCALAR_ATTRS:
        if _incoming_money_is_textual(fields, money_attr):
            if getattr(listing, money_attr) is not None:
                setattr(listing, money_attr, None)
                changed = True
    for attr in _LISTING_SCALAR_FIELDS:
        new_val = fields.get(attr)
        if new_val is None:
            continue
        if attr in _MONEY_SCALAR_ATTRS and _incoming_money_is_textual(fields, attr):
            continue
        if isinstance(new_val, str) and not new_val.strip():
            continue
        if attr == 'published_at' and listing.published_at and not _has_explicit_publish_in_data(fields.get('data')):
            continue
        if attr in ('latitude', 'longitude') and not _has_explicit_coords_in_data(fields.get('data')):
            if getattr(listing, attr) is not None:
                continue
        if getattr(listing, attr) != new_val:
            setattr(listing, attr, new_val)
            changed = True
    new_images = fields.get('images') or []
    if new_images and listing.images != new_images:
        listing.images = new_images
        changed = True
    merged = _merge_listing_data(listing.data, fields.get('data'))
    if merged != (listing.data or {}):
        listing.data = merged
        changed = True
    return changed


def _listing_as_fields(listing: Listing) -> dict:
    return {
        'token': listing.token,
        'title': listing.title,
        'price': listing.price,
        'deposit': listing.deposit,
        'rent': listing.rent,
        'area': listing.area,
        'rooms': listing.rooms,
        'neighborhood': listing.neighborhood,
        'city': listing.city,
        'latitude': listing.latitude,
        'longitude': listing.longitude,
        'business_type': listing.business_type,
        'advertiser_signal': listing.advertiser_signal or '',
        'description': listing.description,
        'link': listing.link,
        'images': listing.images or [],
        'published_at': listing.published_at,
        'expires_at': listing.expires_at,
        'data': listing.data or {},
    }


LISTING_BULK_UPDATE_FIELDS = [
    'title', 'price', 'deposit', 'rent', 'area', 'rooms',
    'neighborhood', 'city', 'latitude', 'longitude',
    'business_type', 'advertiser_signal', 'description', 'link', 'images',
    'published_at', 'expires_at', 'data',
]


def bulk_create_listings_safe(
    dataset: Dataset,
    listings_to_create: List[Listing],
    listings_to_update: List[Listing],
    *,
    batch_size: int = 200,
) -> None:
    """درج آگهی — در تضاد (dataset, token) ادغام می‌کند (retry / همزمانی)."""
    if not listings_to_create:
        return

    incoming_by_token: dict[str, Listing] = {}
    for listing in listings_to_create:
        token = str(listing.token or '').strip()
        if token:
            incoming_by_token[token] = listing
    tokens = list(incoming_by_token.keys())
    if not tokens:
        return

    update_index = {lst.pk: lst for lst in listings_to_update if lst.pk}

    Listing.objects.bulk_create(
        listings_to_create,
        batch_size=batch_size,
        ignore_conflicts=True,
    )

    for existing in Listing.objects.filter(dataset=dataset, token__in=tokens):
        incoming = incoming_by_token.get(existing.token)
        if not incoming:
            continue
        if _update_listing_from_fields(existing, _listing_as_fields(incoming)):
            if existing.pk not in update_index:
                listings_to_update.append(existing)
                update_index[existing.pk] = existing


def _flush_listings(listings: List[Listing]) -> None:
    if listings:
        Listing.objects.bulk_create(listings, ignore_conflicts=True)
        listings.clear()


def _tokens_in_dataframe(df: pd.DataFrame) -> List[str]:
    tokens: List[str] = []
    for idx, row in df.iterrows():
        fields = row_to_listing_fields(row, df)
        token = str(fields.get('token') or '').strip()
        if not token:
            token = f'row_{idx}'
        tokens.append(token)
    return tokens


def import_dataset(
    user,
    file_path: str,
    original_filename: str,
    name: str | None = None,
    path_info: dict | None = None,
) -> ImportResult:
    """وارد کردن فایل — در صورت تکراری بودن، فقط آگهی‌های جدید اضافه می‌شوند."""
    ext = os.path.splitext(original_filename)[1].lower()
    fmt_map = {'.xlsx': 'xlsx', '.xls': 'xlsx', '.csv': 'csv', '.json': 'json'}
    file_format = fmt_map.get(ext, 'csv')
    basename = os.path.basename(original_filename)

    df = read_file_to_dataframe(file_path, ext)
    df = df.where(pd.notna(df), None)
    meta = detect_metadata(df)

    effective_path_info = dict(path_info) if path_info else {}
    if not effective_path_info:
        tx_slug = os.path.splitext(basename)[0]
        tx_type, subcategory = parse_tx_subcategory(tx_slug)
        effective_path_info = {
            'city': meta.get('city', ''),
            'district': meta.get('district', ''),
            'province': meta.get('province', ''),
            'transaction_type': tx_type or meta.get('transaction_type', ''),
            'subcategory': subcategory or meta.get('subcategory', ''),
            'tx_slug': tx_slug,
            'filename': basename,
        }

    if effective_path_info.get('relative_path'):
        effective_path_info['relative_path'] = normalize_source_path(
            effective_path_info['relative_path'],
        )
    meta = merge_path_into_dataset_meta(meta, effective_path_info)
    if not effective_path_info.get('relative_path'):
        meta.setdefault('source_path', basename)
    meta['file_identity'] = build_file_identity(effective_path_info, basename)

    file_size = os.path.getsize(file_path)
    existing, _reactivating = find_existing_dataset(user, basename, effective_path_info)
    is_update = existing is not None

    if is_update:
        dataset = existing
        meta = _preserve_dataset_location_meta(meta, effective_path_info, dataset)
        if not _has_folder_path(effective_path_info):
            old_md = dataset.metadata or {}
            effective_path_info['city'] = dataset.city or effective_path_info.get('city', '')
            effective_path_info['district'] = dataset.district or effective_path_info.get('district', '')
            effective_path_info['province'] = old_md.get('province', '') or effective_path_info.get('province', '')
    else:
        if name:
            dataset_name = name
        elif effective_path_info:
            dataset_name = build_dataset_name(effective_path_info, basename)
        else:
            dataset_name = os.path.splitext(basename)[0]

        tx_type = effective_path_info.get('transaction_type') or meta.get('transaction_type', '')
        city = effective_path_info.get('city') or meta.get('city', '')
        district = effective_path_info.get('district') or meta.get('district', '')
        subcategory = effective_path_info.get('subcategory') or meta.get('subcategory', '')

        dataset = Dataset(
            user=user,
            name=dataset_name,
            original_filename=basename,
            file_format=file_format,
            file_size=file_size,
            row_count=0,
            column_count=len(df.columns),
            columns=list(df.columns.astype(str)),
            transaction_type=tx_type,
            subcategory=subcategory,
            city=city,
            district=district,
            metadata=meta,
            last_opened_at=timezone.now(),
        )

    existing_tokens: Set[str] = set()
    existing_by_token: dict[str, Listing] = {}
    if is_update:
        for listing in Listing.objects.filter(dataset=dataset):
            token = str(listing.token or '').strip()
            if token:
                existing_tokens.add(token)
                existing_by_token[token] = listing

    listings: List[Listing] = []
    listings_to_update: List[Listing] = []
    price_records: List[PriceHistory] = []
    seen_tokens: Set[str] = set()
    tokens_in_file: Set[str] = set()
    added_count = 0
    updated_count = 0
    skipped_count = 0
    suppressed_count = 0
    price_cache = load_latest_snapshots(user, _tokens_in_dataframe(df))
    ingest_mode = resolve_ingest_mode(path_info=effective_path_info, is_mobile=False)
    meta['ingest_mode'] = ingest_mode
    prune_stale = should_prune_stale_listings(is_update=is_update, ingest_mode=ingest_mode)
    suppressed_tokens = get_suppressed_external_ids(
        user, DIVAR_SOURCE_PLATFORM, _tokens_in_dataframe(df),
    )
    listings_to_purge_suppressed: List[Listing] = []

    with transaction.atomic():
        if not is_update:
            dataset.save()

        for idx, row in df.iterrows():
            fields = row_to_listing_fields(row, df)
            token = str(fields.get('token') or '').strip()
            if not token:
                token = f'row_{idx}'
                fields['token'] = token
            tokens_in_file.add(token)

            if token in suppressed_tokens:
                suppressed_count += 1
                if token in existing_by_token:
                    listings_to_purge_suppressed.append(existing_by_token[token])
                continue

            if token in existing_by_token or token in seen_tokens:
                if token in existing_by_token:
                    listing_obj = existing_by_token[token]
                    if _update_listing_from_fields(listing_obj, fields):
                        listings_to_update.append(listing_obj)
                        updated_count += 1
                    else:
                        skipped_count += 1
                    if should_record_price(
                        price_cache, token,
                        fields['price'], fields['deposit'], fields['rent'],
                    ):
                        price_records.append(PriceHistory(
                            user=user,
                            token=token,
                            price=fields['price'],
                            deposit=fields['deposit'],
                            rent=fields['rent'],
                        ))
                else:
                    skipped_count += 1
                continue
            seen_tokens.add(token)

            listings.append(_listing_from_fields(dataset, fields))
            added_count += 1

            if should_record_price(
                price_cache, token,
                fields['price'], fields['deposit'], fields['rent'],
            ):
                price_records.append(PriceHistory(
                    user=user,
                    token=token,
                    price=fields['price'],
                    deposit=fields['deposit'],
                    rent=fields['rent'],
                ))

            if len(listings) >= BATCH_SIZE:
                _flush_listings(listings)

        _flush_listings(listings)

        if listings_to_update:
            Listing.objects.bulk_update(
                listings_to_update,
                LISTING_BULK_UPDATE_FIELDS,
                batch_size=BATCH_SIZE,
            )

        if price_records:
            for i in range(0, len(price_records), BATCH_SIZE):
                PriceHistory.objects.bulk_create(price_records[i:i + BATCH_SIZE])

        if listings_to_purge_suppressed:
            purge_ids = [lst.pk for lst in listings_to_purge_suppressed]
            Listing.objects.filter(pk__in=purge_ids).delete()

        if prune_stale and tokens_in_file:
            Listing.objects.filter(dataset=dataset).exclude(
                token__in=tokens_in_file,
            ).delete()

        dataset.file_size = file_size
        dataset.original_filename = basename
        dataset.file_format = file_format
        dataset.row_count = Listing.objects.filter(dataset=dataset).count()
        dataset.column_count = len(df.columns)
        merged_columns = list(dict.fromkeys(
            list((dataset.columns or [])) + list(df.columns.astype(str))
        )) if is_update else list(df.columns.astype(str))
        dataset.columns = merged_columns
        dataset.metadata = meta
        dataset.last_opened_at = timezone.now()
        if not is_update:
            dataset.is_active = True
        if _has_folder_path(effective_path_info) or not is_update:
            if effective_path_info.get('city'):
                dataset.city = effective_path_info['city']
            if effective_path_info.get('district'):
                dataset.district = effective_path_info['district']
        if effective_path_info.get('transaction_type'):
            dataset.transaction_type = effective_path_info['transaction_type']
        if effective_path_info.get('subcategory'):
            dataset.subcategory = effective_path_info['subcategory']
        if is_update and name:
            dataset.name = name
        elif is_update and effective_path_info.get('relative_path'):
            dataset.name = build_dataset_name(effective_path_info, basename)
        dataset.save()

    from workspace.services.crm_matching_index import bump_user_divar_listings_match_catalog

    bump_user_divar_listings_match_catalog(dataset.user_id)

    return ImportResult(
        dataset=dataset,
        added_count=added_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        suppressed_count=suppressed_count,
        is_update=is_update,
        reactivated=False,
        total_in_file=len(df),
    )


def import_message(result: ImportResult) -> Tuple[str, str]:
    """(level, message) — level: success | info | warning"""
    suppressed_note = ''
    if result.suppressed_count:
        suppressed_note = f' ({result.suppressed_count:,} سرکوب‌شده)'
    if result.is_update:
        if result.added_count > 0 or result.updated_count > 0:
            parts = []
            if result.added_count:
                parts.append(f'{result.added_count:,} آگهی جدید')
            if result.updated_count:
                parts.append(f'{result.updated_count:,} آگهی به‌روز')
            dup = f' ({result.skipped_count:,} بدون تغییر)' if result.skipped_count else ''
            return (
                'info',
                f'فایل «{result.dataset.name}» — {" و ".join(parts)}.{dup}{suppressed_note}',
            )
        if result.skipped_count:
            return (
                'info',
                f'فایل «{result.dataset.name}» قبلاً وجود دارد — '
                f'همه {result.skipped_count:,} آگهی تکراری بودند.',
            )
        return (
            'warning',
            f'فایل «{result.dataset.name}» قبلاً وجود دارد — داده جدیدی برای افزودن یافت نشد.',
        )
    if result.added_count:
        return (
            'success',
            f'فایل جدید «{result.dataset.name}» — {result.added_count:,} آگهی وارد شد.{suppressed_note}',
        )
    return (
        'warning',
        f'فایل جدید «{result.dataset.name}» ایجاد شد اما داده‌ای یافت نشد.',
    )

