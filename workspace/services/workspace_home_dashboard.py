"""داشبورد میزکار V2 — تجمیع داده‌های واقعی و permission-aware."""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Dict, List

from django.db.models import Count
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from workspace.models import Dataset, Listing, PropertyMatchAlert, PropertyVisit
from workspace.services.access import has_active_bot_license
from workspace.services.crm import (
    build_dashboard_charts,
    get_dashboard_stats,
)
from workspace.services.crm_deal_stages import active_stages_for_user, stage_meta_map
from workspace.services.crm_deals import get_deal_stats, is_deal_stale
from workspace.services.crm_property_archive import archived_properties_q
from workspace.services.crm_scope import customers_qs, deals_qs, properties_qs, reminders_qs
from workspace.services.crm_today import get_today_queue
from workspace.services.home_nba import build_home_nba
from workspace.services.jalali_input import format_jalali_date
from workspace.services.workspace_agency_home import build_workspace_agency_panel


TODAY_CENTER_LIMIT = 6
OPPORTUNITY_LIMIT = 4
RECENT_ACTIVITY_LIMIT = 6
UPCOMING_VISIT_DAYS = 7


def _safe_contract_needs_action(user) -> int:
    # هم‌راستا با crm_views._crm_nav_counts: قرارداد ممکن است برای بعضی کاربران در دسترس نباشد.
    try:
        from contracts.services.dashboard import contract_dashboard_stats
        return int(contract_dashboard_stats(user).get('needs_action') or 0)
    except Exception:
        return 0


def _active_contacts_count(crm_stats: Dict[str, Any]) -> int:
    return int(crm_stats.get('new_contacts') or 0) + int(crm_stats.get('in_progress') or 0)


def _active_properties_count(user) -> int:
    return properties_qs(user).exclude(archived_properties_q()).count()


def _build_day_status(*, overdue: int, today_due: int, contracts_action: int) -> Dict[str, str]:
    bits: List[str] = []
    if overdue:
        bits.append(f'{overdue} پیگیری معوق')
    if today_due:
        bits.append(f'{today_due} کار امروز')
    if contracts_action:
        bits.append(f'{contracts_action} قرارداد نیازمند اقدام')
    if not bits:
        return {
            'tone': 'ok',
            'label': 'امروز کار فوری ندارید',
            'short': 'روز آرام',
        }
    return {
        'tone': 'warn' if overdue or contracts_action else 'info',
        'label': ' · '.join(bits),
        'short': bits[0],
    }


def _resolve_queue_item_url(item: Dict[str, Any]) -> str:
    name = item.get('detail_url_name') or 'workspace:crm_today'
    kwargs: Dict[str, Any] = {}
    if name == 'workspace:crm_detail' and item.get('customer_id'):
        kwargs['customer_id'] = item['customer_id']
    elif name == 'workspace:crm_property_detail' and item.get('property_id'):
        kwargs['property_id'] = item['property_id']
    try:
        return reverse(name, kwargs=kwargs) if kwargs else reverse(name)
    except NoReverseMatch:
        return reverse('workspace:crm_today')


def _build_today_center(user, *, queue_items: List[Dict[str, Any]], queue_stats: Dict[str, int]) -> Dict[str, Any]:
    today = timezone.now().date()
    end = today + timedelta(days=UPCOMING_VISIT_DAYS)
    items: List[Dict[str, Any]] = []

    for raw in queue_items:
        kind = raw.get('kind') or 'reminder'
        urgency = raw.get('urgency') or 'today'
        if kind == 'followup':
            label = 'پیگیری'
            icon = 'fa-phone'
        else:
            label = 'یادآوری'
            icon = 'fa-bell'
        subtitle = (raw.get('subtitle') or '').strip()
        # جلوگیری از تکرار نوع اقدام در subtitle
        if subtitle in ('پیگیری امروز', label):
            subtitle = ''
        items.append({
            'key': raw.get('id') or f'{kind}-{raw.get("reminder_id") or raw.get("customer_id")}',
            'kind': kind,
            'urgency': urgency,
            'title': raw.get('title') or 'بدون عنوان',
            'subtitle': subtitle,
            'meta_label': label,
            'icon': icon,
            'url': _resolve_queue_item_url(raw),
            'phone': raw.get('customer_phone') or '',
            'can_call': bool(raw.get('customer_phone')),
            'complete_url': (
                reverse('workspace:reminder_toggle', kwargs={'reminder_id': raw['reminder_id']})
                if kind == 'reminder' and raw.get('reminder_id')
                else ''
            ),
        })

    visits = list(
        PropertyVisit.objects.filter(
            user=user,
            visit_date__gte=today,
            visit_date__lte=end,
        )
        .select_related('customer', 'property')
        .order_by('visit_date')[:5]
    )
    for v in visits:
        title = v.property.title if v.property_id and v.property else (v.listing_title or 'بازدید')
        cust_name = v.customer.name if v.customer_id and v.customer else ''
        url = reverse('workspace:crm_calendar')
        if v.customer_id:
            url = reverse('workspace:crm_detail', kwargs={'customer_id': v.customer_id}) + '?tab=visits'
        items.append({
            'key': f'visit-{v.pk}',
            'kind': 'visit',
            'urgency': 'today' if v.visit_date == today else 'upcoming',
            'title': title,
            'subtitle': ' · '.join(
                p for p in [cust_name, format_jalali_date(v.visit_date)] if p
            ),
            'meta_label': 'بازدید',
            'icon': 'fa-door-open',
            'url': url,
            'phone': '',
            'can_call': False,
            'complete_url': '',
        })

    contracts_n = _safe_contract_needs_action(user)
    if contracts_n:
        items.append({
            'key': 'contracts-action',
            'kind': 'contract',
            'urgency': 'today',
            'title': f'{contracts_n} قرارداد نیازمند اقدام',
            'subtitle': 'تأیید یا تکمیل',
            'meta_label': 'قرارداد',
            'icon': 'fa-file-signature',
            'url': reverse('workspace:contracts_dashboard') + '?focus=needs',
            'phone': '',
            'can_call': False,
            'complete_url': '',
        })

    urgency_rank = {'overdue': 0, 'today': 1, 'upcoming': 2}
    kind_rank = {'followup': 0, 'reminder': 1, 'visit': 2, 'contract': 3}
    items.sort(key=lambda x: (
        urgency_rank.get(x['urgency'], 9),
        kind_rank.get(x['kind'], 9),
        x.get('title') or '',
    ))
    total_count = len(items)
    visible = items[:TODAY_CENTER_LIMIT]

    return {
        'items': visible,
        'visible_count': len(visible),
        'has_more': total_count > len(visible),
        'stats': {
            'total': total_count,
            'overdue': int(queue_stats.get('overdue') or 0),
            'today': int(queue_stats.get('today') or 0),
            'visits': len(visits),
            'contracts': contracts_n,
        },
        'all_url': reverse('workspace:crm_today'),
    }


def _match_opportunities(user, limit: int = 4) -> List[Dict[str, Any]]:
    qs = PropertyMatchAlert.objects.filter(
        user=user,
        status__in=[
            PropertyMatchAlert.STATUS_PENDING,
            PropertyMatchAlert.STATUS_NOTIFIED,
        ],
    )
    by_customer = (
        qs.values('customer_id')
        .annotate(c=Count('id'))
        .order_by('-c')[:limit]
    )
    customer_ids = [row['customer_id'] for row in by_customer if row.get('customer_id')]
    if not customer_ids:
        return []
    names = {
        c.pk: c.name
        for c in customers_qs(user).filter(pk__in=customer_ids).only('id', 'name')
    }
    cards: List[Dict[str, Any]] = []
    for row in by_customer:
        cid = row['customer_id']
        if not cid:
            continue
        count = int(row['c'] or 0)
        cards.append({
            'key': f'match-{cid}',
            'kind': 'match',
            'kind_label': 'تطبیق',
            'tone': 'info',
            'icon': 'fa-house',
            'title': names.get(cid) or 'مخاطب',
            'desc': f'{count} فایل مناسب',
            'url': reverse('workspace:crm_detail', kwargs={'customer_id': cid}) + '?tab=matches',
            'cta': 'بررسی',
        })
    return cards


def _stale_deal_opportunities(user, limit: int = 3) -> List[Dict[str, Any]]:
    active_names = active_stages_for_user(user)
    meta_map = stage_meta_map(user)
    deals = list(
        deals_qs(user)
        .filter(stage__in=active_names)
        .only('id', 'title', 'stage', 'stage_changed_at', 'updated_at', 'created_at', 'user_id', 'next_action_type', 'next_action_at')
        .order_by('-updated_at')[:40]
    )
    cards: List[Dict[str, Any]] = []
    for deal in deals:
        stale = is_deal_stale(deal, meta_map.get(deal.stage))
        no_next = not (deal.next_action_type or deal.next_action_at)
        if not stale and not no_next:
            continue
        if stale:
            desc = 'بدون پیشرفت کافی'
            tone = 'warn'
            kind_label = 'پیگیری ضروری'
            icon = 'fa-hourglass-end'
        else:
            desc = 'بدون اقدام بعدی'
            tone = 'info'
            kind_label = 'معامله'
            icon = 'fa-bolt'
        cards.append({
            'key': f'deal-{deal.pk}',
            'kind': 'deal',
            'kind_label': kind_label,
            'tone': tone,
            'icon': icon,
            'title': deal.title or f'معامله #{deal.pk}',
            'desc': desc,
            'url': reverse('workspace:crm_deal_detail', kwargs={'deal_id': deal.pk}),
            'cta': 'پیگیری',
        })
        if len(cards) >= limit:
            break
    return cards


def _build_opportunities(user, *, home_nba: List[Dict[str, Any]]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []

    for action in home_nba:
        if action.get('key') in ('overdue', 'today'):
            continue
        key = action.get('key') or 'nba'
        items.append({
            'key': key,
            'kind': key,
            'kind_label': {
                'matches': 'تطبیق',
                'agency_inbox': 'آژانس',
                'new_filing': 'فایلینگ',
            }.get(key, 'فرصت'),
            'tone': action.get('tone') or 'info',
            'icon': {
                'matches': 'fa-house',
                'agency_inbox': 'fa-inbox',
                'new_filing': 'fa-folder-open',
            }.get(key, 'fa-lightbulb'),
            'title': action.get('title') or '',
            'desc': (action.get('desc') or '')[:48],
            'url': action.get('url') or '#',
            'cta': action.get('cta') or 'مشاهده',
            'count': action.get('count'),
        })

    for card in _match_opportunities(user):
        if any(i.get('key') == card['key'] for i in items):
            continue
        items.append(card)

    for card in _stale_deal_opportunities(user):
        items.append(card)

    return {
        'items': items[:OPPORTUNITY_LIMIT],
        'empty': not items,
    }


def _build_deal_funnel(user, deal_stats: Dict[str, Any]) -> Dict[str, Any]:
    by_stage = deal_stats.get('by_stage') or {}
    stages = active_stages_for_user(user)
    total_active = int(deal_stats.get('active') or 0) or 1
    rows: List[Dict[str, Any]] = []
    for name in stages:
        count = int(by_stage.get(name) or 0)
        if count <= 0:
            continue
        rows.append({
            'label': name,
            'count': count,
            'pct': int(round(count / total_active * 100)),
        })
    return {
        'rows': rows,
        'active': int(deal_stats.get('active') or 0),
        'stale': int(deal_stats.get('stale') or 0),
        'url': reverse('workspace:crm_deals'),
        'empty': not rows,
    }


def _build_quick_actions(*, has_bot_license: bool, show_agency: bool) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = [
        {
            'key': 'contact',
            'label': 'افزودن مخاطب',
            'icon': 'fa-user-plus',
            'url': reverse('workspace:crm_contacts') + '?open=drawer-contact',
            'tone': 'indigo',
        },
        {
            'key': 'property',
            'label': 'افزودن فایل',
            'icon': 'fa-building',
            'url': reverse('workspace:crm_properties') + '?open=drawer-property',
            'tone': 'violet',
        },
        {
            'key': 'deal',
            'label': 'ثبت معامله',
            'icon': 'fa-handshake',
            'url': reverse('workspace:crm_deal_create'),
            'tone': 'purple',
        },
        {
            'key': 'reminder',
            'label': 'ایجاد یادآوری',
            'icon': 'fa-bell',
            'url': reverse('workspace:crm_reminders') + '?open=drawer-reminder',
            'tone': 'amber',
        },
    ]
    if has_bot_license:
        actions.append({
            'key': 'filing',
            'label': 'جست‌وجوی فایلینگ',
            'icon': 'fa-magnifying-glass',
            'url': reverse('workspace:dataset_list'),
            'tone': 'blue',
        })
    else:
        actions.append({
            'key': 'filing',
            'label': 'جست‌وجوی فایلینگ',
            'icon': 'fa-lock',
            'url': reverse('workspace:upgrade') + '?feature=datasets',
            'tone': 'blue',
        })
    actions.append({
        'key': 'contract',
        'label': 'قرارداد جدید',
        'icon': 'fa-file-signature',
        'url': reverse('workspace:contract_create_standalone'),
        'tone': 'teal',
    })
    actions.append({
        'key': 'ai',
        'label': 'دستیار هوشمند',
        'icon': 'fa-wand-magic-sparkles',
        'url': '#wsHomeSmartCommand',
        'tone': 'rose',
        'is_anchor': True,
    })
    if show_agency:
        actions.append({
            'key': 'agency',
            'label': 'مدیریت آژانس',
            'icon': 'fa-building-user',
            'url': reverse('workspace:agency_hub_dashboard'),
            'tone': 'slate',
        })
    return actions[:8]


def _serialize_recent_activities(user) -> List[Dict[str, Any]]:
    from workspace.models import CustomerActivity

    rows: List[Dict[str, Any]] = []
    qs = (
        CustomerActivity.objects
        .filter(customer__user=user)
        .select_related('customer', 'property')
        .order_by('-created_at')[:RECENT_ACTIVITY_LIMIT]
    )
    for act in qs:
        customer = act.customer
        if getattr(act, 'customer_id', None):
            url = reverse('workspace:crm_detail', kwargs={'customer_id': act.customer_id})
        elif act.property_id:
            url = reverse('workspace:crm_property_detail', kwargs={'property_id': act.property_id})
        else:
            url = reverse('workspace:crm_today')
        title = act.title or act.activity_type or 'فعالیت'
        desc_parts = []
        if customer:
            desc_parts.append(customer.name)
        if act.content:
            desc_parts.append((act.content or '')[:80])
        rows.append({
            'id': act.pk,
            'title': title,
            'desc': ' — '.join(desc_parts),
            'type': act.activity_type or '',
            'url': url,
            'when': act.created_at,
        })
    return rows


def _build_kpi(
    *,
    crm_stats: Dict[str, Any],
    deal_stats: Dict[str, Any],
    queue_stats: Dict[str, int],
    active_properties: int,
) -> Dict[str, Any]:
    overdue = int(crm_stats.get('overdue_followups') or 0)
    due_today = int(crm_stats.get('due_today') or 0)
    today_total = int(queue_stats.get('total') or 0)
    active_contacts = _active_contacts_count(crm_stats)
    active_deals = int(deal_stats.get('active') or 0)
    stale_deals = int(deal_stats.get('stale') or 0)

    def _share(part: int, base: int) -> int:
        if not base:
            return 0
        return int(round(part / base * 100))

    hero_meta = (
        f'{overdue} معوق · {due_today} امروز'
        if (overdue or due_today)
        else 'صف کار خالی است'
    )
    return {
        'today_work': today_total,
        'overdue': overdue,
        'due_today': due_today,
        'hero_meta': hero_meta,
        'overdue_share': _share(overdue, max(today_total, 1)),
        'active_contacts': active_contacts,
        'contacts_total': int(crm_stats.get('total_contacts') or 0),
        'contacts_meta': (
            f'{crm_stats.get("new_contacts") or 0} جدید · {crm_stats.get("in_progress") or 0} در پیگیری'
            if active_contacts
            else 'مخاطب فعالی نیست'
        ),
        'active_properties': active_properties,
        'properties_total': int(crm_stats.get('total_properties') or 0),
        'properties_meta': (
            f'{active_properties} از {crm_stats.get("total_properties") or 0} فایل'
            if active_properties
            else 'فایل فعالی نیست'
        ),
        'active_deals': active_deals,
        'stale_deals': stale_deals,
        'deals_meta': (
            f'{stale_deals} نیازمند پیگیری'
            if stale_deals
            else ('معامله فعالی نیست' if not active_deals else 'همه در مسیر مجاز')
        ),
        'links': {
            'today': reverse('workspace:crm_today'),
            'contacts': reverse('workspace:crm_contacts'),
            'properties': reverse('workspace:crm_properties'),
            'deals': reverse('workspace:crm_deals'),
            'deals_stale': reverse('workspace:crm_deals') + '?bucket=stale',
        },
    }


def build_workspace_home_dashboard(user) -> Dict[str, Any]:
    """Context کامل داشبورد میزکار — فقط داده واقعی."""
    datasets_qs = Dataset.objects.filter(user=user, is_active=True)
    has_bot = has_active_bot_license(user)
    crm_stats = get_dashboard_stats(user)
    deal_stats = get_deal_stats(user)
    queue_items, queue_stats = get_today_queue(user)
    active_properties = _active_properties_count(user)
    contracts_action = _safe_contract_needs_action(user)

    data_stats = {
        'datasets': datasets_qs.count(),
        'listings': Listing.objects.filter(dataset__user=user, dataset__is_active=True).count(),
        'sale': datasets_qs.filter(transaction_type__icontains='فروش').count(),
        'rent': datasets_qs.filter(transaction_type__icontains='اجاره').count(),
    }

    home_nba = build_home_nba(
        user,
        crm_nav_counts={
            'today_overdue': crm_stats['overdue_followups'],
            'today_due': crm_stats['due_today'],
        },
        datasets_qs=datasets_qs,
        has_bot_license=has_bot,
        contact_count=crm_stats['total_contacts'],
        dataset_count=data_stats['datasets'],
    )

    agency_panel = build_workspace_agency_panel(user)
    show_agency = bool(agency_panel)

    charts = build_dashboard_charts(user)
    trend_has_data = False
    for chart in charts:
        if chart.get('id') == 'activity':
            for ds in chart.get('datasets') or []:
                if any(int(v or 0) for v in (ds.get('data') or [])):
                    trend_has_data = True
                    break

    home_is_empty = (
        not crm_stats['total_contacts']
        and not crm_stats['total_properties']
        and not data_stats['datasets']
        and not home_nba
        and not int(deal_stats.get('total') or 0)
    )

    return {
        'data_stats': data_stats,
        'crm_stats': crm_stats,
        'deal_stats': deal_stats,
        'charts_json': json.dumps(charts, ensure_ascii=False),
        'trend_has_data': trend_has_data,
        'active_dataset': datasets_qs.order_by('-updated_at', '-created_at').first(),
        'home_nba': home_nba,
        'home_is_empty': home_is_empty,
        'has_bot_license': has_bot,
        'workspace_agency_panel': agency_panel,
        'home_kpi': _build_kpi(
            crm_stats=crm_stats,
            deal_stats=deal_stats,
            queue_stats=queue_stats,
            active_properties=active_properties,
        ),
        'home_day_status': _build_day_status(
            overdue=int(crm_stats.get('overdue_followups') or 0),
            today_due=int(queue_stats.get('today') or 0),
            contracts_action=contracts_action,
        ),
        'home_today_center': _build_today_center(
            user, queue_items=queue_items, queue_stats=queue_stats,
        ),
        'home_opportunities': _build_opportunities(user, home_nba=home_nba),
        'home_deal_funnel': _build_deal_funnel(user, deal_stats),
        'home_quick_actions': _build_quick_actions(
            has_bot_license=has_bot,
            show_agency=show_agency,
        ),
        'home_recent_activities': _serialize_recent_activities(user),
        'home_notif': {
            'reminders': reminders_qs(user).filter(is_done=False).count(),
            'overdue': int(crm_stats.get('overdue_followups') or 0),
            'url': reverse('workspace:crm_reminders'),
        },
    }
