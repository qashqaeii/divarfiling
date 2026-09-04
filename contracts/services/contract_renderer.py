"""رندر قرارداد به‌صورت سند — برای مرحله بازبینی."""
from __future__ import annotations

from typing import Any, Dict, List

from contracts.constants import CONTRACT_TYPE_JV, CONTRACT_TYPE_LEASE, CONTRACT_TYPE_SALE
from contracts.models import Contract, ContractVersion
from contracts.services.money import amount_display_block, format_toman
from contracts.services.version_copy import version_display_snapshot


def render_contract_document(contract: Contract, version: ContractVersion | None = None) -> List[Dict[str, Any]]:
    """لیست مواد قرارداد برای نمایش در ویزارد/PDF."""
    version = version or contract.current_version
    if not version:
        return []
    snap = version_display_snapshot(version)
    sections: List[Dict[str, Any]] = []
    ctype = contract.contract_type

    sections.append(_section('طرفین قرارداد', _render_parties(snap.get('parties') or []), 'parties'))
    sections.append(_section('مشخصات مورد معامله', _render_property(snap.get('property') or {}), 'property'))

    if ctype == CONTRACT_TYPE_LEASE:
        fin = snap.get('financial') or {}
        sections.append(_section('مدت اجاره', _render_lease_duration(fin), 'financial'))
        sections.append(_section('ودیعه و اجاره‌بها', _render_lease_money(fin), 'financial'))
        sections.append(_section('نحوه پرداخت', _render_lease_payment(fin), 'financial'))
        if fin.get('delivery_date'):
            sections.append(_section('تحویل ملک', _render_delivery(fin), 'financial'))
        if fin.get('costs'):
            sections.append(_section('هزینه‌ها', _render_costs(fin.get('costs') or {}), 'financial'))
        if fin.get('penalties'):
            sections.append(_section('وجه التزام', _render_penalties(fin.get('penalties') or {}), 'financial'))
    elif ctype == CONTRACT_TYPE_SALE:
        fin = snap.get('financial') or {}
        sections.append(_section('مبلغ معامله', _render_sale_price(fin), 'financial'))
        sections.append(_section('برنامه پرداخت', _render_payments(fin), 'financial'))
        sections.append(_section('اقدام برای انتقال رسمی', _render_transfer_plan(fin), 'financial'))
        status_lines = _render_sale_status(snap.get('property') or {})
        if status_lines:
            sections.append(_section('وضعیت ملک (اظهار طرفین)', status_lines, 'property'))
    elif ctype == CONTRACT_TYPE_JV:
        jv = snap.get('jv') or {}
        sections.append(_section('مشارکت', _render_jv(jv), 'jv'))

    witnesses_body = _render_witnesses(snap.get('witnesses') or [])
    if witnesses_body:
        sections.append(_section('شاهدان', witnesses_body, 'witnesses'))

    sections.extend(_render_clauses(snap.get('clauses') or []))
    return [s for s in sections if s.get('body')]


def _section(title: str, body: str, edit_step: str) -> Dict[str, Any]:
    return {'title': title, 'body': body.strip(), 'edit_step': edit_step}


def _render_parties(parties: List[Dict]) -> str:
    lines = []
    role_labels = {
        'landlord': 'موجر', 'tenant': 'مستأجر', 'seller': 'فروشنده',
        'buyer': 'خریدار', 'owner': 'مالک', 'builder': 'سازنده',
    }
    for p in parties:
        role = role_labels.get(p.get('role', ''), p.get('role', ''))
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        share = p.get('ownership_share') or ''
        line = f'• {role}: {name}'
        if p.get('national_id'):
            line += f' — کد ملی: {p["national_id"]}'
        if p.get('mobile'):
            line += f' — موبایل: {p["mobile"]}'
        if share:
            line += f' — قدرالسهم: {share}'
        lines.append(line)
    return '\n'.join(lines)


def _render_property(prop: Dict) -> str:
    fields = [
        ('نوع ملک', prop.get('property_type')),
        ('کاربری', prop.get('usage')),
        ('استان', prop.get('province')),
        ('شهر', prop.get('city')),
        ('منطقه', prop.get('district')),
        ('محله', prop.get('neighborhood')),
        ('آدرس', prop.get('address')),
        ('متراژ', prop.get('area')),
        ('طبقه', prop.get('floor')),
        ('واحد', prop.get('unit')),
        ('سال ساخت', prop.get('build_year')),
        ('نوع سند', prop.get('deed_type')),
        ('پلاک اصلی', prop.get('main_plaque')),
        ('پلاک فرعی', prop.get('sub_plaque')),
    ]
    lines = [f'{k}: {v}' for k, v in fields if v not in (None, '', False)]
    if prop.get('declared_by_parties'):
        lines.append('(بر اساس اظهار طرفین)')
    return '\n'.join(lines)


def _render_lease_duration(fin: Dict) -> str:
    lines = []
    if fin.get('lease_start'):
        lines.append(f'تاریخ شروع: {fin["lease_start"]}')
    if fin.get('lease_end'):
        lines.append(f'تاریخ پایان: {fin["lease_end"]}')
    if fin.get('duration_days'):
        lines.append(f'مدت: {fin["duration_days"]} روز')
    return '\n'.join(lines)


def _render_lease_money(fin: Dict) -> str:
    lines = []
    dep = amount_display_block(fin.get('deposit'))
    rent = amount_display_block(fin.get('monthly_rent'))
    if dep['toman']:
        lines.append(f'ودیعه: {dep["toman"]} ({dep["rial"]}) — {dep["words"]}')
    if fin.get('deposit_mode') == 'retained':
        lines.append('ودیعه قرارداد قبلی نزد موجر باقی می‌ماند.')
        if fin.get('previous_deposit_amount'):
            lines.append(f'مبلغ ودیعه قبلی: {format_toman(fin["previous_deposit_amount"])}')
    if rent['toman']:
        lines.append(f'اجاره ماهانه: {rent["toman"]} ({rent["rial"]}) — {rent["words"]}')
    return '\n'.join(lines)


def _render_lease_payment(fin: Dict) -> str:
    lines = []
    if fin.get('rent_payment_day'):
        lines.append(f'روز پرداخت هر ماه: {fin["rent_payment_day"]}')
    if fin.get('payment_method'):
        lines.append(f'روش پرداخت: {fin["payment_method"]}')
    if fin.get('payment_destination'):
        lines.append(f'مقصد پرداخت: {fin["payment_destination"]}')
    return '\n'.join(lines)


def _render_delivery(fin: Dict) -> str:
    lines = [f'تاریخ تحویل: {fin.get("delivery_date", "—")}']
    if fin.get('delivery_delay_penalty'):
        lines.append(f'وجه التزام تأخیر تحویل: {format_toman(fin["delivery_delay_penalty"])} در روز')
    return '\n'.join(lines)


def _render_costs(costs: Dict) -> str:
    labels = {
        'water': 'آب', 'electricity': 'برق', 'gas': 'گاز', 'phone': 'تلفن',
        'charge': 'شارژ', 'minor_repairs': 'تعمیرات جزئی',
        'major_repairs': 'تعمیرات اساسی', 'property_tax': 'عوارض مالکانه',
    }
    role = {'landlord': 'موجر', 'tenant': 'مستأجر'}
    lines = []
    for key, label in labels.items():
        val = costs.get(key)
        if val:
            lines.append(f'{label}: {role.get(val, val)}')
    return '\n'.join(lines)


def _render_penalties(penalties: Dict) -> str:
    labels = {
        'landlord_delivery_delay': 'تأخیر تحویل موجر',
        'tenant_vacate_delay': 'تأخیر تخلیه مستأجر',
        'deposit_return_delay': 'تأخیر استرداد ودیعه',
    }
    lines = []
    for key, label in labels.items():
        item = penalties.get(key) or {}
        if item.get('enabled') and item.get('amount_per_day'):
            lines.append(f'{label}: {format_toman(item["amount_per_day"])} در روز')
    return '\n'.join(lines)


def _render_sale_price(fin: Dict) -> str:
    block = amount_display_block(fin.get('total_price'))
    return f'{block["toman"]} ({block["rial"]}) — {block["words"]}' if block['toman'] else ''


def _render_payments(fin: Dict) -> str:
    lines = []
    for p in fin.get('payments') or []:
        lines.append(
            f'• {p.get("label", "پرداخت")}: {format_toman(p.get("amount"))} — '
            f'{p.get("due_date", "")} — {p.get("payment_method", "")}'
        )
    total = fin.get('total_price')
    pay_sum = sum(int(p.get('amount') or 0) for p in fin.get('payments') or [])
    if total and pay_sum and int(total) != pay_sum:
        lines.append(f'⚠ مجموع اقساط ({format_toman(pay_sum)}) با مبلغ کل ({format_toman(total)}) برابر نیست.')
    return '\n'.join(lines)


def _render_transfer_plan(fin: Dict) -> str:
    lines = []
    if fin.get('transfer_date'):
        lines.append(f'تاریخ توافق‌شده برای اقدام به انتقال رسمی: {fin["transfer_date"]}')
    if fin.get('transfer_place'):
        lines.append(f'محل: {fin["transfer_place"]}')
    if fin.get('remaining_amount_at_transfer'):
        lines.append(f'مانده در زمان انتقال: {format_toman(fin["remaining_amount_at_transfer"])}')
    return '\n'.join(lines)


def _render_sale_status(prop: Dict) -> str:
    flags = [
        ('has_mortgage', 'ملک در رهن است'),
        ('has_tenant', 'مستأجر دارد'),
        ('has_loan', 'وام دارد'),
        ('has_debt', 'بدهی اعلام شده دارد'),
        ('has_completion_cert', 'پایان کار دارد'),
        ('has_separation_minutes', 'صورت‌مجلس تفکیکی دارد'),
    ]
    return '\n'.join(f'• {label}' for key, label in flags if prop.get(key))


def _render_jv(jv: Dict) -> str:
    lines = [
        f'درصد مالک: {jv.get("owner_percent", "—")}٪',
        f'درصد سازنده: {jv.get("builder_percent", "—")}٪',
    ]
    return '\n'.join(lines)


def _render_witnesses(witnesses: List[Dict]) -> str:
    lines = []
    for w in witnesses:
        role = w.get('witness_role') or f'شاهد {w.get("witness_number", "")}'
        lines.append(
            f'• {role}: {w.get("first_name", "")} {w.get("last_name", "")} — '
            f'{w.get("mobile", "")}'
        )
    return '\n'.join(lines)


def _render_clauses(clauses: List[Dict]) -> List[Dict[str, Any]]:
    sections = []
    for idx, c in enumerate(clauses, 1):
        title = c.get('title', f'ماده {idx}')
        badge = ' [توافق اختصاصی طرفین]' if c.get('is_custom') else ''
        body = c.get('body_text', '')
        sections.append({
            'title': f'ماده {idx} — {title}{badge}',
            'body': body,
            'edit_step': 'clauses',
        })
    return sections
