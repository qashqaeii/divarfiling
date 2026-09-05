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

    sections.append(_section(
        'طرفین قرارداد', _render_parties(snap.get('parties') or []), 'parties', nav_key='parties',
    ))
    sections.append(_section(
        'مشخصات مورد معامله', _render_property(snap.get('property') or {}), 'property', nav_key='property',
    ))

    if ctype == CONTRACT_TYPE_LEASE:
        fin = snap.get('financial') or {}
        sections.append(_section('مدت اجاره', _render_lease_duration(fin), 'financial', nav_key='financial'))
        sections.append(_section('ودیعه و اجاره‌بها', _render_lease_money(fin), 'financial', nav_key='financial'))
        sections.append(_section('نحوه پرداخت', _render_lease_payment(fin), 'financial', nav_key='financial'))
        if fin.get('delivery_date'):
            sections.append(_section('تحویل', _render_delivery(fin), 'financial', nav_key='financial'))
    elif ctype == CONTRACT_TYPE_SALE:
        fin = snap.get('financial') or {}
        sections.append(_section('مبلغ معامله', _render_sale_price(fin), 'financial', nav_key='financial'))
        pay_body = _render_payments(fin)
        sections.append(_section(
            'برنامه پرداخت', pay_body, 'financial', nav_key='financial', section_kind='payments',
        ))
        if fin.get('official_transfer_date') or fin.get('transfer_date') or fin.get('transfer_place'):
            sections.append(_section(
                'اقدام برای انتقال رسمی', _render_transfer_plan(fin), 'financial', nav_key='financial',
                section_kind='transfer',
            ))
        if fin.get('delivery_date'):
            sections.append(_section('تحویل', _render_delivery(fin), 'financial', nav_key='financial'))
    elif ctype == CONTRACT_TYPE_JV:
        jv = snap.get('jv') or {}
        sections.append(_section('مشارکت', _render_jv(jv), 'jv', nav_key='financial'))

    witnesses_body = _render_witnesses(snap.get('witnesses') or [])
    if witnesses_body:
        sections.append(_section('شاهدان', witnesses_body, 'witnesses', nav_key='witnesses'))

    sections.extend(_render_clauses(snap.get('clauses') or [], ctype))
    sections = [s for s in sections if s.get('body')]
    return _number_sections(sections)


def _number_sections(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """شماره‌گذاری پویا — بدون hard-code شکست‌ناپذیر."""
    out = []
    for idx, sec in enumerate(sections, 1):
        title = sec.get('title', '')
        sec = dict(sec)
        if not title.startswith('ماده'):
            sec['title'] = f'ماده {idx} — {title}'
        nav_key = sec.get('nav_key', 'clauses')
        if sec.get('is_custom_section'):
            nav_key = 'custom'
        sec['section_id'] = f'{nav_key}-{idx}'
        sec['nav_key'] = nav_key
        out.append(sec)
    return out


def _section(title: str, body: str, edit_step: str, **extra: Any) -> Dict[str, Any]:
    return {'title': title, 'body': body.strip(), 'edit_step': edit_step, **extra}


def _render_parties(parties: List[Dict]) -> str:
    lines = []
    role_labels = {
        'landlord': 'موجر', 'tenant': 'مستأجر', 'seller': 'فروشنده',
        'buyer': 'خریدار', 'owner': 'مالک', 'builder': 'سازنده',
    }
    for p in parties:
        role = role_labels.get(p.get('role', ''), p.get('role', ''))
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        if p.get('company_name'):
            name = p['company_name']
        if not name:
            continue
        lines.append(f'{role}: {name}')
        if p.get('father_name'):
            lines.append(f'  نام پدر: {p["father_name"]}')
        if p.get('national_id'):
            lines.append(f'  کد ملی: {p["national_id"]}')
        if p.get('mobile'):
            verified = ' (شماره موبایل تأیید شده)' if p.get('mobile_verified') else ''
            lines.append(f'  موبایل: {p["mobile"]}{verified}')
        if p.get('address'):
            lines.append(f'  نشانی: {p["address"]}')
        if p.get('postal_code'):
            lines.append(f'  کد پستی: {p["postal_code"]}')
        share = p.get('ownership_share') or ''
        if share:
            lines.append(f'  قدرالسهم: {share}')
        lines.append('')
    return '\n'.join(lines).strip()


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
        ('تعداد اتاق', prop.get('bedrooms')),
        ('واحد', prop.get('unit')),
        ('سال ساخت', prop.get('build_year')),
        ('نوع سند', prop.get('deed_type')),
        ('پلاک اصلی', prop.get('main_plaque')),
        ('پلاک فرعی', prop.get('sub_plaque')),
    ]
    lines = [f'{k}: {v}' for k, v in fields if v not in (None, '', False)]
    amenities = []
    if prop.get('has_parking'):
        label = 'پارکینگ'
        if prop.get('parking_number'):
            label += f' ({prop["parking_number"]})'
        amenities.append(label)
    if prop.get('has_storage'):
        label = 'انباری'
        if prop.get('storage_number'):
            label += f' ({prop["storage_number"]})'
        amenities.append(label)
    if prop.get('has_elevator'):
        amenities.append('آسانسور')
    if amenities:
        lines.append('امکانات: ' + '، '.join(amenities))
    lines.append('اطلاعات فوق بر اساس اطلاعات ثبت‌شده/اظهار طرفین است.')
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
    lines = []
    if fin.get('delivery_date'):
        lines.append(f'تاریخ تحویل: {fin["delivery_date"]}')
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
        lines.append(
            f'توجه: مجموع اقساط ({format_toman(pay_sum)}) با مبلغ کل ({format_toman(total)}) برابر نیست.',
        )
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
    lines = []
    if jv.get('owner_percent') is not None:
        lines.append(f'درصد مالک: {jv["owner_percent"]}٪')
    if jv.get('builder_percent') is not None:
        lines.append(f'درصد سازنده: {jv["builder_percent"]}٪')
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


def _render_clauses(clauses: List[Dict], contract_type: str) -> List[Dict[str, Any]]:
    from contracts.services.clause_ux import render_clause_sections_for_review
    sections = render_clause_sections_for_review(clauses, contract_type)
    for sec in sections:
        sec.setdefault('nav_key', 'custom' if sec.get('is_custom_section') else 'clauses')
    return sections
