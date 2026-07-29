"""تشخیص سیگنال آگهی‌دهنده — مالک واقعی در برابر مشاور پنهان در پوشش شخصی.

ماژول مشترک بدون وابستگی به Django؛ توسط اکسترکتور و پلتفرم استفاده می‌شود.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, Optional

ADVERTISER_SIGNAL_CONSULTANT = "consultant"
ADVERTISER_SIGNAL_GENUINE_PERSONAL = "genuine_personal"
ADVERTISER_SIGNAL_DISGUISED = "disguised_consultant"

ADVERTISER_SIGNAL_LABELS = {
    ADVERTISER_SIGNAL_CONSULTANT: "مشاور",
    ADVERTISER_SIGNAL_GENUINE_PERSONAL: "مالک واقعی",
    ADVERTISER_SIGNAL_DISGUISED: "مشاور پنهان",
}

ADVERTISER_FILTER_ALL = "all"
ADVERTISER_FILTER_CONSULTANT = "consultant"
ADVERTISER_FILTER_PERSONAL = "personal"
ADVERTISER_FILTER_GENUINE = "genuine_personal"

ADVERTISER_FILTER_VALUES = frozenset({
    ADVERTISER_FILTER_ALL,
    ADVERTISER_FILTER_CONSULTANT,
    ADVERTISER_FILTER_PERSONAL,
    ADVERTISER_FILTER_GENUINE,
})

ADVERTISER_FILTER_LABELS = {
    ADVERTISER_FILTER_ALL: "همه آگهی‌ها",
    ADVERTISER_FILTER_CONSULTANT: "فقط مشاور",
    ADVERTISER_FILTER_PERSONAL: "شخصی",
    ADVERTISER_FILTER_GENUINE: "مالک واقعی",
}

CONSULTANT_NAME_KEYS = (
    "نام مشاور / آژانس",
    "مشاور_نام",
    "agency_name",
    "نام آژانس",
    "نام مشاور",
)

_OFFICIAL_CONSULTANT_TYPES = {
    "premium-panel", "premium_panel", "business", "consultant", "agency",
    "بنگاه", "مشاور", "آژانس",
}

# عباراتی که معمولاً در آگهی‌های مشاور/املاک (حتی با برچسب شخصی) دیده می‌شوند.
_DISGUISED_CONSULTANT_PHRASES: tuple[str, ...] = (
    "مشاور",
    "مشاور شما",
    "مشاور شما در منطقه",
    "مشاور املاک",
    "مشاور ملکی",
    "مشاور ملک",
    "مشاور فروش",
    "مشاورین املاک",
    "گروه مشاورین املاک",
    "مشاوره املاک",
    "کارشناس شما در منطقه",
    "کارشناس شما",
    "کارشناس املاک",
    "کارشناس منطقه",
    "کارشناس حرفه ای",
    "کارشناس حرفه ای منطقه",
    "کارشناس حرفه",
    "کارشناس ملکی",
    "کارشناس ملک",
    "کارشناس فروش",
    "کارشناس ارشد",
    "فایل شخصی",
    "فایل املاک",
    "لطفا املاک تماس نگیرد",
    "لطفاً املاک تماس نگیرد",
    "املاک تماس نگیرید",
    "املاک تماس نگیر",
    "تماس املاک",
    "لطفا همکار های عزیز تماس نگیرید",
    "لطفاً همکار های عزیز تماس نگیرید",
    "همکار های عزیز تماس نگیرید",
    "همکارهای عزیز تماس نگیرید",
    "همکار گرامی تماس نگیرید",
    "همکاران گرامی تماس نگیرید",
    "همکار تماس نگیرید",
    "تماس همکاران",
    "آگهی مشابه",
    "آگهی های مشابه",
    "فایل مشابه",
    "فایل های مشابه",
    "فایل مشابه موجود",
    "موارد مشابه",
    "موارد مشابه موجود",
    "موارد دیگر",
    "بنگاه املاک",
    "آژانس املاک",
    "دفتر املاک",
    "پنل املاک",
    "فقط خریدار واقعی",
    "فقط مستاجر",
    "فقط مستاجران",
    "real estate",
    "realtor",
    "مشاور حرفه ای",
    "مشاور حرفه ای منطقه",
    "مشاور منطقه",
    "مشاور حرفه",
    "آدرس املاک",
    "گروه املاک",
    "املاک شما",
)

# «املاک» به‌تنهایی گسترده است؛ فقط در ترکیب‌های مشکوک بررسی می‌شود.
_DISGUISED_AMLAK_CONTEXTS: tuple[str, ...] = (
    "املاک تماس",
    "تماس املاک",
    "فایل املاک",
    "پنل املاک",
    "همکار املاک",
    "لطفا املاک",
    "لطفاً املاک",
)

# عباراتی که صریحاً مالک بودن آگهی‌دهنده را تأیید می‌کنند — اولویت بالاتر از مشاور پنهان.
_OWNER_AFFIRMATION_PHRASES: tuple[str, ...] = (
    "مالک هستم",
    "من مالک هستم",
    "مالکم",
    "من مالکم",
    "مالک مستقیم",
    "مستقیم از مالک",
    "خودم مالک هستم",
    "خودم صاحب ملک هستم",
    "صاحب ملک هستم",
    "صاحبخانه هستم",
    "این ملک متعلق به خودم است",
    "ملک شخصی خودم",
    "واحد شخصی خودم",
    "خانه خودم",
    "آپارتمان خودم",
    "فروش توسط مالک",
    "اجاره توسط مالک",
    "رهن توسط مالک",
    "بدون واسطه از مالک",
    "بدون واسطه",
    "مستقیم با مالک",
    "ارتباط مستقیم با مالک",
    "تماس با مالک",
    "بدون دخالت مشاور",
    "بدون دخالت املاک",
    "سند به نام خودم",
    "سند به نام اینجانب",
    "مالک سند هستم",
    "مالک شش دانگ",
    "صاحب سند هستم",
    "خودم سازنده هستم",
)

# نام دفتر املاک: «املاک افشین»، «املاک بزرگ فردا» و مشابه.
_AMLAK_AGENCY_NAME_RE = re.compile(
    r"املاک\s+[\u0600-\u06FF]{2,}(?:\s+[\u0600-\u06FF]{2,}){0,2}"
)
_AMLAK_AGENCY_FALSE_POSITIVES: tuple[str, ...] = (
    "تماس",
    "نگیر",
    "نگیرید",
    "مسکونی",
    "تجاری",
    "اداری",
    "مسکن",
    "مستغلات",
    "کشاورزی",
    "صنعتی",
)

_ZWNJ_RE = re.compile(r"[\u200c\u200d\u200e\u200f\ufeff]")
_WS_RE = re.compile(r"\s+")
# پرانتز، ستاره، خط تیره و نمادهای تزئینی که مشاوران برای دور کلیدواژه می‌گذارند.
_DECORATIVE_CHARS_RE = re.compile(r"[\(\)\[\]\{\}«»「」\*•·._\-|~]+")
# برندینگ «املاک» با تزئین: ((املاک))، ***املاک*** و مشابه.
_DECORATIVE_AMLAK_RE = re.compile(
    r"[\(\[\{«「*•._\-|~]{1,}\s*املاک\s*[\)\]\}»」*•._\-|~]{1,}",
    re.IGNORECASE,
)
# «املاک» به‌تنهایی در ابتدای متن/خط (مثلاً بعد از حذف پرانتز).
_AMLAK_LINE_BRANDING_RE = re.compile(r"(?:^|\n)\s*املاک\s*(?:\n|$)")
# برندینگ «کارشناس» با تزئین: ((کارشناس))، ***کارشناس***
_DECORATIVE_KARSHENAS_RE = re.compile(
    r"[\(\[\{«「*•._\-|~]{1,}\s*کارشناس\s*[\)\]\}»」*•._\-|~]{1,}",
)
# «کارشناس» به‌تنهایی — نه «کارشناسی» (مثلاً کارشناسی شده، سند کارشناسی)
_KARSHENAS_WORD_RE = re.compile(r"کارشناس(?!ی)")


def normalize_filter_value(value: str = "") -> str:
    """نرمال‌سازی مقدار فیلتر UI؛ مقادیر نامعتبر → all."""
    key = str(value or "").strip().lower()
    if key in ADVERTISER_FILTER_VALUES:
        return key
    return ADVERTISER_FILTER_ALL


def normalize_ad_text(text: str) -> str:
    """یکسان‌سازی متن فارسی/عربی برای جستجوی الگو."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    normalized = normalized.replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    normalized = _ZWNJ_RE.sub(" ", normalized)
    normalized = _DECORATIVE_CHARS_RE.sub(" ", normalized)
    normalized = _WS_RE.sub(" ", normalized).strip().lower()
    return normalized


def _safe_label(val: Any) -> str:
    s = str(val or "").strip()
    if not s or s.lower() in ("nan", "none", "-", "—"):
        return ""
    return s


def extract_consultant_name(data: Optional[Dict[str, Any]] = None) -> str:
    """نام آژانس/مشاور از دادهٔ خام آگهی (اکسل استخراج)."""
    if not isinstance(data, dict):
        return ""
    for key in CONSULTANT_NAME_KEYS:
        text = _safe_label(data.get(key))
        if text:
            return text
    return ""


def _normalized_phrases(phrases: Iterable[str]) -> tuple[str, ...]:
    return tuple(normalize_ad_text(p) for p in phrases if p)


_NORMALIZED_DISGUISED_PHRASES = _normalized_phrases(_DISGUISED_CONSULTANT_PHRASES)
_NORMALIZED_AMLAK_CONTEXTS = _normalized_phrases(_DISGUISED_AMLAK_CONTEXTS)
# عبارات بلندتر اول تا زیررشته‌های کوتاه‌تر جایگزین نشوند؛ جستجو به ترتیب طول نزولی.
_NORMALIZED_OWNER_PHRASES = tuple(
    sorted(_normalized_phrases(_OWNER_AFFIRMATION_PHRASES), key=len, reverse=True)
)


def is_official_consultant(business_type: str = "", data: Optional[Dict[str, Any]] = None) -> bool:
    bt = normalize_ad_text(business_type or "")
    # برچسب‌های سیگنال اکسل نباید به‌عنوان مشاور رسمی تفسیر شوند
    if bt in (
        "مشاور پنهان",
        "مالک واقعی",
        "مالک",
        ADVERTISER_SIGNAL_DISGUISED,
        ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        "genuine personal",
    ):
        return False
    if bt in _OFFICIAL_CONSULTANT_TYPES:
        return True
    if "premium" in bt:
        return True
    if "مشاور" in bt or "آژانس" in bt or "business" in bt or "agency" in bt:
        return True
    if extract_consultant_name(data):
        return True
    return False


def is_personal_category(business_type: str = "", data: Optional[Dict[str, Any]] = None) -> bool:
    if is_official_consultant(business_type, data):
        return False
    bt = normalize_ad_text(business_type or "")
    if not bt:
        return True
    if bt in (
        "personal",
        "شخصی",
        "private",
        "مالک واقعی",
        "مالک",
        "مشاور پنهان",
        ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        ADVERTISER_SIGNAL_DISGUISED,
    ):
        return True
    return "personal" in bt or bt == "شخصی"


def normalize_business_type_for_storage(business_type: str = "") -> str:
    """
    برچسب‌های نمایشی اکسل را به مقادیر ذخیره‌سازی سازگار با پلتفرم برمی‌گرداند.
    مالک واقعی / مشاور پنهان → شخصی؛ مشاور → مشاور؛ بقیه بدون تغییر معنادار.
    """
    raw = str(business_type or "").strip()
    if not raw:
        return ""
    bt = normalize_ad_text(raw)
    if bt in (
        "مالک واقعی",
        "مالک",
        "مشاور پنهان",
        ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        ADVERTISER_SIGNAL_DISGUISED,
        "personal",
        "private",
        "شخصی",
    ):
        return "شخصی"
    if bt in ("مشاور", ADVERTISER_SIGNAL_CONSULTANT, "premium-panel", "premium_panel", "premium"):
        return "مشاور"
    if bt in ("بنگاه", "business", "agency", "آژانس"):
        return "بنگاه"
    return raw


def _has_amlak_agency_branding(text: str) -> bool:
    """برند دفتر املاک با الگوی «املاک + نام» (مثلاً املاک افشین)."""
    for match in _AMLAK_AGENCY_NAME_RE.finditer(text):
        rest = match.group(0).split("املاک", 1)[-1].strip()
        if not rest:
            continue
        if any(fp in rest for fp in _AMLAK_AGENCY_FALSE_POSITIVES):
            continue
        return True
    return False


def _has_decorative_amlak_branding(raw_text: str, normalized_text: str) -> bool:
    """برندینگ «املاک» با پرانتز/ستاره یا به‌تنهایی در خط اول."""
    if _DECORATIVE_AMLAK_RE.search(raw_text):
        return True
    if _AMLAK_LINE_BRANDING_RE.search(normalized_text):
        return True
    return False


def _has_karshenas_marker(raw_text: str, normalized_text: str) -> bool:
    """کارشناس/کارشناس منطقه/... — بدون «کارشناسی»."""
    if _DECORATIVE_KARSHENAS_RE.search(raw_text):
        return True
    return bool(_KARSHENAS_WORD_RE.search(normalized_text))


def _description_from_data(data: Optional[Dict[str, Any]]) -> str:
    if not data:
        return ""
    for key in ("توضیحات", "description", "متن آگهی"):
        val = data.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text and text.lower() not in ("-", "—", "nan", "none"):
            return text
    return ""


def _combined_ad_text(
    title: str = "",
    description: str = "",
    data: Optional[Dict[str, Any]] = None,
) -> tuple[str, str]:
    """(normalized_combined, raw_combined) برای جستجوی الگو در عنوان/توضیحات."""
    title_norm = normalize_ad_text(title)
    desc_norm = normalize_ad_text(description)
    raw_desc = description
    if not desc_norm.strip() and data:
        raw_desc = _description_from_data(data)
        desc_norm = normalize_ad_text(raw_desc)
    combined = f"{title_norm} {desc_norm}".strip()
    raw_combined = f"{title} {raw_desc}".strip()
    return combined, raw_combined


def has_owner_markers(
    title: str = "",
    description: str = "",
    data: Optional[Dict[str, Any]] = None,
) -> bool:
    """عبارات صریح مالکیت در متن — آگهی‌دهنده مالک است."""
    combined, _ = _combined_ad_text(title, description, data)
    if not combined:
        return False
    for phrase in _NORMALIZED_OWNER_PHRASES:
        if phrase and phrase in combined:
            return True
    return False


def has_disguised_consultant_markers(
    title: str = "",
    description: str = "",
    data: Optional[Dict[str, Any]] = None,
) -> bool:
    combined, raw_combined = _combined_ad_text(title, description, data)
    if not combined:
        return False

    if _has_decorative_amlak_branding(raw_combined, combined):
        return True

    if _has_karshenas_marker(raw_combined, combined):
        return True

    for phrase in _NORMALIZED_DISGUISED_PHRASES:
        if phrase and phrase in combined:
            return True

    for ctx in _NORMALIZED_AMLAK_CONTEXTS:
        if ctx and ctx in combined:
            return True

    if _has_amlak_agency_branding(combined):
        return True

    if data:
        for key, val in data.items():
            key_norm = normalize_ad_text(str(key))
            if "مشاور" not in key_norm and "consultant" not in key_norm:
                continue
            val_norm = normalize_ad_text(str(val or ""))
            if val_norm and val_norm not in ("-", "—", "nan", "none"):
                return True

    return False


def detect_advertiser_signal(
    *,
    title: str = "",
    description: str = "",
    business_type: str = "",
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
        return ""
    # عبارات صریح مالکیت بر نشانه‌های مشاور پنهان اولویت دارند.
    if has_owner_markers(title, description, data):
        return ADVERTISER_SIGNAL_GENUINE_PERSONAL
    if has_disguised_consultant_markers(title, description, data):
        return ADVERTISER_SIGNAL_DISGUISED
    return ADVERTISER_SIGNAL_GENUINE_PERSONAL


def advertiser_signal_label(signal: str) -> str:
    return ADVERTISER_SIGNAL_LABELS.get(signal or "", "")


def row_advertiser_fields(row: Dict[str, Any]) -> Dict[str, str]:
    """استخراج فیلدهای لازم تشخیص سیگنال از ردیف flatten‌شده اکسترکتور."""
    title = str(row.get("title") or row.get("عنوان") or "").strip()
    description = str(row.get("description") or row.get("توضیحات") or "").strip()
    business_type = str(
        row.get("business_type") or row.get("فروشنده_business_type") or ""
    ).strip()
    return {
        "title": title,
        "description": description,
        "business_type": business_type,
    }


def detect_row_advertiser_signal(row: Dict[str, Any]) -> str:
    """تشخیص سیگنال از ردیف خروجی استخراج."""
    fields = row_advertiser_fields(row)
    return detect_advertiser_signal(
        title=fields["title"],
        description=fields["description"],
        business_type=fields["business_type"],
        data=row,
    )


def advertiser_display_label_for_row(row: Dict[str, Any]) -> str:
    """برچسب فارسی ستون «نوع آگهی دهنده» بر اساس سیگنال."""
    signal = detect_row_advertiser_signal(row)
    label = advertiser_signal_label(signal)
    if label:
        return label
    fields = row_advertiser_fields(row)
    bt = normalize_ad_text(fields["business_type"])
    if bt in ("personal", "شخصی", "private") or "personal" in bt:
        return "شخصی"
    if bt in ("business", "بنگاه"):
        return "بنگاه"
    if fields["business_type"]:
        return fields["business_type"]
    return "شخصی"


def row_matches_advertiser_filter(row: Dict[str, Any], advertiser_filter: str = "all") -> bool:
    """آیا ردیف با فیلتر انتخاب‌شده مطابقت دارد؟"""
    key = normalize_filter_value(advertiser_filter)
    if key == ADVERTISER_FILTER_ALL:
        return True
    signal = detect_row_advertiser_signal(row)
    fields = row_advertiser_fields(row)
    if key == ADVERTISER_FILTER_CONSULTANT:
        return signal == ADVERTISER_SIGNAL_CONSULTANT or is_official_consultant(
            fields["business_type"], row
        )
    if key == ADVERTISER_FILTER_PERSONAL:
        return is_personal_category(fields["business_type"], row)
    if key == ADVERTISER_FILTER_GENUINE:
        return signal == ADVERTISER_SIGNAL_GENUINE_PERSONAL
    return True


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
