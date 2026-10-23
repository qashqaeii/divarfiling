"""تبدیل JSON خام دیوار به ردیف export اکسل — هم‌تراز با extractor-app."""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mobile_api.services.divar_location import (
    apply_location_to_export_record,
    extract_post_location,
    location_tokens_agree,
)
from workspace.services.advertiser_signal import row_matches_advertiser_filter
from workspace.services.columns import extract_consultant_name
from workspace.services.property_images import (
    best_divar_image_url_from_mapping,
    deduplicate_divar_image_urls,
)

logger = logging.getLogger(__name__)

_DJANGO_SCRAPER = Path(__file__).resolve().parents[2] / 'scraper'
_MONOREPO_SRC = Path(__file__).resolve().parents[3] / 'src'

_WINDOWS_FLATTEN = None
_WINDOWS_EXPORT = None
_WINDOWS_IMPORT_TRIED = False

ROOMATE_PATTERN = re.compile(
    r'هم[\s\-]?(?:خو?ن?ه|خانه)[\s\-]?[ای‌ی]?',
    re.IGNORECASE | re.UNICODE,
)

CONSULTANT_BUSINESS_TYPES = {
    'premium-panel', 'premium_panel', 'business', 'consultant', 'agency',
    'بنگاه', 'مشاور', 'آژانس',
}


def _scraper_search_paths() -> List[Path]:
    paths: List[Path] = []
    for candidate in (_DJANGO_SCRAPER, _MONOREPO_SRC):
        if candidate.exists() and candidate not in paths:
            paths.append(candidate)
    return paths


def _ensure_windows_modules():
    global _WINDOWS_FLATTEN, _WINDOWS_EXPORT, _WINDOWS_IMPORT_TRIED
    if _WINDOWS_IMPORT_TRIED:
        return _WINDOWS_FLATTEN, _WINDOWS_EXPORT
    _WINDOWS_IMPORT_TRIED = True

    last_error: Optional[Exception] = None
    for scraper_dir in _scraper_search_paths():
        src = str(scraper_dir)
        if src not in sys.path:
            sys.path.insert(0, src)
        try:
            from export_divar_items import export_rows_to_records, flatten_post_detail  # noqa: WPS433
            _WINDOWS_FLATTEN = flatten_post_detail
            _WINDOWS_EXPORT = export_rows_to_records
            logger.info('Loaded export_divar_items from %s', scraper_dir)
            return _WINDOWS_FLATTEN, _WINDOWS_EXPORT
        except Exception as exc:
            last_error = exc
            if src in sys.path:
                sys.path.remove(src)

    logger.warning('Windows scraper import failed: %s', last_error)
    _WINDOWS_FLATTEN = None
    _WINDOWS_EXPORT = None
    return _WINDOWS_FLATTEN, _WINDOWS_EXPORT


def _export_records_from_raw_rows(
    raw_rows: List[Dict[str, Any]],
    category: str,
) -> List[Dict[str, Any]]:
    """همان export_rows_to_records ویندوز — خروجی ستون‌های فارسی کامل."""
    if not raw_rows:
        return []

    _, export_fn = _ensure_windows_modules()
    if export_fn is None:
        raise RuntimeError(
            'ماژول export_divar_items یافت نشد. پوشه scraper باید روی سرور deploy شود.'
        )

    try:
        try:
            return export_fn(raw_rows, category=category)
        except TypeError:
            import export_divar_items as scraper  # noqa: WPS433
            old_cat = scraper.CONFIG.get('category')
            try:
                scraper.CONFIG['category'] = category or old_cat or 'apartment-rent'
                return export_fn(raw_rows)
            finally:
                if old_cat is not None:
                    scraper.CONFIG['category'] = old_cat
    except Exception as exc:
        logger.exception('export_rows_to_records failed')
        raise RuntimeError(f'خطا در نرمال‌سازی export اکسل: {exc}') from exc


def _raw_flatten_row(detail: Dict[str, Any], token: str = '') -> Dict[str, Any]:
    flatten_fn, _ = _ensure_windows_modules()
    if flatten_fn is None:
        raise RuntimeError('flatten_post_detail در دسترس نیست.')
    return flatten_fn(detail)


def _record_for_filters(export_row: Dict[str, Any]) -> Dict[str, Any]:
    consultant_name = extract_consultant_name(export_row)
    business = str(export_row.get('نوع آگهی دهنده') or '').strip()
    if not business:
        business = _advertiser_type_persian(export_row)
    return {
        'token': str(export_row.get('شناسه') or export_row.get('token') or '').strip(),
        'title': str(export_row.get('عنوان') or '').strip(),
        'description': str(export_row.get('توضیحات') or '').strip(),
        'business_type': business,
        'consultant_name': consultant_name,
    }


def _has_meaningful_images(value: Any) -> bool:
    s = str(value or '').strip()
    return bool(s) and s.lower() not in ('-', '—', 'nan', 'none', 'null')


def _image_urls_from_sections(raw: Dict[str, Any]) -> List[str]:
    """استخراج مستقیم از IMAGE carousel در JSON خام."""
    urls: List[str] = []
    sections = raw.get('sections') or []
    if not isinstance(sections, list):
        return urls
    for section in sections:
        if not isinstance(section, dict) or section.get('section_name') != 'IMAGE':
            continue
        for widget in section.get('widgets') or []:
            if not isinstance(widget, dict):
                continue
            data = widget.get('data') or {}
            if not isinstance(data, dict):
                continue
            for item in data.get('items') or []:
                if not isinstance(item, dict):
                    continue
                image = item.get('image') if isinstance(item.get('image'), dict) else {}
                val = best_divar_image_url_from_mapping(image, item)
                if val.startswith('http') and val not in urls:
                    urls.append(val)
    return deduplicate_divar_image_urls(urls)


def _image_urls_from_raw_detail(raw: Dict[str, Any]) -> List[str]:
    """استخراج URL تصویر از JSON خام دیوار وقتی flatten خالی یا placeholder برگردانده."""
    urls = _image_urls_from_sections(raw)
    if urls:
        return urls
    try:
        row = _raw_flatten_row(raw, str(raw.get('token') or ''))
    except Exception:
        return []
    joined = str(row.get('images') or row.get('رسانه_تصاویر') or '').strip()
    if not _has_meaningful_images(joined):
        return []
    if '|' in joined:
        return [part.strip() for part in joined.split('|') if part.strip()]
    return [joined] if joined else []


def _merge_client_images(row: Dict[str, Any], item: Dict[str, Any]) -> None:
    """لینک تصویر ارسالی از کلاینت اندروید — وقتی flatten تصویر نداشت."""
    existing = str(
        row.get('images')
        or row.get('رسانه_تصاویر')
        or row.get('لینک تصاویر')
        or ''
    ).strip()
    if _has_meaningful_images(existing):
        return
    urls_raw = item.get('image_urls') or item.get('imageUrls') or []
    urls: List[str] = []
    if isinstance(urls_raw, list):
        for entry in urls_raw:
            value = str(entry or '').strip()
            if value and value not in urls:
                urls.append(value)
    thumb = str(item.get('thumbnail_url') or item.get('thumbnailUrl') or '').strip()
    if thumb and thumb not in urls:
        urls.append(thumb)
    if not urls:
        raw = item.get('raw')
        if isinstance(raw, dict):
            urls = _image_urls_from_raw_detail(raw)
    if not urls:
        return
    urls = deduplicate_divar_image_urls(urls)
    joined = ' | '.join(urls)
    row['images'] = joined
    row['رسانه_تصاویر'] = joined
    row['لینک تصاویر'] = joined
    row['لینک تصویر اول'] = urls[0]
    row['تصاویر'] = joined
    row['رسانه_تعداد_تصویر'] = len(urls)


def _advertiser_type_persian(row: Dict[str, Any]) -> str:
    consultant = extract_consultant_name(row)
    business = str(
        row.get('نوع آگهی دهنده')
        or row.get('فروشنده_business_type')
        or row.get('business_type')
        or ''
    ).strip().lower()
    if consultant or business in CONSULTANT_BUSINESS_TYPES or 'premium' in business:
        return 'مشاور'
    if business == 'personal' or not business:
        return 'شخصی'
    if 'مشاور' in business or 'آژانس' in business:
        return 'مشاور'
    return business or 'شخصی'


def items_to_export_records(
    items: List[Dict[str, Any]],
    category: str = 'apartment-rent',
    *,
    advertiser_filter: str = 'all',
    max_items: int = 100,
    location_filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    تبدیل آیتم‌های خام موبایل به ردیف‌های export اکسل (مثل فایل JSON ویندوز).
    برمی‌گرداند: (records, skipped_count)
    """
    raw_rows: List[Dict[str, Any]] = []
    skipped = 0

    for item in items:
        token = str(item.get('token') or '').strip()
        raw = item.get('raw') or item
        if not isinstance(raw, dict):
            skipped += 1
            continue
        try:
            row = _raw_flatten_row(raw, token)
        except Exception as exc:
            logger.warning('flatten failed for %s: %s', token, exc)
            skipped += 1
            continue
        token_val = str(row.get('token') or row.get('شناسه') or token or '').strip()
        if not token_val:
            skipped += 1
            continue
        raw_rows.append(row)

    if not raw_rows:
        return [], skipped

    export_records = _export_records_from_raw_rows(raw_rows, category)

    raw_by_token: Dict[str, Dict[str, Any]] = {}
    item_by_token: Dict[str, Dict[str, Any]] = {}
    for item in items:
        tok = str(item.get('token') or '').strip()
        if not tok:
            continue
        item_by_token[tok] = item
        raw = item.get('raw') or item
        if isinstance(raw, dict):
            raw_by_token[tok] = raw

    for rec in export_records:
        tok = str(rec.get('شناسه') or rec.get('token') or '').strip()
        client_item = item_by_token.get(tok)
        if client_item:
            _merge_client_images(rec, client_item)
        raw_detail = raw_by_token.get(tok)
        if raw_detail and client_item and location_tokens_agree(
            str(client_item.get('token') or '').strip(),
            raw_detail,
            tok,
        ):
            loc = extract_post_location(raw_detail, filters=location_filters)
            apply_location_to_export_record(rec, loc)

    filtered: List[Dict[str, Any]] = []
    adv = str(advertiser_filter or 'all').strip().lower()
    for rec in export_records:
        preview = _record_for_filters(rec)
        if is_roommate_ad(preview, category):
            skipped += 1
            continue
        if not row_matches_advertiser_filter({**rec, **preview}, adv):
            skipped += 1
            continue
        filtered.append(rec)
        if len(filtered) >= max_items:
            break

    return filtered, skipped


def flatten_divar_detail(
    detail: Dict[str, Any],
    token: str = '',
    category: str = 'apartment-rent',
) -> Dict[str, Any]:
    """تک آگهی — برای تست و سازگاری."""
    if not isinstance(detail, dict):
        detail = {}
    records, _skipped = items_to_export_records(
        [{'token': token, 'raw': detail}],
        category,
        max_items=1,
    )
    if not records:
        return {}
    rec = records[0]
    preview = _record_for_filters(rec)
    return {
        'token': preview['token'],
        'title': preview['title'],
        'description': preview['description'],
        'business_type': preview['business_type'],
        'consultant_name': preview['consultant_name'],
        'data': rec,
    }


def is_roommate_ad(flat: Dict[str, Any], category_slug: str = '') -> bool:
    if category_slug and 'rent' not in category_slug.lower():
        return False
    text = f"{flat.get('title', '')} {flat.get('description', '')}"
    return bool(ROOMATE_PATTERN.search(text))


def is_consultant_ad(flat: Dict[str, Any]) -> bool:
    business = str(flat.get('business_type') or '').strip().lower()
    if business in CONSULTANT_BUSINESS_TYPES or business == 'مشاور':
        return True
    if flat.get('consultant_name'):
        return True
    return 'مشاور' in business or 'آژانس' in business

