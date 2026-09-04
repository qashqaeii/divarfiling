"""UX و موتور تصمیم‌گیری بندهای قرارداد — بدون تولید متن حقوقی."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from contracts.constants import (
    CONTRACT_TYPE_JV,
    CONTRACT_TYPE_LEASE,
    CONTRACT_TYPE_SALE,
)
from contracts.models import ContractClauseDefinition
from contracts.services.clauses import get_applicable_clauses
from contracts.services.lease_clause_bank import (
    LEASE_CORE_RENDERER_CODES,
    PENALTY_CODE_MAP,
    USAGE_TYPE_LABELS,
    build_lease_clause_context,
)

MAIN_ARTICLE_CODES: Dict[str, Set[str]] = {
    CONTRACT_TYPE_LEASE: set(LEASE_CORE_RENDERER_CODES),
    CONTRACT_TYPE_SALE: {
        'SALE_SUBJECT', 'SALE_PRICE', 'SALE_PAYMENT', 'SALE_DELIVERY', 'SALE_TRANSFER',
    },
    CONTRACT_TYPE_JV: {
        'JV_CONTRIBUTION_OWNER', 'JV_CONTRIBUTION_BUILDER', 'JV_SHARE',
        'JV_UNITS', 'JV_SCHEDULE',
    },
}

UI_CATEGORIES: Dict[str, List[Tuple[str, str]]] = {
    CONTRACT_TYPE_LEASE: [
        ('usage_transfer', 'استفاده و انتقال'),
        ('costs_repairs', 'هزینه‌ها و تعمیرات'),
        ('delivery_vacate', 'تحویل و تخلیه'),
        ('deposit', 'ودیعه'),
        ('penalties', 'وجه التزام'),
        ('termination', 'فسخ و شرایط'),
        ('custom', 'توافقات اختصاصی'),
    ],
    CONTRACT_TYPE_SALE: [
        ('property_status', 'وضعیت مورد معامله'),
        ('payments', 'پرداخت‌ها'),
        ('delivery', 'تحویل'),
        ('official_transfer', 'اقدام برای انتقال رسمی'),
        ('seller_docs', 'مدارک و تعهدات فروشنده'),
        ('buyer_duties', 'تعهدات خریدار'),
        ('costs', 'هزینه‌ها'),
        ('penalties', 'وجه التزام‌ها'),
        ('breach', 'تخلف از تعهدات'),
        ('supplementary', 'شرایط تکمیلی'),
        ('custom', 'توافقات اختصاصی'),
    ],
    CONTRACT_TYPE_JV: [
        ('contributions', 'آورده‌ها'),
        ('shares', 'سهم طرفین'),
        ('units', 'تقسیم واحدها'),
        ('owner_duties', 'تعهدات مالک'),
        ('builder_duties', 'تعهدات سازنده'),
        ('costs', 'هزینه‌ها'),
        ('guarantees', 'تضمین‌ها'),
        ('duration_delivery', 'مدت و تحویل'),
        ('delay', 'تأخیر'),
        ('termination', 'فسخ'),
        ('custom', 'توافقات اختصاصی'),
    ],
}

CLAUSE_UI_CATEGORY: Dict[str, str] = {
    'LEASE_USE_PURPOSE': 'usage_transfer',
    'LEASE_SUBLEASE': 'usage_transfer',
    'LEASE_SUBLEASE_WITH_CONSENT': 'usage_transfer',
    'LEASE_COSTS': 'costs_repairs',
    'LEASE_REPAIRS': 'costs_repairs',
    'LEASE_CARE': 'costs_repairs',
    'LEASE_DELIVERY': 'delivery_vacate',
    'LEASE_VACATE': 'delivery_vacate',
    'LEASE_DEPOSIT_RETURN': 'deposit',
    'LEASE_DEPOSIT_RETAINED': 'deposit',
    'LEASE_PENALTY_DELIVERY': 'penalties',
    'LEASE_PENALTY_VACATE': 'penalties',
    'LEASE_PENALTY_DEPOSIT_RETURN': 'penalties',
    'LEASE_BREACH_TERMINATION': 'termination',
}

REVIEW_ARTICLE_GROUPS: Dict[str, List[Tuple[str, str]]] = {
    CONTRACT_TYPE_LEASE: [
        ('usage_transfer', 'استفاده و انتقال'),
        ('costs_repairs', 'هزینه‌ها و تعمیرات'),
        ('tenant_obligations', 'تعهدات مستأجر'),
        ('landlord_obligations', 'تعهدات موجر'),
        ('delivery_vacate_deposit', 'تحویل، تخلیه و ودیعه'),
        ('penalties', 'وجه التزام'),
        ('termination', 'فسخ و سایر شرایط'),
        ('custom', 'توافقات اختصاصی'),
    ],
    CONTRACT_TYPE_SALE: [
        ('property', 'وضعیت مورد معامله'),
        ('obligations', 'تعهدات طرفین'),
        ('penalties', 'وجه التزام'),
        ('termination', 'فسخ و شرایط'),
        ('custom', 'توافقات اختصاصی'),
    ],
    CONTRACT_TYPE_JV: [
        ('obligations', 'تعهدات طرفین'),
        ('penalties', 'تأخیر و وجه التزام'),
        ('termination', 'فسخ'),
        ('custom', 'توافقات اختصاصی'),
    ],
}

CLAUSE_REVIEW_GROUP: Dict[str, str] = {
    'LEASE_USE_PURPOSE': 'usage_transfer',
    'LEASE_SUBLEASE': 'usage_transfer',
    'LEASE_SUBLEASE_WITH_CONSENT': 'usage_transfer',
    'LEASE_COSTS': 'costs_repairs',
    'LEASE_REPAIRS': 'costs_repairs',
    'LEASE_CARE': 'tenant_obligations',
    'LEASE_DELIVERY': 'landlord_obligations',
    'LEASE_VACATE': 'tenant_obligations',
    'LEASE_DEPOSIT_RETURN': 'delivery_vacate_deposit',
    'LEASE_DEPOSIT_RETAINED': 'delivery_vacate_deposit',
    'LEASE_PENALTY_DELIVERY': 'penalties',
    'LEASE_PENALTY_VACATE': 'penalties',
    'LEASE_PENALTY_DEPOSIT_RETURN': 'penalties',
    'LEASE_BREACH_TERMINATION': 'termination',
    'SALE_MORTGAGE': 'property',
    'SALE_TAX': 'obligations',
    'SALE_DISPUTE': 'termination',
    'JV_PENALTY': 'penalties',
    'JV_DISPUTE': 'termination',
}

LEASE_COST_UI_FIELDS = (
    ('water', 'آب'),
    ('electricity', 'برق'),
    ('gas', 'گاز'),
    ('phone', 'تلفن'),
    ('charge', 'شارژ'),
    ('sewage', 'فاضلاب'),
)

LEASE_PENALTY_FIELDS = (
    ('landlord_delivery_delay', 'pen_landlord_delivery', 'تأخیر تحویل موجر', 'LEASE_PENALTY_DELIVERY'),
    ('tenant_vacate_delay', 'pen_tenant_vacate', 'تأخیر تخلیه مستأجر', 'LEASE_PENALTY_VACATE'),
    ('deposit_return_delay', 'pen_deposit_return', 'تأخیر استرداد ودیعه', 'LEASE_PENALTY_DEPOSIT_RETURN'),
)

SALE_PENALTY_FIELDS = (
    ('payment_delay', 'pen_payment', 'تأخیر پرداخت'),
    ('delivery_delay', 'pen_delivery', 'تأخیر تحویل'),
    ('transfer_delay', 'pen_transfer', 'تأخیر اقدام برای انتقال رسمی'),
)

DEFAULT_LEASE_OPTIONAL = frozenset({'LEASE_CARE', 'LEASE_BREACH_TERMINATION'})


def build_clause_context(wizard: Dict[str, Any]) -> Dict[str, Any]:
    return build_lease_clause_context(wizard)


def _library_clauses(
    contract_type: str,
    context: Dict[str, Any],
    *,
    user=None,
) -> Dict[str, ContractClauseDefinition]:
    clauses = get_applicable_clauses(contract_type, context, user=user)
    main = MAIN_ARTICLE_CODES.get(contract_type, set())
    return {c.code: c for c in clauses if c.code not in main}


def _penalty_inline_values(item: Dict[str, Any]) -> Dict[str, str]:
    amount = item.get('amount_per_day') or item.get('amount') or ''
    return {'amount': str(amount), 'penalty_amount': str(amount)}


def _resolve_lease_clauses(
    wizard: Dict[str, Any],
    library: Dict[str, ContractClauseDefinition],
    selected: List[Dict[str, Any]],
    seen: Set[str],
) -> None:
    fin = wizard.get('financial') or {}
    context = build_lease_clause_context(wizard)

    def add_code(code: str, inline_values: Optional[Dict] = None) -> None:
        if code in seen or code not in library:
            return
        seen.add(code)
        entry: Dict[str, Any] = {'code': code}
        if inline_values:
            entry['inline_values'] = inline_values
        selected.append(entry)

    add_code('LEASE_USE_PURPOSE')

    if not fin.get('transfer_to_third_party_allowed', False):
        add_code('LEASE_SUBLEASE')
    elif fin.get('transfer_requires_landlord_consent', True):
        add_code('LEASE_SUBLEASE_WITH_CONSENT')

    if context.get('has_delivery_date'):
        add_code('LEASE_DELIVERY')

    costs = fin.get('costs') or {}
    if costs:
        add_code('LEASE_COSTS')
    if context.get('has_repair_allocations'):
        add_code('LEASE_REPAIRS')

    optional_codes = {
        item.get('code') for item in (wizard.get('clause_optional') or []) if item.get('code')
    }
    if not wizard.get('clause_optional'):
        optional_codes = set(DEFAULT_LEASE_OPTIONAL)
    for code in optional_codes:
        if code in DEFAULT_LEASE_OPTIONAL or code in library:
            add_code(code)

    if context.get('has_lease_end'):
        add_code('LEASE_VACATE')

    if context.get('has_deposit'):
        if fin.get('deposit_mode') == 'retained':
            add_code('LEASE_DEPOSIT_RETAINED')
        else:
            add_code('LEASE_DEPOSIT_RETURN')

    penalties = fin.get('penalties') or {}
    for key, penalty_code in PENALTY_CODE_MAP.items():
        item = penalties.get(key) or {}
        amt = item.get('amount_per_day') or item.get('amount') or 0
        if item.get('enabled') and amt:
            add_code(penalty_code, _penalty_inline_values(item))


def resolve_selected_clauses(
    contract_type: str,
    wizard: Dict[str, Any],
    *,
    user=None,
) -> List[Dict[str, Any]]:
    context = build_clause_context(wizard)
    library = _library_clauses(contract_type, context, user=user)
    selected: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    if contract_type == CONTRACT_TYPE_LEASE:
        _resolve_lease_clauses(wizard, library, selected, seen)
    elif contract_type == CONTRACT_TYPE_SALE:
        prop = wizard.get('property') or {}
        fin = wizard.get('financial') or {}
        if prop.get('has_mortgage') and 'SALE_MORTGAGE' in library:
            selected.append({'code': 'SALE_MORTGAGE'})
        penalties = fin.get('penalties') or {}
        for item in penalties.values():
            if item.get('enabled') and (item.get('amount_per_day') or item.get('amount')):
                if 'SALE_PENALTY' in library:
                    selected.append({'code': 'SALE_PENALTY', 'inline_values': _penalty_inline_values(item)})
                break
    elif contract_type == CONTRACT_TYPE_JV:
        penalties = (wizard.get('financial') or {}).get('penalties') or {}
        for item in penalties.values():
            if item.get('enabled') and 'JV_PENALTY' in library:
                selected.append({'code': 'JV_PENALTY', 'inline_values': _penalty_inline_values(item)})
                break

    for agreement in wizard.get('custom_agreements') or []:
        body = (agreement.get('body') or agreement.get('body_text') or '').strip()
        if body:
            selected.append({
                'is_custom': True,
                'title': agreement.get('title') or 'توافق اختصاصی',
                'body_text': body,
            })

    if isinstance(wizard.get('selected_clauses'), list):
        for item in wizard['selected_clauses']:
            if item.get('is_custom'):
                body = (item.get('body_text') or '').strip()
                if body and not any(
                    x.get('is_custom') and x.get('body_text') == body for x in selected
                ):
                    selected.append(item)
            elif item.get('code') and item['code'] not in seen and item['code'] in library:
                seen.add(item['code'])
                selected.append(item)

    return selected


def _clause_card(defn: Optional[ContractClauseDefinition], **extra) -> Dict[str, Any]:
    card = dict(extra)
    if defn:
        card.setdefault('clause_code', defn.code)
        card.setdefault('clause_preview', defn.body_template)
        card.setdefault('clause_explanation', defn.plain_explanation)
        card.setdefault('review_status', defn.review_status)
        card.setdefault('is_standard', True)
    return card


def build_clause_sections(
    contract_type: str,
    wizard: Dict[str, Any],
    *,
    user=None,
    is_staff: bool = False,
) -> List[Dict[str, Any]]:
    context = build_clause_context(wizard)
    library = _library_clauses(contract_type, context, user=user)
    fin = wizard.get('financial') or {}
    optional_active = {
        item.get('code') for item in (wizard.get('clause_optional') or []) if item.get('code')
    }
    if not wizard.get('clause_optional') and contract_type == CONTRACT_TYPE_LEASE:
        optional_active = set(DEFAULT_LEASE_OPTIONAL)

    categories = UI_CATEGORIES.get(contract_type, [])
    cards_by_cat: Dict[str, List[Dict[str, Any]]] = {cat_id: [] for cat_id, _ in categories}

    if contract_type == CONTRACT_TYPE_LEASE:
        use_def = library.get('LEASE_USE_PURPOSE')
        usage = fin.get('usage_type', 'residential')
        cards_by_cat['usage_transfer'].append(_clause_card(
            use_def,
            type='usage_choice',
            id='usage',
            title='نوع و حدود استفاده',
            question='مورد اجاره برای چه استفاده‌ای در اختیار مستأجر قرار می‌گیرد؟',
            value=usage,
            options=[{'value': k, 'label': v} for k, v in USAGE_TYPE_LABELS.items()],
            summary=f'استفاده {USAGE_TYPE_LABELS.get(usage, usage)}',
        ))

        transfer_allowed = fin.get('transfer_to_third_party_allowed', False)
        sub_def = library.get('LEASE_SUBLEASE') or library.get('LEASE_SUBLEASE_WITH_CONSENT')
        transfer_val = 'with_consent' if transfer_allowed else 'denied'
        cards_by_cat['usage_transfer'].append(_clause_card(
            sub_def,
            type='choice',
            id='transfer',
            title='انتقال منافع به غیر',
            question='آیا مستأجر اجازه دارد منافع مورد اجاره را به شخص دیگری واگذار کند؟',
            value=transfer_val,
            options=[
                {'value': 'denied', 'label': 'مجاز نیست'},
                {'value': 'with_consent', 'label': 'با رضایت موجر مجاز است'},
            ],
            warning='انتقال به غیر بدون رضایت موجر مجاز نخواهد بود.' if not transfer_allowed else None,
        ))

        costs = fin.get('costs') or {}
        cost_rows = [
            {'key': key, 'label': label, 'value': costs.get(key) or 'tenant'}
            for key, label in LEASE_COST_UI_FIELDS
        ]
        cards_by_cat['costs_repairs'].append({
            'type': 'cost_allocation',
            'id': 'costs',
            'title': 'هزینه‌های جاری و مشترک',
            'question': 'هر هزینه بر عهده چه کسی است؟',
            'rows': cost_rows,
            'clause_code': 'LEASE_COSTS' if library.get('LEASE_COSTS') else None,
            'clause_preview': library['LEASE_COSTS'].body_template if library.get('LEASE_COSTS') else '',
        })

        cards_by_cat['costs_repairs'].append({
            'type': 'repairs_allocation',
            'id': 'repairs',
            'title': 'تعمیرات و نگهداری فنی',
            'question': 'مسئول تعمیرات اساسی و جزئی چه کسی است؟',
            'major_value': costs.get('major_repairs') or 'landlord',
            'minor_value': costs.get('minor_repairs') or 'tenant',
            'clause_code': 'LEASE_REPAIRS' if library.get('LEASE_REPAIRS') else None,
            'clause_preview': library['LEASE_REPAIRS'].body_template if library.get('LEASE_REPAIRS') else '',
        })

        care_def = library.get('LEASE_CARE')
        cards_by_cat['costs_repairs'].append(_clause_card(
            care_def,
            type='optional_clause',
            id='LEASE_CARE',
            title='حفظ و نگهداری مورد اجاره',
            question=care_def.plain_explanation if care_def else 'تعهد به استفاده متعارف و نگهداری ملک',
            enabled='LEASE_CARE' in optional_active,
        ))

        if fin.get('delivery_date') or library.get('LEASE_DELIVERY'):
            del_def = library.get('LEASE_DELIVERY')
            cards_by_cat['delivery_vacate'].append(_clause_card(
                del_def,
                type='info',
                title='تحویل مورد اجاره',
                message=f'تاریخ تحویل: {fin.get("delivery_date") or "—"} (از مرحله مبلغ و مدت)',
            ))

        vac_def = library.get('LEASE_VACATE')
        if fin.get('lease_end'):
            cards_by_cat['delivery_vacate'].append(_clause_card(
                vac_def,
                type='info',
                title='تخلیه در پایان مدت',
                message=f'پایان مدت: {fin.get("lease_end")}',
            ))

        dep_ctx = build_lease_clause_context(wizard)
        if dep_ctx.get('has_deposit'):
            dep_def = library.get('LEASE_DEPOSIT_RETURN') or library.get('LEASE_DEPOSIT_RETAINED')
            cards_by_cat['deposit'].append(_clause_card(
                dep_def,
                type='info',
                title='استرداد ودیعه',
                message=(
                    'ودیعه قرارداد قبلی نزد موجر باقی مانده است.'
                    if fin.get('deposit_mode') == 'retained'
                    else 'بند استرداد ودیعه پس از تخلیه و تحویل.'
                ),
            ))

        for key, prefix, title, penalty_code in LEASE_PENALTY_FIELDS:
            item = (fin.get('penalties') or {}).get(key) or {}
            defn = library.get(penalty_code)
            cards_by_cat['penalties'].append(_clause_card(
                defn,
                type='penalty',
                id=key,
                title=title,
                prefix=prefix,
                enabled=bool(item.get('enabled')),
                amount=item.get('amount_per_day') or '',
                unit=item.get('unit', 'daily'),
                warning=(
                    'برای این مورد وجه التزام تعیین نشده است.'
                    if not item.get('enabled') else None
                ),
            ))

        term_def = library.get('LEASE_BREACH_TERMINATION')
        cards_by_cat['termination'].append(_clause_card(
            term_def,
            type='optional_clause',
            id='LEASE_BREACH_TERMINATION',
            title='تخلف از شروط، فسخ و اقاله',
            question=term_def.plain_explanation if term_def else 'قواعد پایان پیش از موعد قرارداد',
            enabled='LEASE_BREACH_TERMINATION' in optional_active,
        ))

    elif contract_type == CONTRACT_TYPE_SALE:
        prop = wizard.get('property') or {}
        if prop.get('has_tenant'):
            cards_by_cat['property_status'].append({
                'type': 'info',
                'title': 'مستأجر موجود',
                'message': 'ملک دارای مستأجر اعلام شده — بند مربوطه در صورت تأیید حقوقی اضافه می‌شود.',
            })
        for key, prefix, title in SALE_PENALTY_FIELDS:
            item = (fin.get('penalties') or {}).get(key) or {}
            defn = library.get('SALE_PENALTY')
            cards_by_cat['penalties'].append({
                'type': 'penalty',
                'id': key,
                'title': title,
                'prefix': prefix,
                'enabled': bool(item.get('enabled')),
                'amount': item.get('amount_per_day') or item.get('amount') or '',
                'unit': item.get('unit', 'daily'),
                'clause_code': 'SALE_PENALTY' if defn else None,
                'clause_preview': defn.body_template if defn else '',
                'review_status': defn.review_status if defn else '',
            })

    elif contract_type == CONTRACT_TYPE_JV:
        cards_by_cat['duration_delivery'].append({
            'type': 'info',
            'title': 'هشدار حقوقی',
            'message': (
                'این توافق جایگزین تشریفات قانونی و ثبت رسمی لازم نیست. '
                'مشارکت مالک رسمی با سازنده ممکن است مشمول مقررات پیش‌فروش باشد.'
            ),
            'level': 'critical',
        })

    sections = []
    for cat_id, cat_label in categories:
        cards = cards_by_cat.get(cat_id) or []
        if cat_id == 'custom':
            cards = [{
                'type': 'custom_agreements',
                'agreements': wizard.get('custom_agreements') or [],
            }]
        if not cards and cat_id != 'custom':
            continue
        sections.append({'id': cat_id, 'title': cat_label, 'cards': cards})
    return sections


def apply_clauses_step(
    wizard: Dict[str, Any],
    parsed: Dict[str, Any],
    contract_type: str,
    *,
    user=None,
) -> Dict[str, Any]:
    wizard = dict(wizard or {})
    if isinstance(parsed, list):
        wizard['selected_clauses'] = parsed
        customs = [
            {'title': i.get('title', ''), 'body': i.get('body_text', '')}
            for i in parsed if i.get('is_custom')
        ]
        if customs:
            wizard['custom_agreements'] = customs
        return wizard

    fin = dict(wizard.get('financial') or {})

    if contract_type == CONTRACT_TYPE_LEASE:
        transfer = parsed.get('transfer_choice', 'denied')
        fin['transfer_to_third_party_allowed'] = transfer == 'with_consent'
        fin['transfer_requires_landlord_consent'] = transfer == 'with_consent'
        if parsed.get('usage_type'):
            fin['usage_type'] = parsed['usage_type']
        if parsed.get('occupants_count') is not None:
            fin['occupants_count'] = parsed['occupants_count']
        fin['costs'] = parsed.get('costs') or fin.get('costs') or {}
        fin['penalties'] = parsed.get('penalties') or fin.get('penalties') or {}

    wizard['financial'] = fin
    wizard['clause_optional'] = parsed.get('optional_clauses') or []
    wizard['custom_agreements'] = parsed.get('custom_agreements') or []
    wizard['selected_clauses'] = resolve_selected_clauses(
        contract_type, wizard, user=user,
    )
    return wizard


def clause_warnings(wizard: Dict[str, Any], contract_type: str) -> List[str]:
    warnings = []
    fin = wizard.get('financial') or {}
    if contract_type == CONTRACT_TYPE_LEASE:
        if not fin.get('transfer_to_third_party_allowed'):
            warnings.append('انتقال منافع به غیر بدون رضایت موجر مجاز نخواهد بود.')
        penalties = fin.get('penalties') or {}
        if not any(
            (p.get('enabled') and (p.get('amount_per_day') or p.get('amount')))
            for p in penalties.values()
        ):
            warnings.append('هیچ وجه التزامی با مبلغ مشخص تعیین نشده است.')
    return warnings


def render_clause_sections_for_review(
    clauses: List[Dict[str, Any]],
    contract_type: str,
) -> List[Dict[str, Any]]:
    groups = REVIEW_ARTICLE_GROUPS.get(contract_type, [])
    grouped: Dict[str, List[str]] = {gid: [] for gid, _ in groups}
    custom_items: List[Tuple[str, str]] = []

    for c in clauses:
        if not c.get('is_active', True):
            continue
        body = (c.get('body_text') or '').strip()
        if not body:
            continue
        if c.get('is_custom'):
            custom_items.append((c.get('title', 'توافق اختصاصی'), body))
            continue
        code = c.get('code', '')
        group = CLAUSE_REVIEW_GROUP.get(code, 'termination')
        if group not in grouped:
            group = 'termination'
        grouped.setdefault(group, []).append(f'{c.get("title", "")}\n{body}')

    sections = []
    for gid, gtitle in groups:
        if gid == 'custom':
            if not custom_items:
                continue
            lines = [f'{idx}. {title}\n{body}' for idx, (title, body) in enumerate(custom_items, 1)]
            sections.append({
                'title': gtitle,
                'body': '\n\n'.join(lines),
                'edit_step': 'clauses',
                'is_custom_section': True,
            })
            continue
        parts = grouped.get(gid) or []
        if parts:
            sections.append({
                'title': gtitle,
                'body': '\n\n'.join(parts),
                'edit_step': 'clauses',
            })
    return sections
