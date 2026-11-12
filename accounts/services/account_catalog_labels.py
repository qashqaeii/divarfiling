"""برچسب‌های فارسی محصول/پلن برای UI حساب کاربری (داشبورد، نمای کلی)."""
from __future__ import annotations

import re
from typing import Any

_PERSIAN_RE = re.compile(
    r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'
)

_PRODUCT_SLUG_LABELS: dict[str, str] = {
    'divar-extraction-bot': 'ربات استخراج دیوار',
}

_PRODUCT_TITLE_LABELS: dict[str, str] = {
    'local agency plan': 'پلن آژانس (میزکار تیمی)',
    'agency test': 'آژانس — محیط تست',
}

_PLAN_NAME_LABELS: dict[str, str] = {
    'local agency': 'آژانس محلی',
    'agency test plan': 'پلن تست آژانس',
}

_EN_WORDS_FA: dict[str, str] = {
    'local': 'محلی',
    'agency': 'آژانس',
    'plan': 'پلن',
    'test': 'تست',
    'workspace': 'میزکار',
    'crm': 'CRM',
    'bot': 'ربات',
    'header': '',
    'lite': 'لایت',
    'pro': 'حرفه‌ای',
    'premium': 'پریمیوم',
    'yearly': 'سالانه',
    'monthly': 'ماهانه',
    'divar': 'دیوار',
    'extraction': 'استخراج',
}


def _has_persian(text: str) -> bool:
    return bool(_PERSIAN_RE.search(text or ''))


def _first_persian_line(text: str, *, max_len: int = 120) -> str:
    raw = (text or '').strip()
    if not raw:
        return ''
    line = raw.replace('\r\n', '\n').split('\n', 1)[0].strip()
    if len(line) > max_len:
        line = line[: max_len - 1].rstrip() + '…'
    return line if _has_persian(line) else ''


def _translate_loose_en_title(title: str) -> str:
    key = (title or '').strip().lower()
    if key in _PRODUCT_TITLE_LABELS:
        return _PRODUCT_TITLE_LABELS[key]

    tokens = [t for t in re.split(r'[\s\-–—_/]+', title or '') if t]
    if not tokens:
        return title or ''

    lowered = [t.lower() for t in tokens]
    if lowered == ['local', 'agency', 'plan']:
        return 'پلن آژانس (محلی)'
    if 'agency' in lowered and 'test' in lowered:
        return 'پلن تست آژانس'

    fa_tokens: list[str] = []
    for tok in tokens:
        mapped = _EN_WORDS_FA.get(tok.lower())
        if mapped is None:
            return title
        if mapped:
            fa_tokens.append(mapped)

    if not fa_tokens:
        return title or ''

    if fa_tokens and fa_tokens[-1] == 'پلن':
        body = ' '.join(fa_tokens[:-1])
        return f'پلن {body}'.strip() if body else 'پلن'
    return ' '.join(fa_tokens)


def product_account_label(product: Any) -> str:
    if product is None:
        return 'محصول'

    title = (getattr(product, 'title', None) or '').strip()
    if title and _has_persian(title):
        return title

    short = _first_persian_line(getattr(product, 'short_description', None) or '')
    if short:
        return short

    slug = (getattr(product, 'slug', None) or '').strip().lower()
    if slug in _PRODUCT_SLUG_LABELS:
        return _PRODUCT_SLUG_LABELS[slug]

    if title:
        translated = _translate_loose_en_title(title)
        if translated != title or _has_persian(translated):
            return translated

    return title or 'محصول'


def _plan_duration_label(plan: Any) -> str:
    plan_type = (getattr(plan, 'plan_type', None) or '').strip()
    days = int(getattr(plan, 'duration_days', 0) or 0)
    mapping = {
        'daily': '۷ روز',
        'monthly': '۱ ماه',
        'quarterly': '۳ ماه',
        'yearly': '۱ سال',
        'lifetime': 'مادام‌العمر',
        'single': 'یک‌سیستمی',
        'multi': 'چندسیستمی',
    }
    if plan_type in mapping:
        return mapping[plan_type]
    if days:
        return f'{days} روز'
    display = getattr(plan, 'get_plan_type_display', None)
    if callable(display):
        return str(display())
    return ''


def plan_account_label(plan: Any) -> str:
    if plan is None:
        return ''

    name = (getattr(plan, 'name', None) or '').strip()
    if name and _has_persian(name):
        return name

    tagline = (getattr(plan, 'tagline', None) or '').strip()
    if tagline and _has_persian(tagline):
        return tagline

    key = name.lower()
    if key in _PLAN_NAME_LABELS:
        return _PLAN_NAME_LABELS[key]

    duration = _plan_duration_label(plan)
    if name:
        loose = _translate_loose_en_title(name)
        if loose != name or _has_persian(loose):
            if duration and duration not in loose:
                return f'{loose} ({duration})'
            return loose

    display = getattr(plan, 'get_plan_type_display', None)
    if callable(display):
        type_label = str(display())
        if duration and duration != type_label:
            return f'{type_label} · {duration}'
        return type_label

    return duration or name


def order_product_line(order: Any) -> str:
    product = getattr(order, 'product', None)
    return product_account_label(product)


def license_product_line(license_obj: Any) -> str:
    order = getattr(license_obj, 'order', None)
    if order is None:
        plan = getattr(license_obj, 'plan', None)
        product = getattr(plan, 'product', None) if plan else None
    else:
        product = getattr(order, 'product', None)
        plan = getattr(order, 'plan', None)
    title = product_account_label(product)
    plan_label = plan_account_label(plan)
    if plan_label and plan_label.casefold() not in title.casefold():
        return f'{title} — {plan_label}'
    return title
