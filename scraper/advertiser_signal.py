"""تشخیص سیگنال آگهی‌دهنده — مالک واقعی در برابر مشاور پنهان در پوشش شخصی.

موتور V2: Strong Rules + Weighted Signal Scoring + Diagnostics.
ماژول مشترک بدون وابستگی به Django؛ توسط اکسترکتور و پلتفرم استفاده می‌شود.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple, TypedDict

ADVERTISER_SIGNAL_CONSULTANT = "consultant"
ADVERTISER_SIGNAL_GENUINE_PERSONAL = "genuine_personal"
ADVERTISER_SIGNAL_DISGUISED = "disguised_consultant"

ADVERTISER_DETECTOR_VERSION = 2

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

# ---------------------------------------------------------------------------
# Detector configuration (centralized weights / thresholds)
# ---------------------------------------------------------------------------

DETECTOR_WEIGHTS: Dict[str, int] = {
    "critical_disguised": 110,
    "strong_disguised": 75,
    "medium_disguised": 35,
    "soft_disguised": 15,
    "explicit_owner": -50,
    "owner": -30,
    "soft_owner": -15,
}

DETECTOR_THRESHOLDS: Dict[str, int] = {
    "disguised": 60,
    "medium_confidence": 40,
    "high_confidence": 60,
    "very_high_confidence": 100,
}

# Per-reason score cap (prevents double-counting within a category)
REASON_SCORE_CAPS: Dict[str, int] = {
    "agent_contact_restriction": 110,
    "professional_broker_identity": 120,
    "broker_branding": 120,
    "inventory_language": 90,
    "professional_workflow_language": 45,
    "brokerage_sales_language": 40,
    "structured_broker_metadata": 120,
    "explicit_owner_claim": -50,
    "owner_language": -45,
    "soft_owner_language": -30,
}

CRITICAL_REASON_CODES = frozenset({
    "agent_contact_restriction",
    "professional_broker_identity",
    "structured_broker_metadata",
    "broker_branding",
})

STRONG_INVENTORY_REASONS = frozenset({
    "inventory_language_critical",
})

_OFFICIAL_CONSULTANT_TYPES = {
    "premium-panel", "premium_panel", "business", "consultant", "agency",
    "بنگاه", "مشاور", "آژانس",
}

# ---------------------------------------------------------------------------
# Phrase libraries (normalized at module load)
# ---------------------------------------------------------------------------

_PROFESSIONAL_BROKER_PHRASES: Tuple[Tuple[str, int, bool], ...] = (
    ("مشاور املاک", 120, True),
    ("مشاور شما در منطقه", 115, True),
    ("مشاور شما", 115, True),
    ("مشاور حرفه ای منطقه", 110, True),
    ("مشاور حرفه ای", 110, True),
    ("مشاور منطقه", 110, True),
    ("مشاور فروش", 110, True),
    ("مشاور ملکی", 110, True),
    ("مشاور ملک", 110, True),
    ("گروه مشاورین املاک", 120, True),
    ("مشاورین املاک", 115, True),
    ("مشاوره املاک", 110, True),
    ("کارشناس شما در منطقه", 110, True),
    ("کارشناس شما", 105, True),
    ("کارشناس املاک", 115, True),
    ("کارشناس حرفه ای منطقه", 110, True),
    ("کارشناس حرفه ای", 105, True),
    ("کارشناس منطقه", 105, True),
    ("کارشناس ملکی", 105, True),
    ("کارشناس ملک", 105, True),
    ("کارشناس فروش", 105, True),
    ("کارشناس ارشد", 105, True),
    ("دفتر املاک", 115, True),
    ("بنگاه املاک", 115, True),
    ("آژانس املاک", 115, True),
    ("گروه املاک", 110, True),
    ("پنل املاک", 110, True),
    ("آدرس املاک", 105, True),
    ("املاک شما", 105, True),
    ("real estate", 110, True),
    ("realtor", 110, True),
    ("مشاور حرفه", 100, True),
    ("مشاور", 90, True),
)

_INVENTORY_PHRASES: Tuple[Tuple[str, int, str], ...] = (
    ("فایل های مشابه موجود", 90, "inventory_language_critical"),
    ("فایل‌های مشابه موجود", 90, "inventory_language_critical"),
    ("موارد مشابه موجود", 88, "inventory_language_critical"),
    ("مورد مشابه موجود", 85, "inventory_language_critical"),
    ("گزینه های مشابه موجود", 85, "inventory_language_critical"),
    ("گزینه‌های مشابه موجود", 85, "inventory_language_critical"),
    ("فایل مشابه موجود", 85, "inventory_language"),
    ("فایل های مشابه", 82, "inventory_language"),
    ("فایل‌های مشابه", 82, "inventory_language"),
    ("فایل های دیگر", 80, "inventory_language"),
    ("فایل‌های دیگر", 80, "inventory_language"),
    ("گزینه های مشابه", 78, "inventory_language"),
    ("گزینه‌های مشابه", 78, "inventory_language"),
    ("گزینه‌های دیگر", 75, "inventory_language"),
    ("فایل مشابه", 80, "inventory_language"),
    ("موارد مشابه", 78, "inventory_language"),
    ("مورد مشابه", 75, "inventory_language"),
    ("موارد دیگر", 72, "inventory_language"),
    ("فایل بیشتر", 72, "inventory_language"),
    ("فایل‌های بیشتر", 72, "inventory_language"),
    ("فایل فروش", 78, "inventory_language"),
    ("فایل اجاره", 78, "inventory_language"),
    ("فایل رهن", 75, "inventory_language"),
    ("فایل اکازیون", 78, "inventory_language"),
    ("فایل شخصی", 75, "inventory_language"),
    ("فایل مناسب شما", 80, "inventory_language"),
    ("فایل متناسب با بودجه", 82, "inventory_language"),
    ("فایل موجود", 75, "inventory_language"),
    ("آگهی مشابه", 70, "inventory_language"),
    ("آگهی های مشابه", 70, "inventory_language"),
    ("فایل املاک", 78, "inventory_language"),
)

_WORKFLOW_PHRASES: Tuple[Tuple[str, int], ...] = (
    ("جهت ارسال فیلم کامل واحد", 40),
    ("ارسال فیلم کامل واحد", 40),
    ("ارسال فیلم کامل", 38),
    ("ارسال فیلم ملک", 35),
    ("فیلم کامل موجود", 35),
    ("جهت دریافت فیلم", 32),
    ("جهت هماهنگی بازدید", 38),
    ("هماهنگی جهت بازدید", 38),
    ("تنظیم وقت بازدید", 35),
    ("برای بازدید هماهنگ کنید", 35),
    ("بازدید با هماهنگی", 30),
    ("ارسال مشخصات", 28),
    ("اطلاعات بیشتر تماس", 25),
    ("فایل کامل", 30),
)

_SALES_PHRASES: Tuple[Tuple[str, int], ...] = (
    ("فقط خریدار واقعی", 35),
    ("مشتری واقعی", 30),
    ("فقط مشتری", 25),
    ("متناسب با بودجه شما", 32),
    ("بودجه شما", 25),
    ("گزینه مناسب شما", 30),
    ("ملک مناسب شما", 28),
    ("برای معرفی موارد بیشتر", 35),
    ("برای معرفی فایل", 32),
    ("موارد بیشتر موجود است", 35),
    ("فقط مستاجر", 20),
    ("فقط مستاجران", 20),
)

_EXPLICIT_OWNER_PHRASES: Tuple[str, ...] = (
    "من مالک هستم",
    "مالک هستم",
    "من مالکم",
    "مالکم",
    "خودم مالک هستم",
    "خودم صاحب ملک هستم",
    "صاحب ملک هستم",
    "صاحبخانه هستم",
    "این ملک متعلق به خودم است",
    "سند به نام خودم است",
    "سند به نام خودم",
    "سند به نام اینجانب",
    "مالک شش دانگ هستم",
    "مالک شش دانگ",
    "مالک سند هستم",
    "صاحب سند هستم",
    "من صاحب ملک هستم",
)

_OWNER_PHRASES: Tuple[str, ...] = (
    "ملک شخصی خودم",
    "واحد شخصی خودم",
    "خانه خودم",
    "آپارتمان خودم",
    "فروش توسط مالک",
    "اجاره توسط مالک",
    "رهن توسط مالک",
    "مستقیم از مالک",
    "مالک مستقیم",
    "فروش مستقیم توسط مالک",
    "آپارتمان خودم را برای فروش گذاشتم",
)

_SOFT_OWNER_PHRASES: Tuple[str, ...] = (
    "بدون واسطه از مالک",
    "بدون واسطه",
    "مستقیم با مالک",
    "ارتباط مستقیم با مالک",
    "تماس مستقیم با مالک",
    "تماس با مالک",
    "بدون دخالت مشاور",
    "بدون دخالت املاک",
    "خودم سازنده هستم",
)

# عبارت‌هایی که نباید زیررشته «مشاور»/«املاک» در آن‌ها disguised بسازد.
_OWNER_MASK_PHRASES: Tuple[str, ...] = (
    "بدون دخالت مشاور",
    "بدون دخالت املاک",
    "تماس با مالک",
    "تماس مستقیم با مالک",
    "ارتباط مستقیم با مالک",
    "مستقیم با مالک",
    "مستقیم از مالک",
    "فروش املاک مسکونی",
    "فروش املاک تجاری",
    "فروش املاک اداری",
    "املاک مسکونی",
    "املاک تجاری",
    "املاک اداری",
    "املاک مسکن",
    "املاک مستغلات",
)

_AMLAK_AGENCY_FALSE_POSITIVES: Tuple[str, ...] = (
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

_STRUCTURED_BROKER_KEY_PARTS = ("مشاور", "consultant", "agency", "advisor", "real_estate")

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

_ZWNJ_RE = re.compile(r"[\u200c\u200d\u200e\u200f\ufeff]")
_WS_RE = re.compile(r"\s+")
_DECORATIVE_CHARS_RE = re.compile(r"[\(\)\[\]\{\}«»「」\*•·._\-|~]+")
_NEGATION_NORMALIZE_RE = re.compile(r"نمی\s*گیر")
_DASHED_NEGATION_RE = re.compile(r"نـگیر")

_DECORATIVE_AMLAK_RE = re.compile(
    r"[\(\[\{«「*•._\-|~]{1,}\s*املاک\s*[\)\]\}»」*•._\-|~]{1,}",
    re.IGNORECASE,
)
_AMLAK_LINE_BRANDING_RE = re.compile(r"(?:^|\n)\s*املاک\s*(?:\n|$)")
_DECORATIVE_KARSHENAS_RE = re.compile(
    r"[\(\[\{«「*•._\-|~]{1,}\s*کارشناس\s*[\)\]\}»」*•._\-|~]{1,}",
)
_KARSHENAS_WORD_RE = re.compile(r"کارشناس(?!ی)")
_AMLAK_AGENCY_NAME_RE = re.compile(
    r"املاک\s+[\u0600-\u06FF]{2,}(?:\s+[\u0600-\u06FF]{2,}){0,2}",
)
_INVENTORY_FILE_CODE_RE = re.compile(
    r"(?:کد\s*فایل|شماره\s*فایل|فایل\s*شماره)\s*[\d۰-۹]{2,6}",
)
_STANDALONE_MOSHAVER_RE = re.compile(r"(?<![\u0600-\u06FF])مشاور(?![\u0600-\u06FFی])")

_HONORIFICS = r"(?:عزیز|گرامی|محترم)"
_POLITE = r"(?:لطفا|لطفاً)"
_AGENT_TARGET = (
    r"(?:"
    r"همکار(?:ان|های|ها|ای)?|"
    r"مشاور(?:ان|ین)?(?:\s+املاک)?|"
    r"املاک(?:ی)?|"
    r"دفاتر\s+املاک|"
    r"دفتر\s+املاک|"
    r"بنگاه|"
    r"آژانس|"
    r"واسطه|"
    r"دلال"
    r")"
)
_CONTACT_PROHIBITION = (
    r"(?:"
    r"تماس\s*ن(?:گیر|فرما|کن)|"
    r"تماس\s*نگیر(?:ید|ند)?|"
    r"زنگ\s*نزن(?:ید|ند)?|"
    r"پیام\s*ن(?:ده|فرست)(?:ید|ند)?|"
    r"مزاحم\s*نشو(?:ید|ند)?"
    r")"
)
_AGENT_CONTACT_RE = re.compile(
    rf"(?:"
    rf"(?:{_POLITE}\s+)?"
    rf"{_AGENT_TARGET}"
    rf"(?:\s+(?:{_HONORIFICS}|{_POLITE})){{0,3}}"
    rf"(?:\s+.{{0,35}}?){{0,2}}?"
    rf"\s*{_CONTACT_PROHIBITION}"
    rf")",
    re.IGNORECASE | re.UNICODE,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DetectedSignal:
    reason_code: str
    weight: int
    category: str
    matched_text: str
    critical: bool = False


class AdvertiserSignalResult(TypedDict):
    classification: str
    score: int
    confidence: str
    critical: bool
    reasons: List[str]
    matched_signals: List[str]
    matched_owner_signals: List[str]
    matched_disguised_signals: List[str]
    matched_soft_signals: List[str]
    critical_signals: List[str]
    detector_version: int


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

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
    normalized = _NEGATION_NORMALIZE_RE.sub("نگیر", normalized)
    normalized = _DASHED_NEGATION_RE.sub("نگیر", normalized)
    normalized = _WS_RE.sub(" ", normalized).strip().lower()
    return normalized


def _normalized_phrases(phrases: Iterable[str]) -> Tuple[str, ...]:
    return tuple(normalize_ad_text(p) for p in phrases if p)


_NORMALIZED_OWNER_MASK = _normalized_phrases(_OWNER_MASK_PHRASES)
_NORMALIZED_EXPLICIT_OWNER = tuple(
    sorted(_normalized_phrases(_EXPLICIT_OWNER_PHRASES), key=len, reverse=True)
)
_NORMALIZED_OWNER = tuple(sorted(_normalized_phrases(_OWNER_PHRASES), key=len, reverse=True))
_NORMALIZED_SOFT_OWNER = tuple(sorted(_normalized_phrases(_SOFT_OWNER_PHRASES), key=len, reverse=True))


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


def is_official_consultant(business_type: str = "", data: Optional[Dict[str, Any]] = None) -> bool:
    bt = normalize_ad_text(business_type or "")
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
) -> Tuple[str, str]:
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


def _mask_owner_regions(text: str) -> str:
    """ناحیه‌های owner/anti-false-positive را برای جستجوی disguised ماسک می‌کند."""
    masked = text
    for phrase in _NORMALIZED_OWNER_MASK:
        if phrase and phrase in masked:
            masked = masked.replace(phrase, " " * len(phrase))
    return masked


def _find_phrase_matches(
    text: str,
    phrases: Iterable[Tuple[str, ...]],
) -> List[str]:
    found: List[str] = []
    for item in phrases:
        phrase = item[0] if isinstance(item, tuple) else item
        norm = normalize_ad_text(phrase)
        if norm and norm in text:
            found.append(phrase)
    return found


def _extract_phrase_signals(
    text: str,
    phrase_defs: Iterable[Tuple[str, int, Any]],
    default_reason: str,
    default_category: str,
    *,
    critical_default: bool = False,
    mask_owner_regions: bool = False,
) -> List[DetectedSignal]:
    search_text = _mask_owner_regions(text) if mask_owner_regions else text
    signals: List[DetectedSignal] = []
    sorted_defs = sorted(phrase_defs, key=lambda x: len(x[0]), reverse=True)
    consumed_spans: List[Tuple[int, int]] = []

    for item in sorted_defs:
        phrase = item[0]
        weight = item[1]
        extra = item[2] if len(item) > 2 else default_reason
        if isinstance(extra, bool):
            reason = default_reason
            critical = extra
        else:
            reason = str(extra)
            critical = reason in CRITICAL_REASON_CODES or reason in STRONG_INVENTORY_REASONS

        norm = normalize_ad_text(phrase)
        if not norm or norm not in search_text:
            continue

        start = 0
        while True:
            idx = search_text.find(norm, start)
            if idx < 0:
                break
            end = idx + len(norm)
            if any(not (end <= s or idx >= e) for s, e in consumed_spans):
                start = idx + 1
                continue
            consumed_spans.append((idx, end))
            signals.append(DetectedSignal(
                reason_code=reason,
                weight=weight,
                category=default_category,
                matched_text=phrase,
                critical=critical or reason in CRITICAL_REASON_CODES,
            ))
            start = end
    return signals


def _has_amlak_agency_branding(text: str) -> Optional[str]:
    for match in _AMLAK_AGENCY_NAME_RE.finditer(text):
        rest = match.group(0).split("املاک", 1)[-1].strip()
        if not rest:
            continue
        if any(fp in rest for fp in _AMLAK_AGENCY_FALSE_POSITIVES):
            continue
        return match.group(0)
    return None


def _extract_all_signals(
    combined: str,
    raw_combined: str,
    data: Optional[Dict[str, Any]],
) -> List[DetectedSignal]:
    signals: List[DetectedSignal] = []

    # --- Owner signals (negative weight) ---
    for phrase in _NORMALIZED_EXPLICIT_OWNER:
        if phrase in combined:
            signals.append(DetectedSignal(
                reason_code="explicit_owner_claim",
                weight=DETECTOR_WEIGHTS["explicit_owner"],
                category="owner",
                matched_text=phrase,
            ))
    for phrase in _NORMALIZED_OWNER:
        if phrase in combined:
            signals.append(DetectedSignal(
                reason_code="owner_language",
                weight=DETECTOR_WEIGHTS["owner"],
                category="owner",
                matched_text=phrase,
            ))
    for phrase in _NORMALIZED_SOFT_OWNER:
        if phrase in combined:
            signals.append(DetectedSignal(
                reason_code="soft_owner_language",
                weight=DETECTOR_WEIGHTS["soft_owner"],
                category="soft_owner",
                matched_text=phrase,
            ))

    # --- Critical: agent contact restriction ---
    for match in _AGENT_CONTACT_RE.finditer(combined):
        signals.append(DetectedSignal(
            reason_code="agent_contact_restriction",
            weight=DETECTOR_WEIGHTS["critical_disguised"],
            category="critical_disguised",
            matched_text=match.group(0).strip(),
            critical=True,
        ))

    # --- Critical: broker branding ---
    if _DECORATIVE_AMLAK_RE.search(raw_combined):
        signals.append(DetectedSignal(
            reason_code="broker_branding",
            weight=115,
            category="critical_disguised",
            matched_text="((املاک))",
            critical=True,
        ))
    if _AMLAK_LINE_BRANDING_RE.search(combined):
        signals.append(DetectedSignal(
            reason_code="broker_branding",
            weight=110,
            category="critical_disguised",
            matched_text="املاک",
            critical=True,
        ))
    if _DECORATIVE_KARSHENAS_RE.search(raw_combined):
        signals.append(DetectedSignal(
            reason_code="broker_branding",
            weight=110,
            category="critical_disguised",
            matched_text="((کارشناس))",
            critical=True,
        ))
    # کارشناس — نه «کارشناسی»
    if _KARSHENAS_WORD_RE.search(_mask_owner_regions(combined)):
        for match in _KARSHENAS_WORD_RE.finditer(_mask_owner_regions(combined)):
            signals.append(DetectedSignal(
                reason_code="professional_broker_identity",
                weight=105,
                category="critical_disguised",
                matched_text=match.group(0),
                critical=True,
            ))
            break

    agency_match = _has_amlak_agency_branding(combined)
    if agency_match:
        signals.append(DetectedSignal(
            reason_code="professional_broker_identity",
            weight=115,
            category="critical_disguised",
            matched_text=agency_match,
            critical=True,
        ))

    # --- Professional broker phrases ---
    broker_defs = [
        (p, w, c) for p, w, c in _PROFESSIONAL_BROKER_PHRASES
    ]
    signals.extend(_extract_phrase_signals(
        combined,
        broker_defs,
        default_reason="professional_broker_identity",
        default_category="critical_disguised",
        critical_default=True,
        mask_owner_regions=True,
    ))

    # Standalone مشاور (after masking owner regions)
    masked = _mask_owner_regions(combined)
    if _STANDALONE_MOSHAVER_RE.search(masked):
        match = _STANDALONE_MOSHAVER_RE.search(masked)
        if match:
            signals.append(DetectedSignal(
                reason_code="professional_broker_identity",
                weight=90,
                category="strong_disguised",
                matched_text=match.group(0),
                critical=True,
            ))

    # --- Inventory language ---
    inv_defs = [(p, w, r) for p, w, r in _INVENTORY_PHRASES]
    signals.extend(_extract_phrase_signals(
        combined,
        inv_defs,
        default_reason="inventory_language",
        default_category="strong_disguised",
    ))
    for match in _INVENTORY_FILE_CODE_RE.finditer(combined):
        signals.append(DetectedSignal(
            reason_code="inventory_language_critical",
            weight=88,
            category="strong_disguised",
            matched_text=match.group(0).strip(),
            critical=True,
        ))

    # --- Workflow / sales soft-medium ---
    wf_defs = [(p, w, "professional_workflow_language") for p, w in _WORKFLOW_PHRASES]
    signals.extend(_extract_phrase_signals(
        combined, wf_defs, "professional_workflow_language", "medium_disguised",
    ))
    sales_defs = [(p, w, "brokerage_sales_language") for p, w in _SALES_PHRASES]
    signals.extend(_extract_phrase_signals(
        combined, sales_defs, "brokerage_sales_language", "soft_disguised",
    ))

    # --- Structured metadata ---
    if data:
        for key, val in data.items():
            key_norm = normalize_ad_text(str(key))
            if not any(part in key_norm for part in _STRUCTURED_BROKER_KEY_PARTS):
                continue
            val_norm = normalize_ad_text(str(val or ""))
            if val_norm and val_norm not in ("-", "—", "nan", "none"):
                signals.append(DetectedSignal(
                    reason_code="structured_broker_metadata",
                    weight=120,
                    category="critical_disguised",
                    matched_text=f"{key}={val}",
                    critical=True,
                ))

    return signals


def _aggregate_score(signals: List[DetectedSignal]) -> Tuple[int, Dict[str, int]]:
    """جمع وزن‌ها با dedup per reason_code (max weight) و cap per category."""
    by_reason: Dict[str, List[DetectedSignal]] = {}
    for sig in signals:
        by_reason.setdefault(sig.reason_code, []).append(sig)

    reason_contributions: Dict[str, int] = {}
    for reason, group in by_reason.items():
        weight = max(s.weight for s in group)
        cap = REASON_SCORE_CAPS.get(reason)
        if cap is not None:
            if weight > 0:
                weight = min(weight, cap)
            else:
                weight = max(weight, cap)
        reason_contributions[reason] = weight

    return sum(reason_contributions.values()), reason_contributions


def _confidence_label(score: int, critical: bool) -> str:
    if critical or score >= DETECTOR_THRESHOLDS["very_high_confidence"]:
        return "very_high"
    if score >= DETECTOR_THRESHOLDS["high_confidence"]:
        return "high"
    if score >= DETECTOR_THRESHOLDS["medium_confidence"]:
        return "medium"
    return "low"


def _classify_from_signals(signals: List[DetectedSignal], score: int) -> Tuple[str, bool, List[str]]:
    critical_signals = [
        s for s in signals
        if s.critical or s.reason_code in CRITICAL_REASON_CODES
        or s.reason_code in STRONG_INVENTORY_REASONS
    ]
    disguised_reasons = sorted({
        s.reason_code for s in signals if s.weight > 0
    })
    is_critical = bool(critical_signals)

    if is_critical:
        return ADVERTISER_SIGNAL_DISGUISED, True, disguised_reasons

    if score >= DETECTOR_THRESHOLDS["disguised"]:
        return ADVERTISER_SIGNAL_DISGUISED, False, disguised_reasons

    return ADVERTISER_SIGNAL_GENUINE_PERSONAL, False, disguised_reasons


def _build_result(
    classification: str,
    score: int,
    confidence: str,
    critical: bool,
    reasons: List[str],
    signals: List[DetectedSignal],
) -> AdvertiserSignalResult:
    owner_matches = [s.matched_text for s in signals if s.weight < 0]
    disguised_matches = [s.matched_text for s in signals if s.weight > 0]
    soft_matches = [
        s.matched_text for s in signals
        if s.weight > 0 and s.category in ("medium_disguised", "soft_disguised")
    ]
    critical_match_texts = [
        s.matched_text for s in signals
        if s.critical or s.reason_code in CRITICAL_REASON_CODES
        or s.reason_code in STRONG_INVENTORY_REASONS
    ]
    return AdvertiserSignalResult(
        classification=classification,
        score=score,
        confidence=confidence,
        critical=critical,
        reasons=reasons,
        matched_signals=[s.matched_text for s in signals],
        matched_owner_signals=owner_matches,
        matched_disguised_signals=disguised_matches,
        matched_soft_signals=soft_matches,
        critical_signals=critical_match_texts,
        detector_version=ADVERTISER_DETECTOR_VERSION,
    )


def analyze_advertiser_signal(
    *,
    title: str = "",
    description: str = "",
    business_type: str = "",
    data: Optional[Dict[str, Any]] = None,
) -> AdvertiserSignalResult:
    """
    تحلیل کامل با score، confidence و diagnostics.
    """
    if is_official_consultant(business_type, data):
        return _build_result(
            ADVERTISER_SIGNAL_CONSULTANT, 0, "very_high", False, ["official_consultant"], [],
        )
    if not is_personal_category(business_type, data):
        return _build_result("", 0, "low", False, ["not_personal"], [])

    combined, raw_combined = _combined_ad_text(title, description, data)
    if not combined:
        return _build_result(
            ADVERTISER_SIGNAL_GENUINE_PERSONAL, 0, "low", False, ["empty_text"], [],
        )

    signals = _extract_all_signals(combined, raw_combined, data)
    score, _ = _aggregate_score(signals)
    classification, critical, reasons = _classify_from_signals(signals, score)
    confidence = _confidence_label(score, critical)
    return _build_result(classification, score, confidence, critical, reasons, signals)


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
    return analyze_advertiser_signal(
        title=title,
        description=description,
        business_type=business_type,
        data=data,
    )["classification"]


def has_owner_markers(
    title: str = "",
    description: str = "",
    data: Optional[Dict[str, Any]] = None,
) -> bool:
    """عبارات مالکیت در متن — شامل explicit، medium و soft owner."""
    combined, raw_combined = _combined_ad_text(title, description, data)
    if not combined:
        return False
    signals = _extract_all_signals(combined, raw_combined, data)
    return any(s.weight < 0 for s in signals)


def has_disguised_consultant_markers(
    title: str = "",
    description: str = "",
    data: Optional[Dict[str, Any]] = None,
) -> bool:
    """نشانه‌های مشاور پنهان در متن (disguised-positive signals)."""
    combined, raw_combined = _combined_ad_text(title, description, data)
    if not combined:
        return False
    signals = _extract_all_signals(combined, raw_combined, data)
    score, _ = _aggregate_score(signals)
    critical = any(
        s.critical or s.reason_code in CRITICAL_REASON_CODES
        or s.reason_code in STRONG_INVENTORY_REASONS
        for s in signals
    )
    if critical:
        return True
    return score >= DETECTOR_THRESHOLDS["disguised"] or any(s.weight > 0 for s in signals)


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
