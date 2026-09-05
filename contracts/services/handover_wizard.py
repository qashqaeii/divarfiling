"""زمینه و خلاصه UI ویزارد صورت‌جلسه تحویل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.utils import timezone

from contracts.constants import (
    HANDOVER_COMMON_EQUIPMENT,
    HANDOVER_CONDITION_ITEMS,
    HANDOVER_CONDITION_STATUSES,
    HANDOVER_DELIVERER_ROLES,
    HANDOVER_KEY_TYPES,
    HANDOVER_METER_UTILITIES,
    HANDOVER_RECEIVER_ROLES,
    HANDOVER_WIZARD_STEPS,
)
from workspace.services.jalali_input import format_jalali_date, to_persian_digits

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

STATUS_LABELS = dict(HANDOVER_CONDITION_STATUSES)
STEP_LABELS = dict(HANDOVER_WIZARD_STEPS)
VALID_STEPS = {key for key, _ in HANDOVER_WIZARD_STEPS}

KEY_ICONS = {
    'کلید درب اصلی': 'fa-door-closed',
    'کلید واحد': 'fa-key',
    'کلید انباری': 'fa-box-archive',
    'کلید پارکینگ': 'fa-square-parking',
    'ریموت پارکینگ': 'fa-wifi',
    'کارت ورود': 'fa-id-card',
    'سایر': 'fa-ellipsis',
}

CONDITION_ICONS = {
    'دیوارها': 'fa-border-all',
    'کف': 'fa-grip',
    'سقف': 'fa-house',
    'درب‌ها': 'fa-door-open',
    'پنجره‌ها': 'fa-window-maximize',
    'کابینت': 'fa-kitchen-set',
    'شیرآلات': 'fa-faucet',
    'سرویس بهداشتی': 'fa-bath',
    'پکیج': 'fa-temperature-high',
    'رادیاتور': 'fa-fire',
    'کولر': 'fa-snowflake',
    'آیفون': 'fa-phone',
    'برق': 'fa-bolt',
    'روشنایی': 'fa-lightbulb',
}


def _party_name(party: Optional[dict]) -> str:
    if not party:
        return ''
    return f'{party.get("first_name") or ""} {party.get("last_name") or ""}'.strip()


def _party_key(party: Optional[dict]) -> tuple:
    party = party or {}
    return (
        (party.get('national_id') or '').strip(),
        (party.get('mobile') or '').strip(),
        _party_name(party),
    )


def _find_party_idx(parties: List[dict], selected: Optional[dict]) -> Optional[int]:
    if not selected:
        return None
    selected_key = _party_key(selected)
    if any(selected_key):
        for idx, party in enumerate(parties):
            if _party_key(party) == selected_key:
                return idx
    name = _party_name(selected)
    if name:
        for idx, party in enumerate(parties):
            if _party_name(party) == name:
                return idx
    return None


def _first_role_idx(parties: List[dict], roles: tuple) -> Optional[int]:
    for idx, party in enumerate(parties):
        if (party.get('role') or '') in roles:
            return idx
    return 0 if parties else None


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip() or default)
    except (TypeError, ValueError):
        return default


def _normalize_step(step: str) -> str:
    return step if step in VALID_STEPS else 'basic'


def build_handover_wizard_context(handover, *, step: str) -> Dict[str, Any]:
    step = _normalize_step(step)
    snap = handover.snapshot_json or {}
    parties = list(snap.get('parties') or [])
    property_data = snap.get('property') or {}
    delivered = snap.get('delivered_by') or {}
    received = snap.get('received_by') or {}

    delivered_idx = _find_party_idx(parties, delivered)
    received_idx = _find_party_idx(parties, received)
    if delivered_idx is None:
        delivered_idx = _first_role_idx(parties, HANDOVER_DELIVERER_ROLES)
    if received_idx is None:
        received_idx = _first_role_idx(parties, HANDOVER_RECEIVER_ROLES)
        if received_idx is not None and received_idx == delivered_idx and len(parties) > 1:
            received_idx = next((i for i in range(len(parties)) if i != delivered_idx), received_idx)

    party_cards = []
    for idx, party in enumerate(parties):
        party_cards.append({
            'index': idx,
            'first_name': party.get('first_name') or '',
            'last_name': party.get('last_name') or '',
            'name': _party_name(party) or 'بدون نام',
            'role': party.get('role') or '',
            'role_label': ROLE_LABELS.get(party.get('role') or '', party.get('role') or ''),
            'mobile': party.get('mobile') or '',
            'national_id': party.get('national_id') or '',
            'is_delivered': idx == delivered_idx,
            'is_received': idx == received_idx,
        })

    saved_keys = {item.get('type'): item for item in (snap.get('keys') or []) if item.get('type')}
    key_rows = []
    used_types = set()
    for idx, key_type in enumerate(HANDOVER_KEY_TYPES):
        saved = saved_keys.get(key_type) or {}
        used_types.add(key_type)
        key_rows.append({
            'index': idx,
            'type': key_type,
            'count': _safe_int(saved.get('count'), 0),
            'notes': saved.get('notes') or '',
            'icon': KEY_ICONS.get(key_type, 'fa-key'),
            'is_custom': False,
        })
    extra_idx = len(key_rows)
    for item in snap.get('keys') or []:
        key_type = item.get('type') or ''
        if not key_type or key_type in used_types:
            continue
        key_rows.append({
            'index': extra_idx,
            'type': key_type,
            'count': _safe_int(item.get('count'), 0),
            'notes': item.get('notes') or '',
            'icon': 'fa-key',
            'is_custom': True,
        })
        extra_idx += 1

    saved_meters = {item.get('utility'): item for item in (snap.get('meters') or [])}
    meter_rows = []
    for util, label, icon, unit in HANDOVER_METER_UTILITIES:
        saved = saved_meters.get(util) or {}
        meter_rows.append({
            'utility': util,
            'label': label,
            'icon': icon,
            'unit': unit,
            'meter_number': saved.get('meter_number') or '',
            'reading': saved.get('reading') or '',
            'notes': saved.get('notes') or '',
        })

    saved_conditions = {item.get('item'): item for item in (snap.get('conditions') or [])}
    condition_rows = []
    for name in HANDOVER_CONDITION_ITEMS:
        saved = saved_conditions.get(name) or {}
        status = saved.get('status') or 'unchecked'
        condition_rows.append({
            'item': name,
            'status': status,
            'status_label': STATUS_LABELS.get(status, status),
            'note': saved.get('note') or '',
            'icon': CONDITION_ICONS.get(name, 'fa-circle-check'),
        })

    equipment_rows = []
    for idx, item in enumerate(snap.get('equipment') or []):
        if not (item.get('name') or '').strip():
            continue
        status = item.get('status') or 'ok'
        equipment_rows.append({
            'index': idx,
            'name': item.get('name') or '',
            'count': item.get('count') or '1',
            'status': status,
            'status_label': STATUS_LABELS.get(status, status),
            'notes': item.get('notes') or '',
        })
    if not equipment_rows:
        equipment_rows = [{
            'index': 0, 'name': '', 'count': '1', 'status': 'ok',
            'status_label': STATUS_LABELS['ok'], 'notes': '',
        }]

    step_keys = [key for key, _ in HANDOVER_WIZARD_STEPS]
    step_number = step_keys.index(step) + 1
    step_total = len(step_keys)
    prev_step = step_keys[step_number - 2] if step_number > 1 else ''
    next_step = step_keys[step_number] if step_number < step_total else ''

    date_saved = format_jalali_date(handover.handover_date) if handover.handover_date else ''
    time_saved = handover.handover_time.strftime('%H:%M') if handover.handover_time else ''
    date_display = date_saved or format_jalali_date(timezone.localdate())
    time_display = time_saved or timezone.localtime().strftime('%H:%M')

    photos = list(handover.attachments.filter(attachment_type='property_photo').order_by('created_at'))
    review = _build_review(
        handover=handover,
        snap=snap,
        property_data=property_data,
        party_cards=party_cards,
        key_rows=key_rows,
        meter_rows=meter_rows,
        condition_rows=condition_rows,
        equipment_rows=equipment_rows,
        photos=photos,
        date_display=date_saved,
        time_display=time_saved,
    )

    return {
        'handover_step': step,
        'display_steps': HANDOVER_WIZARD_STEPS,
        'step_number': step_number,
        'step_total': step_total,
        'prev_step': prev_step,
        'next_step': next_step,
        'next_step_label': STEP_LABELS.get(next_step, ''),
        'prev_step_label': STEP_LABELS.get(prev_step, ''),
        'snapshot': snap,
        'property_data': property_data,
        'party_cards': party_cards,
        'delivered_idx': delivered_idx if delivered_idx is not None else '',
        'received_idx': received_idx if received_idx is not None else '',
        'key_rows': key_rows,
        'next_key_index': extra_idx,
        'meter_rows': meter_rows,
        'condition_rows': condition_rows,
        'condition_statuses': HANDOVER_CONDITION_STATUSES,
        'equipment_rows': equipment_rows,
        'common_equipment': HANDOVER_COMMON_EQUIPMENT,
        'photos': photos,
        'handover_date_display': date_display,
        'handover_time_display': time_display,
        'notes_value': handover.notes or '',
        'review': review,
        'progress_pct': int(round((step_number / step_total) * 100)),
    }


def _build_review(
    *,
    handover,
    snap,
    property_data,
    party_cards,
    key_rows,
    meter_rows,
    condition_rows,
    equipment_rows,
    photos,
    date_display,
    time_display,
) -> Dict[str, Any]:
    delivered = next((p for p in party_cards if p['is_delivered']), None)
    received = next((p for p in party_cards if p['is_received']), None)
    keys_present = [row for row in key_rows if row['count'] > 0]
    meters_present = [row for row in meter_rows if row['reading'] or row['meter_number']]
    conditions_checked = [row for row in condition_rows if row['status'] != 'unchecked']
    equipment_present = [row for row in equipment_rows if (row.get('name') or '').strip()]
    issues = []

    if not delivered or delivered['name'] == 'بدون نام':
        issues.append({
            'severity': 'block',
            'message': 'تحویل‌دهنده مشخص نشده است.',
            'edit_step': 'basic',
            'edit_label': 'مشخصات',
        })
    if not received or received['name'] == 'بدون نام':
        issues.append({
            'severity': 'block',
            'message': 'تحویل‌گیرنده مشخص نشده است.',
            'edit_step': 'basic',
            'edit_label': 'مشخصات',
        })
    if delivered and received and delivered['index'] == received['index']:
        issues.append({
            'severity': 'warn',
            'message': 'تحویل‌دهنده و تحویل‌گیرنده یک نفر هستند.',
            'edit_step': 'basic',
            'edit_label': 'مشخصات',
        })
    if not handover.handover_date:
        issues.append({
            'severity': 'warn',
            'message': 'تاریخ تحویل هنوز ذخیره نشده است.',
            'edit_step': 'basic',
            'edit_label': 'مشخصات',
        })
    if not keys_present:
        issues.append({
            'severity': 'warn',
            'message': 'هیچ کلیدی ثبت نشده است.',
            'edit_step': 'keys',
            'edit_label': 'کلیدها',
        })
    if not meters_present:
        issues.append({
            'severity': 'warn',
            'message': 'قرائت کنتورها خالی است.',
            'edit_step': 'meters',
            'edit_label': 'کنتورها',
        })
    unchecked_count = len(condition_rows) - len(conditions_checked)
    if unchecked_count:
        issues.append({
            'severity': 'warn',
            'message': f'{to_persian_digits(unchecked_count)} مورد از وضعیت ملک بررسی نشده است.',
            'edit_step': 'conditions',
            'edit_label': 'وضعیت ملک',
        })

    blocking = [item for item in issues if item['severity'] == 'block']
    if blocking:
        readiness, message, detail = 'blocked', 'صورت‌جلسه هنوز ناقص است', 'قبل از ارسال، موارد الزامی را تکمیل کنید.'
    elif issues:
        readiness, message, detail = 'warning', 'آماده ارسال — چند مورد اختیاری مانده', 'می‌توانید ارسال کنید؛ موارد هشدار را در صورت نیاز تکمیل کنید.'
    else:
        readiness, message, detail = 'ready', 'صورت‌جلسه آماده ارسال است', 'پس از ارسال، طرفین با پیامک و کد تأیید صورت‌جلسه را امضا می‌کنند.'

    condition_counts = {'ok': 0, 'minor': 0, 'repair': 0, 'damaged': 0, 'unchecked': 0}
    for row in condition_rows:
        condition_counts[row['status']] = condition_counts.get(row['status'], 0) + 1

    completeness = [
        {'label': 'تاریخ و طرفین', 'value': 'تکمیل' if not blocking else 'ناقص', 'status': 'ok' if not blocking else 'warn'},
        {'label': 'کلیدها', 'value': f'{to_persian_digits(len(keys_present))} مورد', 'status': 'ok' if keys_present else 'warn'},
        {'label': 'کنتورها', 'value': f'{to_persian_digits(len(meters_present))} مورد', 'status': 'ok' if meters_present else 'warn'},
        {'label': 'وضعیت ملک', 'value': f'{to_persian_digits(len(conditions_checked))} از {to_persian_digits(len(condition_rows))}', 'status': 'ok' if not unchecked_count else 'warn'},
        {'label': 'تجهیزات', 'value': f'{to_persian_digits(len(equipment_present))} مورد', 'status': 'ok' if equipment_present else 'neutral'},
        {'label': 'تصاویر', 'value': f'{to_persian_digits(len(photos))} عکس', 'status': 'ok' if photos else 'neutral'},
    ]

    return {
        'readiness': readiness,
        'readiness_message': message,
        'readiness_detail': detail,
        'issues': issues,
        'blocking_count': len(blocking),
        'send_disabled': bool(blocking),
        'completeness': completeness,
        'delivered': delivered,
        'received': received,
        'keys': keys_present,
        'meters': meters_present,
        'conditions': condition_rows,
        'condition_counts': condition_counts,
        'equipment': equipment_present,
        'photos': photos,
        'property': property_data,
        'notes': handover.notes or '',
        'date_display': date_display,
        'time_display': time_display,
        'status_label': handover.get_status_display(),
    }
