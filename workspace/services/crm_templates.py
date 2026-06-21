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
