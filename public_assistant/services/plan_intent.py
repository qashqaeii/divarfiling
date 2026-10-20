"""شناسایی سؤال‌های قیمت/انتخاب اشتراک — جدا از قیمت‌گذاری ملک."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from public_assistant.services.persian_text import normalize_persian

if TYPE_CHECKING:
    from public_assistant.models import PublicChatSession

_PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')

_SUBSCRIPTION_STRONG = (
    'لایسنس',
    'license',
    'اشتراک',
    'پلن',
    'plan',
    'خرید اشتراک',
    'تمدید اشتراک',
    'خرید لایسنس',
    'هزینه اشتراک',
    'قیمت اشتراک',
    'قیمت لایسنس',
    'قیمت پلن',
    'نسخه آزمایشی',
    'پلن آزمایشی',
    'آزمایشی خرید',
)

_SUBSCRIPTION_MEDIUM = (
    'چنده',
    'هزینه',
    'قیمت',
    'خرید',
    'تمدید',
    'ارزون',
    'ارزان',
    'به صرفه',
    'به‌صرفه',
    'کدوم بهتر',
    'کدام بهتر',
    'ماهانه',
    'سه ماهه',
    'سه‌ماهه',
    'سالانه',
    'یکساله',
    'یک ساله',
    'yearly',
    'monthly',
    'quarterly',
    'trial',
    'آزمایشی',
    'هدیه',
    'هفت روز',
    'هفت‌روزه',
    'رایگان ثبت',
)

_PROPERTY_STRONG = (
    'ملک',
    'آگهی',
    'فایل شخصی',
    'قیمت گذاری فایل',
    'قیمت‌گذاری فایل',
    'قیمت ملک',
    'قیمت این ملک',
    'متری',
    'متراژ',
    'ودیعه',
    'اجاره ماهانه',
    'مالک',
    'فروشنده',
    'خریدار ملک',
    'listing',
    'متر',
)

_TEAM_PATTERNS = (
    re.compile(r'(\d+)\s*(?:نفر|مشاور|نفره|نفرای|نفری)'),
    re.compile(r'ما\s*(\d+)\s*نفر'),
    re.compile(r'تیم\s*(\d+)'),
)

_AGENCY_HINTS = ('آژانس', 'تیم', 'دفتر', 'چند مشاور', 'گروهی', 'مدیر آژانس')
_SOLO_HINTS = ('تنها', 'تک نفر', 'تک‌نفر', 'مستقل', 'alone', 'solo', 'خودم', 'تنهایی')
_NEWBIE_HINTS = ('تازه شروع', 'تازه کار', 'جدید شدم', 'شروع کردم', 'مبتدی')

_DURATION_MAP = {
    'monthly': ('ماهانه', 'یک ماهه', 'یک‌ماهه', '۱ ماه', '1 ماه', 'monthly'),
    'quarterly': ('سه ماهه', 'سه‌ماهه', '۳ ماه', '3 ماه', '90 روز', 'quarterly'),
    'yearly': ('سالانه', 'یکساله', 'یک ساله', 'یک‌ساله', '۱۲ ماه', '12 ماه', 'yearly'),
    'daily': ('هفت روز', 'هفت‌روزه', '۷ روز', '7 روز', 'آزمایشی', 'trial', 'daily'),
}


@dataclass
class SubscriptionQueryContext:
    is_subscription: bool
    is_property_listing: bool
    wants_price: bool
    wants_comparison: bool
    wants_recommendation: bool
    wants_trial_info: bool
    wants_welcome_gift: bool
    wants_features: bool
    team_size: int | None
    solo_advisor: bool
    agency_context: bool
    newbie: bool
    duration: str | None
    raw_message: str


def _to_ascii_digits(text: str) -> str:
    return text.translate(_PERSIAN_DIGITS)


def extract_team_size(text: str) -> int | None:
    norm = _to_ascii_digits(normalize_persian(text))
    for pat in _TEAM_PATTERNS:
        m = pat.search(norm)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 100:
                return n
    return None


def extract_duration(text: str) -> str | None:
    norm = normalize_persian(text)
    for key, hints in _DURATION_MAP.items():
        if any(h in norm for h in hints):
            return key
    return None


def _session_context_text(session: PublicChatSession | None) -> str:
    if not session:
        return ''
    from public_assistant.models import PublicChatMessage

    parts: list[str] = []
    for m in session.messages.order_by('-created_at')[:6]:
        if m.role == PublicChatMessage.ROLE_USER:
            parts.append(m.content)
    return ' '.join(parts)


def _is_share_file_context(norm: str) -> bool:
    return 'اشتراک' in norm and any(
        w in norm for w in ('فایل', 'لینک', 'مشتری', 'عمومی', 'share', 'بفرست', 'ارسال')
    )


def newbie_hint(text: str) -> bool:
    norm = normalize_persian(text)
    return any(h in norm for h in _NEWBIE_HINTS)


def analyze_subscription_query(
    message: str,
    session: PublicChatSession | None = None,
) -> SubscriptionQueryContext:
    norm = normalize_persian(message)
    history = _session_context_text(session)
    combined = normalize_persian(f'{history} {message}')

    if _is_share_file_context(norm):
        return SubscriptionQueryContext(
            is_subscription=False,
            is_property_listing=False,
            wants_price=False,
            wants_comparison=False,
            wants_recommendation=False,
            wants_trial_info=False,
            wants_welcome_gift=False,
            wants_features=False,
            team_size=None,
            solo_advisor=False,
            agency_context=False,
            newbie=False,
            duration=None,
            raw_message=message,
        )

    property_score = sum(1 for h in _PROPERTY_STRONG if h in norm)
    subscription_score = sum(1 for h in _SUBSCRIPTION_STRONG if h in norm)
    if any(h in norm for h in _SUBSCRIPTION_MEDIUM):
        subscription_score += 1

    agency_context = any(h in combined for h in _AGENCY_HINTS)
    team_size = extract_team_size(combined)
    if team_size and team_size >= 2:
        agency_context = True
        subscription_score += 2

    solo = any(h in combined for h in _SOLO_HINTS) or (
        'تنها' in combined and 'کار' in combined
    )
    if solo:
        subscription_score += 1

    has_subscription_anchor = any(h in norm for h in _SUBSCRIPTION_STRONG)
    if property_score >= 1 and not has_subscription_anchor:
        is_property = True
    elif property_score >= 2 and subscription_score < 2:
        is_property = True
    else:
        is_property = False

    is_subscription = subscription_score >= 1 and not is_property
    if team_size and team_size >= 2 and not is_property:
        is_subscription = True

    wants_price = any(w in norm for w in ('قیمت', 'چنده', 'هزینه', 'چقدر', 'مبلغ', 'تومان'))
    wants_comparison = any(
        w in norm
        for w in ('بهتر', 'بهتره', 'به صرفه', 'به‌صرفه', 'مقایسه', 'فرق', 'تفاوت')
    ) or ' یا ' in f' {norm} '
    wants_recommendation = any(
        w in norm for w in ('پیشنهاد', 'بخرم', 'مناسب', 'کدوم', 'کدام', 'انتخاب', 'بهتره', 'بهتر است')
    )
    wants_trial_info = any(w in norm for w in ('آزمایشی', 'trial', 'پلن آزمایشی')) and not any(
        w in norm for w in ('هدیه', 'خوش آمد', 'ثبت نام', 'ثبت‌نام', 'رایگان')
    )
    wants_welcome_gift = any(
        w in norm for w in ('هدیه', 'خوش آمد', 'خوش‌آمد', 'رایگان ثبت', 'هفت روز رایگان', 'هفته رایگان')
    )
    wants_features = any(
        w in norm for w in ('crm', 'هوش', 'ai', 'امکانات', 'قابلیت', 'شامل', 'دارد')
    ) and is_subscription

    duration = extract_duration(combined)

    if not is_property and (wants_price or wants_comparison or wants_recommendation):
        is_subscription = is_subscription or subscription_score >= 1

    return SubscriptionQueryContext(
        is_subscription=is_subscription,
        is_property_listing=is_property,
        wants_price=wants_price,
        wants_comparison=wants_comparison,
        wants_recommendation=wants_recommendation or newbie_hint(combined),
        wants_trial_info=wants_trial_info,
        wants_welcome_gift=wants_welcome_gift,
        wants_features=wants_features,
        team_size=team_size,
        solo_advisor=solo,
        agency_context=agency_context,
        newbie=newbie_hint(combined),
        duration=duration,
        raw_message=message,
    )
