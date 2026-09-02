"""تحلیل قابل‌نمایش آگهی‌دهنده — لایه Presentation روی موتور advertiser_signal V2."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.services.advertiser_signal import (
    ADVERTISER_SIGNAL_CONSULTANT,
    ADVERTISER_SIGNAL_DISGUISED,
    ADVERTISER_SIGNAL_GENUINE_PERSONAL,
    analyze_advertiser_signal,
    advertiser_signal_label,
)
from workspace.services.advertiser_signal import _description_from_data  # noqa: PLC2701

# ---------------------------------------------------------------------------
# Reason mapping (تنها منبع متمرکز برای UI)
# ---------------------------------------------------------------------------

REASON_LABELS: Dict[str, str] = {
    'agent_contact_restriction': 'محدودیت تماس برای مشاوران و همکاران',
    'professional_broker_identity': 'عبارات مرتبط با فعالیت حرفه‌ای املاک',
    'inventory_language': 'استفاده از ادبیات چندفایلی و فایل‌های مشابه',
    'inventory_language_critical': 'ادبیات قوی فایل و کد فایل',
    'professional_workflow_language': 'ادبیات حرفه‌ای هماهنگی و بازدید',
    'brokerage_sales_language': 'عبارات بازاریابی و فیلتر مشتری',
    'broker_branding': 'نشانه‌های برند یا دفتر املاک',
    'structured_broker_metadata': 'اطلاعات ساختاری مرتبط با مشاور',
    'explicit_owner_claim': 'اظهار مستقیم مالکیت',
    'owner_language': 'عبارات مرتبط با فروش یا ارتباط مستقیم با مالک',
    'soft_owner_language': 'عبارات مرتبط با معامله بدون واسطه',
    'official_consultant': 'مشاور رسمی در دیوار',
}

REASON_DESCRIPTIONS: Dict[str, str] = {
    'agent_contact_restriction': (
        'در متن از مشاوران یا همکاران خواسته شده تماس نگیرند؛ '
        'این یکی از نشانه‌های قوی فعالیت مشاوری در بازار املاک ایران است.'
    ),
    'professional_broker_identity': (
        'عباراتی در متن دیده شد که معمولاً در آگهی‌های مشاوران حرفه‌ای استفاده می‌شود.'
    ),
    'inventory_language': (
        'در متن به فایل‌ها یا موارد مشابه اشاره شده که نشانه مدیریت چند ملک است.'
    ),
    'inventory_language_critical': (
        'اشاره مستقیم به کد فایل یا فایل‌های مشابه موجود — نشانه قوی فعالیت مشاوری.'
    ),
    'professional_workflow_language': (
        'ادبیات هماهنگی بازدید یا ارسال فیلم که در کار مشاوری رایج است.'
    ),
    'brokerage_sales_language': (
        'عباراتی مثل «فقط خریدار واقعی» یا «گزینه مناسب شما» در متن دیده شد.'
    ),
    'broker_branding': (
        'نشانه‌های برندینگ دفتر املاک یا استفاده تزئینی از واژه‌های تخصصی مشاور.'
    ),
    'structured_broker_metadata': (
        'در داده‌های آگهی اطلاعات ساختاری مرتبط با مشاور شناسایی شد.'
    ),
    'explicit_owner_claim': 'آگهی‌دهنده به مالکیت مستقیم ملک اشاره کرده است.',
    'owner_language': 'عباراتی مرتبط با فروش یا ارتباط مستقیم با مالک در متن دیده شد.',
    'soft_owner_language': 'عباراتی مثل «بدون واسطه» در متن دیده شد.',
    'official_consultant': 'این آگهی با حساب مشاور/آژانس رسمی در دیوار منتشر شده است.',
}

CONFIDENCE_LABELS: Dict[str, str] = {
    'very_high': 'اطمینان خیلی بالا',
    'high': 'اطمینان بالا',
    'medium': 'اطمینان متوسط',
    'low': 'اطمینان پایین',
}

PRIMARY_REASON_PRIORITY: tuple[str, ...] = (
    'agent_contact_restriction',
    'structured_broker_metadata',
    'professional_broker_identity',
    'broker_branding',
    'inventory_language_critical',
    'inventory_language',
    'professional_workflow_language',
    'brokerage_sales_language',
)

DISCLAIMER_TEXT = (
    'این تحلیل بر اساس متن آگهی و قواعد تشخیصی سیستم است و جایگزین '
    'بررسی انسانی یا تماس مستقیم نمی‌شود.'
)

# ترتیب نمایش: reasonهای critical مهم‌تر
_CRITICAL_REASONS = frozenset({
    'agent_contact_restriction',
    'professional_broker_identity',
    'structured_broker_metadata',
    'broker_branding',
    'inventory_language_critical',
})


def _listing_description(listing) -> str:
    description = getattr(listing, 'description', '') or ''
    if not str(description).strip():
        description = _description_from_data(getattr(listing, 'data', None) or {})
    return description


def _humanize_matched_text(text: str, reason_code: str) -> str:
    """تبدیل matched_text خام به جمله قابل فهم — بدون regex/weight."""
    t = (text or '').strip()
    if not t:
        return ''
    if reason_code == 'agent_contact_restriction':
        if 'همکار' in t:
            return 'از همکاران خواسته شده تماس نگیرند'
        if 'مشاور' in t:
            return 'از مشاوران خواسته شده تماس نگیرند'
        if 'املاک' in t:
            return 'از املاک خواسته شده تماس نگیرند'
        if 'بنگاه' in t or 'آژانس' in t:
            return 'از بنگاه/آژانس خواسته شده تماس نگیرند'
        if 'واسطه' in t or 'دلال' in t:
            return 'از واسطه خواسته شده تماس نگیرند'
        return 'محدودیت تماس برای فعالان بازار املاک در متن ذکر شده'
    if reason_code in ('inventory_language', 'inventory_language_critical'):
        if 'کد فایل' in t or 'شماره فایل' in t:
            return f'اشاره به {t}'
        if 'مشابه' in t or 'موارد' in t or 'گزینه' in t:
            return f'اشاره به {t}'
        if 'فایل' in t:
            return f'استفاده از ادبیات فایل: «{t}»'
    if reason_code == 'professional_workflow_language':
        if 'فیلم' in t:
            return 'ارسال فیلم کامل ملک پیشنهاد شده'
        if 'بازدید' in t or 'هماهنگ' in t:
            return 'هماهنگی جهت بازدید ذکر شده'
        return f'ادبیات حرفه‌ای: «{t}»'
    if reason_code == 'professional_broker_identity':
        return f'عبارات مشاوری: «{t}»'
    if reason_code == 'broker_branding':
        return 'نشانه برندینگ دفتر املاک در متن'
    if reason_code == 'brokerage_sales_language':
        return f'«{t}»'
    if reason_code == 'structured_broker_metadata':
        return 'اطلاعات مشاور در داده‌های آگهی'
    if reason_code == 'explicit_owner_claim':
        return f'اظهار مالکیت: «{t}»'
    if reason_code in ('owner_language', 'soft_owner_language'):
        return f'«{t}»'
    if len(t) > 80:
        return t[:77] + '…'
    return f'«{t}»'


def _pick_primary_reason(reason_codes: List[str]) -> str:
    for code in PRIMARY_REASON_PRIORITY:
        if code in reason_codes:
            return code
    return reason_codes[0] if reason_codes else ''


def _qualified_classification_label(classification: str, confidence: str) -> str:
    if confidence in ('low', 'medium'):
        if classification == ADVERTISER_SIGNAL_GENUINE_PERSONAL:
            return 'احتمالاً مالک واقعی'
        if classification == ADVERTISER_SIGNAL_DISGUISED:
            return 'نیازمند بررسی'
    return advertiser_signal_label(classification) or 'شخصی'


def _build_summary(
    classification: str,
    confidence: str,
    primary_reason: str,
    has_owner: bool,
    has_disguised: bool,
) -> str:
    if classification == ADVERTISER_SIGNAL_CONSULTANT:
        return REASON_DESCRIPTIONS.get('official_consultant', '')

    if classification == ADVERTISER_SIGNAL_DISGUISED:
        if primary_reason and primary_reason in REASON_DESCRIPTIONS:
            return REASON_DESCRIPTIONS[primary_reason]
        return 'در متن آگهی نشانه‌های قوی فعالیت مشاوری شناسایی شد.'

    # genuine_personal
    if has_owner:
        return (
            'بر اساس متن آگهی، نشانه قوی از فعالیت مشاوری شناسایی نشد. '
            'آگهی‌دهنده به مالکیت مستقیم ملک اشاره کرده است.'
        )
    if has_disguised and confidence in ('low', 'medium'):
        return (
            'بر اساس متن آگهی، نشانه معناداری از فعالیت مشاوری دیده نشد؛ '
            'با این حال برخی عبارات مبهم وجود دارد و بررسی بیشتر توصیه می‌شود.'
        )
    return (
        'بر اساس متن آگهی و اطلاعات آگهی‌دهنده، '
        'نشانه قوی از فعالیت مشاوری شناسایی نشد.'
    )


def _group_signals_by_reason(
    raw: Any,
    reason_codes: List[str],
) -> Dict[str, List[str]]:
    """از matched texts و reason codes، bulletهای گروه‌بندی‌شده بساز."""
    disguised = list(raw.get('matched_disguised_signals') or [])
    critical = list(raw.get('critical_signals') or [])
    owner = list(raw.get('matched_owner_signals') or [])
    soft = list(raw.get('matched_soft_signals') or [])

    primary: List[str] = []
    secondary: List[str] = []
    owner_bullets: List[str] = []
    seen: set[str] = set()

    def add_unique(target: List[str], item: str) -> None:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            target.append(key)

    for code in reason_codes:
        if code in _CRITICAL_REASONS:
            for text in critical + disguised:
                hint = _humanize_matched_text(text, code)
                add_unique(primary, hint)

    for text in critical:
        for code in reason_codes:
            if code in _CRITICAL_REASONS:
                add_unique(primary, _humanize_matched_text(text, code))

    for text in disguised:
        if text in critical:
            continue
        for code in reason_codes:
            if code not in _CRITICAL_REASONS and code in (
                'inventory_language', 'inventory_language_critical',
                'professional_workflow_language', 'brokerage_sales_language',
            ):
                add_unique(
                    secondary if code in ('professional_workflow_language', 'brokerage_sales_language') else primary,
                    _humanize_matched_text(text, code),
                )

    for text in soft:
        add_unique(secondary, _humanize_matched_text(text, 'professional_workflow_language'))

    for text in owner:
        for code in ('explicit_owner_claim', 'owner_language', 'soft_owner_language'):
            if code in reason_codes:
                add_unique(owner_bullets, _humanize_matched_text(text, code))
                break
        else:
            add_unique(owner_bullets, _humanize_matched_text(text, 'explicit_owner_claim'))

    if not primary and disguised:
        for text in disguised[:4]:
            add_unique(primary, _humanize_matched_text(text, reason_codes[0] if reason_codes else ''))

    return {
        'primary': primary[:6],
        'secondary': secondary[:4],
        'owner': owner_bullets[:4],
    }


def analyze_listing_advertiser(listing) -> Dict[str, Any]:
    """تحلیل کامل یک Listing — خروجی امن برای UI (بدون regex/weight خام)."""
    raw = analyze_advertiser_signal(
        title=getattr(listing, 'title', '') or '',
        description=_listing_description(listing),
        business_type=getattr(listing, 'business_type', '') or '',
        data=getattr(listing, 'data', None) or {},
    )
    classification = raw.get('classification') or ''
    confidence = raw.get('confidence') or 'low'
    reason_codes = list(raw.get('reasons') or [])
    owner_signals_raw = list(raw.get('matched_owner_signals') or [])
    disguised_reasons = [c for c in reason_codes if c not in (
        'explicit_owner_claim', 'owner_language', 'soft_owner_language',
        'official_consultant', 'not_personal', 'empty_text',
    )]

    primary_reason = _pick_primary_reason(disguised_reasons or reason_codes)
    groups = _group_signals_by_reason(raw, disguised_reasons or reason_codes)

    # owner bullets مستقل از reason_codes (وزن منفی در reasons نیست)
    if owner_signals_raw and not groups['owner']:
        seen_owner: set[str] = set()
        for text in owner_signals_raw:
            for code in ('explicit_owner_claim', 'owner_language', 'soft_owner_language'):
                hint = _humanize_matched_text(text, code)
                if hint and hint not in seen_owner:
                    seen_owner.add(hint)
                    groups['owner'].append(hint)
    classification_label = advertiser_signal_label(classification) or 'شخصی'
    qualified_label = _qualified_classification_label(classification, confidence)
    confidence_label = CONFIDENCE_LABELS.get(confidence, 'اطمینان پایین')

    badge_label = f'{qualified_label} · {confidence_label}'
    if confidence in ('very_high', 'high'):
        badge_label = f'{classification_label} · {confidence_label}'

    human_reasons = [
        REASON_LABELS.get(code, code)
        for code in disguised_reasons
        if code in REASON_LABELS
    ]

    return {
        'classification': classification,
        'classification_label': classification_label,
        'classification_label_qualified': qualified_label,
        'confidence': confidence,
        'confidence_label': confidence_label,
        'badge_label': badge_label,
        'critical': bool(raw.get('critical')),
        'primary_reason': primary_reason,
        'primary_reason_label': REASON_LABELS.get(primary_reason, ''),
        'summary': _build_summary(
            classification,
            confidence,
            primary_reason,
            bool(groups['owner']),
            bool(groups['primary'] or groups['secondary']),
        ),
        'primary_signals': groups['primary'],
        'secondary_signals': groups['secondary'],
        'owner_signals': groups['owner'],
        'reasons': human_reasons,
        'disclaimer': DISCLAIMER_TEXT,
        'detector_version': raw.get('detector_version', 1),
        # score فقط برای admin/debug — در template نمایش داده نشود
        'score': raw.get('score', 0),
    }


def build_public_analysis_payload(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """خروجی امن UI — بدون score و reason_code داخلی."""
    return {
        k: v for k, v in analysis.items()
        if k not in ('score', 'primary_reason')
    }


def attach_feedback_state(analysis: Dict[str, Any], feedback_obj) -> Dict[str, Any]:
    """وضعیت feedback کاربر را به analysis اضافه می‌کند."""
    if feedback_obj is None:
        analysis['feedback'] = {'submitted': None, 'user_correction': ''}
        return analysis
    analysis['feedback'] = {
        'submitted': feedback_obj.feedback,
        'user_correction': feedback_obj.user_correction or '',
    }
    return analysis
