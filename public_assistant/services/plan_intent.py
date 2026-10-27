"""شناسایی سؤال‌های قیمت/انتخاب اشتراک — جدا از قیمت‌گذاری ملک."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from public_assistant.services.persian_text import normalize_persian

if TYPE_CHECKING:
    from public_assistant.models import PublicChatSession

_PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
_ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_WORD_NUMBERS = {
    'یک': 1,
    'دو': 2,
    'سه': 3,
    'چهار': 4,
    'چار': 4,
    'پنج': 5,
    'شش': 6,
    'شیش': 6,
    'هفت': 7,
    'هشت': 8,
    'نه': 9,
    'ده': 10,
}

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

_SUBSCRIPTION_FILING = (
    'اشتراک فایلینگ',
    'پلن فایلینگ',
    'لایسنس فایلینگ',
    'خرید اشتراک فایلینگ',
)

_PRODUCT_OPERATIONS_HINTS = (
    'بودجه',
    'مشتری',
    'مخاطب',
    'تطبیق',
    'مچینگ',
    'انعطاف',
    'زونکن',
    'کمد',
    'بایگانی',
    'dataset',
    'دیتاست',
    'مجموعه فایل',
    'آگهی',
    'استخراج',
    'فایل شخصی',
    'املاک شخصی',
    'پیشنهادها',
    'قرارداد اجاره',
    'تمدید اجاره',
    'rental_contract',
    'محله‌های',
    'محله های',
    'متراژ',
    'خریدار',
    'مستأجر',
    'مستاجر',
    'معامله',
    'تکراری',
    'به‌روزرسانی',
    'به روزرسانی',
    'تغییر قیمت',
    'صفحه‌بندی',
    'matches-more',
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
    'خریدار',
    'مشتری',
    'مخاطب',
    'listing',
    'متر',
    'بودجه',
    'محله',
    'تطبیق',
    'زونکن',
    'بایگانی',
    'dataset',
)

_TEAM_PATTERNS = (
    re.compile(r'(\d+)\s*تا\s*(?:نفر|مشاور|عضو|لایسنس)'),
    re.compile(r'(\d+)\s*(?:نفر|مشاور|نفره|نفرای|نفری|لایسنس)'),
    re.compile(r'(?:آژانس|تیم|دفتر)\s*(?:ما\s*)?(\d+)\s*(?:نفر|مشاور)'),
    re.compile(r'ما\s*(\d+)\s*نفر'),
    re.compile(r'تیم\s*(\d+)'),
    re.compile(r'(\d+)\s*نفر\s*شدیم'),
    re.compile(r'تعداد(?:مون|مان)\s*(?:شده\s*)?(\d+)'),
    re.compile(r'شدیم\s*(\d+)\s*نفر'),
    re.compile(r'از\s*\d+\s*نفر\s*شدیم\s*(\d+)'),
)
_TEAM_WORD_PATTERNS = (
    re.compile(r'(?:ما|آژانس)\s*(' + '|'.join(_WORD_NUMBERS) + r')\s*(?:نفر|مشاور|نفریم)'),
    re.compile(r'(' + '|'.join(_WORD_NUMBERS) + r')\s*تا\s*(?:نفر|مشاور)'),
    re.compile(r'(' + '|'.join(_WORD_NUMBERS) + r')\s*(?:نفر|مشاور)'),
)

_AGENCY_HINTS = ('آژانس', 'تیم', 'دفتر', 'چند مشاور', 'گروهی', 'مدیر آژانس')
_SOLO_HINTS = ('تنها', 'تک نفر', 'تک‌نفر', 'مستقل', 'alone', 'solo', 'خودم', 'تنهایی')
_NEWBIE_HINTS = ('تازه شروع', 'تازه کار', 'جدید شدم', 'شروع کردم', 'مبتدی')

_DURATION_ORDER = ('quarterly', 'yearly', 'monthly', 'daily')
_DURATION_MAP = {
    'monthly': ('ماهانه', 'یک ماهه', 'یک‌ماهه', '۱ ماه', '1 ماه', 'monthly'),
    'quarterly': ('سه ماهه', 'سه‌ماهه', '۳ ماه', '3 ماه', '90 روز', 'quarterly'),
    'yearly': ('سالانه', 'یکساله', 'یک ساله', 'یک‌ساله', '۱۲ ماه', '12 ماه', 'yearly'),
    'daily': ('هفت روز', 'هفت‌روزه', '۷ روز', '7 روز', 'trial', 'daily'),
}

_SHARE_FILE_RE = re.compile(
    r'(لینک\s+اشتراک\s+فایل|اشتراک\s+فایل\s+برای|اشتراک\s+گذاری\s+فایل|share\s+فایل|لینک\s+برای\s+مشتری)',
    re.IGNORECASE,
)

_HOWTO_BREAK = ('چطور', 'چطوری', 'چگونه', 'چجوری', 'آموزش', 'راهنما')
_CRM_TOPIC = ('مخاطب', 'crm', 'ثبت مشتری', 'معامله', 'deal')


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
    needs_team_count: bool
    raw_message: str


def _to_ascii_digits(text: str) -> str:
    return text.translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)


def _size_looks_like_file_count(norm: str, end_index: int) -> bool:
    tail = norm[end_index : end_index + 16]
    return bool(re.match(r'\s*(?:فایل|آگهی|ملک|dataset|دیتاست)', tail))


def extract_team_size(text: str) -> int | None:
    norm = _to_ascii_digits(normalize_persian(text))
    found: list[int] = []
    for pat in _TEAM_PATTERNS:
        for m in pat.finditer(norm):
            if _size_looks_like_file_count(norm, m.end()):
                continue
            n = int(m.group(1))
            if 1 <= n <= 100:
                found.append(n)
    for pat in _TEAM_WORD_PATTERNS:
        for m in pat.finditer(normalize_persian(text)):
            word = m.group(1)
            n = _WORD_NUMBERS.get(word)
            if n and 1 <= n <= 100:
                found.append(n)
    if not found:
        return None
    return found[-1]


def extract_duration(text: str) -> str | None:
    norm = normalize_persian(text)
    for key in _DURATION_ORDER:
        if any(h in norm for h in _DURATION_MAP[key]):
            return key
    if any(h in norm for h in _DURATION_MAP['daily']):
        return 'daily'
    return None


def _is_share_file_context(norm: str) -> bool:
    if 'فایلینگ' in norm and any(w in norm for w in ('اشتراک', 'پلن', 'لایسنس', 'قیمت')):
        return False
    if _SHARE_FILE_RE.search(norm):
        return True
    if any(h in norm for h in _HOWTO_BREAK) and 'لینک' in norm and 'مشتری' in norm:
        if 'فایلینگ' in norm or 'پلن' in norm or 'لایسنس' in norm:
            return False
        return True
    if 'اشتراک' in norm and 'لینک' in norm and 'مشتری' in norm:
        if 'فایلینگ' in norm or 'پلن' in norm or 'لایسنس' in norm:
            return False
        return True
    return False


def _has_subscription_anchor(norm: str) -> bool:
    if any(h in norm for h in _SUBSCRIPTION_STRONG):
        return True
    if any(h in norm for h in _SUBSCRIPTION_FILING):
        return True
    if 'اشتراک' in norm and 'فایلینگ' in norm:
        return True
    if 'قیمت' in norm and any(w in norm for w in ('اشتراک', 'لایسنس', 'پلن', 'ربات', 'استخراج')):
        return True
    if 'خرید' in norm and any(w in norm for w in ('اشتراک', 'لایسنس', 'پلن', 'ربات')):
        return True
    team = extract_team_size(norm)
    if team is not None and any(
        w in norm for w in ('قیمت', 'ماهانه', 'مشاور', 'لایسنس', 'اشتراک', 'تخفیف', 'آژانس', 'نفر')
    ):
        return True
    if extract_duration(norm) and any(
        w in norm for w in ('قیمت', 'چقدر', 'چنده', 'هزینه', 'می‌شود', 'میشود', 'بخرم', 'پلن')
    ):
        if not is_product_operations_topic(norm):
            return True
    return False


def is_product_operations_topic(norm: str) -> bool:
    """سؤال عملیاتی CRM/فایلینگ — نه خرید اشتراک."""
    score = sum(1 for h in _PRODUCT_OPERATIONS_HINTS if h in norm)
    if 'پیشنهاد' in norm and any(w in norm for w in ('فایل', 'ملک', 'مشتری', 'مخاطب', 'بودجه')):
        score += 2
    if 'قیمت' in norm and any(w in norm for w in ('آگهی', 'ملک', 'فایل', 'دیوار', 'تغییر', 'به روز', 'به‌روز')):
        score += 2
    if 'خرید' in norm and any(w in norm for w in ('ملک', 'آپارتمان', 'خانه', 'زمین', 'واحد')):
        score += 2
    if 'فایلینگ دیوار' in norm and any(w in norm for w in ('آگهی', 'استخراج', 'تطبیق', 'crm', 'میزکار')):
        score += 2
    if 'ماه' in norm and any(w in norm for w in ('قبل', 'بعد', 'یادآوری', 'قرارداد', 'اجاره')):
        score += 1
    return score >= 2


def _is_subscription_topic(norm: str) -> bool:
    return _has_subscription_anchor(norm)


def _is_subscription_followup(norm: str) -> bool:
    if extract_team_size(norm) or extract_duration(norm):
        return True
    short = len(norm.split()) <= 10
    if not short:
        return False
    hints = (
        'چقدر',
        'چنده',
        'سالانه',
        'ماهانه',
        'سه ماه',
        'سه‌ماه',
        'حالا',
        'شدیم',
        'نفر',
        'مشاور',
    )
    return any(h in norm for h in hints)


def _is_topic_break(norm: str) -> bool:
    if _is_share_file_context(norm):
        return True
    if is_product_operations_topic(norm):
        return True
    if any(h in norm for h in _HOWTO_BREAK) and any(h in norm for h in _CRM_TOPIC):
        return True
    if any(h in norm for h in _HOWTO_BREAK) and not _is_subscription_topic(norm):
        return True
    return False


def is_independent_user_turn(message: str) -> bool:
    """سؤال تازه و مستقل — برای بازیابی بدون الحاق پیام قبلی."""
    norm = normalize_persian(message)
    tokens = [t for t in re.split(r'[^\w\u0600-\u06ff]+', norm) if len(t) >= 2]
    if len(tokens) >= 12 or len(norm) >= 90:
        return True
    if ('؟' in message or '?' in message) and len(tokens) >= 7:
        return True
    if is_product_operations_topic(norm) and len(tokens) >= 5:
        return True
    if _has_subscription_anchor(norm):
        return True
    return False


def _resolve_slots_from_history(
    session: PublicChatSession | None,
    current_message: str,
) -> tuple[int | None, str | None]:
    """تعداد/مدت از پیام فعلی اولویت دارد؛ فقط پیام‌های بعد از آخرین topic break."""
    current_team = extract_team_size(current_message)
    current_duration = extract_duration(current_message)
    if current_team is not None and current_duration is not None:
        return current_team, current_duration

    if not session:
        return current_team, current_duration

    from public_assistant.models import PublicChatMessage

    current_norm = normalize_persian(current_message)
    msgs = list(
        session.messages.filter(role=PublicChatMessage.ROLE_USER).order_by('-created_at', '-id')[:12]
    )

    history_team: int | None = None
    history_duration: str | None = None
    for m in msgs:
        if normalize_persian(m.content) == current_norm:
            continue
        norm = normalize_persian(m.content)
        if _is_topic_break(norm):
            break
        if not (_is_subscription_topic(norm) or _is_subscription_followup(norm)):
            continue
        t = extract_team_size(m.content)
        d = extract_duration(m.content)
        if t is not None and history_team is None:
            history_team = t
        if d is not None and history_duration is None:
            history_duration = d

    team = current_team if current_team is not None else history_team
    duration = current_duration if current_duration is not None else history_duration
    return team, duration


def _session_context_text(session: PublicChatSession | None) -> str:
    """فقط برای سازگاری — ویژگی‌های کاربر از پیام فعلی استخراج می‌شوند."""
    if not session:
        return ''
    return ''


def newbie_hint(text: str) -> bool:
    norm = normalize_persian(text)
    return any(h in norm for h in _NEWBIE_HINTS)


def analyze_subscription_query(
    message: str,
    session: PublicChatSession | None = None,
) -> SubscriptionQueryContext:
    norm = normalize_persian(message)

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
            needs_team_count=False,
            raw_message=message,
        )

    if is_product_operations_topic(norm) and not _has_subscription_anchor(norm):
        return SubscriptionQueryContext(
            is_subscription=False,
            is_property_listing=True,
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
            needs_team_count=False,
            raw_message=message,
        )

    property_score = sum(1 for h in _PROPERTY_STRONG if h in norm)
    has_subscription_anchor = _has_subscription_anchor(norm)
    subscription_score = sum(1 for h in _SUBSCRIPTION_STRONG if h in norm)
    if any(h in norm for h in _SUBSCRIPTION_FILING):
        subscription_score += 2
    if has_subscription_anchor and any(h in norm for h in _SUBSCRIPTION_MEDIUM):
        subscription_score += 1

    team_size, duration = _resolve_slots_from_history(session, message)

    agency_context = any(h in norm for h in _AGENCY_HINTS)
    if team_size and team_size >= 2:
        agency_context = True
        if has_subscription_anchor:
            subscription_score += 2

    wants_price = any(w in norm for w in ('قیمت', 'چنده', 'هزینه', 'چقدر', 'مبلغ', 'تومان'))
    if wants_price and property_score >= 1 and not has_subscription_anchor:
        wants_price = False

    solo = any(h in norm for h in _SOLO_HINTS) or ('تنها' in norm and 'کار' in norm)
    if team_size and team_size >= 2:
        solo = False
    if agency_context and wants_price:
        solo = False
    if solo:
        subscription_score += 1

    if property_score >= 1 and not has_subscription_anchor:
        is_property = True
    elif property_score >= 2 and subscription_score < 2:
        is_property = True
    elif is_product_operations_topic(norm) and not has_subscription_anchor:
        is_property = True
    else:
        is_property = False

    is_subscription = bool(has_subscription_anchor and subscription_score >= 1 and not is_property)
    if team_size and team_size >= 2 and has_subscription_anchor and not is_property:
        is_subscription = True
    wants_comparison = any(
        w in norm
        for w in ('بهتر', 'بهتره', 'به صرفه', 'به‌صرفه', 'مقایسه', 'فرق', 'تفاوت')
    ) or (' یا ' in f' {norm} ' and has_subscription_anchor)
    if wants_comparison and is_property and not has_subscription_anchor:
        wants_comparison = False
    wants_recommendation = any(
        w in norm for w in ('بخرم', 'مناسب', 'کدوم', 'کدام', 'انتخاب', 'بهتره', 'بهتر است')
    )
    if 'پیشنهاد' in norm:
        if any(w in norm for w in ('پلن', 'لایسنس', 'اشتراک')):
            wants_recommendation = True
        elif any(w in norm for w in ('فایل', 'ملک', 'مشتری', 'مخاطب', 'بودجه')):
            wants_recommendation = False
        elif has_subscription_anchor:
            wants_recommendation = True
    wants_trial_info = any(w in norm for w in ('آزمایشی', 'trial', 'پلن آزمایشی')) and not any(
        w in norm for w in ('هدیه', 'خوش آمد', 'ثبت نام', 'ثبت‌نام', 'رایگان')
    )
    wants_welcome_gift = any(
        w in norm for w in ('هدیه', 'خوش آمد', 'خوش‌آمد', 'رایگان ثبت', 'هفت روز رایگان', 'هفته رایگان')
    ) or (
        'رایگان' in norm
        and any(w in norm for w in ('هفت', '۷ روز', '7 روز', 'هفته', 'خوش', 'هدیه', 'ثبت'))
    )
    wants_features = any(
        w in norm for w in ('crm', 'هوش', 'ai', 'امکانات', 'قابلیت', 'شامل', 'دارد')
    ) and is_subscription

    if not is_property and has_subscription_anchor and (
        wants_price or wants_comparison or wants_recommendation
    ):
        is_subscription = True

    if (
        not is_subscription
        and not is_property
        and session
        and _is_subscription_followup(norm)
        and (team_size is not None or duration is not None)
    ):
        is_subscription = True

    needs_team_count = bool(
        is_subscription
        and agency_context
        and wants_price
        and team_size is None
        and not solo
    )

    if wants_welcome_gift and extract_team_size(message) is None and not any(
        h in norm for h in _AGENCY_HINTS
    ):
        team_size = None
        agency_context = False
        needs_team_count = False

    return SubscriptionQueryContext(
        is_subscription=is_subscription,
        is_property_listing=is_property,
        wants_price=wants_price,
        wants_comparison=wants_comparison,
        wants_recommendation=wants_recommendation
        or (newbie_hint(norm) and (has_subscription_anchor or is_subscription)),
        wants_trial_info=wants_trial_info,
        wants_welcome_gift=wants_welcome_gift,
        wants_features=wants_features,
        team_size=team_size,
        solo_advisor=solo,
        agency_context=agency_context,
        newbie=newbie_hint(norm),
        duration=duration,
        needs_team_count=needs_team_count,
        raw_message=message,
    )
