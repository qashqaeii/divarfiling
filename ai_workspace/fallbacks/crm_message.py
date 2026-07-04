"""Fallback پیام CRM — از قالب‌های موجود."""
from __future__ import annotations

from typing import Any, Dict

from workspace.models import CRMMessageTemplate, Customer
from workspace.services.crm_templates import ensure_default_templates, render_message_template


def build(context: Dict[str, Any]) -> str:
    customer = context.get('_customer')
    if not isinstance(customer, Customer):
        return _plain_fallback(context)

    ensure_default_templates(customer.user)
    category = 'پیشنهاد' if context.get('top_matches_text') else 'پیگیری'
    tpl = (
        CRMMessageTemplate.objects.filter(user=customer.user, category=category)
        .order_by('id')
        .first()
    )
    if not tpl:
        tpl = CRMMessageTemplate.objects.filter(user=customer.user).order_by('id').first()
    if tpl:
        extra = {}
        if context.get('top_matches_text'):
            extra['matches'] = context['top_matches_text']
        return render_message_template(tpl, customer, extra=extra)
    return _plain_fallback(context)


def _plain_fallback(context: Dict[str, Any]) -> str:
    name = context.get('name') or 'مشتری'
    areas = context.get('areas') or ''
    lines = [f'سلام {name} عزیز،', '']
    if areas:
        lines.append(f'درخواست شما برای منطقه {areas} را پیگیری می‌کنم.')
    else:
        lines.append('درخواست شما را پیگیری می‌کنم.')
    lines.extend(['', 'در صورت تمایل برای هماهنگی بازدید در خدمتم.', 'با احترام'])
    return '\n'.join(lines)
