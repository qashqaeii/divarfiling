"""اعلان خودکار تطبیق مخاطب با املاک — فایل شخصی و فایلینگ دیوار."""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from django.contrib.auth import get_user_model
from django.db import close_old_connections, transaction
from django.utils import timezone

from workspace.constants import LEAD_TYPES
from workspace.models import Customer, PropertyMatchAlert
from workspace.services.crm_matching import MATCH_TYPES, compute_match_total_count, get_customer_matches

logger = logging.getLogger(__name__)

MATCH_ELIGIBLE_TYPES = MATCH_TYPES | LEAD_TYPES
AUTO_NOTIFY_MIN_SCORE = 55
AUTO_NOTIFY_MAX_PER_USER = 8
AUTO_NOTIFY_MAX_PER_CUSTOMER = 1
POST_EXTRACT_MAX_CUSTOMERS = 60


def is_match_eligible(customer: Customer) -> bool:
    from workspace.services.crm_contact_archive import is_contact_archived

    if is_contact_archived(customer):
        return False
    return customer.customer_type in MATCH_ELIGIBLE_TYPES


def _match_snapshot_for_alert(user, match: Dict[str, Any]) -> Dict[str, Any]:
    from workspace.services.crm_matching_access import match_alert_snapshot_for_viewer

    return match_alert_snapshot_for_viewer(user, match)


def _match_key(match: Dict[str, Any]) -> str:
    if match.get('source') == 'crm':
        return f'crm:{match.get("property_id")}'
    return f'divar:{match.get("token")}'


def _existing_keys(user, customer: Customer) -> Set[str]:
    return set(
        PropertyMatchAlert.objects.filter(
            user=user,
            customer=customer,
        ).values_list('match_key', flat=True)
    )


def _already_suggested_keys(customer: Customer) -> Set[str]:
    keys: Set[str] = set()
    for link in customer.property_links.filter(role='پیشنهادی').select_related('property'):
        if link.property_id:
            keys.add(f'crm:{link.property_id}')
    for listing in customer.linked_listings.filter(role='پیشنهادی'):
        if listing.token:
            keys.add(f'divar:{listing.token}')
    return keys


def filter_new_matches(
    customer: Customer,
    user,
    matches: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """ملک‌هایی که هنوز اعلان/پیشنهاد نشده‌اند."""
    skip = _existing_keys(user, customer) | _already_suggested_keys(customer)
    fresh = []
    for m in matches:
        key = _match_key(m)
        if key in skip:
            continue
        fresh.append({**m, 'match_key': key})
    return fresh


def record_match_alerts(
    user,
    customer: Customer,
    matches: List[Dict[str, Any]],
    *,
    status: str = PropertyMatchAlert.STATUS_PENDING,
    notified_at=None,
) -> List[PropertyMatchAlert]:
    created: List[PropertyMatchAlert] = []
    for m in matches:
        key = m.get('match_key') or _match_key(m)
        if PropertyMatchAlert.objects.filter(
            user=user,
            customer=customer,
            match_key=key,
            status=PropertyMatchAlert.STATUS_DISMISSED,
        ).exists():
            continue
        alert, was_created = PropertyMatchAlert.objects.get_or_create(
            user=user,
            customer=customer,
            match_key=key,
            defaults={
                'source': m.get('source', 'crm'),
                'crm_property_id': m.get('property_id') if m.get('source') == 'crm' else None,
                'listing_token': (m.get('token') or '') if m.get('source') == 'divar' else '',
                'score': int(m.get('score') or 0),
                'match_snapshot': _match_snapshot_for_alert(user, m),
                'status': status,
                'notified_at': notified_at,
            },
        )
        if was_created:
            created.append(alert)
    return created


def discover_customer_matches(
    customer: Customer,
    user,
    *,
    divar_enabled: bool,
    min_score: int = AUTO_NOTIFY_MIN_SCORE,
    dataset_id: str = '',
) -> List[Dict[str, Any]]:
    if not is_match_eligible(customer):
        return []
    from workspace.services.crm_contact_archive import is_contact_archived

    if is_contact_archived(customer):
        return []
    data = get_customer_matches(
        customer,
        user,
        divar_enabled=divar_enabled,
        dataset_id=dataset_id or None,
        paginate=False,
    )
    if not data.get('eligible'):
        return []
    all_matches = list(data.get('crm_matches', [])) + list(data.get('divar_matches', []))
    strong = [m for m in all_matches if int(m.get('score') or 0) >= min_score]
    strong.sort(key=lambda x: int(x.get('score') or 0), reverse=True)
    return filter_new_matches(customer, user, strong)


def _notify_customer_matches(
    user,
    customer: Customer,
    matches: List[Dict[str, Any]],
    *,
    send_push: bool = True,
) -> bool:
    from mobile_api.services.notification_copy import customer_match as copy_customer_match
    from mobile_api.services.notification_service import create_notification

    if not matches:
        return False
    top = matches[0]
    title, body = copy_customer_match(
        customer.name,
        top.get('title') or 'ملک',
        count=len(matches),
    )
    now = timezone.now()
    record_match_alerts(
        user, customer, matches,
        status=PropertyMatchAlert.STATUS_NOTIFIED,
        notified_at=now,
    )
    create_notification(
        user,
        notification_type='customer_match',
        title=title,
        body=body,
        deep_link=f'divarfiling://crm/contacts/{customer.pk}/matches',
        data={
            'contact_id': customer.pk,
            'contact_name': customer.name,
            'match_count': len(matches),
            'top_score': top.get('score'),
            'top_title': top.get('title', ''),
            'source': top.get('source', ''),
            'digest': False,
            'day': timezone.localdate().isoformat(),
        },
        send_push=send_push,
    )
    return True


def _notify_customer_match_digest(
    user,
    batch: List[Tuple[Customer, List[Dict[str, Any]]]],
    *,
    send_push: bool = True,
) -> bool:
    from mobile_api.services.notification_copy import customer_match_digest
    from mobile_api.services.notification_service import create_notification

    if not batch:
        return False
    now = timezone.now()
    contacts_summary: List[Tuple[str, int]] = []
    total_matches = 0
    contact_ids: List[int] = []
    for customer, matches in batch:
        record_match_alerts(
            user, customer, matches,
            status=PropertyMatchAlert.STATUS_NOTIFIED,
            notified_at=now,
        )
        contacts_summary.append((customer.name, len(matches)))
        total_matches += len(matches)
        contact_ids.append(customer.pk)

    title, body = customer_match_digest(contacts_summary, total_matches=total_matches)
    top_customer, top_matches = batch[0]
    top = top_matches[0] if top_matches else {}
    create_notification(
        user,
        notification_type='customer_match',
        title=title,
        body=body,
        deep_link=f'divarfiling://crm/contacts/{top_customer.pk}/matches',
        data={
            'digest': True,
            'contact_count': len(batch),
            'contact_ids': contact_ids,
            'match_count': total_matches,
            'top_contact_id': top_customer.pk,
            'top_contact_name': top_customer.name,
            'top_score': top.get('score'),
            'top_title': top.get('title', ''),
            'contact_id': top_customer.pk,
            'day': timezone.localdate().isoformat(),
        },
        send_push=send_push,
    )
    return True


def process_user_customer_matches(
    user,
    *,
    divar_enabled: bool,
    dataset_id: str = '',
    max_customers: int = 200,
) -> int:
    from mobile_api.services.notification_scheduler import user_push_enabled

    if not user_push_enabled(user, 'customer_match'):
        return 0

    from workspace.services.crm_contact_archive import archived_contacts_q

    batch: List[Tuple[Customer, List[Dict[str, Any]]]] = []
    customers = (
        Customer.objects.filter(user=user)
        .exclude(archived_contacts_q())
        .filter(customer_type__in=MATCH_ELIGIBLE_TYPES)
        .order_by('-updated_at')[:max_customers]
    )
    for customer in customers:
        if len(batch) >= AUTO_NOTIFY_MAX_PER_USER:
            break
        matches = discover_customer_matches(
            customer,
            user,
            divar_enabled=divar_enabled,
            dataset_id=dataset_id,
        )
        if not matches:
            continue
        batch.append((customer, matches[:3]))
    if not batch:
        return 0

    push_enabled = user_push_enabled(user, 'customer_match')
    if len(batch) == 1:
        customer, matches = batch[0]
        if _notify_customer_matches(user, customer, matches, send_push=push_enabled):
            return 1
        return 0

    if _notify_customer_match_digest(user, batch, send_push=push_enabled):
        return len(batch)
    return 0


def process_customer_matches(*, match_hour: int = 2) -> int:
    """اسکن شبانه مخاطبین و ارسال اعلان تطبیق — یک‌بار در ساعت match_hour."""
    from django.contrib.auth import get_user_model

    from mobile_api.services.notification_scheduler import _users_with_mobile_devices
    from workspace.services.access import has_active_bot_license

    now = timezone.localtime(timezone.now())
    if now.hour != match_hour:
        return 0

    User = get_user_model()
    sent = 0
    for user_id in _users_with_mobile_devices().values_list('pk', flat=True):
        user = User.objects.filter(pk=user_id, is_active=True).first()
        if not user:
            continue
        divar_enabled = has_active_bot_license(user)
        sent += process_user_customer_matches(user, divar_enabled=divar_enabled)
    return sent


def notify_matches_after_extract(user, *, dataset_id: str = '') -> int:
    """پس از استخراج/آپلود فایلینگ — بررسی فوری تطبیق‌ها."""
    from workspace.services.access import has_active_bot_license

    return process_user_customer_matches(
        user,
        divar_enabled=has_active_bot_license(user),
        dataset_id=dataset_id,
        max_customers=POST_EXTRACT_MAX_CUSTOMERS,
    )


def _post_extract_match_cache_key(user_id: int, dataset_id: str = '') -> str:
    return f'crm:post-extract-match:{user_id}:{dataset_id or "all"}'


def _run_post_extract_matching(user_id: int, dataset_id: str = '') -> None:
    from django.core.cache import cache

    close_old_connections()
    lock_key = _post_extract_match_cache_key(user_id, dataset_id)
    if not cache.add(lock_key, '1', timeout=900):
        logger.info('skip duplicate post-extract matching key=%s', lock_key)
        return
    try:
        User = get_user_model()
        user = User.objects.filter(pk=user_id, is_active=True).first()
        if not user:
            return
        notify_matches_after_extract(user, dataset_id=dataset_id)
    except Exception:
        logger.exception('post-extract customer matching failed user=%s dataset=%s', user_id, dataset_id)
    finally:
        cache.delete(lock_key)
        close_old_connections()


def schedule_notify_matches_after_extract(user, *, dataset_id: str = '') -> None:
    """اجرای تطبیق پس از استخراج در پس‌زمینه تا آپلود موبایل timeout نشود."""
    user_id = user.pk
    ds_id = str(dataset_id or '')

    def _start() -> None:
        thread = threading.Thread(
            target=_run_post_extract_matching,
            args=(user_id, ds_id),
            daemon=True,
            name=f'post-extract-match-{user_id}',
        )
        thread.start()

    transaction.on_commit(_start)


def contact_matches_payload(user, contact_id: int, request=None) -> Optional[Dict[str, Any]]:
    from workspace.services.access import has_active_bot_license
    from workspace.services.crm_scope import customer_for_user
    from workspace.services.property_suggestion_share import enrich_match_data_links

    customer = customer_for_user(user, contact_id)
    if not customer:
        return None
    divar_enabled = has_active_bot_license(user)
    page = 1
    page_size = None
    if request is not None:
        try:
            page = max(1, int(request.GET.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        raw_size = request.GET.get('page_size')
        if raw_size:
            try:
                page_size = max(1, min(100, int(raw_size)))
            except (TypeError, ValueError):
                page_size = None
    data = get_customer_matches(
        customer,
        user,
        divar_enabled=divar_enabled,
        page=page,
        page_size=page_size,
    )
    data = enrich_match_data_links(user, request, data)
    crm_matches = data.get('crm_matches', [])
    divar_matches = data.get('divar_matches', [])
    if 'total_count' in data:
        total_count = int(data['total_count'])
    else:
        total_count = compute_match_total_count({
            **data,
            'crm_matches': crm_matches,
            'divar_matches': divar_matches,
        })
    return {
        'eligible': bool(data.get('eligible')),
        'is_builder': bool(data.get('is_builder')),
        'message': data.get('message', ''),
        'divar_locked': bool(data.get('divar_locked')),
        'match_groups': data.get('match_groups', []),
        'crm_matches': crm_matches,
        'divar_matches': divar_matches,
        'total_count': total_count,
        'crm_total_count': int(data.get('crm_total_count') or len(crm_matches)),
        'divar_total_count': int(data.get('divar_total_count') or len(divar_matches)),
        'match_page': int(data.get('match_page') or 1),
        'match_page_size': int(data.get('match_page_size') or 0),
        'crm_has_more': bool(data.get('crm_has_more')),
        'divar_has_more': bool(data.get('divar_has_more')),
        'matching_tolerance_percent': data.get('matching_tolerance_percent', 20),
        'customer': {
            'id': customer.pk,
            'full_name': customer.name,
            'customer_type': customer.customer_type,
        },
    }


def suggest_contact_matches(
    user,
    contact_id: int,
    selected: List[Dict[str, Any]],
    *,
    note: str = '',
    request=None,
) -> Tuple[Optional[str], int]:
    from workspace.services.crm import apply_property_suggestions
    from workspace.services.crm_scope import customer_for_user

    customer = customer_for_user(user, contact_id)
    if not customer:
        return None, 0
    if not selected:
        raise ValueError('حداقل یک ملک انتخاب کنید.')
    from workspace.services.access import has_active_bot_license
    if not has_active_bot_license(user):
        selected = [m for m in selected if m.get('source') != 'divar']
    if not selected:
        raise ValueError('تطبیق فایلینگ دیوار نیاز به لایسنس فعال دارد.')
    divar_enabled = has_active_bot_license(user)
    text, linked = apply_property_suggestions(
        customer, user, selected, note=note, request=request, divar_enabled=divar_enabled,
    )
    now = timezone.now()
    for m in selected:
        key = _match_key(m)
        PropertyMatchAlert.objects.update_or_create(
            user=user,
            customer=customer,
            match_key=key,
            defaults={
                'source': m.get('source', 'crm'),
                'crm_property_id': m.get('property_id') if m.get('source') == 'crm' else None,
                'listing_token': (m.get('token') or '') if m.get('source') == 'divar' else '',
                'score': int(m.get('score') or 0),
                'match_snapshot': {
                    'title': m.get('title', ''),
                    'price_label': m.get('price_label', ''),
                },
                'status': PropertyMatchAlert.STATUS_SUGGESTED,
                'notified_at': now,
            },
        )
    return text, linked


def property_contact_matches_payload(user, property_id: int, request=None) -> Optional[Dict[str, Any]]:
    from django.urls import reverse

    from workspace.services.crm_matching import get_property_contact_matches
    from workspace.services.crm_property_share import build_property_share_context
    from workspace.services.crm_scope import can_edit_property, property_for_user

    prop = property_for_user(user, property_id)
    if not prop:
        return None
    share_ctx = build_property_share_context(user, prop)
    if share_ctx.mask_sensitive or not can_edit_property(user, prop):
        return {
            'eligible': False,
            'forbidden': True,
            'message': 'دسترسی به پیشنهاد مخاطب برای این فایل مجاز نیست.',
            'matches': [],
            'total_count': 0,
            'property': {
                'id': prop.pk,
                'title': prop.title or '',
                'deal_mode': prop.deal_mode or '',
            },
        }
    data = get_property_contact_matches(prop, user)
    matches = []
    for m in data.get('matches') or []:
        item = dict(m)
        try:
            item['internal_url'] = reverse(
                'workspace:crm_detail', kwargs={'customer_id': item['customer_id']},
            )
        except Exception:
            item['internal_url'] = ''
        matches.append(item)
    return {
        'eligible': bool(data.get('eligible')),
        'forbidden': False,
        'message': data.get('message', ''),
        'matches': matches,
        'total_count': int(data.get('total_count') or 0),
        'deal_mode': data.get('deal_mode', ''),
        'deal_label': data.get('deal_label', ''),
        'is_sale': bool(data.get('is_sale')),
        'is_rent': bool(data.get('is_rent')),
        'property': {
            'id': prop.pk,
            'title': prop.title or '',
            'deal_mode': prop.deal_mode or '',
            'neighborhood': prop.neighborhood or prop.district or '',
            'area': prop.area,
            'property_type': prop.property_type or '',
        },
    }


def suggest_property_contacts(
    user,
    property_id: int,
    customer_ids: List[Any],
    *,
    note: str = '',
    request=None,
) -> Dict[str, Any]:
    from workspace.services.crm import apply_contact_suggestions
    from workspace.services.crm_property_share import build_property_share_context
    from workspace.services.crm_scope import can_edit_property, property_for_user

    prop = property_for_user(user, property_id)
    if not prop:
        raise ValueError('ملک یافت نشد.')
    share_ctx = build_property_share_context(user, prop)
    if share_ctx.mask_sensitive:
        raise ValueError('در اشتراک محرمانه امکان پیشنهاد مخاطب وجود ندارد.')
    if not can_edit_property(user, prop):
        raise ValueError('امکان پیشنهاد مخاطب برای این فایل را ندارید.')
    if not customer_ids:
        raise ValueError('حداقل یک مخاطب انتخاب کنید.')
    return apply_contact_suggestions(
        prop, user, customer_ids, note=note, request=request,
    )
