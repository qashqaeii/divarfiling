"""تشخیص سیگنال آگهی‌دهنده — مالک واقعی در برابر مشاور پنهان در پوشش شخصی."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, Optional

from workspace.services.columns import extract_consultant_name

ADVERTISER_SIGNAL_CONSULTANT = 'consultant'
ADVERTISER_SIGNAL_GENUINE_PERSONAL = 'genuine_personal'
ADVERTISER_SIGNAL_DISGUISED = 'disguised_consultant'

ADVERTISER_SIGNAL_LABELS = {
    ADVERTISER_SIGNAL_CONSULTANT: 'مشاور',
    ADVERTISER_SIGNAL_GENUINE_PERSONAL: 'مالک واقعی',
    ADVERTISER_SIGNAL_DISGUISED: 'مشاور پنهان',
}

_OFFICIAL_CONSULTANT_TYPES = {
    'premium-panel', 'premium_panel', 'business', 'consultant', 'agency',
    'بنگاه', 'مشاور', 'آژانس',
}

# عباراتی که معمولاً در آگهی‌های مشاور/املاک (حتی با برچسب شخصی) دیده می‌شوند.
_DISGUISED_CONSULTANT_PHRASES: tuple[str, ...] = (
    'مشاور شما',
    'مشاور شما در منطقه',
    'مشاور املاک',
    'مشاور ملکی',
    'مشاور ملک',
    'مشاور فروش',
    'مشاورین املاک',
    'گروه مشاورین املاک',
    'مشاوره املاک',
    'کارشناس شما در منطقه',
    'کارشناس شما',
    'کارشناس املاک',
    'فایل شخصی',
    'فایل املاک',
    'لطفا املاک تماس نگیرد',
    'لطفاً املاک تماس نگیرد',
    'املاک تماس نگیرید',
    'املاک تماس نگیر',
    'تماس املاک',
    'لطفا همکار های عزیز تماس نگیرید',
    'لطفاً همکار های عزیز تماس نگیرید',
    'همکار های عزیز تماس نگیرید',
    'همکارهای عزیز تماس نگیرید',
    'همکار گرامی تماس نگیرید',
    'همکاران گرامی تماس نگیرید',
    'همکار تماس نگیرید',
    'تماس همکاران',
    'آگهی مشابه',
    'بنگاه املاک',
    'آژانس املاک',
    'دفتر املاک',
    'پنل املاک',
    'فقط خریدار واقعی',
    'فقط مستاجر',
    'فقط مستاجران',
    'real estate',
    'realtor',
)

# «املاک» به‌تنهایی گسترده است؛ فقط در ترکیب‌های مشکوک بررسی می‌شود.
_DISGUISED_AMLAK_CONTEXTS: tuple[str, ...] = (
    'املاک تماس',
    'تماس املاک',
    'فایل املاک',
    'پنل املاک',
    'همکار املاک',
    'لطفا املاک',
    'لطفاً املاک',
)

_ZWNJ_RE = re.compile(r'[\u200c\u200d\u200e\u200f\ufeff]')
_WS_RE = re.compile(r'\s+')


def normalize_ad_text(text: str) -> str:
    """یکسان‌سازی متن فارسی/عربی برای جستجوی الگو."""
    if not text:
        return ''
    normalized = unicodedata.normalize('NFKC', str(text))
    normalized = normalized.replace('ي', 'ی').replace('ك', 'ک').replace('‌', ' ')
    normalized = _ZWNJ_RE.sub(' ', normalized)
    normalized = _WS_RE.sub(' ', normalized).strip().lower()
    return normalized


def _normalized_phrases(phrases: Iterable[str]) -> tuple[str, ...]:
    return tuple(normalize_ad_text(p) for p in phrases if p)


_NORMALIZED_DISGUISED_PHRASES = _normalized_phrases(_DISGUISED_CONSULTANT_PHRASES)
_NORMALIZED_AMLAK_CONTEXTS = _normalized_phrases(_DISGUISED_AMLAK_CONTEXTS)


def is_official_consultant(business_type: str = '', data: Optional[Dict[str, Any]] = None) -> bool:
    bt = normalize_ad_text(business_type or '')
    if bt in _OFFICIAL_CONSULTANT_TYPES:
        return True
    if 'premium' in bt:
        return True
    if 'مشاور' in bt or 'آژانس' in bt or 'business' in bt or 'agency' in bt:
        return True
    if extract_consultant_name(data):
        return True
    return False


def is_personal_category(business_type: str = '', data: Optional[Dict[str, Any]] = None) -> bool:
    if is_official_consultant(business_type, data):
        return False
    bt = normalize_ad_text(business_type or '')
    if not bt:
        return True
    if bt in ('personal', 'شخصی', 'private'):
        return True
    return 'personal' in bt or bt == 'شخصی'


def has_disguised_consultant_markers(
    title: str = '',
    description: str = '',
    data: Optional[Dict[str, Any]] = None,
) -> bool:
    title_norm = normalize_ad_text(title)
    desc_norm = normalize_ad_text(description)
    combined = f'{title_norm} {desc_norm}'.strip()
    if not combined:
        return False

    for phrase in _NORMALIZED_DISGUISED_PHRASES:
        if phrase and phrase in combined:
            return True

    for ctx in _NORMALIZED_AMLAK_CONTEXTS:
        if ctx and ctx in combined:
            return True

    if data:
        for key, val in data.items():
            key_norm = normalize_ad_text(str(key))
            if 'مشاور' not in key_norm and 'consultant' not in key_norm:
                continue
            val_norm = normalize_ad_text(str(val or ''))
            if val_norm and val_norm not in ('-', '—', 'nan', 'none'):
                return True

    return False


def detect_advertiser_signal(
    *,
    title: str = '',
    description: str = '',
    business_type: str = '',
    data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    consultant — مشاور رسمی
    disguised_consultant — شخصی در دیوار اما نشانه‌های مشاور/املاک در متن
    genuine_personal — شخصی واقعی بدون نشانه مشاور (ارزشمند برای تماس)
    """
    if is_official_consultant(business_type, data):
        return ADVERTISER_SIGNAL_CONSULTANT
    if not is_personal_category(business_type, data):
        return ''
    if has_disguised_consultant_markers(title, description, data):
        return ADVERTISER_SIGNAL_DISGUISED
    return ADVERTISER_SIGNAL_GENUINE_PERSONAL


def advertiser_signal_label(signal: str) -> str:
    return ADVERTISER_SIGNAL_LABELS.get(signal or '', '')


def count_signals(signals: Iterable[str]) -> Dict[str, int]:
    counts = {
        ADVERTISER_SIGNAL_GENUINE_PERSONAL: 0,
        ADVERTISER_SIGNAL_DISGUISED: 0,
        ADVERTISER_SIGNAL_CONSULTANT: 0,
    }
    for signal in signals:
        if signal in counts:
            counts[signal] += 1
    return counts


def listing_advertiser_signal(listing) -> str:
    stored = str(getattr(listing, 'advertiser_signal', '') or '').strip()
    if stored:
        return stored
    return detect_advertiser_signal(
        title=getattr(listing, 'title', '') or '',
        description=getattr(listing, 'description', '') or '',
        business_type=getattr(listing, 'business_type', '') or '',
        data=getattr(listing, 'data', None) or {},
    )


def listing_advertiser_display(listing) -> Dict[str, str]:
    """برچسب و استایل نمایش نوع آگهی‌دهنده برای جدول، هدر و اطلاعات تکمیلی."""
    signal = listing_advertiser_signal(listing)
    label = advertiser_signal_label(signal)

    if signal == ADVERTISER_SIGNAL_GENUINE_PERSONAL:
        return {
            'signal': signal,
            'label': label,
            'pill_class': 'mk-pub-pill--genuine',
            'icon': 'fa-user-check',
            'title': 'آگهی شخصی بدون نشانه مشاور — مالک واقعی',
        }
    if signal == ADVERTISER_SIGNAL_DISGUISED:
        return {
            'signal': signal,
            'label': label,
            'pill_class': 'mk-pub-pill--disguised',
            'icon': 'fa-user-secret',
            'title': 'آگهی با برچسب شخصی اما نشانه‌های مشاور در متن',
        }
    if signal == ADVERTISER_SIGNAL_CONSULTANT or is_official_consultant(
        getattr(listing, 'business_type', '') or '',
        getattr(listing, 'data', None) or {},
    ):
        return {
            'signal': ADVERTISER_SIGNAL_CONSULTANT,
            'label': 'مشاور',
            'pill_class': 'mk-pub-pill--consultant',
            'icon': 'fa-building',
            'title': 'مشاور / آژانس املاک',
        }
    return {
        'signal': signal or '',
        'label': 'شخصی',
        'pill_class': 'mk-pub-pill--personal',
        'icon': 'fa-user',
        'title': 'آگهی شخصی',
    }


def count_listings_by_advertiser_display(qs) -> Dict[str, int]:
    counts = {
        ADVERTISER_SIGNAL_GENUINE_PERSONAL: 0,
        ADVERTISER_SIGNAL_DISGUISED: 0,
        ADVERTISER_SIGNAL_CONSULTANT: 0,
        'personal_other': 0,
    }
    for listing in qs.only(
        'advertiser_signal', 'title', 'description', 'business_type', 'data',
    ).iterator():
        signal = listing_advertiser_signal(listing)
        if signal == ADVERTISER_SIGNAL_GENUINE_PERSONAL:
            counts[ADVERTISER_SIGNAL_GENUINE_PERSONAL] += 1
        elif signal == ADVERTISER_SIGNAL_DISGUISED:
            counts[ADVERTISER_SIGNAL_DISGUISED] += 1
        elif signal == ADVERTISER_SIGNAL_CONSULTANT:
            counts[ADVERTISER_SIGNAL_CONSULTANT] += 1
        else:
            counts['personal_other'] += 1
    return counts
