"""اقدام بعدی، پیگیری سریع و timeline معامله."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from django.utils import timezone

from workspace.constants import (
    DEAL_ACTION_ICONS,
    DEAL_ACTION_OTHER,
    DEAL_FOLLOWUP_KEYS,
    DEAL_FOLLOWUP_LABELS,
    DEAL_NEXT_ACTION_KEYS,
    DEAL_NEXT_ACTION_LABELS,
    DEAL_STAGE_LOST,
    DEAL_STAGE_WON,
)
from workspace.models import CRMDeal, CRMDealFollowUp, CustomerActivity
from workspace.services.jalali_input import format_jalali_date, format_jalali_datetime, to_persian_digits


def _aware(dt: datetime) -> datetime:
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


def _normalize_action_type(raw: str, *, allowed: set) -> str:
    key = (raw or '').strip()
    if key in allowed:
        return key
    return DEAL_ACTION_OTHER


def is_next_action_overdue(deal: CRMDeal, *, now: Optional[datetime] = None) -> bool:
    if not deal.next_action_at or not deal.next_action_type:
        return False
    ts = _aware(deal.next_action_at)
    ref = now or timezone.now()
    return ts < ref


def _relative_day_label(ts: datetime, *, now: Optional[datetime] = None) -> str:
    ref = (now or timezone.now()).date()
    local = timezone.localtime(_aware(ts))
    day = local.date()
    if day == ref:
        return 'امروز'
    if day == ref - timedelta(days=1):
        return 'دیروز'
    return format_jalali_date(day)


def _time_label(ts: datetime) -> str:
    local = timezone.localtime(_aware(ts))
    return to_persian_digits(local.strftime('%H:%M'))


def format_next_action_schedule(deal: CRMDeal, *, now: Optional[datetime] = None) -> str:
    if not deal.next_action_at:
        return ''
    day = _relative_day_label(deal.next_action_at, now=now)
    clock = _time_label(deal.next_action_at)
    return f'{day}، {clock}'


def serialize_next_action(deal: CRMDeal, *, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    action_type = (deal.next_action_type or '').strip()
    if not action_type and not deal.next_action_at:
        return None
    ref = now or timezone.now()
    overdue = is_next_action_overdue(deal, now=ref)
    label = DEAL_NEXT_ACTION_LABELS.get(action_type, action_type or 'سایر')
    schedule = format_next_action_schedule(deal, now=ref) if deal.next_action_at else ''
    at_input = format_jalali_datetime(deal.next_action_at) if deal.next_action_at else ''
    return {
        'type': action_type or DEAL_ACTION_OTHER,
        'label': label,
        'at': deal.next_action_at.isoformat() if deal.next_action_at else None,
        'at_input': at_input,
        'note': deal.next_action_note or '',
        'is_overdue': overdue,
        'schedule_label': schedule,
        'icon': DEAL_ACTION_ICONS.get(action_type, 'fa-ellipsis'),
        'compact_label': _compact_next_action_label(deal, now=ref),
    }


def _compact_next_action_label(deal: CRMDeal, *, now: Optional[datetime] = None) -> str:
    if not deal.next_action_type:
        return ''
    label = DEAL_NEXT_ACTION_LABELS.get(deal.next_action_type, deal.next_action_type)
    if not deal.next_action_at:
        return label
    ref = now or timezone.now()
    if is_next_action_overdue(deal, now=ref):
        days = max(1, (ref.date() - timezone.localtime(_aware(deal.next_action_at)).date()).days)
        if days == 1:
            return 'پیگیری عقب‌افتاده — دیروز'
        return f'پیگیری عقب‌افتاده — {to_persian_digits(str(days))} روز'
    schedule = format_next_action_schedule(deal, now=ref)
    return f'{label} {schedule}'


def set_next_action(
    deal: CRMDeal,
    *,
    action_type: str = '',
    action_at: Optional[datetime] = None,
    note: str = '',
    save: bool = True,
) -> CRMDeal:
    deal.next_action_type = _normalize_action_type(action_type, allowed=DEAL_NEXT_ACTION_KEYS) if action_type else ''
    deal.next_action_at = action_at
    deal.next_action_note = (note or '')[:300]
    if save:
        deal.save(update_fields=['next_action_type', 'next_action_at', 'next_action_note', 'updated_at'])
    return deal


def clear_next_action(deal: CRMDeal, *, save: bool = True) -> CRMDeal:
    deal.next_action_type = ''
    deal.next_action_at = None
    deal.next_action_note = ''
    if save:
        deal.save(update_fields=['next_action_type', 'next_action_at', 'next_action_note', 'updated_at'])
    return deal


def create_follow_up(
    deal: CRMDeal,
    user,
    *,
    follow_up_type: str,
    note: str = '',
    next_action_type: str = '',
    next_action_at: Optional[datetime] = None,
    next_action_note: str = '',
) -> CRMDealFollowUp:
    fu_type = _normalize_action_type(follow_up_type, allowed=DEAL_FOLLOWUP_KEYS)
    follow_up = CRMDealFollowUp.objects.create(
        deal=deal,
        user=user,
        follow_up_type=fu_type,
        note=(note or '').strip(),
    )
    if next_action_type or next_action_at:
        set_next_action(
            deal,
            action_type=next_action_type,
            action_at=next_action_at,
            note=next_action_note,
            save=True,
        )
    else:
        deal.save(update_fields=['updated_at'])
    return follow_up


def complete_next_action(
    deal: CRMDeal,
    user,
    *,
    result_note: str = '',
) -> Optional[CRMDealFollowUp]:
    action_type = (deal.next_action_type or '').strip()
    if not action_type:
        return None
    note = (result_note or '').strip()
    if not note and deal.next_action_note:
        note = deal.next_action_note
    if not note:
        label = DEAL_NEXT_ACTION_LABELS.get(action_type, 'اقدام')
        note = f'{label} انجام شد.'
    follow_up = create_follow_up(
        deal,
        user,
        follow_up_type=action_type if action_type in DEAL_FOLLOWUP_KEYS else DEAL_ACTION_OTHER,
        note=note,
    )
    clear_next_action(deal, save=True)
    return follow_up


def _parse_stage_change(content: str) -> Optional[tuple[str, str]]:
    if '→' not in content:
        return None
    try:
        left, right = content.split('→', 1)
        old = left.split(':')[-1].strip()
        new = right.strip()
        return old, new
    except (IndexError, ValueError):
        return None


def _timeline_from_activity(act: CustomerActivity, deal: CRMDeal) -> Optional[Dict[str, Any]]:
    meta = act.metadata or {}
    if meta.get('deal_id') != deal.pk:
        return None
    ts = act.created_at
    if act.activity_type == 'تغییر وضعیت':
        parsed = _parse_stage_change(act.content or '')
        if parsed:
            old_stage, new_stage = parsed
            return {
                'kind': 'stage_change',
                'at': ts,
                'title': 'تغییر مرحله',
                'body': f'{old_stage} ← {new_stage}',
                'icon': 'fa-arrows-turn-right',
                'type_label': 'مرحله',
            }
    if act.activity_type == 'املاک' and meta.get('stage'):
        return {
            'kind': 'deal_created',
            'at': ts,
            'title': 'معامله ایجاد شد',
            'body': act.content or deal.title,
            'icon': 'fa-handshake',
            'type_label': 'ایجاد',
        }
    return None


def get_deal_timeline(
    deal: CRMDeal,
    *,
    limit: int = 30,
    offset: int = 0,
) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []

    events.append({
        'kind': 'deal_created',
        'at': deal.created_at,
        'title': 'معامله ایجاد شد',
        'body': deal.title,
        'icon': 'fa-handshake',
        'type_label': 'ایجاد',
    })

    for fu in deal.follow_ups.select_related('user').order_by('-created_at')[:200]:
        events.append({
            'kind': 'follow_up',
            'at': fu.created_at,
            'title': DEAL_FOLLOWUP_LABELS.get(fu.follow_up_type, fu.follow_up_type),
            'body': fu.note or '',
            'icon': DEAL_ACTION_ICONS.get(fu.follow_up_type, 'fa-comment-dots'),
            'type_label': 'پیگیری',
        })

    activities = (
        CustomerActivity.objects.filter(customer_id=deal.customer_id)
        .order_by('-created_at')[:200]
    )
    for act in activities:
        item = _timeline_from_activity(act, deal)
        if item:
            events.append(item)

    if deal.closed_at and deal.stage == DEAL_STAGE_WON:
        events.append({
            'kind': 'deal_won',
            'at': deal.closed_at,
            'title': 'معامله بسته شد',
            'body': 'معامله با موفقیت نهایی شد.',
            'icon': 'fa-trophy',
            'type_label': 'بستن',
        })
    elif deal.closed_at and deal.stage == DEAL_STAGE_LOST:
        reason = deal.lost_reason or 'از دست رفته'
        events.append({
            'kind': 'deal_lost',
            'at': deal.closed_at,
            'title': 'معامله از دست رفت',
            'body': reason,
            'icon': 'fa-circle-xmark',
            'type_label': 'بستن',
        })

    if deal.contract_date and deal.contract_number:
        contract_ts = timezone.make_aware(
            datetime.combine(deal.contract_date, datetime.min.time()),
        ) if isinstance(deal.contract_date, date) else deal.created_at
        events.append({
            'kind': 'contract',
            'at': contract_ts,
            'title': 'قرارداد ثبت شد',
            'body': f'شماره {deal.contract_number}',
            'icon': 'fa-file-contract',
            'type_label': 'قرارداد',
        })

    dedup: dict = {}
    for ev in events:
        key = (ev['kind'], ev['at'], ev.get('title', ''), ev.get('body', ''))
        dedup[key] = ev
    merged = sorted(dedup.values(), key=lambda x: x['at'], reverse=True)

    total = len(merged)
    page = merged[offset:offset + limit]
    return {
        'items': [serialize_timeline_item(ev) for ev in page],
        'total': total,
        'limit': limit,
        'offset': offset,
        'has_more': offset + limit < total,
    }


def serialize_timeline_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    ts = raw['at']
    if not isinstance(ts, datetime):
        ts = timezone.now()
    local = timezone.localtime(_aware(ts))
    return {
        'kind': raw['kind'],
        'at': ts.isoformat(),
        'day_label': _relative_day_label(ts),
        'time_label': _time_label(ts),
        'datetime_label': format_jalali_datetime(ts),
        'title': raw.get('title') or '',
        'body': raw.get('body') or '',
        'icon': raw.get('icon') or 'fa-circle',
        'type_label': raw.get('type_label') or '',
    }


def last_follow_up_summary(deal: CRMDeal) -> Optional[Dict[str, Any]]:
    fu = deal.follow_ups.order_by('-created_at').first()
    if not fu:
        return None
    return {
        'type': fu.follow_up_type,
        'label': DEAL_FOLLOWUP_LABELS.get(fu.follow_up_type, fu.follow_up_type),
        'note': fu.note or '',
        'at': fu.created_at.isoformat() if fu.created_at else None,
    }


def _follow_up_next_action_payload(payload: dict) -> dict:
    """Extract optional next-action fields from a follow-up request."""
    nested = payload.get('next_action')
    if isinstance(nested, dict):
        return nested
    return {
        key: payload.get(key)
        for key in ('next_action_type', 'next_action_at', 'next_action_note', 'clear', 'clear_next_action')
        if key in payload
    }


def parse_next_action_payload(payload: dict) -> Dict[str, Any]:
    """Parse next-action fields from dedicated or follow-up payloads."""
    if not payload:
        return {'action_type': '', 'action_at': None, 'note': '', 'clear': False}

    has_follow_up_next_fields = any(
        key in payload for key in ('next_action_type', 'next_action_at', 'next_action_note')
    )
    if has_follow_up_next_fields:
        action_type = (payload.get('next_action_type') or '').strip()
        note = (payload.get('next_action_note') or '').strip()
        action_at = payload.get('next_action_at')
    else:
        action_type = (payload.get('type') or payload.get('action_type') or '').strip()
        note = (payload.get('note') or '').strip()
        action_at = payload.get('at') or payload.get('next_action_at')
    parsed_at = None
    if action_at:
        if isinstance(action_at, datetime):
            parsed_at = _aware(action_at)
        elif isinstance(action_at, str) and action_at.strip():
            from workspace.services.jalali_input import parse_jalali_datetime_string
            parsed_at = parse_jalali_datetime_string(action_at.strip())
            if parsed_at is None:
                try:
                    parsed_at = datetime.fromisoformat(action_at.replace('Z', '+00:00'))
                    parsed_at = _aware(parsed_at)
                except ValueError:
                    parsed_at = None
    clear = payload.get('clear') is True or payload.get('clear_next_action') is True
    return {
        'action_type': action_type,
        'action_at': parsed_at,
        'note': note,
        'clear': clear,
    }
