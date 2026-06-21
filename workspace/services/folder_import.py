"""وارد کردن دسته‌ای فایل‌های output با تفکیک استان / شهر / منطقه."""
from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from workspace.constants import SUPPORTED_UPLOAD_EXTENSIONS

SKIP_FILENAMES = frozenset({
    'error_report.txt', 'temp_map.html', 'thumbnails.json', '.ds_store',
})
SKIP_EXTENSIONS = frozenset({
    '.pdf', '.html', '.htm', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.zip', '.db',
})

_TOKEN_DIR_RE = re.compile(r'^[a-zA-Z0-9]{6,12}$')


def is_importable_file(filename: str) -> bool:
    base = os.path.basename(filename.replace('\\', '/'))
    if base.lower() in SKIP_FILENAMES or base.startswith('.'):
        return False
    # فایل قفل Excel وقتی workbook در Excel باز است (~$filename.xlsx)
    if base.startswith('~$'):
        return False
    ext = os.path.splitext(base)[1].lower()
    if ext in SKIP_EXTENSIONS:
        return False
    return ext in SUPPORTED_UPLOAD_EXTENSIONS


def _norm_part(part: str) -> str:
    return (part or '').strip().replace('_', ' ')


def _strip_output_parts(parts: List[str]) -> List[str]:
    """حذف هر چیزی تا و شامل پوشه output — برای انتخاب پوشه والد یا خود output."""
    for i, part in enumerate(parts):
        if part.lower() == 'output':
            return parts[i + 1:]
    return parts


def normalize_source_path(relative_path: str) -> str:
    """مسیر یکتا برای شناسایی فایل — بدون پیشوند output."""
    path = (relative_path or '').replace('\\', '/').strip('/')
    parts = [p for p in path.split('/') if p and p != '.']
    parts = _strip_output_parts(parts)
    return '/'.join(parts)


def _tx_kind(label: str) -> str:
    slug = (label or '').replace('_', ' ')
    if 'اجاره' in slug or 'رهن' in slug:
        return 'rent'
    if 'فروش' in slug:
        return 'sale'
    return ''


def _parse_location_dirs(dirs: List[str]) -> Tuple[str, str, str]:
    """استان / شهر / منطقه از عمق مسیر — پوشه تک‌سطحی = شهر."""
    if not dirs:
        return '', '', ''
    if len(dirs) == 1:
        return '', _norm_part(dirs[0]), ''
    if len(dirs) == 2:
        return _norm_part(dirs[0]), _norm_part(dirs[1]), ''
    return _norm_part(dirs[0]), _norm_part(dirs[1]), _norm_part(dirs[2])


def normalize_file_identity(rel_path: str) -> str:
    """مسیر یکتا بدون پسوند فایل — برای تطبیق آپلود تکی و پوشه."""
    rel = normalize_source_path(rel_path)
    if not rel:
        return ''
    parts = rel.split('/')
    if parts:
        parts[-1] = os.path.splitext(parts[-1])[0]
    return '/'.join(parts).lower()


def build_file_identity(path_info: Optional[Dict[str, Any]], basename: str) -> str:
    """کلید یکتا: مسیر نسبی یا استان/شهر/منطقه/نوع-فایل."""
    pi = path_info or {}
    rel_id = normalize_file_identity(pi.get('relative_path', ''))
    if rel_id:
        return rel_id
    tx_slug = (pi.get('tx_slug') or os.path.splitext(basename)[0]).strip().replace(' ', '_')
    loc = [_norm_part(pi.get(k, '')) for k in ('province', 'city', 'district')]
    loc = [p for p in loc if p]
    if loc:
        return '/'.join(loc + [tx_slug]).lower()
    return os.path.splitext(basename)[0].lower()


def locations_match(dataset_meta: Dict[str, Any], dataset_city: str, dataset_district: str,
                    path_info: Dict[str, Any]) -> bool:
    """آیا مجموعه‌داده قبلی همان مکان مسیر پوشه است؟"""
    if not path_info:
        return True

    pi_prov = _norm_part(path_info.get('province', ''))
    pi_city = _norm_part(path_info.get('city', ''))
    pi_dist = _norm_part(path_info.get('district', ''))
    md = dataset_meta or {}
    ds_prov = _norm_part(md.get('province', ''))
    ds_city = _norm_part(dataset_city or md.get('city', ''))
    ds_dist = _norm_part(dataset_district or md.get('district', ''))

    if pi_dist and ds_dist:
        return pi_dist == ds_dist and (not pi_city or not ds_city or pi_city == ds_city)

    if pi_dist and not ds_dist:
        return False
    if ds_dist and not pi_dist:
        return False

    if pi_city and ds_city and pi_city == ds_city:
        if pi_prov and ds_prov:
            return pi_prov == ds_prov
        return True

    if pi_city and ds_city and pi_city != ds_city:
        return False

    if pi_prov and ds_city and not pi_city and pi_prov == ds_city:
        return True

    if pi_prov and ds_prov and pi_prov == ds_prov and not pi_city and not ds_city:
        return True

    return False


def transaction_match(dataset_tx: str, dataset_filename: str, path_info: Dict[str, Any],
                      basename: str) -> bool:
    """فروش و اجاره نباید به یک فایل قبلی وصل شوند."""
    incoming = (path_info or {}).get('tx_slug') or os.path.splitext(basename)[0]
    want = _tx_kind(incoming)
    if not want:
        return True
    have = _tx_kind(f'{dataset_tx} {os.path.splitext(dataset_filename)[0]}')
    if not have:
        return True
    return want == have


def _norm_subcategory(val: str) -> str:
    return (val or '').strip().replace('_', ' ')


def _incoming_subcategory(path_info: Dict[str, Any], basename: str) -> str:
    pi = path_info or {}
    sub = _norm_subcategory(pi.get('subcategory', ''))
    if sub:
        return sub
    _, sub = parse_tx_subcategory(pi.get('tx_slug') or os.path.splitext(basename)[0])
    return _norm_subcategory(sub)


def _dataset_subcategory(
    dataset_subcategory: str,
    dataset_filename: str,
    dataset_meta: Dict[str, Any],
) -> str:
    md = dataset_meta or {}
    sub = _norm_subcategory(dataset_subcategory or md.get('subcategory', ''))
    if sub:
        return sub
    _, sub = parse_tx_subcategory(os.path.splitext(dataset_filename)[0])
    return _norm_subcategory(sub)


def subcategory_match(
    dataset_subcategory: str,
    dataset_filename: str,
    dataset_meta: Dict[str, Any],
    path_info: Dict[str, Any],
    basename: str,
) -> bool:
    """آپارتمان، مغازه و دفتر کار در یک شهر نباید به یک مجموعه‌داده وصل شوند."""
    incoming_sub = _incoming_subcategory(path_info, basename)
    ds_sub = _dataset_subcategory(dataset_subcategory, dataset_filename, dataset_meta)
    if incoming_sub and ds_sub:
        return incoming_sub == ds_sub

    inc_stem = _norm_subcategory(os.path.splitext(basename)[0])
    ds_stem = _norm_subcategory(os.path.splitext(dataset_filename)[0])
    return inc_stem == ds_stem


def parse_tx_subcategory(label: str) -> Tuple[str, str]:
    """فروش_آپارتمان → (فروش مسکونی, آپارتمان)"""
    raw = (label or '').strip()
    slug = raw.replace('_', ' ').strip()
    if not slug:
        return '', ''

    tx = ''
    sub = slug
    if re.search(r'فروش.*اداری|فروش.*تجاری', slug):
        tx, sub = 'فروش اداری و تجاری', re.sub(r'^فروش\s*(اداری\s*و\s*تجاری|اداری|تجاری)\s*', '', slug).strip()
    elif re.search(r'اجاره.*اداری|اجاره.*تجاری', slug):
        tx, sub = 'اجاره اداری و تجاری', re.sub(r'^اجاره\s*(اداری\s*و\s*تجاری|اداری|تجاری)\s*', '', slug).strip()
    elif slug.startswith('فروش'):
        tx, sub = 'فروش مسکونی', slug[4:].strip(' -_')
    elif slug.startswith('اجاره'):
        tx, sub = 'اجاره مسکونی', slug[5:].strip(' -_')
    elif slug.startswith('رهن'):
        tx, sub = 'رهن', slug[3:].strip(' -_')
    else:
        sub = slug

    return tx, sub or slug


def parse_output_relative_path(relative_path: str) -> Dict[str, Any]:
    """
    مسیر نسبی پوشه output:
    output/استان/شهر/منطقه/فروش_آپارتمان/file.xlsx
    یا: استان/شهر/منطقه/فروش_آپارتمان.xlsx
    """
    path = (relative_path or '').replace('\\', '/').strip('/')
    parts = [p for p in path.split('/') if p and p != '.']
    if not parts:
        return {}

    parts = _strip_output_parts(parts)

    filename = parts[-1] if parts else ''
    dirs = parts[:-1]

    while dirs and _TOKEN_DIR_RE.match(dirs[-1]):
        dirs = dirs[:-1]

    province, city, district = _parse_location_dirs(dirs)

    tx_label = ''
    if len(dirs) >= 4:
        tx_label = dirs[3]
    elif filename:
        tx_label = os.path.splitext(filename)[0]

    transaction_type, subcategory = parse_tx_subcategory(tx_label.replace(' ', '_'))
    norm_path = normalize_source_path(path)

    return {
        'province': province,
        'city': city,
        'district': district,
        'transaction_type': transaction_type,
        'subcategory': subcategory,
        'tx_slug': tx_label,
        'relative_path': norm_path,
        'filename': filename,
    }


def build_dataset_name(path_info: Dict[str, Any], original_filename: str) -> str:
    parts: List[str] = []
    if path_info.get('district'):
        parts.append(path_info['district'])
    elif path_info.get('city'):
        parts.append(path_info['city'])
    if path_info.get('subcategory'):
        parts.append(path_info['subcategory'])
    elif path_info.get('transaction_type'):
        parts.append(path_info['transaction_type'])
    if parts:
        return ' — '.join(parts)
    return os.path.splitext(os.path.basename(original_filename))[0]


def dataset_path_info_from_record(
    dataset_city: str = '',
    dataset_district: str = '',
    original_filename: str = '',
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """بازسازی path_info از رکورد موجود — برای تطبیق فایل‌های قدیمی."""
    md = metadata or {}
    tx_slug = os.path.splitext(original_filename)[0]
    tx_type = md.get('transaction_type', '')
    subcategory = md.get('subcategory', '')
    if not tx_type or not subcategory:
        parsed_tx, parsed_sub = parse_tx_subcategory(tx_slug)
        tx_type = tx_type or parsed_tx
        subcategory = subcategory or parsed_sub
    return {
        'province': md.get('province', ''),
        'city': dataset_city or md.get('city', ''),
        'district': dataset_district or md.get('district', ''),
        'transaction_type': tx_type,
        'subcategory': subcategory,
        'tx_slug': tx_slug,
        'relative_path': md.get('source_path', ''),
        'filename': original_filename,
    }


def merge_path_into_dataset_meta(meta: Dict[str, Any], path_info: Dict[str, Any]) -> Dict[str, Any]:
    """اولویت با مسیر پوشه — دقیق‌تر از داده داخل فایل."""
    out = dict(meta or {})
    if not path_info:
        return out

    if path_info.get('province'):
        out['province'] = path_info['province']
    if path_info.get('city'):
        out['city'] = path_info['city']
    if path_info.get('district'):
        out['district'] = path_info['district']
    if path_info.get('transaction_type'):
        out['transaction_type'] = path_info['transaction_type']
    if path_info.get('subcategory'):
        out['subcategory'] = path_info['subcategory']
    if path_info.get('relative_path'):
        out['source_path'] = path_info['relative_path']
    identity = build_file_identity(path_info, path_info.get('filename', ''))
    if identity:
        out['file_identity'] = identity
    return out


def group_import_results(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """گروه‌بندی نتایج: استان → شهر → فایل‌ها."""
    tree: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
    for item in items:
        prov = item.get('province') or 'سایر'
        city = item.get('city') or '—'
        tree[prov][city].append(item)

    groups = []
    for province in sorted(tree.keys(), key=lambda x: (x == 'سایر', x)):
        cities = []
        for city in sorted(tree[province].keys(), key=lambda x: (x == '—', x)):
            files = sorted(tree[province][city], key=lambda x: x.get('name', ''))
            cities.append({'city': city, 'files': files})
        groups.append({'province': province, 'cities': cities})
    return groups
