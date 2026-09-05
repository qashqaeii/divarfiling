"""UX و موتور تصمیم‌گیری بندهای قرارداد — بدون تولید متن حقوقی."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from contracts.constants import (
    CLAUSE_REVIEW_PENDING,
    CLAUSE_REVIEW_REVIEWED,
    CLAUSE_REVIEW_STATUSES,
    CONTRACT_TYPE_JV,
    CONTRACT_TYPE_LEASE,
    CONTRACT_TYPE_SALE,
)
from contracts.models import ContractClauseDefinition
from contracts.services.clauses import get_applicable_clauses
from contracts.services.lease_clause_bank import (
    LEASE_CORE_RENDERER_CODES,
    PENALTY_CODE_MAP as LEASE_PENALTY_CODE_MAP,
    USAGE_TYPE_LABELS,
    build_lease_clause_context,
)
from contracts.services.sale_clause_bank import (
    SALE_CORE_RENDERER_CODES,
    SALE_COST_ITEM_LABELS,
    SALE_PENALTY_CODE_MAP,
    build_sale_clause_context,
)

MAIN_ARTICLE_CODES: Dict[str, Set[str]] = {
    CONTRACT_TYPE_LEASE: set(LEASE_CORE_RENDERER_CODES),
    CONTRACT_TYPE_SALE: set(SALE_CORE_RENDERER_CODES),
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
        ('property_status', 'وضعیت ملک'),
        ('delivery_docs', 'تحویل و مدارک'),
        ('official_transfer', 'انتقال رسمی'),
        ('obligations', 'تعهدات طرفین'),
        ('costs', 'هزینه‌ها'),
        ('penalties', 'وجه التزام'),
        ('termination', 'فسخ و شرایط'),
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
        ('property_status', 'وضعیت اعلامی مورد معامله'),
        ('payment_core', 'ثمن و نحوه پرداخت'),
        ('delivery', 'تحویل مورد معامله'),
        ('seller_obligations', 'تعهدات فروشنده'),
        ('buyer_obligations', 'تعهدات خریدار'),
        ('official_transfer', 'اقدامات مربوط به انتقال رسمی'),
        ('costs', 'هزینه‌ها'),
        ('penalties', 'وجه التزام‌ها'),
        ('termination', 'تخلف از تعهدات و شرایط پایان قرارداد'),
        ('custom', 'توافقات اختصاصی طرفین'),
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
    'SALE_PROPERTY_DECLARATIONS': 'property_status',
    'SALE_EXISTING_TENANT': 'property_status',
    'SALE_DELIVERY': 'delivery',
    'SALE_DOCUMENTS': 'seller_obligations',
    'SALE_OFFICIAL_TRANSFER': 'official_transfer',
    'SALE_SELLER_OBLIGATIONS': 'seller_obligations',
    'SALE_BUYER_OBLIGATIONS': 'buyer_obligations',
    'SALE_PAYMENT_OBLIGATION': 'buyer_obligations',
    'SALE_COSTS': 'costs',
    'SALE_PENALTY_PAYMENT': 'penalties',
    'SALE_PENALTY_DELIVERY': 'penalties',
    'SALE_PENALTY_OFFICIAL_TRANSFER': 'penalties',
    'SALE_BREACH_TERMINATION': 'termination',
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
    ('payment_delay', 'pen_payment', 'تأخیر پرداخت', 'SALE_PENALTY_PAYMENT'),
    ('delivery_delay', 'pen_delivery', 'تأخیر تحویل', 'SALE_PENALTY_DELIVERY'),
    ('transfer_delay', 'pen_transfer', 'تأخیر اقدام برای انتقال رسمی', 'SALE_PENALTY_OFFICIAL_TRANSFER'),
)

SALE_COST_UI_FIELDS = tuple(SALE_COST_ITEM_LABELS.items())

DEFAULT_LEASE_OPTIONAL = frozenset({'LEASE_CARE', 'LEASE_BREACH_TERMINATION'})
DEFAULT_SALE_OPTIONAL = frozenset({
    'SALE_DOCUMENTS', 'SALE_SELLER_OBLIGATIONS', 'SALE_BUYER_OBLIGATIONS',
    'SALE_PAYMENT_OBLIGATION', 'SALE_BREACH_TERMINATION',
})


def clause_review_badge(review_status: str) -> Optional[str]:
    if review_status == CLAUSE_REVIEW_REVIEWED:
        return 'بند بررسی‌شده'
    if review_status == CLAUSE_REVIEW_PENDING:
        return 'بند پیشنهادی'
    return None


def clause_review_status_label(review_status: str) -> str:
    labels = dict(CLAUSE_REVIEW_STATUSES)
    return labels.get(review_status, review_status)


def build_clause_context(wizard: Dict[str, Any], contract_type: str = CONTRACT_TYPE_LEASE) -> Dict[str, Any]:
    if contract_type == CONTRACT_TYPE_SALE:
        return build_sale_clause_context(wizard)
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
    unit = item.get('unit', 'daily')
    return {
        'amount': str(amount),
        'penalty_amount': str(amount),
        'penalty_unit': unit,
        'unit': unit,
    }


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
    for key, penalty_code in LEASE_PENALTY_CODE_MAP.items():
        item = penalties.get(key) or {}
        amt = item.get('amount_per_day') or item.get('amount') or 0
        if item.get('enabled') and amt:
            add_code(penalty_code, _penalty_inline_values(item))


def _resolve_sale_clauses(
    wizard: Dict[str, Any],
    library: Dict[str, ContractClauseDefinition],
    selected: List[Dict[str, Any]],
    seen: Set[str],
) -> None:
    fin = wizard.get('financial') or {}
    prop = wizard.get('property') or {}
    context = build_sale_clause_context(wizard)

    def add_code(code: str, inline_values: Optional[Dict] = None) -> None:
        if code in seen or code not in library:
            return
        seen.add(code)
        entry: Dict[str, Any] = {'code': code}
        if inline_values:
            entry['inline_values'] = inline_values
        selected.append(entry)

    add_code('SALE_PROPERTY_DECLARATIONS')
    if context.get('property_has_tenant'):
        add_code('SALE_EXISTING_TENANT')
    if context.get('has_delivery_date'):
        add_code('SALE_DELIVERY')
    if context.get('has_official_transfer_plan'):
        add_code('SALE_OFFICIAL_TRANSFER')
    if context.get('has_sale_cost_allocations'):
        add_code('SALE_COSTS')

    optional_codes = {
        item.get('code') for item in (wizard.get('clause_optional') or []) if item.get('code')
    }
    if not wizard.get('clause_optional'):
        optional_codes = set(DEFAULT_SALE_OPTIONAL)
    for code in optional_codes:
        if code in DEFAULT_SALE_OPTIONAL or code in library:
            add_code(code)

    penalties = fin.get('penalties') or {}
    for key, penalty_code in SALE_PENALTY_CODE_MAP.items():
        item = penalties.get(key) or {}
        amt = item.get('amount_per_day') or item.get('amount') or 0
        if item.get('enabled') and amt:
            unit = item.get('unit', 'daily')
            add_code(penalty_code, {
                'amount': str(amt),
                'penalty_amount': str(amt),
                'penalty_unit': unit,
                'unit': unit,
            })


def resolve_selected_clauses(
    contract_type: str,
    wizard: Dict[str, Any],
    *,
    user=None,
) -> List[Dict[str, Any]]:
    context = build_clause_context(wizard, contract_type)
    library = _library_clauses(contract_type, context, user=user)
    selected: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    if contract_type == CONTRACT_TYPE_LEASE:
        _resolve_lease_clauses(wizard, library, selected, seen)
    elif contract_type == CONTRACT_TYPE_SALE:
        _resolve_sale_clauses(wizard, library, selected, seen)
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
        card.setdefault('review_badge', clause_review_badge(defn.review_status))
        card.setdefault('review_status_label', clause_review_status_label(defn.review_status))
    return card


def build_clause_sections(
    contract_type: str,
    wizard: Dict[str, Any],
    *,
    user=None,
    is_staff: bool = False,
) -> List[Dict[str, Any]]:
    context = build_clause_context(wizard, contract_type)
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
        costs_def = library.get('LEASE_COSTS')
        cards_by_cat['costs_repairs'].append({
            'type': 'cost_allocation',
            'id': 'costs',
            'title': 'هزینه‌های جاری و مشترک',
            'question': 'هر هزینه بر عهده چه کسی است؟',
            'rows': cost_rows,
            'clause_code': 'LEASE_COSTS' if costs_def else None,
            'clause_preview': costs_def.body_template if costs_def else '',
            'review_status': costs_def.review_status if costs_def else '',
            'review_badge': clause_review_badge(costs_def.review_status) if costs_def else None,
            'review_status_label': clause_review_status_label(costs_def.review_status) if costs_def else '',
        })

        repairs_def = library.get('LEASE_REPAIRS')
        cards_by_cat['costs_repairs'].append({
            'type': 'repairs_allocation',
            'id': 'repairs',
            'title': 'تعمیرات و نگهداری فنی',
            'question': 'مسئول تعمیرات اساسی و جزئی چه کسی است؟',
            'major_value': costs.get('major_repairs') or 'landlord',
            'minor_value': costs.get('minor_repairs') or 'tenant',
            'clause_code': 'LEASE_REPAIRS' if repairs_def else None,
            'clause_preview': repairs_def.body_template if repairs_def else '',
            'review_status': repairs_def.review_status if repairs_def else '',
            'review_badge': clause_review_badge(repairs_def.review_status) if repairs_def else None,
            'review_status_label': clause_review_status_label(repairs_def.review_status) if repairs_def else '',
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
        if not wizard.get('clause_optional'):
            optional_active = set(DEFAULT_SALE_OPTIONAL)

        decl_def = library.get('SALE_PROPERTY_DECLARATIONS')
        cards_by_cat['property_status'].append(_clause_card(
            decl_def,
            type='info',
            title='وضعیت اعلامی مورد معامله',
            message='بر اساس اظهار فروشنده — فایلینگ استعلام ثبتی انجام نمی‌دهد.',
        ))

        tenant_def = library.get('SALE_EXISTING_TENANT')
        has_tenant = prop.get('has_tenant') or fin.get('property_has_tenant')
        cards_by_cat['property_status'].append({
            'type': 'choice',
            'id': 'has_tenant',
            'title': 'مستأجر یا متصرف',
            'question': 'آیا ملک در حال حاضر مستأجر یا متصرف دارد؟',
            'value': 'yes' if has_tenant else 'no',
            'options': [
                {'value': 'no', 'label': 'خیر'},
                {'value': 'yes', 'label': 'بله'},
            ],
            'clause_code': 'SALE_EXISTING_TENANT' if tenant_def else None,
            'clause_preview': tenant_def.body_template if tenant_def else '',
            'review_status': tenant_def.review_status if tenant_def else '',
            'review_badge': clause_review_badge(tenant_def.review_status) if tenant_def else None,
            'review_status_label': clause_review_status_label(tenant_def.review_status) if tenant_def else '',
        })

        del_def = library.get('SALE_DELIVERY')
        if fin.get('delivery_date') or del_def:
            cards_by_cat['delivery_docs'].append(_clause_card(
                del_def,
                type='info',
                title='تحویل مورد معامله',
                message=f'تاریخ تحویل: {fin.get("delivery_date") or "—"} (از مرحله مبلغ و پرداخت)',
            ))

        doc_def = library.get('SALE_DOCUMENTS')
        cards_by_cat['delivery_docs'].append(_clause_card(
            doc_def,
            type='optional_clause',
            id='SALE_DOCUMENTS',
            title='ارائه مدارک مورد نیاز',
            question=doc_def.plain_explanation if doc_def else 'مدارک لازم برای انتقال',
            enabled='SALE_DOCUMENTS' in optional_active,
        ))

        xfer_def = library.get('SALE_OFFICIAL_TRANSFER')
        if fin.get('official_transfer_date') or fin.get('transfer_date') or fin.get('transfer_place'):
            cards_by_cat['official_transfer'].append(_clause_card(
                xfer_def,
                type='info',
                title='اقدام برای انتقال رسمی',
                message=(
                    f'تاریخ: {fin.get("official_transfer_date") or fin.get("transfer_date") or "—"} — '
                    f'محل: {fin.get("transfer_place") or "—"}'
                ),
            ))

        seller_def = library.get('SALE_SELLER_OBLIGATIONS')
        buyer_def = library.get('SALE_BUYER_OBLIGATIONS')
        cards_by_cat['obligations'].append(_clause_card(
            seller_def,
            type='optional_clause',
            id='SALE_SELLER_OBLIGATIONS',
            title='تعهدات فروشنده',
            question=seller_def.plain_explanation if seller_def else 'تعهدات فروشنده',
            enabled='SALE_SELLER_OBLIGATIONS' in optional_active,
        ))
        cards_by_cat['obligations'].append(_clause_card(
            buyer_def,
            type='optional_clause',
            id='SALE_BUYER_OBLIGATIONS',
            title='تعهدات خریدار',
            question=buyer_def.plain_explanation if buyer_def else 'تعهدات خریدار',
            enabled='SALE_BUYER_OBLIGATIONS' in optional_active,
        ))

        sale_costs = fin.get('sale_costs') or {}
        cost_rows = [
            {'key': key, 'label': label, 'value': sale_costs.get(key) or ''}
            for key, label in SALE_COST_UI_FIELDS
        ]
        costs_def = library.get('SALE_COSTS')
        cards_by_cat['costs'].append({
            'type': 'sale_cost_allocation',
            'id': 'sale_costs',
            'title': 'هزینه‌های مرتبط با معامله',
            'question': 'هر هزینه بر عهده چه کسی است؟',
            'rows': cost_rows,
            'clause_code': 'SALE_COSTS' if costs_def else None,
            'clause_preview': costs_def.body_template if costs_def else '',
            'review_status': costs_def.review_status if costs_def else '',
            'review_badge': clause_review_badge(costs_def.review_status) if costs_def else None,
            'review_status_label': clause_review_status_label(costs_def.review_status) if costs_def else '',
        })

        for key, prefix, title, penalty_code in SALE_PENALTY_FIELDS:
            item = (fin.get('penalties') or {}).get(key) or {}
            defn = library.get(penalty_code)
            cards_by_cat['penalties'].append(_clause_card(
                defn,
                type='penalty',
                id=key,
                title=title,
                prefix=prefix,
                enabled=bool(item.get('enabled')),
                amount=item.get('amount_per_day') or item.get('amount') or '',
                unit=item.get('unit', 'daily'),
            ))

        term_def = library.get('SALE_BREACH_TERMINATION')
        cards_by_cat['termination'].append(_clause_card(
            term_def,
            type='optional_clause',
            id='SALE_BREACH_TERMINATION',
            title='تخلف از تعهدات و پایان قرارداد',
            question=term_def.plain_explanation if term_def else 'قواعد پایان قرارداد',
            enabled='SALE_BREACH_TERMINATION' in optional_active,
        ))

        pay_def = library.get('SALE_PAYMENT_OBLIGATION')
        if fin.get('payments') or fin.get('total_price'):
            cards_by_cat['obligations'].append(_clause_card(
                pay_def,
                type='optional_clause',
                id='SALE_PAYMENT_OBLIGATION',
                title='تعهد پرداخت ثمن',
                question='متن تعهد — مبالغ در ماده مالی نمایش داده می‌شود.',
                enabled='SALE_PAYMENT_OBLIGATION' in optional_active,
            ))

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

    elif contract_type == CONTRACT_TYPE_SALE:
        fin['penalties'] = parsed.get('penalties') or fin.get('penalties') or {}
        fin['sale_costs'] = parsed.get('sale_costs') or fin.get('sale_costs') or {}
        if parsed.get('property_has_tenant') is not None:
            wizard = dict(wizard)
            prop = dict(wizard.get('property') or {})
            prop['has_tenant'] = bool(parsed.get('property_has_tenant'))
            wizard['property'] = prop

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
