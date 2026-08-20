"""اقدام پیشنهادی پرونده مخاطب — فقط از context موجود، بدون موتور Match اضافه."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.urls import reverse

CLOSED_DEAL_STAGES = frozenset({'بسته‌شده', 'از دست رفته'})


def has_no_preferences(customer) -> bool:
    """اگر هیچ ترجیح مهمی ثبت نشده — همان معیار خالی بودن سایدبار فعلی."""
    if getattr(customer, 'customer_type', '') == 'سازنده':
        return not any((
            customer.property_type,
            customer.budget_min,
            customer.budget_max,
            customer.min_area,
            customer.max_area,
            customer.areas,
            customer.builder_buy_property_types,
            customer.builder_buy_budget_min,
            customer.builder_buy_budget_max,
            customer.builder_buy_min_area,
            customer.builder_buy_max_area,
            customer.builder_buy_areas,
        ))
    return not any((
        customer.property_type,
        customer.budget_min,
        customer.budget_max,
        customer.deposit_min,
        customer.deposit_max,
        customer.rent_min,
        customer.rent_max,
        customer.min_area,
        customer.max_area,
        customer.rooms_min,
        customer.rooms_max,
        customer.rooms,
        customer.year_min,
        customer.year_max,
        customer.floor_min,
        customer.floor_max,
        customer.want_parking,
        customer.want_storage,
        customer.want_elevator,
        customer.areas,
    ))
    if getattr(customer, 'customer_type', '') == 'سازنده':
        return not any((
            customer.property_type,
            customer.budget_min,
            customer.budget_max,
            customer.min_area,
            customer.max_area,
            customer.areas,
            customer.builder_buy_property_types,
            customer.builder_buy_budget_min,
            customer.builder_buy_budget_max,
            customer.builder_buy_min_area,
            customer.builder_buy_max_area,
            customer.builder_buy_areas,
        ))
    return not any((
        customer.property_type,
        customer.budget_min,
        customer.budget_max,
        customer.deposit_min,
        customer.deposit_max,
        customer.rent_min,
        customer.rent_max,
        customer.min_area,
        customer.max_area,
        customer.rooms_min,
        customer.rooms_max,
        customer.rooms,
        customer.year_min,
        customer.year_max,
        customer.floor_min,
        customer.floor_max,
        customer.want_parking,
        customer.want_storage,
        customer.want_elevator,
        customer.areas,
    ))


def _match_count(match_data: Optional[dict]) -> int:
    if not match_data or not match_data.get('eligible'):
        return 0
    if 'total_count' in match_data:
        try:
            return int(match_data['total_count'] or 0)
        except (TypeError, ValueError):
            return 0
    return len(match_data.get('crm_matches') or []) + len(match_data.get('divar_matches') or [])


def _suggested_linked_count(property_links, linked_listings) -> int:
    n = sum(1 for link in (property_links or []) if getattr(link, 'role', '') == 'پیشنهادی')
    n += sum(1 for item in (linked_listings or []) if getattr(item, 'role', '') == 'پیشنهادی')
    return n


def _active_deals(deals) -> List[Any]:
    active = []
    for deal in deals or []:
        stage = getattr(deal, 'stage', '') or ''
        if stage in CLOSED_DEAL_STAGES or getattr(deal, 'closed_at', None):
            continue
        active.append(deal)
    return active


def _last_call(activities):
    for item in activities or []:
        if getattr(item, 'activity_type', '') == 'تماس':
            return item
    return None


def _deal_mode_label(customer) -> str:
    has_sale = bool(customer.budget_min or customer.budget_max)
    has_rent = bool(
        customer.deposit_min or customer.deposit_max or customer.rent_min or customer.rent_max
    )
    ctype = getattr(customer, 'customer_type', '') or ''
    if 'اجاره' in ctype:
        return 'اجاره'
    if 'خرید' in ctype or ctype in {'خریدار', 'فروشنده', 'فروشنده ملک', 'مالک'}:
        if has_rent and not has_sale:
            return 'اجاره'
        return 'خرید'
    if has_sale and has_rent:
        return 'خرید / اجاره'
    if has_sale:
        return 'خرید'
    if has_rent:
        return 'اجاره'
    return ''


def _nba(
    *,
    key: str,
    title: str,
    desc: str,
    cta: str,
    action: str,
    drawer: str = '',
    form_tab: str = '',
    tab: str = '',
    url: str = '',
    form_action: str = '',
) -> Dict[str, Any]:
    return {
        'key': key,
        'title': title,
        'desc': desc,
        'cta': cta,
        'action': action,
        'drawer': drawer,
        'form_tab': form_tab,
        'tab': tab,
        'url': url,
        'form_action': form_action,
    }


def build_contact_workflow(
    *,
    customer,
    follow_up_state: str,
    activities,
    match_data: Optional[dict],
    property_links,
    linked_listings,
    visits,
    deals,
    can_edit: bool,
) -> Dict[str, Any]:
    match_count = _match_count(match_data)
    suggested_linked = _suggested_linked_count(property_links, linked_listings)
    active_deals = _active_deals(deals)
    last_call = _last_call(activities)
    no_prefs = has_no_preferences(customer)
    nba = None

    if can_edit and follow_up_state in ('overdue', 'today'):
        is_overdue = follow_up_state == 'overdue'
        if customer.phone:
            nba = _nba(
                key='followup',
                title='پیگیری معوق است' if is_overdue else 'پیگیری امروز است',
                desc='پس از تماس می‌توانید پیگیری بعدی را ثبت کنید',
                cta='ثبت تماس',
                action='form',
                form_action='log_call',
            )
        else:
            nba = _nba(
                key='followup',
                title='پیگیری معوق است' if is_overdue else 'پیگیری امروز است',
                desc='نتیجه پیگیری را در پرونده ثبت کنید',
                cta='انجام پیگیری',
                action='form',
                form_action='complete_followup',
            )
    elif can_edit and no_prefs:
        nba = _nba(
            key='need',
            title='نیاز مشتری هنوز ثبت نشده',
            desc='بودجه، محله یا مشخصات ملک در پرونده نیست',
            cta='ثبت نیاز',
            action='drawer',
            drawer='drawer-edit',
            form_tab='prefs',
        )
    elif active_deals:
        deal = active_deals[0]
        nba = _nba(
            key='deal_open',
            title=f'معامله فعال: {deal.stage}',
            desc=getattr(deal, 'title', '') or 'ادامه از پرونده معامله',
            cta='ادامه معامله',
            action='url',
            url=reverse('workspace:crm_deal_detail', kwargs={'deal_id': deal.pk}),
        )
    elif match_count:
        nba = _nba(
            key='matches',
            title=f'{match_count} فایل پیشنهادی آماده است',
            desc='بر اساس ترجیحات همین مخاطب',
            cta='مشاهده فایل‌های پیشنهادی',
            action='tab',
            tab='matches',
        )
    elif can_edit and suggested_linked:
        nba = _nba(
            key='send',
            title=f'{suggested_linked} فایل برای ارسال آماده است',
            desc='از پرونده همین مخاطب انتخاب و ارسال کنید',
            cta='ارسال برای مخاطب',
            action='tab',
            tab='properties',
        )
    elif can_edit and visits and not active_deals:
        nba = _nba(
            key='deal_start',
            title='بازدید ثبت شده و معامله‌ای باز نیست',
            desc='در صورت توافق می‌توانید معامله را از مسیر موجود شروع کنید',
            cta='شروع معامله',
            action='drawer',
            drawer='drawer-deal',
        )
    elif can_edit and follow_up_state == 'none':
        nba = _nba(
            key='next_follow',
            title='پیگیری بعدی ثبت نشده',
            desc='زمان تماس یا پیگیری بعد را مشخص کنید',
            cta='ثبت پیگیری بعدی',
            action='drawer',
            drawer='drawer-followup',
        )

    summary = {
        'has_no_preferences': no_prefs,
        'match_count': match_count,
        'suggested_linked': suggested_linked,
        'deal_mode': _deal_mode_label(customer),
        'last_call': last_call,
        'active_deal_count': len(active_deals),
        'closed_deal_count': max(0, len(deals or []) - len(active_deals)),
        'has_visit': bool(visits),
    }
    return {'nba': nba, 'summary': summary}
