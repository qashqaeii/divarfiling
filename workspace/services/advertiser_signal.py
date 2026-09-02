"""تشخیص سیگنال آگهی‌دهنده — wrapper جنگو روی ماژول مشترک advertiser_signal."""
from __future__ import annotations

from typing import Dict

from workspace.services.advertiser_signal_loader import ensure_advertiser_signal_importable

ensure_advertiser_signal_importable()

from advertiser_signal import (  # noqa: E402
    ADVERTISER_DETECTOR_VERSION,
    ADVERTISER_FILTER_ALL,
    ADVERTISER_FILTER_CONSULTANT,
    ADVERTISER_FILTER_GENUINE,
    ADVERTISER_FILTER_LABELS,
    ADVERTISER_FILTER_PERSONAL,
    ADVERTISER_FILTER_VALUES,
    ADVERTISER_SIGNAL_CONSULTANT,
    ADVERTISER_SIGNAL_DISGUISED,
    ADVERTISER_SIGNAL_GENUINE_PERSONAL,
    ADVERTISER_SIGNAL_LABELS,
    analyze_advertiser_signal,
    advertiser_display_label_for_row,
    advertiser_signal_label,
    count_signals,
    detect_advertiser_signal,
    detect_row_advertiser_signal,
    extract_consultant_name,
    has_disguised_consultant_markers,
    has_owner_markers,
    is_official_consultant,
    is_personal_category,
    normalize_ad_text,
    normalize_business_type_for_storage,
    normalize_filter_value,
    row_advertiser_fields,
    row_matches_advertiser_filter,
)

# توابع داخلی که تست‌ها / کد قدیمی ممکن است نیاز داشته باشند
from advertiser_signal import _description_from_data  # noqa: E402

__all__ = [
    'ADVERTISER_FILTER_ALL',
    'ADVERTISER_FILTER_CONSULTANT',
    'ADVERTISER_FILTER_GENUINE',
    'ADVERTISER_FILTER_LABELS',
    'ADVERTISER_FILTER_PERSONAL',
    'ADVERTISER_FILTER_VALUES',
    'ADVERTISER_SIGNAL_CONSULTANT',
    'ADVERTISER_SIGNAL_DISGUISED',
    'ADVERTISER_SIGNAL_GENUINE_PERSONAL',
    'ADVERTISER_SIGNAL_LABELS',
    'analyze_advertiser_signal',
    'advertiser_display_label_for_row',
    'advertiser_signal_label',
    'count_listings_by_advertiser_display',
    'count_signals',
    'detect_advertiser_signal',
    'detect_row_advertiser_signal',
    'disguised_consultant_listing_ids',
    'extract_consultant_name',
    'has_disguised_consultant_markers',
    'has_owner_markers',
    'is_official_consultant',
    'is_personal_category',
    'listing_advertiser_display',
    'listing_advertiser_signal',
    'normalize_ad_text',
    'normalize_business_type_for_storage',
    'normalize_filter_value',
    'property_advertiser_display',
    'row_advertiser_fields',
    'row_matches_advertiser_filter',
]


def listing_advertiser_signal(listing) -> str:
    """همیشه از متن آگهی تشخیص می‌دهد — مقدار ذخیره‌شده ممکن است قدیمی باشد."""
    data = getattr(listing, 'data', None) or {}
    description = getattr(listing, 'description', '') or ''
    if not str(description).strip():
        description = _description_from_data(data)
    return detect_advertiser_signal(
        title=getattr(listing, 'title', '') or '',
        description=description,
        business_type=getattr(listing, 'business_type', '') or '',
        data=data,
    )


def property_advertiser_display(business_type: str = '') -> Dict[str, str]:
    """برچسب نوع آگهی‌دهنده برای فایل‌های شخصی CRM (فقط business_type)."""
    raw = (business_type or '').strip()
    lowered = raw.lower().replace('\u200c', '')
    if lowered == 'مالک':
        return {
            'signal': ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            'label': 'مالک',
            'short_label': 'مالک',
            'pill_class': 'mk-pub-pill--genuine',
            'tag_class': 'mk-adv-tag--genuine',
            'icon': 'fa-user-check',
            'title': 'آگهی مالک',
        }
    if (
        'مشاور' in lowered
        or lowered in ('consultant', 'premium-panel', 'premium', 'business', 'بنگاه', 'agency')
    ):
        return {
            'signal': ADVERTISER_SIGNAL_CONSULTANT,
            'label': 'مشاور',
            'short_label': 'مشاور',
            'pill_class': 'mk-pub-pill--consultant',
            'tag_class': 'mk-adv-tag--consultant',
            'icon': 'fa-building',
            'title': 'مشاور / آژانس املاک',
        }
    if raw:
        return {
            'signal': '',
            'label': raw,
            'short_label': raw,
            'pill_class': 'mk-pub-pill--personal',
            'tag_class': 'mk-adv-tag--personal',
            'icon': 'fa-user',
            'title': raw,
        }
    return {
        'signal': '',
        'label': 'شخصی',
        'short_label': 'شخصی',
        'pill_class': 'mk-pub-pill--personal',
        'tag_class': 'mk-adv-tag--personal',
        'icon': 'fa-user',
        'title': 'آگهی شخصی',
    }


def listing_advertiser_display(listing) -> Dict[str, str]:
    """برچسب و استایل نمایش نوع آگهی‌دهنده برای جدول، هدر و اطلاعات تکمیلی."""
    signal = listing_advertiser_signal(listing)
    label = advertiser_signal_label(signal)

    if signal == ADVERTISER_SIGNAL_GENUINE_PERSONAL:
        return {
            'signal': signal,
            'label': label,
            'short_label': 'مالک',
            'pill_class': 'mk-pub-pill--genuine',
            'tag_class': 'mk-adv-tag--genuine',
            'icon': 'fa-user-check',
            'title': 'آگهی شخصی بدون نشانه مشاور — مالک واقعی',
        }
    if signal == ADVERTISER_SIGNAL_DISGUISED:
        return {
            'signal': signal,
            'label': label,
            'short_label': 'مشاور پنهان',
            'pill_class': 'mk-pub-pill--disguised',
            'tag_class': 'mk-adv-tag--disguised',
            'icon': 'fa-user-secret',
            'title': 'مشاور پنهان — آگهی با برچسب شخصی اما نشانه‌های مشاور در متن',
        }
    if signal == ADVERTISER_SIGNAL_CONSULTANT or is_official_consultant(
        getattr(listing, 'business_type', '') or '',
        getattr(listing, 'data', None) or {},
    ):
        return {
            'signal': ADVERTISER_SIGNAL_CONSULTANT,
            'label': 'مشاور',
            'short_label': 'مشاور',
            'pill_class': 'mk-pub-pill--consultant',
            'tag_class': 'mk-adv-tag--consultant',
            'icon': 'fa-building',
            'title': 'مشاور / آژانس املاک',
        }
    return {
        'signal': signal or '',
        'label': 'شخصی',
        'short_label': 'شخصی',
        'pill_class': 'mk-pub-pill--personal',
        'tag_class': 'mk-adv-tag--personal',
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


def disguised_consultant_listing_ids(qs) -> list[int]:
    """شناسه آگهی‌های مشاور پنهان — هم‌راستا با count_listings_by_advertiser_display."""
    ids: list[int] = []
    for listing in qs.only(
        'id', 'advertiser_signal', 'title', 'description', 'business_type', 'data',
    ).iterator():
        if listing_advertiser_signal(listing) == ADVERTISER_SIGNAL_DISGUISED:
            ids.append(listing.id)
    return ids
