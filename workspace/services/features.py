"""استخراج ویژگی‌های ملک از داده آگهی."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from workspace.services.columns import is_consultant

_FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
_ROOM_WORDS = {
    'یک': '1', 'دو': '2', 'سه': '3', 'چهار': '4', 'پنج': '5',
    'شش': '6', 'هفت': '7', 'هشت': '8', 'نه': '9', 'ده': '10',
}

FEATURE_KEYS = {
    'build_year': ('ساخت', 'سال ساخت', 'build_year', 'سن بنا', 'سال ساخت بنا'),
    'floor': ('طبقه', 'floor', 'طبقه واحد'),
    'elevator': ('آسانسور', 'elevator'),
    'parking': ('پارکینگ', 'parking', 'جای پارک'),
    'storage': ('انباری', 'storage', 'انبار'),
    'balcony': ('بالکن', 'balcony', 'تراس', 'بالکن و تراس'),
    'lobby': ('لابی', 'lobby', 'لابی شیک'),
    'pool': ('استخر', 'pool', 'استخر سرپوشیده'),
    'roof_garden': ('روف گاردن', 'roof_garden', 'روف', 'بام باغ'),
    'jacuzzi': ('جکوزی', 'jacuzzi', 'جکوزی'),
    'gym': ('سالن ورزش', 'gym', 'باشگاه', 'سالن بدنسازی'),
    'rooms': ('اتاق', 'rooms', 'تعداد اتاق', 'اتاق خواب'),
}

POSITIVE = ('دارد', 'yes', 'true', '1', 'هست', 'داره', 'می‌باشد', 'میباشد')
NEGATIVE = ('ندارد', 'no', 'false', '0', 'نیست', 'نداره', '-', '—', 'خیر')
_POSITIVE_EXACT = frozenset(p.lower() for p in POSITIVE)
_NEGATIVE_EXACT = frozenset(n.lower() for n in NEGATIVE)
# ارقام تکی فقط با تطبیق دقیق — نه به‌صورت زیررشته داخل «12» یا «10»
_BOOL_DIGIT_TOKENS = frozenset({'0', '1'})
_POSITIVE_SUB = tuple(p for p in POSITIVE if p.lower() not in _BOOL_DIGIT_TOKENS)
_NEGATIVE_SUB = tuple(
    n for n in NEGATIVE
    if n not in ('-', '—') and n.lower() not in _BOOL_DIGIT_TOKENS
)

_YEAR_ONLY_RE = re.compile(r'^(13|14|19|20)\d{2}$')


def _column_matches_alias(column: str, alias: str) -> bool:
    """تطبیق دقیق ستون — بدون اشتباه گرفتن «ساخت» با «جهت ساختمان»."""
    col = str(column or '').strip()
    al = str(alias or '').strip()
    if not col or not al:
        return False
    if col == al:
        return True
    cl, al_lower = col.lower(), al.lower()
    if cl == al_lower:
        return True
    if len(al) >= 5 and al_lower in cl:
        return True
    return False


def _get_from_data(data: dict, keys: Tuple[str, ...]) -> Any:
    if not data:
        return None
    ordered = sorted(keys, key=len, reverse=True)
    for key in ordered:
        if key in data:
            return data[key]
    lower_map = {str(k).strip().lower(): k for k in data}
    for key in ordered:
        lk = key.lower()
        if lk in lower_map:
            return data[lower_map[lk]]
    for col, val in data.items():
        for key in ordered:
            if _column_matches_alias(col, key):
                return val
    return None


def get_exact_from_data(data: dict, key: str) -> Any:
    """فقط تطبیق دقیق نام ستون — برای ویژگی‌های تفصیلی."""
    if not data or not key:
        return None
    if key in data:
        return data[key]
    kl = key.lower()
    for col, val in data.items():
        if str(col).strip().lower() == kl:
            return val
    return None


def parse_bool_feature(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    s = str(value).strip()
    if not s or s.lower() in ('nan', 'none'):
        return None
    sl = s.lower()
    if sl in ('-', '—'):
        return None
    if sl in _NEGATIVE_EXACT:
        return False
    if sl in _POSITIVE_EXACT:
        return True
    # منفی‌ها قبل از مثبت — «ندارد» شامل «دارد» است؛ «-» نامشخص است
    # ارقام 0/1 فقط exact (بالا) — نه زیررشته داخل اعداد چندرقمی
    if any(n in sl for n in _NEGATIVE_SUB):
        return False
    if any(p in sl for p in _POSITIVE_SUB):
        return True
    return None


def parse_rooms_value(value: Any) -> str:
    if value is None:
        return ''
    s = str(value).strip()
    if not s or s in ('-', '—', 'nan', 'None'):
        return ''
    t = s.translate(_FA_DIGITS)
    m = re.search(r'(\d+)', t)
    if m:
        return m.group(1)
    return s


def parse_rooms_from_text(text: str) -> str:
    if not text:
        return ''
    t = text.translate(_FA_DIGITS)
    for pattern in (r'(\d+)\s*خواب', r'(\d+)\s*اتاق', r'(\d+)خواب', r'(\d+)خوابه'):
        m = re.search(pattern, t)
        if m:
            return m.group(1)
    for word, num in _ROOM_WORDS.items():
        if re.search(rf'{word}\s*خواب', text):
            return num
    return ''


def parse_build_year(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if isinstance(value, float) and value != value:
            return None
        s = str(value).strip().replace(',', '')
        if not s:
            return None
        m = re.search(r'(13|14|19|20)\d{2}', s)
        if m:
            y = int(m.group())
            if y < 1300:
                return y
            if 1300 <= y <= 1450:
                return y
        y = int(float(s))
        if 1300 <= y <= 1450 or 1950 <= y <= 2030:
            return y
    except (ValueError, TypeError):
        pass
    return None


def extract_listing_features(listing) -> Dict[str, Any]:
    """ویژگی‌های استاندارد از مدل Listing."""
    data = listing.data or {}
    build_year = parse_build_year(_get_from_data(data, FEATURE_KEYS['build_year']))
    if not build_year and listing.title:
        m = re.search(r'(13|14)\d{2}', listing.title.translate(_FA_DIGITS))
        if m:
            build_year = parse_build_year(m.group())

    floor_raw = _get_from_data(data, FEATURE_KEYS['floor'])
    floor = str(floor_raw).strip() if floor_raw not in (None, '', '-') else ''
    if not floor and listing.title:
        m = re.search(r'طبقه\s*(\d+)', listing.title.translate(_FA_DIGITS))
        if m:
            floor = m.group(1)

    rooms_raw = listing.rooms or _get_from_data(data, FEATURE_KEYS['rooms'])
    rooms = parse_rooms_value(rooms_raw)
    if not rooms:
        rooms = parse_rooms_from_text(listing.title or '')

    elevator = parse_bool_feature(_get_from_data(data, FEATURE_KEYS['elevator']))
    parking = parse_bool_feature(_get_from_data(data, FEATURE_KEYS['parking']))
    storage = parse_bool_feature(_get_from_data(data, FEATURE_KEYS['storage']))
    balcony = parse_bool_feature(_get_from_data(data, FEATURE_KEYS['balcony']))
    lobby = parse_bool_feature(_get_from_data(data, FEATURE_KEYS['lobby']))
    pool = parse_bool_feature(_get_from_data(data, FEATURE_KEYS['pool']))
    roof_garden = parse_bool_feature(_get_from_data(data, FEATURE_KEYS['roof_garden']))
    jacuzzi = parse_bool_feature(_get_from_data(data, FEATURE_KEYS['jacuzzi']))
    gym = parse_bool_feature(_get_from_data(data, FEATURE_KEYS['gym']))

    if any(x is None for x in (elevator, parking, storage)):
        from workspace.services.listing_features import _collect_raw_features
        raw = _collect_raw_features(data)
        if elevator is None:
            elevator = parse_bool_feature(raw.get('آسانسور'))
        if parking is None:
            parking = parse_bool_feature(raw.get('پارکینگ'))
        if storage is None:
            storage = parse_bool_feature(raw.get('انباری'))
        if balcony is None:
            balcony = parse_bool_feature(raw.get('بالکن'))

    from workspace.services.listing_features import feature_highlights_for_listing
    from workspace.services.advertiser_signal import listing_advertiser_display
    highlights = feature_highlights_for_listing(listing)
    advertiser = listing_advertiser_display(listing)

    amenities = []
    for flag, name in (
        (elevator, 'آسانسور'), (parking, 'پارکینگ'), (storage, 'انباری'),
        (balcony, 'بالکن'), (lobby, 'لابی'), (pool, 'استخر'),
        (roof_garden, 'روف گاردن'), (jacuzzi, 'جکوزی'), (gym, 'سالن ورزش'),
    ):
        if flag:
            amenities.append(name)

    core_flags = (elevator, parking, storage)
    secondary_flags = (balcony, lobby, pool, roof_garden, jacuzzi, gym)
    amenity_flags = core_flags + secondary_flags
    return {
        'rooms': rooms,
        'build_year': build_year,
        'floor': floor,
        'elevator': elevator,
        'parking': parking,
        'storage': storage,
        'balcony': balcony,
        'lobby': lobby,
        'pool': pool,
        'roof_garden': roof_garden,
        'jacuzzi': jacuzzi,
        'gym': gym,
        'amenities': amenities,
        'amenity_count': sum(1 for x in core_flags if x),
        'secondary_amenity_count': sum(1 for x in secondary_flags if x),
        'is_consultant': advertiser['signal'] == 'consultant',
        'advertiser': advertiser,
        'advertiser_label': advertiser['label'],
        'has_amenity_data': any(x is not None for x in amenity_flags),
        'highlights': highlights,
    }


def area_bucket(area: Optional[float]) -> str:
    if not area or area <= 0:
        return 'نامشخص'
    if area < 50:
        return 'زیر ۵۰'
    if area < 70:
        return '۵۰–۷۰'
    if area < 90:
        return '۷۰–۹۰'
    if area < 120:
        return '۹۰–۱۲۰'
    return '۱۲۰+'


# بازه‌های استاندارد بدون هم‌پوشانی — برای تحلیل بازار
STANDARD_AREA_BUCKET_DEFS = (
    (0, 30, '۰–۳۰ متر'),
    (30, 60, '۳۰–۶۰ متر'),
    (60, 90, '۶۰–۹۰ متر'),
    (90, 150, '۹۰–۱۵۰ متر'),
    (150, 250, '۱۵۰–۲۵۰ متر'),
    (250, float('inf'), '۲۵۰+ متر'),
)


def standard_area_bucket_edges(
    areas=None,
    *,
    min_size: int = 3,
) -> list:
    """باکت‌های ثابت متراژ — فقط بازه‌هایی که حداقل min_size فایل دارند."""
    if areas is None:
        return list(STANDARD_AREA_BUCKET_DEFS)
    clean = areas.dropna() if hasattr(areas, 'dropna') else []
    if len(clean) == 0:
        return list(STANDARD_AREA_BUCKET_DEFS)
    out = []
    for lo, hi, label in STANDARD_AREA_BUCKET_DEFS:
        if hi == float('inf'):
            count = int((clean >= lo).sum())
        else:
            count = int(((clean >= lo) & (clean < hi)).sum())
        if count >= min_size:
            out.append((lo, hi, label))
    return out or [STANDARD_AREA_BUCKET_DEFS[0]]


def assign_standard_area_bucket(area: Optional[float], edges=None) -> str:
    if not area or area <= 0:
        return 'نامشخص'
    edges = edges or STANDARD_AREA_BUCKET_DEFS
    for i, (lo, hi, label) in enumerate(edges):
        if hi == float('inf'):
            if area >= lo:
                return label
        elif lo <= area < hi:
            return label
    return edges[-1][2]
