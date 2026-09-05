"""Context builder for Contract Wizard review step."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from contracts.constants import (
    CONTRACT_TYPE_JV,
    CONTRACT_TYPE_LEASE,
    CONTRACT_TYPE_SALE,
)
from contracts.models import Contract, ContractVersion
from contracts.services.clause_ux import clause_warnings, resolve_selected_clauses
from contracts.services.clauses import get_applicable_clauses
from contracts.services.contract_renderer import render_contract_document
from contracts.services.money import amount_display_block, format_toman, parse_toman_amount
from contracts.services.version_copy import version_display_snapshot

ROLE_LABELS = {
    'landlord': 'موجر',
    'tenant': 'مستأجر',
    'seller': 'فروشنده',
    'buyer': 'خریدار',
    'owner': 'مالک',
    'builder': 'سازنده',
    'witness': 'شاهد',
    'other': 'سایر',
}

COST_LABELS = {
    'water': 'آب',
    'electricity': 'برق',
    'gas': 'گاز',
    'phone': 'تلفن',
    'charge': 'شارژ',
    'minor_repairs': 'تعمیرات جزئی',
    'major_repairs': 'تعمیرات اساسی',
    'property_tax': 'عوارض مالکانه',
}

SALE_COST_LABELS = {
    'transfer_costs': 'هزینه انتقال',
    'notary': 'دفترخانه',
    'post_delivery_costs': 'هزینه‌های بعد از تحویل',
}

PENALTY_LABELS = {
    'landlord_delivery_delay': 'تأخیر تحویل موجر',
    'tenant_vacate_delay': 'تأخیر تخلیه مستأجر',
    'deposit_return_delay': 'تأخیر استرداد ودیعه',
    'payment_delay': 'تأخیر پرداخت',
    'delivery_delay': 'تأخیر تحویل',
    'transfer_delay': 'تأخیر انتقال رسمی',
}

PLACEHOLDER_RE = re.compile(r'\{\{[^}]+\}\}|(?<!\w)None(?!\w)|undefined', re.IGNORECASE)

NAV_ITEMS = [
    ('parties', 'طرفین'),
    ('property', 'ملک'),
    ('financial', 'مبلغ و پرداخت'),
    ('clauses', 'شرایط قرارداد'),
    ('witnesses', 'شاهدان'),
    ('custom', 'توافقات'),
    ('final', 'تأیید نهایی'),
]


def build_review_context(
    contract: Contract,
    *,
    validation_errors: Optional[List[str]] = None,
    version: Optional[ContractVersion] = None,
) -> Dict[str, Any]:
    version = version or contract.current_version
    if not version:
        return _empty_review_context(contract)

    snap = version_display_snapshot(version)
    contract_sections = render_contract_document(contract, version)
    validation_errors = validation_errors or []

    parties = _build_parties(version, snap.get('parties') or [])
    witnesses = _build_witnesses(snap.get('witnesses') or [])
    property_info = _build_property(snap.get('property') or {})
    fin = snap.get('financial') or {}
    payment_schedule = _build_payment_schedule(fin, snap.get('payments') or [])
    financial_summary = _build_financial_summary(contract.contract_type, fin)
    important_dates = _build_important_dates(contract.contract_type, fin, snap.get('important_dates') or {})
    clause_stats = _build_clause_stats(contract, version, snap)
    penalty_summary = _build_penalty_summary(contract.contract_type, fin)
    costs_summary = _build_costs_summary(contract.contract_type, fin)
    custom_agreements = _build_custom_agreements(snap.get('clauses') or [])
    issues = _collect_issues(
        contract, version, snap, validation_errors, contract_sections,
        parties, witnesses, payment_schedule,
    )
    readiness = _readiness_state(issues)
    completeness = _build_completeness(
        contract, parties, property_info, financial_summary,
        payment_schedule, clause_stats, custom_agreements, witnesses, issues,
    )
    nav_items = _build_nav_items(contract.contract_type, contract_sections, custom_agreements, witnesses)

    return {
        'readiness': readiness,
        'readiness_message': _readiness_message(readiness),
        'readiness_detail': _readiness_detail(readiness),
        'issues': issues,
        'blocking_count': sum(1 for i in issues if i['severity'] == 'block'),
        'warning_count': sum(1 for i in issues if i['severity'] == 'warn'),
        'parties': parties,
        'witnesses': witnesses,
        'property': property_info,
        'financial_summary': financial_summary,
        'payment_schedule': payment_schedule,
        'important_dates': important_dates,
        'clause_stats': clause_stats,
        'penalty_summary': penalty_summary,
        'costs_summary': costs_summary,
        'custom_agreements': custom_agreements,
        'completeness': completeness,
        'nav_items': nav_items,
        'contract_meta': {
            'internal_number': contract.internal_number,
            'version_number': version.version_number,
            'status': contract.status,
            'status_label': contract.get_status_display(),
            'type_label': contract.get_contract_type_display(),
            'party_count': len(parties),
        },
        'send_disabled': readiness == 'blocked',
        'send_disabled_reason': _send_disabled_reason(issues),
        'version_locks_on_send': True,
    }


def _empty_review_context(contract: Contract) -> Dict[str, Any]:
    return {
        'readiness': 'blocked',
        'readiness_message': 'قرارداد هنوز آماده ارسال نیست.',
        'readiness_detail': 'نسخه قرارداد یافت نشد.',
        'issues': [{'message': 'نسخه قرارداد یافت نشد.', 'severity': 'block', 'edit_step': 'parties', 'edit_label': 'اصلاح'}],
        'blocking_count': 1,
        'warning_count': 0,
        'parties': [],
        'witnesses': [],
        'property': {},
        'financial_summary': {},
        'payment_schedule': {'rows': [], 'total': 0, 'contract_total': 0, 'mismatch': False},
        'important_dates': [],
        'clause_stats': {'included': 0, 'excluded': 0},
        'penalty_summary': [],
        'costs_summary': [],
        'custom_agreements': [],
        'completeness': [],
        'nav_items': [],
        'contract_meta': {
            'internal_number': contract.internal_number,
            'version_number': 0,
            'status': contract.status,
            'status_label': contract.get_status_display(),
            'type_label': contract.get_contract_type_display(),
            'party_count': 0,
        },
        'send_disabled': True,
        'send_disabled_reason': 'نسخه قرارداد یافت نشد.',
        'version_locks_on_send': True,
    }


def _build_parties(version: ContractVersion, snap_parties: List[Dict]) -> List[Dict[str, Any]]:
    db_parties = {
        (p.role, p.first_name, p.last_name, p.mobile): p
        for p in version.parties.order_by('sort_order', 'pk')
    }
    out = []
    for p in snap_parties:
        role = p.get('role', '')
        key = (p.get('role'), p.get('first_name'), p.get('last_name'), p.get('mobile'))
        db_p = db_parties.get(key)
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        if p.get('company_name'):
            name = p['company_name']
        item = {
            'role': role,
            'role_label': ROLE_LABELS.get(role, role),
            'name': name or '—',
            'first_name': p.get('first_name', ''),
            'last_name': p.get('last_name', ''),
            'father_name': p.get('father_name', ''),
            'national_id': p.get('national_id', ''),
            'mobile': p.get('mobile', ''),
            'address': p.get('address', ''),
            'postal_code': p.get('postal_code', ''),
            'ownership_share': p.get('ownership_share', ''),
            'person_type': p.get('person_type', 'natural'),
            'mobile_verified': bool(getattr(db_p, 'mobile_verified', False)),
        }
        out.append(item)
    return out


def _build_witnesses(witnesses: List[Dict]) -> List[Dict[str, Any]]:
    out = []
    for w in witnesses:
        name = f"{w.get('first_name', '')} {w.get('last_name', '')}".strip()
        out.append({
            'name': name or '—',
            'role': w.get('witness_role') or f'شاهد {w.get("witness_number", "")}',
            'mobile': w.get('mobile', ''),
            'national_id': w.get('national_id', ''),
        })
    return out


def _build_property(prop: Dict) -> Dict[str, Any]:
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

    return {
        'property_type': prop.get('property_type', ''),
        'city': prop.get('city', ''),
        'district': prop.get('district', '') or prop.get('neighborhood', ''),
        'address': prop.get('address', ''),
        'area': prop.get('area', ''),
        'floor': prop.get('floor', ''),
        'build_year': prop.get('build_year', ''),
        'bedrooms': prop.get('bedrooms', ''),
        'unit': prop.get('unit', ''),
        'main_plaque': prop.get('main_plaque', ''),
        'sub_plaque': prop.get('sub_plaque', ''),
        'amenities': amenities,
        'declared_by_parties': bool(prop.get('declared_by_parties')),
        'has_data': any(prop.get(k) for k in (
            'property_type', 'city', 'address', 'area', 'floor', 'build_year',
        )),
    }


def _build_payment_schedule(fin: Dict, snap_payments: List[Dict]) -> Dict[str, Any]:
    rows = []
    payments = fin.get('payments') or []
    if payments:
        for idx, p in enumerate(payments, 1):
            rows.append({
                'index': idx,
                'label': p.get('label') or f'پرداخت {idx}',
                'amount': parse_toman_amount(p.get('amount')),
                'amount_display': format_toman(p.get('amount')),
                'due_date': p.get('due_date', ''),
                'method': p.get('payment_method', ''),
                'notes': p.get('notes', ''),
            })
    elif snap_payments:
        for idx, p in enumerate(snap_payments, 1):
            due = p.get('due_date', '')
            if due and 'T' in str(due):
                due = str(due).split('T')[0]
            rows.append({
                'index': idx,
                'label': p.get('label') or f'پرداخت {idx}',
                'amount': parse_toman_amount(p.get('amount')),
                'amount_display': format_toman(p.get('amount')),
                'due_date': due,
                'method': p.get('payment_method', ''),
                'notes': p.get('notes', ''),
            })

    total = sum(r['amount'] or 0 for r in rows)
    contract_total = parse_toman_amount(fin.get('total_price')) or 0
    mismatch = bool(rows and contract_total and total != contract_total)
    return {
        'rows': rows,
        'total': total,
        'total_display': format_toman(total) if total else '',
        'contract_total': contract_total,
        'contract_total_display': format_toman(contract_total) if contract_total else '',
        'mismatch': mismatch,
        'has_rows': bool(rows),
    }


def _build_financial_summary(contract_type: str, fin: Dict) -> Dict[str, Any]:
    if contract_type == CONTRACT_TYPE_SALE:
        block = amount_display_block(fin.get('total_price'))
        return {
            'kind': 'sale',
            'total_price': fin.get('total_price'),
            'toman': block['toman'],
            'rial': block['rial'],
            'words': block['words'],
            'transfer_date': fin.get('transfer_date') or fin.get('official_transfer_date', ''),
            'transfer_place': fin.get('transfer_place', ''),
            'transfer_notes': fin.get('transfer_notes', ''),
        }
    if contract_type == CONTRACT_TYPE_LEASE:
        dep = amount_display_block(fin.get('deposit'))
        rent = amount_display_block(fin.get('monthly_rent'))
        return {
            'kind': 'lease',
            'deposit': dep,
            'monthly_rent': rent,
            'lease_start': fin.get('lease_start', ''),
            'lease_end': fin.get('lease_end', ''),
            'duration_days': fin.get('duration_days', ''),
            'delivery_date': fin.get('delivery_date', ''),
        }
    jv = fin if False else {}
    return {'kind': contract_type}


def _build_important_dates(contract_type: str, fin: Dict, snap_dates: Dict) -> List[Dict[str, str]]:
    items = []
    contract_date = fin.get('contract_date') or fin.get('agreement_date')
    if contract_date:
        items.append({'label': 'تاریخ قرارداد', 'value': contract_date})

    if contract_type == CONTRACT_TYPE_LEASE:
        for key, label in (
            ('lease_start', 'شروع اجاره'),
            ('lease_end', 'پایان اجاره'),
            ('delivery_date', 'تحویل'),
            ('vacate_date', 'تخلیه'),
        ):
            val = fin.get(key) or snap_dates.get(key)
            if val:
                items.append({'label': label, 'value': val})
        if fin.get('rent_payment_day'):
            items.append({'label': 'روز پرداخت ماهانه', 'value': str(fin['rent_payment_day'])})

    if contract_type == CONTRACT_TYPE_SALE:
        for key, label in (
            ('delivery_date', 'تحویل'),
            ('transfer_date', 'انتقال رسمی'),
            ('official_transfer_date', 'انتقال رسمی'),
        ):
            val = fin.get(key) or snap_dates.get(key)
            if val and not any(i['label'] == label for i in items):
                items.append({'label': label, 'value': val})

    for row in fin.get('payments') or []:
        if row.get('due_date'):
            items.append({
                'label': f'سررسید: {row.get("label", "پرداخت")}',
                'value': row['due_date'],
            })
    return items


def _build_clause_stats(contract: Contract, version: ContractVersion, snap: Dict) -> Dict[str, Any]:
    wizard = contract.wizard_data or {}
    included = [c for c in (snap.get('clauses') or []) if c.get('is_active', True) and (c.get('body_text') or '').strip()]
    included_count = len(included)
    try:
        applicable = get_applicable_clauses(contract.contract_type, wizard, user=contract.user)
        applicable_codes = {c.code for c in applicable}
    except Exception:
        applicable_codes = set()
    selected_codes = {c.get('code') for c in (wizard.get('selected_clauses') or []) if c.get('code')}
    active_codes = {c.get('code') for c in included if c.get('code')}
    all_selected = selected_codes | active_codes
    excluded = max(len(applicable_codes - all_selected), 0) if applicable_codes else 0
    return {
        'included': included_count,
        'excluded': excluded,
        'has_custom': any(c.get('is_custom') for c in included),
    }


def _build_penalty_summary(contract_type: str, fin: Dict) -> List[Dict[str, str]]:
    penalties = fin.get('penalties') or {}
    out = []
    for key, item in penalties.items():
        if not isinstance(item, dict) or not item.get('enabled'):
            continue
        label = PENALTY_LABELS.get(key, key)
        amount = item.get('amount_per_day') or item.get('amount')
        if not amount:
            continue
        unit = 'روزانه' if item.get('amount_per_day') or item.get('unit') == 'daily' else 'مقطوع'
        out.append({'label': label, 'amount_display': format_toman(amount), 'unit': unit})
    if contract_type == CONTRACT_TYPE_SALE and fin.get('delivery_delay_penalty'):
        out.append({
            'label': 'تأخیر تحویل',
            'amount_display': format_toman(fin['delivery_delay_penalty']),
            'unit': 'روزانه',
        })
    return out


def _build_costs_summary(contract_type: str, fin: Dict) -> List[Dict[str, str]]:
    role_labels = {'landlord': 'موجر', 'tenant': 'مستأجر', 'seller': 'فروشنده', 'buyer': 'خریدار', 'shared': 'مشترک'}
    out = []
    if contract_type == CONTRACT_TYPE_LEASE:
        costs = fin.get('costs') or {}
        for key, val in costs.items():
            if val:
                out.append({'label': COST_LABELS.get(key, key), 'value': role_labels.get(val, val)})
    elif contract_type == CONTRACT_TYPE_SALE:
        costs = fin.get('sale_costs') or {}
        for key, val in costs.items():
            if val:
                out.append({'label': SALE_COST_LABELS.get(key, key), 'value': role_labels.get(val, val)})
    return out


def _build_custom_agreements(clauses: List[Dict]) -> List[Dict[str, str]]:
    return [
        {'title': c.get('title') or 'توافق اختصاصی', 'body': (c.get('body_text') or '').strip()}
        for c in clauses
        if c.get('is_custom') and c.get('is_active', True) and (c.get('body_text') or '').strip()
    ]


def _collect_issues(
    contract: Contract,
    version: ContractVersion,
    snap: Dict,
    validation_errors: List[str],
    contract_sections: List[Dict],
    parties: List[Dict],
    witnesses: List[Dict],
    payment_schedule: Dict,
) -> List[Dict[str, str]]:
    issues = []
    for err in validation_errors:
        issues.append({
            'message': err,
            'severity': 'block',
            'edit_step': _guess_edit_step(err),
            'edit_label': 'اصلاح',
        })

    for p in parties:
        if not p.get('mobile'):
            issues.append({
                'message': f'شماره تماس {p["role_label"]} وارد نشده',
                'severity': 'warn',
                'edit_step': 'parties',
                'edit_label': 'اصلاح',
            })
        if not (p.get('first_name') or p.get('last_name')) or p.get('name') in ('', '—'):
            issues.append({
                'message': f'نام {p["role_label"]} تکمیل نشده',
                'severity': 'block',
                'edit_step': 'parties',
                'edit_label': 'اصلاح',
            })

    if contract.contract_type == CONTRACT_TYPE_LEASE and len(witnesses) < 2:
        issues.append({
            'message': 'دو شاهد برای قرارداد اجاره الزامی است',
            'severity': 'block',
            'edit_step': 'witnesses',
            'edit_label': 'اصلاح',
        })
    elif contract.contract_type == CONTRACT_TYPE_LEASE and len(witnesses) < 2:
        pass

    if payment_schedule.get('mismatch'):
        issues.append({
            'message': 'جمع برنامه پرداخت با مبلغ کل معامله مطابقت ندارد',
            'severity': 'block',
            'edit_step': 'financial',
            'edit_label': 'اصلاح',
        })

    fin = snap.get('financial') or {}
    if contract.contract_type == CONTRACT_TYPE_SALE:
        if fin.get('transfer_date') or fin.get('official_transfer_date'):
            if not fin.get('transfer_place'):
                issues.append({
                    'message': 'محل انتقال رسمی تکمیل نشده',
                    'severity': 'warn',
                    'edit_step': 'financial',
                    'edit_label': 'اصلاح',
                })

    for sec in contract_sections:
        body = sec.get('body', '')
        if PLACEHOLDER_RE.search(body):
            issues.append({
                'message': f'بند «{sec.get("title", "")}» دارای داده ناقص است',
                'severity': 'block',
                'edit_step': sec.get('edit_step', 'clauses'),
                'edit_label': 'اصلاح',
            })

    wizard = contract.wizard_data or {}
    for warn in clause_warnings(wizard, contract.contract_type):
        issues.append({
            'message': warn,
            'severity': 'warn',
            'edit_step': 'clauses',
            'edit_label': 'اصلاح',
        })

    seen = set()
    deduped = []
    for item in issues:
        key = (item['message'], item['severity'])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _guess_edit_step(error: str) -> str:
    err = error.lower()
    if 'شاهد' in error:
        return 'witnesses'
    if any(w in error for w in ('اجاره', 'ودیعه', 'پرداخت', 'مبلغ')):
        return 'financial'
    if 'بند' in error:
        return 'clauses'
    if 'طرف' in error:
        return 'parties'
    if 'مشارکت' in error or 'درصد' in error:
        return 'financial'
    return 'parties'


def _readiness_state(issues: List[Dict]) -> str:
    if any(i['severity'] == 'block' for i in issues):
        return 'blocked'
    if any(i['severity'] == 'warn' for i in issues):
        return 'warning'
    return 'ready'


def _readiness_message(readiness: str) -> str:
    return {
        'ready': 'قرارداد آماده ارسال است',
        'warning': 'قرارداد قابل ارسال است، اما چند مورد نیاز به توجه دارد',
        'blocked': 'قرارداد هنوز آماده ارسال نیست',
    }.get(readiness, '')


def _readiness_detail(readiness: str) -> str:
    return {
        'ready': 'همه اطلاعات ضروری تکمیل شده‌اند.',
        'warning': 'می‌توانید ارسال کنید؛ پیشنهاد می‌شود موارد زیر را بررسی کنید.',
        'blocked': 'برای ارسال، موارد زیر را تکمیل کنید.',
    }.get(readiness, '')


def _send_disabled_reason(issues: List[Dict]) -> str:
    blocks = [i for i in issues if i['severity'] == 'block']
    if not blocks:
        return ''
    count = len(blocks)
    return f'برای ارسال، ابتدا {count} مورد ناقص را تکمیل کنید.'


def _build_completeness(
    contract: Contract,
    parties: List[Dict],
    property_info: Dict,
    financial_summary: Dict,
    payment_schedule: Dict,
    clause_stats: Dict,
    custom_agreements: List,
    witnesses: List[Dict],
    issues: List[Dict],
) -> List[Dict[str, str]]:
    items = []
    items.append({
        'label': 'طرفین',
        'status': 'ok' if parties else 'missing',
        'value': f'{len(parties)} نفر' if parties else 'ناقص',
    })
    items.append({
        'label': 'ملک',
        'status': 'ok' if property_info.get('has_data') else 'warn',
        'value': 'تکمیل' if property_info.get('has_data') else 'ناقص',
    })
    if contract.contract_type == CONTRACT_TYPE_SALE:
        total = financial_summary.get('toman', '')
        items.append({
            'label': 'مبلغ',
            'status': 'ok' if total else 'missing',
            'value': total.replace(' تومان', '') if total else '—',
        })
        if payment_schedule.get('has_rows'):
            items.append({
                'label': 'برنامه پرداخت',
                'status': 'warn' if payment_schedule.get('mismatch') else 'ok',
                'value': f'{len(payment_schedule["rows"])} مرحله',
            })
    elif contract.contract_type == CONTRACT_TYPE_LEASE:
        rent = (financial_summary.get('monthly_rent') or {}).get('toman', '')
        items.append({
            'label': 'اجاره',
            'status': 'ok' if rent else 'missing',
            'value': rent.replace(' تومان', '') if rent else '—',
        })
    items.append({
        'label': 'بندهای قرارداد',
        'status': 'ok' if clause_stats.get('included') else 'missing',
        'value': f'{clause_stats.get("included", 0)} بند',
    })
    items.append({
        'label': 'توافقات اختصاصی',
        'status': 'ok' if custom_agreements else 'neutral',
        'value': f'{len(custom_agreements)} مورد' if custom_agreements else 'ندارد',
    })
    if contract.contract_type == CONTRACT_TYPE_LEASE:
        w_status = 'ok' if len(witnesses) >= 2 else 'warn'
        items.append({
            'label': 'شاهدان',
            'status': w_status,
            'value': f'{len(witnesses)} نفر' if witnesses else 'ثبت نشده',
        })
    blocks = [i for i in issues if i['severity'] == 'block']
    items.append({
        'label': 'اعتبارسنجی',
        'status': 'ok' if not blocks else 'missing',
        'value': 'بدون خطای مسدودکننده' if not blocks else f'{len(blocks)} مورد',
    })
    return items


def _build_nav_items(
    contract_type: str,
    contract_sections: List[Dict],
    custom_agreements: List,
    witnesses: List[Dict],
) -> List[Dict[str, str]]:
    present_keys = {s.get('nav_key') for s in contract_sections}
    if custom_agreements:
        present_keys.add('custom')
    if witnesses:
        present_keys.add('witnesses')
    present_keys.add('final')

    items = []
    for key, label in NAV_ITEMS:
        if key == 'witnesses' and contract_type != CONTRACT_TYPE_LEASE:
            continue
        if key == 'custom' and 'custom' not in present_keys and not custom_agreements:
            continue
        if key in ('parties', 'property', 'financial', 'clauses', 'witnesses', 'custom'):
            if key not in present_keys and key != 'clauses':
                continue
        target = f'ct-review-sec-{key}'
        if key == 'clauses':
            target = next(
                (f'ct-review-sec-{s.get("section_id")}' for s in contract_sections if s.get('nav_key') == 'clauses'),
                'ct-review-sec-clauses',
            )
        items.append({'key': key, 'label': label, 'target': target})
    return items
