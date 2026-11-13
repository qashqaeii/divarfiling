"""استان/شهر دیوار از places-web.json — مشترک با اتوماسیون و پروفایل مشاور."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

# کلیدهای قدیمی پروفایl (advisor_profile_catalog) → slug استان در دیوار
LEGACY_PROVINCE_TO_DIVAR_SLUG: Dict[str, str] = {
    'tehran': 'tehran-province',
    'alborz': 'alborz-province',
    'isfahan': 'isfahan-province',
    'fars': 'fars-province',
    'khorasan_razavi': 'khorasan-razavi-province',
    'east_azerbaijan': 'azarbaijan-east-province',
    'west_azerbaijan': 'azerbaijan-west-province',
    'khuzestan': 'khuzestan-province',
    'mazandaran': 'mazandaran-province',
    'gilan': 'gilan-province',
    'kerman': 'kerman-province',
    'yazd': 'yazd-province',
    'qom': 'qom-province',
}


def _places_file_path() -> Optional[Path]:
    pd = (getattr(settings, 'PHONE_DETECTOR_DIR', None) or '').strip()
    candidates: list[Path] = []
    if pd:
        root = Path(pd).expanduser().resolve().parent
        candidates.append(root / 'config' / 'places-web.json')
        candidates.append(Path(pd).expanduser().resolve() / 'config' / 'places-web.json')
    base = Path(getattr(settings, 'BASE_DIR', Path.cwd()))
    candidates.extend([
        base.parent / 'config' / 'places-web.json',
        Path('/root/config/places-web.json'),
    ])
    for path in candidates:
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=1)
def _load_places_raw() -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    path = _places_file_path()
    if not path:
        return {}, []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, list):
            return {}, []
    except (OSError, json.JSONDecodeError):
        return {}, []
    id_to_node: dict[int, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict) or 'id' not in item:
            continue
        node = dict(item)
        if node.get('name') is not None:
            node['name'] = str(node['name']).strip()
        id_to_node[int(item['id'])] = node
    return id_to_node, data


def places_config_available() -> bool:
    return bool(_load_places_raw()[0])


@lru_cache(maxsize=1)
def _province_nodes() -> List[dict[str, Any]]:
    id_to_node, _ = _load_places_raw()
    provinces = [n for n in id_to_node.values() if str(n.get('type')) == '1']
    provinces.sort(key=lambda x: str(x.get('name', '')))
    return provinces


@lru_cache(maxsize=1)
def _cities_by_province_id() -> Dict[int, List[dict[str, Any]]]:
    id_to_node, _ = _load_places_raw()
    cities = [n for n in id_to_node.values() if str(n.get('type')) == '2']
    out: Dict[int, List[dict[str, Any]]] = {}
    for city in cities:
        parent = city.get('parent')
        if parent is None:
            continue
        pid = int(parent)
        out.setdefault(pid, []).append(city)
    for lst in out.values():
        lst.sort(key=lambda x: str(x.get('name', '')))
    return out


@lru_cache(maxsize=1)
def _slug_to_province() -> Dict[str, dict[str, Any]]:
    return {
        str(p.get('slug') or '').strip(): p
        for p in _province_nodes()
        if (p.get('slug') or '').strip()
    }


def resolve_province_slug(stored: Optional[str]) -> str:
    """slug استان دیوار؛ مقادیر legacy را نرمال می‌کند."""
    key = (stored or '').strip()
    if not key:
        return ''
    legacy = LEGACY_PROVINCE_TO_DIVAR_SLUG.get(key)
    if legacy:
        key = legacy
    if key in _slug_to_province():
        return key
    # اگر قبلاً نام فارسی ذخیره شده
    for prov in _province_nodes():
        if key == str(prov.get('name') or '').strip():
            return str(prov.get('slug') or '').strip()
    return key


def province_label(stored: Optional[str]) -> str:
    slug = resolve_province_slug(stored)
    prov = _slug_to_province().get(slug)
    if prov:
        return str(prov.get('name') or slug)
    return (stored or '').strip() or '—'


def list_provinces_for_select() -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    for prov in _province_nodes():
        slug = str(prov.get('slug') or '').strip()
        name = str(prov.get('name') or '').strip()
        if slug and name:
            rows.append((slug, name))
    return rows


def list_cities_for_province_slug(province_slug: str) -> List[Tuple[str, str]]:
    """(value, label) — value همان نام فارسی شهر (سازگار با ذخیره فعلی)."""
    slug = resolve_province_slug(province_slug)
    prov = _slug_to_province().get(slug)
    if not prov:
        return []
    cities = _cities_by_province_id().get(int(prov['id']), [])
    out: List[Tuple[str, str]] = []
    for city in cities:
        name = str(city.get('name') or '').strip()
        if not name or name.startswith('کل '):
            continue
        out.append((name, name))
    return out


def cities_by_province_for_js() -> Dict[str, List[Dict[str, str]]]:
    """برای پر کردن dropdown شهر در مرورگر."""
    payload: Dict[str, List[Dict[str, str]]] = {}
    for slug, prov in _slug_to_province().items():
        cities = _cities_by_province_id().get(int(prov['id']), [])
        items: List[Dict[str, str]] = []
        for city in cities:
            name = str(city.get('name') or '').strip()
            if not name or name.startswith('کل '):
                continue
            items.append({
                'name': name,
                'slug': str(city.get('slug') or '').strip(),
            })
        if items:
            payload[slug] = items
    return payload


def city_in_province(province_slug: str, city_name: str) -> bool:
    city_name = (city_name or '').strip()
    if not city_name:
        return False
    return any(value == city_name for value, _ in list_cities_for_province_slug(province_slug))


def list_districts_for_city(city_name: str, *, limit: int = 400) -> list[str]:
    """مناطق یک شهر — type=4 در places-web."""
    city_name = (city_name or '').strip()
    if not city_name:
        return []
    id_to_node, raw = _load_places_raw()
    city_id = None
    for item in raw:
        if str(item.get('type')) == '2' and str(item.get('name') or '').strip() == city_name:
            city_id = item.get('id')
            break
    if city_id is None:
        return []
    names: list[str] = []
    for item in raw:
        if item.get('parent') == city_id and str(item.get('type')) == '4':
            name = str(item.get('name') or '').strip()
            if name:
                names.append(name)
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered[:limit]
