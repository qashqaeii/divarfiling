"""Variable Registry و Template Engine امن برای Automation SMS."""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from django.conf import settings
from django.urls import NoReverseMatch, reverse

logger = logging.getLogger(__name__)

# فقط placeholderهای ساده {snake_case} — بدون expression یا attribute access
_VARIABLE_PATTERN = re.compile(r'\{([a-z_][a-z0-9_]*)\}')
_INVALID_BRACE_PATTERN = re.compile(r'\{[^{}]*\}')
_BROKEN_BRACE_PATTERN = re.compile(r'\{[^{}]*$|^[^{}]*\}|(?<!\{)\{(?![a-z_])|\}(?!\})')


@dataclass(frozen=True)
class VariableDef:
    key: str
    label: str
    description: str
    example: str
    category: str
    optional: bool = False
    allow_empty: bool = False


VARIABLE_REGISTRY: Dict[str, VariableDef] = {
    'name_part': VariableDef(
        'name_part', 'نام کاربر', 'نام کوتاه کاربر در ابتدای جمله',
        ' علی', 'user', allow_empty=True,
    ),
    'full_name': VariableDef(
        'full_name', 'نام کامل', 'نام و نام‌خانوادگی کاربر',
        'علی محمدی', 'user', allow_empty=True,
    ),
    'username': VariableDef(
        'username', 'نام کاربری', 'شناسه ورود کاربر',
        'ali_user', 'user', optional=True, allow_empty=True,
    ),
    'product': VariableDef(
        'product', 'محصول', 'نام محصول یا سرویس',
        'فایلینگ دیوار', 'product',
    ),
    'plan': VariableDef(
        'plan', 'پلن', 'نام پلن اشتراک',
        'ماهانه', 'product', optional=True, allow_empty=True,
    ),
    'price': VariableDef(
        'price', 'مبلغ', 'مبلغ عددی',
        '891000', 'product', optional=True, allow_empty=True,
    ),
    'price_formatted': VariableDef(
        'price_formatted', 'مبلغ (خوانا)', 'مبلغ با جداکننده',
        '891,000', 'product', optional=True, allow_empty=True,
    ),
    'code': VariableDef(
        'code', 'کد تخفیف', 'کد تخفیف در صورت وجود کمپین',
        'SAVE10', 'product', optional=True,
    ),
    'link': VariableDef(
        'link', 'لینک اقدام', 'لینک اصلی اقدام (تمدید/خرید)',
        'https://divarfiling.ir/pricing/', 'product',
    ),
    'date': VariableDef(
        'date', 'تاریخ', 'تاریخ مرتبط با رویداد',
        '1404/06/10', 'time', optional=True, allow_empty=True,
    ),
    'days_left': VariableDef(
        'days_left', 'روز باقی‌مانده', 'تعداد روز تا انقضا',
        '۳', 'time', optional=True, allow_empty=True,
    ),
    'expiry_date': VariableDef(
        'expiry_date', 'تاریخ انقضا', 'تاریخ پایان اشتراک',
        '1404/06/15', 'time', optional=True, allow_empty=True,
    ),
    'hours_ago': VariableDef(
        'hours_ago', 'ساعت گذشته', 'مدت زمان گذشته از رویداد',
        '۵', 'time', optional=True, allow_empty=True,
    ),
    'order_id': VariableDef(
        'order_id', 'شناسه سفارش', 'شماره سفارش',
        '12345', 'order', optional=True, allow_empty=True,
    ),
    'order_amount': VariableDef(
        'order_amount', 'مبلغ سفارش', 'مبلغ سفارش',
        '891,000', 'order', optional=True, allow_empty=True,
    ),
    'order_product': VariableDef(
        'order_product', 'محصول سفارش', 'نام محصول سفارش',
        'فایلینگ دیوار', 'order', optional=True, allow_empty=True,
    ),
    'license_plan': VariableDef(
        'license_plan', 'پلن لایسنس', 'نام پلن فعال',
        'ماهانه', 'license', optional=True, allow_empty=True,
    ),
    'license_expiry': VariableDef(
        'license_expiry', 'انقضای لایسنس', 'تاریخ انقضای لایسنس',
        '1404/06/15', 'license', optional=True, allow_empty=True,
    ),
    'download_link': VariableDef(
        'download_link', 'لینک دانلود', 'لینک دانلود نسخه ویندوز',
        'https://divarfiling.ir/license-guide/#download', 'windows', optional=True,
    ),
    'activation_link': VariableDef(
        'activation_link', 'لینک فعال‌سازی', 'راهنمای فعال‌سازی',
        'https://divarfiling.ir/license-guide/', 'windows', optional=True,
    ),
    'guide_link': VariableDef(
        'guide_link', 'لینک راهنما', 'راهنمای شروع یا فعال‌سازی',
        'https://divarfiling.ir/license-guide/', 'windows',
    ),
    'crm_link': VariableDef(
        'crm_link', 'لینک CRM', 'ورود به CRM فایلینگ دیوار',
        'https://divarfiling.ir/workspace/crm/', 'crm',
    ),
    'academy_link': VariableDef(
        'academy_link', 'لینک آکادمی', 'آموزش ویدیویی فایلینگ دیوار',
        'https://divarfiling.ir/academy/videos/', 'crm',
    ),
}

RULE_ALLOWED_VARIABLES: Dict[str, Set[str]] = {
    'license_expiring_3d': {
        'name_part', 'full_name', 'plan', 'product', 'days_left', 'expiry_date',
        'license_plan', 'license_expiry', 'link', 'date',
    },
    'expired_renewal_campaign': {
        'name_part', 'full_name', 'plan', 'product', 'expiry_date',
        'license_plan', 'license_expiry', 'link', 'code', 'date',
    },
    'pending_recovery': {
        'name_part', 'full_name', 'product', 'order_product', 'order_amount',
        'order_id', 'plan', 'price_formatted', 'code', 'link',
    },
    'failed_payment_followup': {
        'name_part', 'full_name', 'product', 'order_product', 'order_amount',
        'order_id', 'plan', 'link',
    },
    'users_onboarding': {
        'name_part', 'full_name', 'link', 'academy_link',
    },
    'windows_activation_nudge': {
        'name_part', 'full_name', 'download_link', 'activation_link', 'guide_link', 'link',
    },
    'windows_activate_no_launch': {
        'name_part', 'full_name', 'guide_link', 'link',
    },
    'crm_not_started_nudge': {
        'name_part', 'full_name', 'crm_link', 'academy_link', 'link',
    },
}

RULE_DEFAULT_TEMPLATES: Dict[str, str] = {
    'license_expiring_3d': (
        'سلام{name_part} 👋\n'
        'اشتراک فایلینگ دیوارت تا {days_left} روز دیگه تموم می‌شه.\n'
        'برای تمدید سریع: {link}'
    ),
    'expired_renewal_campaign': (
        'سلام{name_part} 👋\n'
        'اشتراک فایلینگ دیوارت تموم شده.\n'
        'برای فعال شدن دوباره سرویس، از اینجا تمدید کن:\n'
        '{link}'
    ),
    'pending_recovery': (
        'سلام{name_part} 👋\n'
        'خرید {product} هنوز کامل نشده.\n'
        'اگه قصد خرید داری، از اینجا ادامه بده:\n'
        '{link}'
    ),
    'failed_payment_followup': (
        'سلام{name_part} 👋\n'
        'پرداخت {product} کامل نشد.\n'
        'می‌تونی دوباره از اینجا امتحان کنی:\n'
        '{link}'
    ),
    'users_onboarding': (
        'سلام{name_part} 👋\n'
        'برای شروع کار با فایلینگ دیوار، این راهنمای کوتاه رو ببین:\n'
        '{academy_link}'
    ),
    'windows_activation_nudge': (
        'سلام{name_part} 👋\n'
        'نسخه ویندوز رو دانلود کردی ولی هنوز فعال نشده.\n'
        'راهنمای فعال‌سازی:\n'
        '{guide_link}'
    ),
    'windows_activate_no_launch': (
        'سلام{name_part} 👋\n'
        'فعال‌سازی انجام شده؛ فقط یک قدم مونده 🙂\n'
        'راهنمای شروع سریع:\n'
        '{guide_link}'
    ),
    'crm_not_started_nudge': (
        'سلام{name_part} 👋\n'
        'با CRM فایلینگ دیوار می‌تونی مشتری‌ها و پیگیری‌هات رو مرتب مدیریت کنی.\n'
        'شروع سریع:\n'
        '{crm_link}'
    ),
}

CATEGORY_LABELS = {
    'user': 'کاربر',
    'product': 'محصول',
    'time': 'زمان',
    'order': 'سفارش',
    'license': 'لایسنس',
    'windows': 'ویندوز',
    'crm': 'CRM / آموزش',
}


@dataclass
class TemplateValidation:
    ok: bool
    error: str = ''
    errors: List[str] = field(default_factory=list)
    variables_used: List[str] = field(default_factory=list)
    invalid_variables: List[str] = field(default_factory=list)
    disallowed_variables: List[str] = field(default_factory=list)


@dataclass
class TemplateRenderResult:
    ok: bool
    message: str = ''
    error: str = ''
    missing_variables: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    variables_used: List[str] = field(default_factory=list)


def _site_base() -> str:
    return (getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir').rstrip('/')


def _abs_url(path: str) -> str:
    if path.startswith('http://') or path.startswith('https://'):
        return path
    base = _site_base()
    if not path.startswith('/'):
        path = '/' + path
    return f'{base}{path}'


def _safe_reverse(name: str, **kwargs) -> str:
    try:
        return _abs_url(reverse(name, kwargs=kwargs or None))
    except NoReverseMatch:
        return _site_base() + '/'


def system_link_urls() -> Dict[str, str]:
    guide = _safe_reverse('license_guide')
    return {
        'link': getattr(settings, 'LICENSE_RENEWAL_LANDING_URL', None) or f'{_site_base()}/pricing/',
        'guide_link': guide,
        'activation_link': guide,
        'download_link': f'{guide}#download',
        'academy_link': _safe_reverse('public_academy_playlist'),
        'crm_link': _safe_reverse('workspace:crm_dashboard'),
    }


def parse_template_variables(template: str) -> List[str]:
    """استخراج متغیرهای template به ترتیب ظاهر."""
    if not template:
        return []
    seen: Set[str] = set()
    ordered: List[str] = []
    for match in _VARIABLE_PATTERN.finditer(template):
        key = match.group(1)
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def _find_syntax_errors(template: str) -> List[str]:
    errors: List[str] = []
    if not template:
        return errors
    # placeholderهای نامعتبر مثل {unknown-var} یا {name.attr}
    for match in _INVALID_BRACE_PATTERN.finditer(template):
        raw = match.group(0)
        if not _VARIABLE_PATTERN.fullmatch(raw):
            errors.append(f'ساختار نامعتبر: {raw}')
    # آکولاد باز/بسته نشده
    if template.count('{') != template.count('}'):
        errors.append('تعداد آکولادهای باز و بسته برابر نیست.')
    return errors


def validate_template(template: str, rule_key: str = '') -> TemplateValidation:
    template = (template or '').strip()
    if not template:
        return TemplateValidation(ok=False, error='متن پیام نمی‌تواند خالی باشد.')

    syntax_errors = _find_syntax_errors(template)
    if syntax_errors:
        return TemplateValidation(ok=False, error=syntax_errors[0], errors=syntax_errors)

    used = parse_template_variables(template)
    unknown = [v for v in used if v not in VARIABLE_REGISTRY]
    if unknown:
        msg = f'متغیر {{{unknown[0]}}} برای این اتوماسیون قابل استفاده نیست.'
        return TemplateValidation(
            ok=False,
            error=msg,
            variables_used=used,
            invalid_variables=unknown,
        )

    allowed = RULE_ALLOWED_VARIABLES.get(rule_key)
    disallowed: List[str] = []
    if allowed is not None:
        disallowed = [v for v in used if v not in allowed]
        if disallowed:
            msg = f'متغیر {{{disallowed[0]}}} برای این اتوماسیون قابل استفاده نیست.'
            return TemplateValidation(
                ok=False,
                error=msg,
                variables_used=used,
                disallowed_variables=disallowed,
            )

    return TemplateValidation(ok=True, variables_used=used)


def normalize_context(context: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Aliasهای سازگار با Runtime قدیمی + لینک‌های سیستمی."""
    ctx = dict(context or {})
    links = system_link_urls()

    if ctx.get('days') and not ctx.get('days_left'):
        ctx['days_left'] = ctx['days']
    if ctx.get('amount') and not ctx.get('order_amount'):
        ctx['order_amount'] = ctx['amount']
    if ctx.get('product') and not ctx.get('order_product'):
        ctx['order_product'] = ctx['product']
    if ctx.get('plan') and not ctx.get('license_plan'):
        ctx['license_plan'] = ctx['plan']
    if ctx.get('expiry_date') and not ctx.get('license_expiry'):
        ctx['license_expiry'] = ctx['expiry_date']

    for key, url in links.items():
        if not (ctx.get(key) or '').strip():
            ctx[key] = url

    if not (ctx.get('link') or '').strip():
        ctx['link'] = links['link']

    return {k: str(v or '') for k, v in ctx.items()}


def build_sample_context(rule_key: str = '') -> Dict[str, str]:
    ctx: Dict[str, str] = {}
    for key, var_def in VARIABLE_REGISTRY.items():
        ctx[key] = var_def.example
    ctx.update(system_link_urls())
    if rule_key == 'license_expiring_3d':
        ctx['days_left'] = '۳'
        ctx['days'] = '۳'
    return ctx


def safe_render(template: str, context: Dict[str, str]) -> str:
    """جایگزینی whitelist-only — بدون format/eval."""
    normalized = normalize_context(context)

    def _replacer(match: re.Match) -> str:
        key = match.group(1)
        if key not in VARIABLE_REGISTRY:
            return match.group(0)
        return normalized.get(key, '')

    return _VARIABLE_PATTERN.sub(_replacer, template or '')


def render_template(
    template: str,
    context: Dict[str, str],
    *,
    rule_key: str = '',
    strict_send: bool = False,
) -> TemplateRenderResult:
    validation = validate_template(template, rule_key)
    if not validation.ok:
        return TemplateRenderResult(ok=False, error=validation.error, variables_used=validation.variables_used)

    normalized = normalize_context(context)
    missing: List[str] = []
    warnings: List[str] = []

    for var_key in validation.variables_used:
        value = (normalized.get(var_key) or '').strip()
        var_def = VARIABLE_REGISTRY[var_key]
        if not value:
            if var_def.allow_empty:
                continue
            label = var_def.label
            if strict_send:
                missing.append(var_key)
            else:
                warnings.append(f'⚠️ {{{var_key}}} ({label}) برای این مخاطب مقدار ندارد.')

    if strict_send and missing:
        labels = ', '.join(f'{{{v}}}' for v in missing)
        return TemplateRenderResult(
            ok=False,
            error=f'متغیرهای بدون مقدار: {labels}',
            missing_variables=missing,
            variables_used=validation.variables_used,
            warnings=warnings,
        )

    message = safe_render(template, normalized)
    if not message.strip():
        return TemplateRenderResult(
            ok=False,
            error='پیام پس از render خالی شد.',
            variables_used=validation.variables_used,
            warnings=warnings,
        )

    return TemplateRenderResult(
        ok=True,
        message=message,
        variables_used=validation.variables_used,
        warnings=warnings,
    )


def get_effective_template(rule) -> str:
    """Template ذخیره‌شده یا پیش‌فرض Rule."""
    custom = (getattr(rule, 'message_template', '') or '').strip()
    if custom:
        return custom
    rule_key = getattr(rule, 'key', '') or ''
    return RULE_DEFAULT_TEMPLATES.get(rule_key, '')


def rule_template_is_valid(rule) -> TemplateValidation:
    template = get_effective_template(rule)
    rule_key = getattr(rule, 'key', '') or ''
    if not template:
        return TemplateValidation(ok=False, error='قالب پیامی تعریف نشده.')
    return validate_template(template, rule_key)


def get_default_template(rule_key: str) -> str:
    return RULE_DEFAULT_TEMPLATES.get(rule_key, '')


def variables_for_rule(rule_key: str) -> List[Dict[str, str]]:
    allowed = RULE_ALLOWED_VARIABLES.get(rule_key, set())
    rows: List[Dict[str, str]] = []
    for key in sorted(allowed, key=lambda k: (VARIABLE_REGISTRY[k].category, VARIABLE_REGISTRY[k].label)):
        var_def = VARIABLE_REGISTRY[key]
        rows.append({
            'key': key,
            'label': var_def.label,
            'description': var_def.description,
            'example': var_def.example,
            'category': var_def.category,
            'category_label': CATEGORY_LABELS.get(var_def.category, var_def.category),
            'placeholder': f'{{{key}}}',
            'optional': var_def.optional,
        })
    return rows


def estimate_sms_info(text: str) -> Dict[str, Any]:
    content = text or ''
    length = len(content)
    is_unicode = any(ord(ch) > 127 for ch in content)
    if is_unicode:
        single_limit = 70
        segment_size = 67
    else:
        single_limit = 160
        segment_size = 153

    if length == 0:
        segments = 0
    elif length <= single_limit:
        segments = 1
    else:
        segments = math.ceil(length / segment_size)

    long_warning = ''
    if segments > 1:
        long_warning = 'پیام طولانی است و ممکن است در چند پیامک ارسال شود.'

    return {
        'char_count': length,
        'segments': segments,
        'encoding': 'unicode' if is_unicode else 'gsm',
        'segment_label': f'حدود {segments} پیامک' if segments else '—',
        'long_warning': long_warning,
    }


def enrich_candidate_context(context: Dict[str, str], *, user=None) -> Dict[str, str]:
    """غنی‌سازی context مخاطب برای render."""
    ctx = dict(context or {})
    if user is not None:
        first = (getattr(user, 'first_name', '') or '').strip()
        last = (getattr(user, 'last_name', '') or '').strip()
        full = f'{first} {last}'.strip()
        if full and not ctx.get('full_name'):
            ctx['full_name'] = full
        if not ctx.get('name_part'):
            ctx['name_part'] = f' {first}' if first else ''
        if not ctx.get('username'):
            ctx['username'] = getattr(user, 'username', '') or ''
    return normalize_context(ctx)
