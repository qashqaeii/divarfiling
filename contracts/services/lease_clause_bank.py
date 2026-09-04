"""بانک Phase 1 بندهای رهن و اجاره — metadata و متن پیشنهادی (review_pending)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from contracts.constants import CLAUSE_REVIEW_PENDING, CONTRACT_TYPE_LEASE
from contracts.services.money import format_toman

# ——— کدهای مواد اصلی (از wizard/renderer؛ در Clause Library فعال نیستند) ———
LEASE_CORE_RENDERER_CODES = frozenset({
    'LEASE_SUBJECT', 'LEASE_TERM', 'LEASE_DEPOSIT', 'LEASE_RENT',
    'LEASE_PAYMENT', 'LEASE_RENT_PAYMENT',
})

# ——— risk metadata (بدون migration) ———
LEASE_CLAUSE_RISK: Dict[str, str] = {
    'LEASE_USE_PURPOSE': 'medium',
    'LEASE_SUBLEASE': 'high',
    'LEASE_SUBLEASE_WITH_CONSENT': 'high',
    'LEASE_DELIVERY': 'medium',
    'LEASE_COSTS': 'medium',
    'LEASE_REPAIRS': 'high',
    'LEASE_CARE': 'medium',
    'LEASE_VACATE': 'medium',
    'LEASE_DEPOSIT_RETURN': 'high',
    'LEASE_PENALTY_DELIVERY': 'high',
    'LEASE_PENALTY_VACATE': 'high',
    'LEASE_PENALTY_DEPOSIT_RETURN': 'high',
    'LEASE_BREACH_TERMINATION': 'high',
}

USAGE_TYPE_LABELS = {
    'residential': 'مسکونی',
    'office': 'اداری',
    'commercial': 'تجاری',
    'other': 'سایر',
}

COST_ITEM_LABELS = {
    'water': 'آب',
    'electricity': 'برق',
    'gas': 'گاز',
    'phone': 'تلفن',
    'charge': 'شارژ ساختمان',
    'sewage': 'فاضلاب',
    'property_tax': 'عوارض',
    'other_consumption_costs': 'سایر هزینه‌های مصرفی',
}

PARTY_LABELS = {'landlord': 'موجر', 'tenant': 'مستأجر'}

PENALTY_CODE_MAP = {
    'landlord_delivery_delay': 'LEASE_PENALTY_DELIVERY',
    'tenant_vacate_delay': 'LEASE_PENALTY_VACATE',
    'deposit_return_delay': 'LEASE_PENALTY_DEPOSIT_RETURN',
}

# superseded by Phase 1 — deactivate on seed
LEASE_DEPRECATED_CODES = frozenset({
    'LEASE_UTILITIES', 'LEASE_PENALTY', 'LEASE_DISPUTE', 'LEASE_SUBLEASE_OLD',
})

LEASE_PHASE1_DEFINITIONS: List[Dict[str, Any]] = [
    {
        'code': 'LEASE_USE_PURPOSE',
        'title': 'نوع و حدود استفاده از مورد اجاره',
        'category': 'usage',
        'plain_explanation': 'نوع استفاده را مشخص کنید تا حدود استفاده مستأجر در قرارداد روشن باشد.',
        'body_template': (
            'مستأجر متعهد است مورد اجاره را صرفاً برای استفاده {{usage_type}} و در حدود متعارف '
            'آن مورد استفاده قرار دهد و از هرگونه استفاده مغایر با نوع استفاده تعیین‌شده یا استفاده‌ای '
            'که موجب ورود خسارت یا ایجاد مزاحمت غیرمتعارف شود خودداری نماید.'
        ),
        'condition_expression': {},
        'is_required': False,
        'is_recommended': True,
        'is_optional': False,
        'legal_reference': 'قانون مدنی — مواد 490، 492',
        'legal_source_code': 'CIVIL_CODE',
        'legal_note': 'Civil Code Art. 490, 492; general contractual terms',
    },
    {
        'code': 'LEASE_SUBLEASE',
        'title': 'انتقال منافع به غیر — منع',
        'category': 'transfer',
        'plain_explanation': (
            'اصل قانونی امکان انتقال منافع است مگر خلاف آن شرط شود؛ انتخاب طرفین باید صریح باشد.'
        ),
        'body_template': (
            'مستأجر حق واگذاری تمام یا بخشی از منافع مورد اجاره به شخص ثالث را، تحت هر عنوانی '
            'که موجب انتقال حق استفاده از مورد اجاره شود، بدون رضایت موجر ندارد.'
        ),
        'condition_expression': {'transfer_to_third_party_allowed': False},
        'is_recommended': True,
        'legal_reference': 'قانون مدنی — ماده 474',
        'legal_source_code': 'CIVIL_CODE',
        'legal_note': 'Civil Code Art. 474',
    },
    {
        'code': 'LEASE_SUBLEASE_WITH_CONSENT',
        'title': 'انتقال منافع به غیر — با رضایت موجر',
        'category': 'transfer',
        'plain_explanation': (
            'اصل قانونی امکان انتقال منافع است مگر خلاف آن شرط شود؛ انتخاب طرفین باید صریح باشد.'
        ),
        'body_template': (
            'واگذاری منافع مورد اجاره به شخص ثالث صرفاً با رضایت موجر و در حدود شرایط مورد توافق '
            'طرفین امکان‌پذیر است.'
        ),
        'condition_expression': {'transfer_to_third_party_allowed': True},
        'is_recommended': True,
        'legal_reference': 'قانون مدنی — ماده 474',
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'LEASE_DELIVERY',
        'title': 'تحویل مورد اجاره',
        'category': 'delivery',
        'plain_explanation': 'تاریخ واقعی تحویل و وضعیت ملک را مشخص کنید.',
        'body_template': (
            'موجر متعهد است مورد اجاره را در تاریخ {{delivery_date}} با توابع و ملحقات مورد توافق، '
            'در وضعیتی که امکان استفاده مورد نظر مستأجر فراهم باشد، تحویل دهد.'
        ),
        'condition_expression': {'has_delivery_date': True},
        'is_recommended': True,
        'legal_reference': 'قانون مدنی — مواد 476، 477',
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'LEASE_COSTS',
        'title': 'هزینه‌های جاری و مشترک',
        'category': 'costs',
        'plain_explanation': 'مسئول پرداخت هر هزینه را مشخص کنید تا در پایان قرارداد اختلاف کمتری ایجاد شود.',
        'body_template': '{{costs_dynamic_body}}',
        'condition_expression': {'has_cost_allocations': True},
        'is_recommended': True,
        'legal_reference': 'قانون روابط موجر و مستأجر — ماده 4',
        'legal_source_code': 'LANDLORD_TENANT',
    },
    {
        'code': 'LEASE_REPAIRS',
        'title': 'تعمیرات و نگهداری فنی',
        'category': 'repairs',
        'plain_explanation': 'مسئول تعمیرات اساسی و جزئی را جداگانه تعیین کنید.',
        'body_template': (
            'هزینه تعمیرات و مخارج لازم برای امکان استفاده متعارف از مورد اجاره مطابق قانون و توافق '
            'طرفین بر عهده {{major_repairs_party}} است. هزینه تعمیرات جزئی و امور ناشی از استفاده '
            'روزمره مطابق توافق طرفین بر عهده {{minor_repairs_party}} خواهد بود.'
        ),
        'condition_expression': {'has_repair_allocations': True},
        'is_recommended': True,
        'legal_reference': 'قانون مدنی — مواد 485، 486',
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'LEASE_CARE',
        'title': 'حفظ و نگهداری مورد اجاره',
        'category': 'obligations',
        'plain_explanation': 'این بند درباره خسارت ناشی از استفاده نامتعارف است، نه فرسودگی عادی.',
        'body_template': (
            'مستأجر متعهد است در استفاده از مورد اجاره رفتار متعارف داشته و از تعدی یا تفریط خودداری '
            'نماید. مسئولیت خساراتی که ناشی از تعدی، تفریط یا استفاده خارج از حدود مورد توافق مستأجر '
            'باشد، بر عهده وی خواهد بود.'
        ),
        'is_required': False,
        'is_recommended': True,
        'is_optional': True,
        'legal_reference': 'قانون مدنی — مواد 490، 493',
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'LEASE_VACATE',
        'title': 'تخلیه در پایان مدت',
        'category': 'vacating',
        'plain_explanation': 'تعهد تخلیه در پایان مدت را روشن می‌کند.',
        'body_template': (
            'با پایان مدت اجاره و در صورت عدم تمدید یا توافق جدید، مستأجر مکلف است مورد اجاره را '
            'تخلیه و مطابق وضعیت قابل استناد در قرارداد و صورت‌جلسه‌های مرتبط به موجر تحویل دهد.'
        ),
        'condition_expression': {'has_lease_end': True},
        'is_recommended': True,
        'legal_reference': 'قانون مدنی — ماده 494؛ قانون روابط موجر و مستأجر — مواد 3، 4',
        'legal_source_code': 'LANDLORD_TENANT',
    },
    {
        'code': 'LEASE_DEPOSIT_RETURN',
        'title': 'استرداد ودیعه',
        'category': 'deposit',
        'plain_explanation': 'اگر ودیعه قرارداد قبلی باقی مانده، همان را ثبت کنید.',
        'body_template': (
            'موجر متعهد است در پایان رابطه استیجاری و همزمان با انجام شرایط قانونی و قراردادی مربوط '
            'به تخلیه و تحویل، مبلغ ودیعه/قرض‌الحسنه موضوع قرارداد را مطابق مقررات و توافق طرفین '
            'مسترد نماید.'
        ),
        'condition_expression': {'has_deposit': True, 'deposit_mode': ['new']},
        'is_recommended': True,
        'legal_reference': 'قانون روابط موجر و مستأجر — مواد 2 (اصلاح 1403)، 4',
        'legal_source_code': 'LANDLORD_TENANT',
    },
    {
        'code': 'LEASE_DEPOSIT_RETAINED',
        'title': 'باقی‌ماندن ودیعه قرارداد قبلی',
        'category': 'deposit',
        'plain_explanation': 'اگر ودیعه قرارداد قبلی باقی مانده، همان را ثبت کنید.',
        'body_template': (
            'طرفین توافق دارند مبلغ {{deposit_amount}} تومان از ودیعه قرارداد پیشین با مشخصات '
            '{{previous_contract_reference}} به عنوان ودیعه این قرارداد نیز نزد موجر باقی بماند.'
        ),
        'condition_expression': {'deposit_mode': 'retained'},
        'is_recommended': True,
        'legal_reference': 'قانون روابط موجر و مستأجر — مواد 2، 4',
        'legal_source_code': 'LANDLORD_TENANT',
    },
    {
        'code': 'LEASE_PENALTY_DELIVERY',
        'title': 'وجه التزام تأخیر در تحویل',
        'category': 'penalties',
        'plain_explanation': 'وجه التزام فقط وقتی وارد قرارداد شود که خود طرفین آن را فعال و مبلغ آن را مشخص کرده باشند.',
        'body_template': (
            'در صورت تأخیر موجر در تحویل مورد اجاره پس از تاریخ مقرر، موجر بابت هر روز تأخیر مبلغ '
            '{{amount}} تومان به عنوان وجه التزام قراردادی به مستأجر پرداخت خواهد کرد.'
        ),
        'legal_reference': 'قانون مدنی — مواد 221، 226، 230',
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'LEASE_PENALTY_VACATE',
        'title': 'وجه التزام تأخیر در تخلیه',
        'category': 'penalties',
        'plain_explanation': 'وجه التزام فقط وقتی وارد قرارداد شود که خود طرفین آن را فعال و مبلغ آن را مشخص کرده باشند.',
        'body_template': (
            'در صورت ادامه تصرف مستأجر پس از پایان مدت قرارداد بدون توافق جدید، مستأجر بابت هر روز '
            'تأخیر مبلغ {{amount}} تومان به عنوان وجه التزام قراردادی پرداخت خواهد کرد؛ اعمال این '
            'شرط تابع حقوق و الزامات قانونی طرفین خواهد بود.'
        ),
        'legal_reference': 'قانون مدنی — مواد 221، 226، 230',
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'LEASE_PENALTY_DEPOSIT_RETURN',
        'title': 'وجه التزام تأخیر در استرداد ودیعه',
        'category': 'penalties',
        'plain_explanation': 'وجه التزام فقط وقتی وارد قرارداد شود که خود طرفین آن را فعال و مبلغ آن را مشخص کرده باشند.',
        'body_template': (
            'در صورت تأخیر موجر در استرداد ودیعه پس از تحقق شرایط قراردادی و قانونی استرداد آن، موجر '
            'بابت هر روز تأخیر مبلغ {{amount}} تومان به عنوان وجه التزام قراردادی پرداخت خواهد کرد.'
        ),
        'legal_reference': 'قانون مدنی — مواد 221، 226، 230؛ قانون روابط موجر و مستأجر — ماده 4',
        'legal_source_code': 'CIVIL_CODE',
    },
    {
        'code': 'LEASE_BREACH_TERMINATION',
        'title': 'تخلف از شروط، فسخ و اقاله',
        'category': 'termination',
        'plain_explanation': 'این بند قواعد کلی پایان پیش از موعد قرارداد را توضیح می‌دهد.',
        'body_template': (
            'قرارداد در مدت مقرر برای طرفین لازم‌الاتباع است و پایان پیش از موعد آن صرفاً با توافق '
            'طرفین (اقاله)، وجود حق فسخ مقرر در قرارداد یا وجود سبب قانونی امکان‌پذیر خواهد بود. '
            'در صورت تخلف از شروطی که برای آن حق فسخ یا ضمانت اجرای مشخص پیش‌بینی شده است، طرف '
            'ذی‌حق می‌تواند مطابق مفاد قرارداد و مقررات قانونی اقدام نماید.'
        ),
        'is_recommended': True,
        'is_optional': True,
        'legal_reference': 'قانون مدنی — مواد 10، 219، 496',
        'legal_source_code': 'CIVIL_CODE',
    },
]


def _deposit_amount(fin: Dict[str, Any]) -> int:
    try:
        if fin.get('deposit_mode') == 'retained':
            return int(fin.get('previous_deposit_amount') or fin.get('deposit') or 0)
        return int(fin.get('deposit') or 0)
    except (TypeError, ValueError):
        return 0


def build_lease_clause_context(wizard: Dict[str, Any]) -> Dict[str, Any]:
    """Context غنی برای condition و render بندهای اجاره."""
    fin = wizard.get('financial') or {}
    prop = wizard.get('property') or {}
    costs = fin.get('costs') or {}
    ctx = {**prop, **fin}
    ctx['deposit_mode'] = fin.get('deposit_mode', 'new')
    ctx['old_deposit_retained'] = fin.get('deposit_mode') == 'retained'
    ctx['has_deposit'] = _deposit_amount(fin) > 0
    ctx['has_delivery_date'] = bool(fin.get('delivery_date'))
    ctx['has_lease_end'] = bool(fin.get('lease_end'))
    ctx['has_cost_allocations'] = bool(costs)
    ctx['has_repair_allocations'] = bool(
        costs.get('minor_repairs') or costs.get('major_repairs')
    )
    ctx['transfer_to_third_party_allowed'] = bool(fin.get('transfer_to_third_party_allowed'))
    ctx['transfer_requires_landlord_consent'] = bool(
        fin.get('transfer_requires_landlord_consent', fin.get('transfer_to_third_party_allowed'))
    )
    ctx['property_has_tenant'] = bool(prop.get('has_tenant'))
    ctx['property_has_mortgage'] = bool(prop.get('has_mortgage'))
    ctx['old_deposit_retained'] = fin.get('deposit_mode') == 'retained'
    penalties = fin.get('penalties') or {}
    for key, item in penalties.items():
        ctx[f'penalty_{key}_enabled'] = bool(item.get('enabled'))
        amt = item.get('amount_per_day') or item.get('amount') or 0
        ctx[f'penalty_{key}_amount'] = int(amt) if amt else 0
    return ctx


def render_costs_body(costs: Dict[str, str]) -> str:
    lines = []
    for key, label in COST_ITEM_LABELS.items():
        party = costs.get(key)
        if party in PARTY_LABELS:
            lines.append(f'هزینه {label} بر عهده {PARTY_LABELS[party]} است.')
    return '\n'.join(lines) if lines else ''


def render_lease_clause_body(
    code: str,
    body_template: str,
    *,
    fin: Optional[Dict[str, Any]] = None,
    inline_values: Optional[Dict[str, Any]] = None,
) -> str:
    """رندر متن بند اجاره با متغیرهای ساختاریافته — بدون بازنویسی حقوقی."""
    fin = fin or {}
    costs = fin.get('costs') or {}
    values = dict(inline_values or {})

    if code == 'LEASE_USE_PURPOSE':
        usage = fin.get('usage_type', 'residential')
        values['usage_type'] = USAGE_TYPE_LABELS.get(usage, usage)
        text = body_template.replace('{{usage_type}}', values['usage_type'])
        occupants = fin.get('occupants_count')
        if occupants:
            text += f'\nحداکثر تعداد ساکن مورد توافق: {occupants} نفر.'
        return text

    if code == 'LEASE_COSTS':
        dynamic = render_costs_body(costs)
        return dynamic or body_template.replace('{{costs_dynamic_body}}', '')

    if code == 'LEASE_REPAIRS':
        major = PARTY_LABELS.get(costs.get('major_repairs', 'landlord'), 'موجر')
        minor = PARTY_LABELS.get(costs.get('minor_repairs', 'tenant'), 'مستأجر')
        return (
            body_template
            .replace('{{major_repairs_party}}', major)
            .replace('{{minor_repairs_party}}', minor)
        )

    if code == 'LEASE_DEPOSIT_RETAINED':
        dep = _deposit_amount(fin)
        ref = fin.get('previous_contract_ref') or fin.get('previous_contract_reference') or '—'
        return (
            body_template
            .replace('{{deposit_amount}}', format_toman(dep) if dep else '—')
            .replace('{{previous_contract_reference}}', str(ref))
        )

    if code == 'LEASE_DELIVERY':
        text = body_template.replace('{{delivery_date}}', fin.get('delivery_date') or '—')
        if fin.get('delivery_condition_note'):
            text += f'\n{fin["delivery_condition_note"]}'
        return text

    if code.startswith('LEASE_PENALTY_'):
        amount = values.get('amount') or values.get('penalty_amount') or ''
        if amount:
            try:
                amount = format_toman(int(amount))
            except (TypeError, ValueError):
                amount = str(amount)
        return body_template.replace('{{amount}}', amount or '—')

    text = body_template
    for key, val in values.items():
        text = text.replace(f'{{{{{key}}}}}', str(val))
    for key, val in fin.items():
        if isinstance(val, (str, int, float)) and f'{{{{{key}}}}}' in text:
            text = text.replace(f'{{{{{key}}}}}', str(val))
    return text
