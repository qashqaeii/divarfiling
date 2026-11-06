"""قالب‌های پیام CRM — فاز ۳."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.constants import MESSAGE_TEMPLATE_CATEGORIES
from workspace.models import CRMMessageTemplate, Customer, WorkspaceSettings


DEFAULT_TEMPLATES = [
    {
        'name': 'پیگیری اولیه',
        'category': 'پیگیری',
        'body': (
            'سلام {name} عزیز\n'
            'مشاور املاک {agency} هستم. درخواست شما برای {type} را پیگیری می‌کنم.\n'
            'در صورت تمایل برای هماهنگی بازدید در خدمتم.'
        ),
    },
    {
        'name': 'یادآوری بازدید',
        'category': 'بازدید',
        'body': (
            'سلام {name}\n'
            'یادآوری بازدید ملک. لطفاً در صورت نیاز به تغییر زمان اطلاع دهید.\n'
            'با احترام — {agency}'
        ),
    },
    {
        'name': 'ارسال پیشنهاد',
        'category': 'پیشنهاد',
        'body': (
            'سلام {name}\n'
            'چند ملک متناسب با بودجه و منطقه مورد نظر شما ({areas}) آماده کردم.\n'
            'آماده هماهنگی بازدید هستم.'
        ),
    },
    {
        'name': 'خوش‌آمد سرنخ',
        'category': 'خوش‌آمد',
        'body': (
            'سلام {name} عزیز\n'
            'از تماس شما سپاسگزارم. پرونده شما در {agency} ثبت شد و به‌زودی پیگیری می‌کنم.'
        ),
    },
]


def ensure_default_templates(user) -> None:
    if CRMMessageTemplate.objects.filter(user=user).exists():
        return
    CRMMessageTemplate.objects.bulk_create([
        CRMMessageTemplate(
            user=user, is_system=True,
            channel='واتساپ', **tpl,
        )
        for tpl in DEFAULT_TEMPLATES
    ])


def list_templates(user, category: Optional[str] = None) -> List[CRMMessageTemplate]:
    ensure_default_templates(user)
    qs = CRMMessageTemplate.objects.filter(user=user)
    if category:
        qs = qs.filter(category=category)
    return list(qs.order_by('category', 'name'))


def render_message_template(
    template: CRMMessageTemplate,
    customer: Customer,
    *,
    agency: str = '',
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    if not agency:
        try:
            agency = WorkspaceSettings.objects.get(user=customer.user).agency_name
        except WorkspaceSettings.DoesNotExist:
            agency = ''
    agency = agency or 'آژانس املاک'

    mapping = {
        '{name}': customer.name or '',
        '{phone}': customer.phone or '',
        '{type}': customer.customer_type or '',
        '{status}': customer.status or '',
        '{areas}': customer.areas or customer.district or '',
        '{agency}': agency,
    }
    if extra:
        for k, v in extra.items():
            mapping[f'{{{k}}}'] = str(v or '')

    text = template.body
    for key, val in mapping.items():
        text = text.replace(key, val)
    return text.strip()


def templates_by_category(user) -> Dict[str, List[CRMMessageTemplate]]:
    ensure_default_templates(user)
    grouped: Dict[str, List[CRMMessageTemplate]] = {c: [] for c in MESSAGE_TEMPLATE_CATEGORIES}
    for tpl in CRMMessageTemplate.objects.filter(user=user).order_by('name'):
        grouped.setdefault(tpl.category, []).append(tpl)
    return grouped


_CATEGORY_SEG_KEYS = {
    'پیگیری': 'followup',
    'بازدید': 'visit',
    'پیشنهاد': 'offer',
    'خوش‌آمد': 'welcome',
    'سفارشی': 'custom_cat',
}


def build_templates_kpi_stats(templates: List[CRMMessageTemplate]) -> Dict[str, Any]:
    """آمار قالب پیام برای fl-kpi-pro."""
    total = len(templates)
    whatsapp = sum(1 for t in templates if t.channel == 'واتساپ')
    sms = sum(1 for t in templates if t.channel == 'پیامک')
    custom = sum(1 for t in templates if not t.is_system)
    categories = len({t.category for t in templates if t.category})

    def _share(part: int, base: int) -> int:
        if not base:
            return 0
        return int(round((part / base) * 100))

    by_cat: Dict[str, int] = {}
    for t in templates:
        cat = t.category or 'سفارشی'
        by_cat[cat] = by_cat.get(cat, 0) + 1

    mix_segments = []
    for cat in MESSAGE_TEMPLATE_CATEGORIES:
        count = by_cat.get(cat, 0)
        if count <= 0:
            continue
        mix_segments.append({
            'key': _CATEGORY_SEG_KEYS.get(cat, 'other'),
            'label': cat,
            'count': count,
            'pct': _share(count, total),
        })
    for cat, count in by_cat.items():
        if cat in MESSAGE_TEMPLATE_CATEGORIES or count <= 0:
            continue
        mix_segments.append({
            'key': 'other',
            'label': cat,
            'count': count,
            'pct': _share(count, total),
        })

    if total:
        hero_bits = []
        if categories:
            hero_bits.append(f'{categories} دسته')
        if whatsapp:
            hero_bits.append(f'{whatsapp} واتساپ')
        if sms:
            hero_bits.append(f'{sms} پیامک')
        hero_meta = ' · '.join(hero_bits) if hero_bits else 'کتابخانه قالب آماده است'
    else:
        hero_meta = 'هنوز قالبی ندارید'

    if whatsapp:
        whatsapp_meta = f'{_share(whatsapp, total)}٪ از قالب‌ها برای واتساپ'
    elif total:
        whatsapp_meta = 'قالب واتساپ ندارید'
    else:
        whatsapp_meta = 'هنوز قالبی نیست'

    if sms:
        sms_meta = f'{_share(sms, total)}٪ از قالب‌ها برای پیامک'
    elif total:
        sms_meta = 'قالب پیامک ندارید'
    else:
        sms_meta = 'هنوز قالبی نیست'

    if custom:
        custom_meta = f'{_share(custom, total)}٪ ساختهٔ خودتان'
    elif total:
        custom_meta = 'هنوز قالب شخصی نساخته‌اید'
    else:
        custom_meta = 'اولین قالب را بسازید'

    return {
        'total': total,
        'whatsapp': whatsapp,
        'sms': sms,
        'custom': custom,
        'categories': categories,
        'mix_segments': mix_segments,
        'hero_meta': hero_meta,
        'whatsapp_share': _share(whatsapp, total),
        'whatsapp_meta': whatsapp_meta,
        'sms_share': _share(sms, total),
        'sms_meta': sms_meta,
        'custom_share': _share(custom, total),
        'custom_meta': custom_meta,
    }


SAMPLE_PREVIEW_VALUES = {
    '{name}': 'علی محمدی',
    '{phone}': '۰۹۱۲۱۲۳۴۵۶۷',
    '{type}': 'خریدار',
    '{status}': 'در حال پیگیری',
    '{areas}': 'سعادت‌آباد، شهرک غرب',
    '{agency}': 'آژانس املاک نمونه',
}


def preview_template_body(body: str, *, agency: str = '') -> str:
    """پیش‌نمایش قالب با داده نمونه."""
    mapping = dict(SAMPLE_PREVIEW_VALUES)
    if agency:
        mapping['{agency}'] = agency
    text = body or ''
    for key, val in mapping.items():
        text = text.replace(key, val)
    return text.strip()
