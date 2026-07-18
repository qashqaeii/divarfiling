"""ویژگی‌های تفصیلی فایل شخصی CRM — انتخاب‌محور بر اساس نوع معامله و نوع ملک."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from workspace.constants import LISTING_FEATURE_GROUPS, PROPERTY_BOOL_AMENITY_LABELS

# ── Choices ──────────────────────────────────────────────────────────────

CHOICES_DIRECTION = ('شمالی', 'جنوبی', 'شرقی', 'غربی')
CHOICES_FLOORING = (
    'سرامیک', 'پارکت', 'پارکت چوبی', 'لمینت', 'کفپوش PVC', 'موکت', 'موزاییک',
)
CHOICES_BATHROOM = ('ایرانی', 'فرنگی', 'هردو')
CHOICES_COOLING = (
    'کولر آبی', 'کولر گازی', 'داکت اسپلیت', 'اسپلیت', 'فن‌کویل', 'پنکه',
)
CHOICES_HEATING = (
    'بخاری', 'شوفاژ', 'فن‌کویل', 'از کف', 'داکت اسپلیت', 'اسپلیت', 'شومینه',
)
CHOICES_HOT_WATER = ('آبگرمکن', 'موتورخانه', 'پکیج')
CHOICES_KITCHEN = ('اپن', 'جزیره', 'نیمه‌اپن', 'بسته')
CHOICES_SUITABLE = ('خانواده', 'مجرد', 'هر دو')
CHOICES_CABINET = ('MDF', 'های‌گلاس', 'ممبران', 'فلزی', 'چوب', 'سایر')
CHOICES_DEED = ('تک‌برگ', 'قولنامه‌ای', 'منگوله‌دار', 'سایر')
CHOICES_FACADE = ('سنگ', 'آجر', 'سیمان', 'کامپوزیت', 'چوب', 'شیشه', 'سایر')
CHOICES_OCCUPANCY = ('تخلیه', 'در اختیار مالک', 'در اختیار مستاجر')
CHOICES_DOC_STATUS = ('آزاد', 'در رهن', 'وکالتی', 'سایر')
CHOICES_CURRENT_STATUS = ('تخلیه', 'فعال', 'در حال بهره‌برداری', 'نیاز به تعمیر', 'سایر')
CHOICES_BUILDING_POS = ('نبش', 'میانی', 'گذری', 'بر اصلی', 'داخل کوچه', 'سایر')
CHOICES_USAGE = (
    'اداری', 'موقعیت اداری', 'تجاری', 'پزشکی', 'آموزشی',
    'صنعتی', 'خدماتی', 'ورزشی', 'فرهنگی', 'مذهبی', 'سایر',
)

COMMERCIAL_PROPERTY_TYPES = frozenset({'اداری', 'مغازه'})
RENT_DEAL_MODES = frozenset({'اجاره', 'رهن و اجاره'})
SALE_DEAL_MODES = frozenset({'فروش', 'پیش‌فروش'})

# کلیدهایی که با چک‌باکس امکانات هم‌پوشانی دارند — روی ذخیره به amenity_flags هم می‌روند
FEATURE_BOOL_TO_AMENITY = {
    'بالکن': 'بالکن',
    'استخر': 'استخر',
    'سونا': 'سونا',
    'جکوزی': 'جکوزی',
    'حیوان خانگی مجاز': 'حیوان خانگی مجاز',
    'بازسازی شده': 'بازسازی شده',
    'قابل معاوضه': 'قابل معاوضه',
    'نگهبانی': 'نگهبانی',
}

# این برچسب‌ها فقط از سوییچ‌های بخش ویژگی‌ها مدیریت می‌شوند (در چک‌باکس امکانات نشان داده نمی‌شوند)
FEATURE_MANAGED_AMENITY_LABELS = frozenset(FEATURE_BOOL_TO_AMENITY.values())


def seed_feature_toggles_from_amenities(
    feature_data: Optional[dict],
    amenity_labels: Sequence[str],
) -> Dict[str, str]:
    """اگر سوییچ ویژگی خالی باشد، از تیک‌های امکانات قدیمی مقداردهی می‌کند."""
    out = dict(feature_data or {})
    selected = {str(x).strip() for x in (amenity_labels or []) if str(x).strip()}
    for feat_key, amenity_label in FEATURE_BOOL_TO_AMENITY.items():
        current = _normalize_toggle(str(out.get(feat_key) or ''))
        if current in ('دارد', 'ندارد'):
            continue
        if amenity_label in selected:
            out[feat_key] = 'دارد'
    return out


def amenity_groups_excluding_feature_managed(
    groups_meta: Sequence[Dict[str, Any]],
    *,
    selected: set,
) -> List[Dict[str, Any]]:
    """گروه‌های چک‌باکس امکانات بدون موارد تکراری بخش ویژگی‌ها."""
    groups: List[Dict[str, Any]] = []
    for group in groups_meta:
        items = [
            {
                'label': label,
                'icon': icon,
                'checked': label in selected,
            }
            for label, icon in group['items']
            if label not in FEATURE_MANAGED_AMENITY_LABELS
        ]
        if not items:
            continue
        groups.append({
            'id': group['id'],
            'title': group['title'],
            'icon': group['icon'],
            'items': items,
        })
    return groups


def _int_choices(lo: int, hi: int) -> Tuple[str, ...]:
    return tuple(str(i) for i in range(lo, hi + 1))


def _field(
    key: str,
    *,
    widget: str,
    label: str = '',
    choices: Sequence[str] = (),
    min_v: int | None = None,
    max_v: int | None = None,
    hint: str = '',
    icon: str = 'fa-circle',
) -> Dict[str, Any]:
    return {
        'key': key,
        'label': label or key,
        'widget': widget,  # select | chips | toggle | number | date
        'choices': tuple(choices),
        'min': min_v,
        'max': max_v,
        'hint': hint,
        'icon': icon,
        'input_name': f'feat__{key}',
    }


# Catalog of all selectable fields (shared defs)
FIELDS: Dict[str, Dict[str, Any]] = {
    'تعداد واحد در طبقه': _field(
        'تعداد واحد در طبقه', widget='select', choices=_int_choices(1, 20),
        icon='fa-door-closed',
    ),
    'تعداد کل طبقات ساختمان': _field(
        'تعداد کل طبقات ساختمان', widget='select', choices=_int_choices(1, 30),
        icon='fa-building',
    ),
    'جهت ساختمان': _field(
        'جهت ساختمان', widget='chips', choices=CHOICES_DIRECTION, icon='fa-compass',
    ),
    'جنس کف': _field(
        'جنس کف', widget='chips', choices=CHOICES_FLOORING, icon='fa-border-all',
    ),
    'سرویس بهداشتی': _field(
        'سرویس بهداشتی', widget='chips', choices=CHOICES_BATHROOM, icon='fa-toilet',
    ),
    'بالکن': _field('بالکن', widget='toggle', icon='fa-fan'),
    'سرمایش': _field(
        'سرمایش', widget='chips', choices=CHOICES_COOLING, label='سیستم سرمایش',
        icon='fa-snowflake',
    ),
    'گرمایش': _field(
        'گرمایش', widget='chips', choices=CHOICES_HEATING, label='سیستم گرمایش',
        icon='fa-fire',
    ),
    'تأمین‌کننده آب گرم': _field(
        'تأمین‌کننده آب گرم', widget='chips', choices=CHOICES_HOT_WATER, icon='fa-shower',
    ),
    'حیوان خانگی مجاز': _field(
        'حیوان خانگی مجاز', widget='toggle', icon='fa-paw',
    ),
    'نوع آشپزخانه': _field(
        'نوع آشپزخانه', widget='chips', choices=CHOICES_KITCHEN, icon='fa-kitchen-set',
    ),
    'مناسب برای': _field(
        'مناسب برای', widget='chips', choices=CHOICES_SUITABLE, icon='fa-users',
    ),
    'جنس کابینت': _field(
        'جنس کابینت', widget='chips', choices=CHOICES_CABINET,         icon='fa-box-archive',
    ),
    'بازسازی شده': _field('بازسازی شده', widget='toggle', icon='fa-hammer'),
    'استخر': _field('استخر', widget='toggle', icon='fa-water-ladder'),
    'سونا': _field('سونا', widget='toggle', icon='fa-temperature-high'),
    'جکوزی': _field('جکوزی', widget='toggle', icon='fa-hot-tub-person'),
    'مبله': _field('مبله', widget='toggle', icon='fa-couch'),
    'حداقل مدت قرارداد': _field(
        'حداقل مدت قرارداد', widget='select', choices=_int_choices(1, 36),
        label='حداقل مدت قرارداد (ماه)', icon='fa-calendar',
    ),
    'تاریخ تخلیه': _field(
        'تاریخ تخلیه', widget='date', label='تاریخ تخلیه / آماده تحویل',
        hint='تاریخ تقریبی آماده‌بودن واحد — تقویم شمسی', icon='fa-calendar-check',
    ),
    'نوع سند': _field(
        'نوع سند', widget='chips', choices=CHOICES_DEED, icon='fa-file-contract',
    ),
    'نمای ساختمان': _field(
        'نمای ساختمان', widget='chips', choices=CHOICES_FACADE, icon='fa-building-columns',
    ),
    'وضعیت سکونت': _field(
        'وضعیت سکونت', widget='chips', choices=CHOICES_OCCUPANCY, icon='fa-house-user',
    ),
    'تعداد سرویس بهداشتی': _field(
        'تعداد سرویس بهداشتی', widget='select', choices=_int_choices(0, 10), icon='fa-toilet',
    ),
    'تعداد پارکینگ': _field(
        'تعداد پارکینگ', widget='select', choices=_int_choices(0, 10), icon='fa-square-parking',
    ),
    'تعداد حمام': _field(
        'تعداد حمام', widget='select', choices=_int_choices(0, 10), icon='fa-bath',
    ),
    'وام دارد': _field('وام دارد', widget='toggle', icon='fa-sack-dollar'),
    'قابل معاوضه': _field('قابل معاوضه', widget='toggle', icon='fa-right-left'),
    # Commercial
    'وضعیت سند': _field(
        'وضعیت سند', widget='chips', choices=CHOICES_DOC_STATUS, icon='fa-file-signature',
    ),
    'وضعیت فعلی': _field(
        'وضعیت فعلی', widget='chips', choices=CHOICES_CURRENT_STATUS, icon='fa-circle-info',
    ),
    'موقعیت ساختمان': _field(
        'موقعیت ساختمان', widget='chips', choices=CHOICES_BUILDING_POS, icon='fa-map-pin',
    ),
    'تعداد خط تلفن': _field(
        'تعداد خط تلفن', widget='select', choices=_int_choices(0, 20), icon='fa-phone',
    ),
    'اتاق مدیریت': _field('اتاق مدیریت', widget='toggle', icon='fa-user-tie'),
    'اتاق کنفرانس': _field('اتاق کنفرانس', widget='toggle', icon='fa-people-group'),
    'فضای پذیرش': _field(
        'فضای پذیرش', widget='toggle', label='فضای پذیرش / منشی', icon='fa-chair',
    ),
    'آبدارخانه': _field(
        'آبدارخانه', widget='toggle', label='آبدارخانه / آشپزخانه کوچک', icon='fa-mug-hot',
    ),
    'تابلوخور': _field('تابلوخور', widget='toggle', icon='fa-sign-hanging'),
    'ورودی مجزا': _field('ورودی مجزا', widget='toggle', icon='fa-door-open'),
    'نگهبانی': _field(
        'نگهبانی', widget='toggle', label='نگهبانی / لابی‌من', icon='fa-user-shield',
    ),
    'نوع کاربری ملک': _field(
        'نوع کاربری ملک', widget='chips', choices=CHOICES_USAGE, icon='fa-briefcase',
    ),
}
CRM_FEATURE_FORM_KEYS = frozenset(FIELDS.keys())

# Legacy skip for display merge with amenity text (bools still stored in feature_data)
CRM_FEATURE_SKIP_KEYS = frozenset(PROPERTY_BOOL_AMENITY_LABELS)

RENT_GROUPS: Tuple[Dict[str, Any], ...] = (
    {
        'id': 'rent_building',
        'title': 'ساختمان و طبقه',
        'icon': 'fa-building',
        'keys': (
            'تعداد واحد در طبقه', 'تعداد کل طبقات ساختمان', 'جهت ساختمان', 'بالکن',
        ),
    },
    {
        'id': 'rent_comfort',
        'title': 'رفاهی و تاسیسات',
        'icon': 'fa-couch',
        'keys': (
            'جنس کف', 'سرویس بهداشتی', 'سرمایش', 'گرمایش',
            'تأمین‌کننده آب گرم', 'نوع آشپزخانه', 'جنس کابینت',
        ),
    },
    {
        'id': 'rent_terms',
        'title': 'شرایط اجاره',
        'icon': 'fa-file-signature',
        'keys': (
            'مناسب برای', 'حیوان خانگی مجاز', 'مبله', 'بازسازی شده',
            'حداقل مدت قرارداد', 'تاریخ تخلیه',
        ),
    },
    {
        'id': 'rent_luxury',
        'title': 'امکانات لوکس',
        'icon': 'fa-spa',
        'keys': ('استخر', 'سونا', 'جکوزی'),
    },
)

SALE_GROUPS: Tuple[Dict[str, Any], ...] = (
    {
        'id': 'sale_building',
        'title': 'ساختمان و نما',
        'icon': 'fa-building',
        'keys': (
            'تعداد واحد در طبقه', 'تعداد کل طبقات ساختمان', 'جهت ساختمان',
            'بالکن', 'نمای ساختمان',
        ),
    },
    {
        'id': 'sale_comfort',
        'title': 'رفاهی و تاسیسات',
        'icon': 'fa-couch',
        'keys': (
            'جنس کف', 'سرویس بهداشتی', 'سرمایش', 'گرمایش',
            'تأمین‌کننده آب گرم', 'نوع آشپزخانه', 'جنس کابینت',
        ),
    },
    {
        'id': 'sale_counts',
        'title': 'تعداد و ظرفیت',
        'icon': 'fa-hashtag',
        'keys': ('تعداد پارکینگ', 'تعداد حمام', 'تعداد سرویس بهداشتی'),
    },
    {
        'id': 'sale_legal',
        'title': 'سند و وضعیت',
        'icon': 'fa-file-contract',
        'keys': (
            'نوع سند', 'وضعیت سکونت', 'بازسازی شده', 'وام دارد', 'قابل معاوضه',
        ),
    },
    {
        'id': 'sale_luxury',
        'title': 'امکانات لوکس',
        'icon': 'fa-spa',
        'keys': ('استخر', 'جکوزی', 'سونا'),
    },
)

COMMERCIAL_GROUPS: Tuple[Dict[str, Any], ...] = (
    {
        'id': 'com_status',
        'title': 'وضعیت و موقعیت',
        'icon': 'fa-briefcase',
        'keys': (
            'نوع کاربری ملک', 'وضعیت سند', 'وضعیت فعلی', 'موقعیت ساختمان',
            'تعداد کل طبقات ساختمان',
        ),
    },
    {
        'id': 'com_hvac',
        'title': 'تاسیسات',
        'icon': 'fa-temperature-half',
        'keys': ('گرمایش', 'سرمایش', 'تعداد سرویس بهداشتی', 'تعداد خط تلفن'),
    },
    {
        'id': 'com_spaces',
        'title': 'فضاها و امکانات',
        'icon': 'fa-door-open',
        'keys': (
            'اتاق مدیریت', 'اتاق کنفرانس', 'فضای پذیرش', 'آبدارخانه',
            'تابلوخور', 'ورودی مجزا', 'نگهبانی',
        ),
    },
)

PROFILES: Dict[str, Dict[str, Any]] = {
    'rent': {
        'id': 'rent',
        'title': 'ویژگی‌های اجاره',
        'hint': 'انتخاب سریع — مخصوص رهن و اجاره',
        'groups': RENT_GROUPS,
    },
    'sale': {
        'id': 'sale',
        'title': 'سایر ویژگی‌ها و امکانات',
        'hint': 'انتخاب سریع — مخصوص فروش',
        'groups': SALE_GROUPS,
    },
    'commercial': {
        'id': 'commercial',
        'title': 'ویژگی‌های اداری / تجاری',
        'hint': 'انتخاب سریع — مخصوص ملک اداری و تجاری',
        'groups': COMMERCIAL_GROUPS,
    },
}


def resolve_feature_profile(deal_mode: str = '', property_type: str = '') -> str:
    """پروفایل فرم ویژگی بر اساس نوع ملک و معامله."""
    pt = (property_type or '').strip()
    dm = (deal_mode or '').strip()
    if pt in COMMERCIAL_PROPERTY_TYPES:
        return 'commercial'
    if dm in RENT_DEAL_MODES:
        return 'rent'
    return 'sale'


def profile_keys(profile_id: str) -> frozenset:
    profile = PROFILES.get(profile_id) or PROFILES['sale']
    keys: List[str] = []
    for group in profile['groups']:
        keys.extend(group['keys'])
    return frozenset(keys)


def extract_feature_data_from_listing_data(data: Optional[dict]) -> Dict[str, str]:
    """کپی کلیدهای شناخته‌شده از data آگهی."""
    raw = data or {}
    out: Dict[str, str] = {}
    for key in CRM_FEATURE_FORM_KEYS:
        val = raw.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text and text.lower() not in ('nan', 'none', '-', 'null'):
            out[key] = text
    # aliases
    aliases = {
        'سیستم سرمایش': 'سرمایش',
        'سیستم گرمایش': 'گرمایش',
        'تاریخ تخلیه یا آماده تحویل': 'تاریخ تخلیه',
        'فضای پذیرش/منشی': 'فضای پذیرش',
        'آبدارخانه/آشپزخانه کوچک': 'آبدارخانه',
        'نگهبانی/لابی من': 'نگهبانی',
        'نگهبانی/لابی‌من': 'نگهبانی',
    }
    for src, dest in aliases.items():
        if dest in out:
            continue
        val = raw.get(src)
        if val is None:
            continue
        text = str(val).strip()
        if text and text.lower() not in ('nan', 'none', '-', 'null'):
            out[dest] = text
    return out


def _normalize_toggle(value: str) -> str:
    v = (value or '').strip().lower()
    if v in ('1', 'true', 'yes', 'on', 'دارد', 'بله', 'هست'):
        return 'دارد'
    if v in ('0', 'false', 'no', 'off', 'ندارد', 'خیر', 'نیست'):
        return 'ندارد'
    return (value or '').strip()


def normalize_feature_date_value(value: str) -> str:
    """نرمال‌سازی تاریخ ویژگی به شمسی با ارقام فارسی (مثلاً ۱۴۰۵/۰۴/۲۷)."""
    raw = (value or '').strip()
    if not raw or raw in ('-', '—'):
        return ''
    from workspace.services.jalali_input import (
        format_jalali_date,
        parse_jalali_date_string,
        to_persian_digits,
    )
    parsed = parse_jalali_date_string(raw)
    if parsed:
        return to_persian_digits(format_jalali_date(parsed))
    return raw


def format_feature_date_display(value: str) -> str:
    """نمایش تاریخ ذخیره‌شده در فیلد فرم (شمسی)."""
    return normalize_feature_date_value(value)


def parse_feature_data_from_post(
    post,
    *,
    deal_mode: str = '',
    property_type: str = '',
    existing: Optional[dict] = None,
) -> Dict[str, str]:
    """
    خواندن feat__* از POST و ادغام با feature_data قبلی.
    فقط کلیدهای پروفایل فعال از POST بازنویسی می‌شوند.
    """
    import json

    profile_id = resolve_feature_profile(deal_mode, property_type)
    active_keys = profile_keys(profile_id)
    prev = dict(existing or {})

    # drop previous values for active profile keys, then refill from POST
    out = {k: v for k, v in prev.items() if k not in active_keys}

    getlist = getattr(post, 'getlist', None)
    keys = list(post.keys()) if hasattr(post, 'keys') else []
    has_feat_fields = any(str(k).startswith('feat__') for k in keys)

    posted: Dict[str, str] = {}
    if has_feat_fields:
        for key in keys:
            if not str(key).startswith('feat__'):
                continue
            feat_key = str(key)[6:].strip()
            if feat_key not in CRM_FEATURE_FORM_KEYS:
                continue
            if callable(getlist):
                vals = getlist(key)
                text = str(vals[0] if vals else '').strip()
            else:
                text = str(post.get(key) or '').strip()
            meta = FIELDS.get(feat_key) or {}
            if meta.get('widget') == 'toggle':
                # unchecked toggles don't appear — handled below
                if text:
                    posted[feat_key] = _normalize_toggle(text)
            elif meta.get('widget') == 'date':
                if text:
                    posted[feat_key] = normalize_feature_date_value(text)
            elif text:
                posted[feat_key] = text
        # toggles in active profile: missing = ندارد when form submitted with profile marker
        if post.get('feat_profile') == profile_id:
            for key in active_keys:
                if (FIELDS.get(key) or {}).get('widget') == 'toggle' and key not in posted:
                    posted[key] = 'ندارد'
    else:
        raw_json = (post.get('features_json') or '').strip() if hasattr(post, 'get') else ''
        if raw_json:
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    for key, val in parsed.items():
                        k = str(key).strip()
                        if k not in CRM_FEATURE_FORM_KEYS:
                            continue
                        text = str(val).strip() if val is not None else ''
                        if text:
                            posted[k] = text
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

    for key, val in posted.items():
        if key in active_keys or not has_feat_fields:
            out[key] = val
    return out


def amenity_labels_from_feature_data(feature_data: Optional[dict]) -> List[str]:
    """برچسب‌های امکانات بولین برای همگام‌سازی با amenity_flags."""
    data = feature_data or {}
    labels: List[str] = []
    for feat_key, amenity_label in FEATURE_BOOL_TO_AMENITY.items():
        val = _normalize_toggle(str(data.get(feat_key) or ''))
        if val == 'دارد' and amenity_label not in labels:
            labels.append(amenity_label)
    return labels


def sync_total_floors_from_feature_data(feature_data: Optional[dict]) -> Optional[int]:
    raw = (feature_data or {}).get('تعداد کل طبقات ساختمان')
    if raw is None or str(raw).strip() == '':
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def feature_form_groups_with_values(
    feature_data: Optional[dict] = None,
    *,
    deal_mode: str = '',
    property_type: str = '',
    profile_id: str = '',
) -> List[Dict[str, Any]]:
    """گروه‌های پروفایل با مقدار و متادیتای ویجت."""
    pid = profile_id or resolve_feature_profile(deal_mode, property_type)
    profile = PROFILES.get(pid) or PROFILES['sale']
    data = feature_data or {}
    groups: List[Dict[str, Any]] = []
    for group in profile['groups']:
        items = []
        for key in group['keys']:
            meta = dict(FIELDS[key])
            raw_val = str(data.get(key) or '').strip()
            if meta['widget'] == 'toggle':
                meta['checked'] = _normalize_toggle(raw_val) == 'دارد'
                meta['value'] = 'دارد' if meta['checked'] else 'ندارد'
            elif meta['widget'] == 'date':
                meta['value'] = format_feature_date_display(raw_val)
                meta['checked'] = False
            else:
                meta['value'] = raw_val
                meta['checked'] = False
            items.append(meta)
        groups.append({
            'id': group['id'],
            'title': group['title'],
            'icon': group['icon'],
            'items': items,
        })
    return groups


def feature_form_context(
    feature_data: Optional[dict] = None,
    *,
    deal_mode: str = '',
    property_type: str = '',
) -> Dict[str, Any]:
    profile_id = resolve_feature_profile(deal_mode, property_type)
    profile = PROFILES[profile_id]
    data = feature_data or {}
    return {
        'profile_id': profile_id,
        'title': profile['title'],
        'hint': profile['hint'],
        'groups': feature_form_groups_with_values(data, profile_id=profile_id),
        'all_profiles': [
            {
                'id': pid,
                'title': p['title'],
                'hint': p['hint'],
                'groups': feature_form_groups_with_values(data, profile_id=pid),
            }
            for pid, p in PROFILES.items()
        ],
    }


def feature_profile_groups_from_data(feature_data: Optional[dict]) -> List[Dict[str, Any]]:
    """گروه‌های نمایش پرونده از feature_data."""
    data = feature_data or {}
    # Prefer listing-style groups for known keys; append extras
    used = set()
    groups: List[Dict[str, Any]] = []
    for group in LISTING_FEATURE_GROUPS:
        items: List[Dict[str, Any]] = []
        for key in group['keys']:
            val = data.get(key)
            if val is None or not str(val).strip():
                continue
            used.add(key)
            display_val = str(val).strip()
            if (FIELDS.get(key) or {}).get('widget') == 'date':
                display_val = format_feature_date_display(display_val) or display_val
            items.append({
                'key': key,
                'label': (FIELDS.get(key) or {}).get('label') or key,
                'value': display_val,
                'state': 'neutral',
                'known': True,
            })
        if items:
            groups.append({
                'id': group['id'],
                'title': group['title'],
                'icon': group['icon'],
                'accent': group.get('accent', ''),
                'items': items,
            })
    extra_items = []
    for key, val in data.items():
        if key in used or not str(val or '').strip():
            continue
        extra_items.append({
            'key': key,
            'label': (FIELDS.get(key) or {}).get('label') or key,
            'value': str(val).strip(),
            'state': 'neutral',
            'known': True,
        })
    if extra_items:
        groups.append({
            'id': 'crm_extra',
            'title': 'سایر ویژگی‌ها',
            'icon': 'fa-list',
            'accent': 'slate',
            'items': extra_items,
        })
    return groups
