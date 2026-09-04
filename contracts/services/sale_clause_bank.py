"""بانک Phase 1 بندهای فروش / مبایعه‌نامه — review_pending."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from contracts.services.money import format_toman

SALE_CORE_RENDERER_CODES = frozenset({
    'SALE_SUBJECT', 'SALE_PRICE', 'SALE_PAYMENT', 'SALE_TRANSFER',
    'SALE_PAYMENT_OBLIGATION',
})

SALE_DEPRECATED_CODES = frozenset({
    'SALE_MORTGAGE', 'SALE_TAX', 'SALE_DISPUTE', 'SALE_PENALTY',
})

SALE_COST_ITEM_LABELS = {
    'transfer_costs': 'هزینه‌های انتقال',
    'notary_costs': 'هزینه‌های دفترخانه',
    'pre_delivery_costs': 'بدهی‌ها و هزینه‌های قبل از تحویل',
    'post_delivery_costs': 'هزینه‌های بعد از تحویل',
    'other_costs': 'سایر هزینه توافق‌شده',
}

SALE_PARTY_LABELS = {
    'seller': 'فروشنده',
    'buyer': 'خریدار',
    'shared': 'مشترک',
}

SALE_PENALTY_CODE_MAP = {
    'payment_delay': 'SALE_PENALTY_PAYMENT',
    'delivery_delay': 'SALE_PENALTY_DELIVERY',
    'transfer_delay': 'SALE_PENALTY_OFFICIAL_TRANSFER',
}

SALE_PHASE1_DEFINITIONS: List[Dict[str, Any]] = [
    {
        'code': 'SALE_PROPERTY_DECLARATIONS',
        'title': 'وضعیت اعلامی مورد معامله',
        'category': 'property_status',
        'plain_explanation': 'وضعیت ملک را بر اساس اظهار فروشنده ثبت کنید؛ فایلینگ استعلام ثبتی انجام نمی‌دهد.',
        'body_template': (
            'فروشنده اعلام می‌نماید وضعیت مورد معامله از حیث تصرف و شرایط اعلام‌شده، مطابق اطلاعات '
            'مندرج در این قرارداد است و مسئولیت صحت اطلاعات و اظهارات ارائه‌شده بر عهده اظهارکننده '
            'خواهد بود.'
        ),
        'is_recommended': True,
        'legal_source_code': 'CIVIL_CODE',
        'legal_reference': 'قانون مدنی — ماده 10',
    },
    {
        'code': 'SALE_EXISTING_TENANT',
        'title': 'وجود مستأجر یا متصرف',
        'category': 'property_status',
        'plain_explanation': 'اگر ملک مستأجر یا متصرف دارد، این مورد را مشخص کنید.',
        'body_template': (
            'فروشنده اعلام می‌نماید مورد معامله در زمان تنظیم قرارداد دارای مستأجر یا متصرف است. '
            'وضعیت تحویل و خاتمه یا ادامه تصرف، مطابق توافقات ثبت‌شده بین طرفین خواهد بود.'
        ),
        'condition_expression': {'property_has_tenant': True},
        'is_recommended': True,
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_DELIVERY',
        'title': 'تحویل مورد معامله',
        'category': 'delivery',
        'plain_explanation': 'تاریخ و شرایط تحویل را از مرحله مبلغ و پرداخت بررسی کنید.',
        'body_template': (
            'فروشنده متعهد است مورد معامله را در تاریخ {{delivery_date}} با توابع، ملحقات و اقلام '
            'مورد توافق، مطابق مشخصات ثبت‌شده در قرارداد، به خریدار تحویل دهد.'
        ),
        'condition_expression': {'has_delivery_date': True},
        'is_recommended': True,
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_PAYMENT_OBLIGATION',
        'title': 'تعهد خریدار به پرداخت ثمن',
        'category': 'payment',
        'plain_explanation': 'متن تعهد پرداخت — مبالغ در ماده مالی قرارداد نمایش داده می‌شود.',
        'body_template': (
            'خریدار متعهد است ثمن معامله را مطابق مبالغ، مواعد و روش‌های پرداخت ثبت‌شده در برنامه '
            'پرداخت این قرارداد پرداخت نماید.'
        ),
        'condition_expression': {'has_payment_schedule': True},
        'is_optional': True,
        'is_recommended': True,
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_DOCUMENTS',
        'title': 'ارائه مدارک مورد نیاز',
        'category': 'seller_obligations',
        'plain_explanation': 'فروشنده مدارک لازم برای ادامه فرآیند را ارائه می‌کند.',
        'body_template': (
            'فروشنده متعهد است مدارک و مستنداتی را که برای انجام اقدامات توافق‌شده مربوط به '
            'انتقال مورد معامله لازم است، در حدود تعهدات این قرارداد و در موعد مقرر ارائه نماید.'
        ),
        'is_optional': True,
        'is_recommended': True,
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_OFFICIAL_TRANSFER',
        'title': 'اقدام برای انتقال رسمی',
        'category': 'official_transfer',
        'plain_explanation': 'زمان و محل اقدام برای انتقال رسمی را مشخص کنید.',
        'body_template': (
            'طرفین متعهدند در تاریخ {{official_transfer_date}} و در محل {{official_transfer_place}}، '
            'حسب الزامات قانونی و شرایط مورد معامله، برای انجام اقدامات لازم جهت انتقال رسمی و '
            'ارائه مدارک مورد نیاز اقدام نمایند.'
        ),
        'condition_expression': {'has_official_transfer_plan': True},
        'is_recommended': True,
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_SELLER_OBLIGATIONS',
        'title': 'تعهدات فروشنده',
        'category': 'seller_obligations',
        'plain_explanation': 'تعهدات کلی فروشنده در چارچوب قرارداد.',
        'body_template': (
            'فروشنده متعهد است در حدود مفاد این قرارداد، همکاری لازم برای تحویل مورد معامله، '
            'ارائه مدارک مورد توافق و انجام اقدامات لازم مربوط به انتقال را در مواعد تعیین‌شده انجام دهد.'
        ),
        'is_optional': True,
        'is_recommended': True,
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_BUYER_OBLIGATIONS',
        'title': 'تعهدات خریدار',
        'category': 'buyer_obligations',
        'plain_explanation': 'تعهدات کلی خریدار در چارچوب قرارداد.',
        'body_template': (
            'خریدار متعهد است پرداخت‌های مقرر، ارائه مدارک مورد نیاز خود و حضور یا همکاری لازم '
            'برای انجام مراحل توافق‌شده معامله را در مواعد تعیین‌شده انجام دهد.'
        ),
        'is_optional': True,
        'is_recommended': True,
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_COSTS',
        'title': 'هزینه‌های مرتبط با معامله',
        'category': 'costs',
        'plain_explanation': 'مسئول هر هزینه را مشخص کنید؛ پیش‌فرض قانونی تحمیل نمی‌شود.',
        'body_template': '{{costs_dynamic_body}}',
        'condition_expression': {'has_sale_cost_allocations': True},
        'is_recommended': True,
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_PENALTY_PAYMENT',
        'title': 'وجه التزام تأخیر در پرداخت',
        'category': 'penalties',
        'plain_explanation': 'فقط در صورت فعال‌سازی و تعیین مبلغ توسط طرفین.',
        'body_template': (
            'در صورت تأخیر خریدار در انجام پرداختی که موعد آن در قرارداد مشخص شده است، خریدار '
            'مطابق توافق طرفین مبلغ {{amount}} تومان به عنوان وجه التزام {{penalty_unit}} پرداخت خواهد کرد.'
        ),
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_PENALTY_DELIVERY',
        'title': 'وجه التزام تأخیر در تحویل',
        'category': 'penalties',
        'plain_explanation': 'فقط در صورت فعال‌سازی و تعیین مبلغ توسط طرفین.',
        'body_template': (
            'در صورت تأخیر فروشنده در تحویل مورد معامله پس از موعد تعیین‌شده، فروشنده مطابق توافق '
            'طرفین مبلغ {{amount}} تومان به عنوان وجه التزام {{penalty_unit}} پرداخت خواهد کرد.'
        ),
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_PENALTY_OFFICIAL_TRANSFER',
        'title': 'وجه التزام تأخیر در اقدام برای انتقال رسمی',
        'category': 'penalties',
        'plain_explanation': 'فقط در صورت فعال‌سازی و تعیین مبلغ توسط طرفین.',
        'body_template': (
            'در صورت عدم انجام تعهد مربوط به حضور یا اقدام برای انتقال رسمی در موعد تعیین‌شده '
            'توسط هر یک از طرفین، مسئولیت و وجه التزام توافق‌شده برای شخص متخلف مطابق مفاد این '
            'قرارداد اعمال خواهد شد.'
        ),
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'SALE_BREACH_TERMINATION',
        'title': 'تخلف از تعهدات و پایان قرارداد',
        'category': 'termination',
        'plain_explanation': 'قواعد کلی پایان یا انحلال قرارداد.',
        'body_template': (
            'قرارداد برای طرفین لازم‌الاتباع است و پایان یا انحلال آن پیش از اجرای کامل، صرفاً '
            'بر اساس توافق طرفین، حق فسخ مقرر در قرارداد یا سبب قانونی امکان‌پذیر خواهد بود. '
            'در صورت تخلف از تعهدی که برای آن ضمانت اجرای مشخص پیش‌بینی شده است، طرف ذی‌حق '
            'می‌تواند مطابق قرارداد و مقررات قانونی اقدام نماید.'
        ),
        'is_optional': True,
        'is_recommended': True,
        'legal_source_code': 'CIVIL_CODE',
    },
]


def build_sale_clause_context(wizard: Dict[str, Any]) -> Dict[str, Any]:
    fin = wizard.get('financial') or {}
    prop = wizard.get('property') or {}
    ctx = {**prop, **fin}
    ctx['property_has_tenant'] = bool(prop.get('has_tenant'))
    ctx['has_delivery_date'] = bool(fin.get('delivery_date'))
    ctx['has_payment_schedule'] = bool(fin.get('payments') or fin.get('total_price'))
    ctx['has_official_transfer_plan'] = bool(
        fin.get('official_transfer_date') or fin.get('transfer_date') or fin.get('transfer_place')
    )
    sale_costs = fin.get('sale_costs') or {}
    ctx['has_sale_cost_allocations'] = bool(sale_costs)
    ctx['sale_costs'] = sale_costs
    penalties = fin.get('penalties') or {}
    for key, item in penalties.items():
        ctx[f'penalty_{key}_enabled'] = bool(item.get('enabled'))
    return ctx


def render_sale_costs_body(costs: Dict[str, str]) -> str:
    lines = []
    for key, label in SALE_COST_ITEM_LABELS.items():
        party = costs.get(key)
        if party in SALE_PARTY_LABELS:
            lines.append(f'{label} بر عهده {SALE_PARTY_LABELS[party]} است.')
    return '\n'.join(lines)


def render_sale_clause_body(
    code: str,
    body_template: str,
    *,
    fin: Optional[Dict[str, Any]] = None,
    prop: Optional[Dict[str, Any]] = None,
    inline_values: Optional[Dict[str, Any]] = None,
) -> str:
    fin = fin or {}
    prop = prop or {}
    values = dict(inline_values or {})

    if code == 'SALE_COSTS':
        return render_sale_costs_body(fin.get('sale_costs') or {}) or body_template.replace(
            '{{costs_dynamic_body}}', '',
        )

    if code == 'SALE_DELIVERY':
        text = body_template.replace('{{delivery_date}}', fin.get('delivery_date') or '—')
        if fin.get('delivery_condition_note'):
            text += '\nوضعیت تحویل می‌تواند در صورت‌جلسه تحویل مرتبط ثبت شود.'
        return text

    if code == 'SALE_EXISTING_TENANT':
        text = body_template
        notes = []
        if prop.get('tenant_name'):
            notes.append(f'نام مستأجر/متصرف: {prop["tenant_name"]}')
        if prop.get('tenant_phone'):
            notes.append(f'تماس: {prop["tenant_phone"]}')
        if prop.get('occupancy_note'):
            notes.append(prop['occupancy_note'])
        if notes:
            text += '\n' + '\n'.join(notes)
        return text

    if code == 'SALE_OFFICIAL_TRANSFER':
        return (
            body_template
            .replace('{{official_transfer_date}}', fin.get('official_transfer_date') or fin.get('transfer_date') or '—')
            .replace('{{official_transfer_place}}', fin.get('transfer_place') or '—')
        )

    if code.startswith('SALE_PENALTY_'):
        amount = values.get('amount') or values.get('penalty_amount') or ''
        unit = values.get('penalty_unit') or values.get('unit') or 'daily'
        unit_label = 'روزانه' if unit == 'daily' else 'موردی'
        try:
            amount = format_toman(int(amount)) if amount else '—'
        except (TypeError, ValueError):
            amount = str(amount) if amount else '—'
        return (
            body_template
            .replace('{{amount}}', amount)
            .replace('{{penalty_unit}}', unit_label)
        )

    text = body_template
    for key, val in values.items():
        text = text.replace(f'{{{{{key}}}}}', str(val))
    return text
