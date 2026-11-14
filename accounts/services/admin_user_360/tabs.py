"""بارگذاری داده هر تب پرونده ۳۶۰."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from django.db.models import Count, Prefetch, Q, Sum
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    GrowthJourneyEvent,
    MarketingCampaignRecipient,
    RecoveryAttribution,
    SmsMessageLog,
    UserDiscountIssuance,
)
from accounts.services.admin_user_360.common import (
    TAB_LABELS,
    _jalali,
    fa_digits,
    license_campaign_key_label,
    mask_national_id,
    sms_purpose_label,
    normalize_phone,
    paginate_qs,
    resolve_panel_activity_days,
    resolve_timeline_days_filter,
    safe_profile,
    safe_query_int,
)
from accounts.services.admin_user_360.support_tickets import support_form_options
from accounts.services.admin_user_360.charts import (
    chart_audit_action_counts,
    chart_audit_log_daily,
    chart_crm_status_breakdown,
    chart_feature_usage,
    chart_license_status_counts,
    chart_orders_by_status,
    chart_paid_revenue_monthly,
    chart_ticket_status,
)
from accounts.services.admin_user_360.insights import build_customer_insights
from accounts.services.growth_journey import growth_journey_event_label
from accounts.services.sms.log_preview import (
    resolve_sms_log_preview,
    resolve_sms_message_body,
    sms_log_detail_lines,
)
from accounts.services.admin_user_360.timeline import build_activity_timeline, daily_activity_counts
from accounts.services.admin_users_management import (
    LICENSE_STATUS_LABELS,
    ORDER_STATUS_LABELS,
    get_user_management_detail,
)
from licenses.models import AuditLog, License, LicenseActivation, LicenseCampaignGrant
from mobile_api.models import (
    MobileCloudExtractionJob,
    MobileDevice,
    MobileExtractionRun,
    MobileSyncOperation,
)
from shop.models import CardTransferSubmission, Order, Transaction
from shop.templatetags.persian_tags import transaction_status_fa
from workspace.models import (
    AgencySubscription,
    CRMAgency,
    CRMAgencyMember,
    CRMDeal,
    Customer,
    Dataset,
    Reminder,
    Ticket,
    TicketMessage,
    UserListingActivity,
)

def tab_overview(user, summary: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    detail = get_user_management_detail(user.id) or summary
    insights = build_customer_insights(user, detail)
    activity_span = resolve_panel_activity_days(kwargs.get('days'))
    activity_series = daily_activity_counts(user, days=activity_span)
    tickets_open = Ticket.objects.filter(user=user).exclude(status='closed').count()
    last_order = Order.objects.filter(user=user, status='paid').order_by('-paid_at').first()
    last_ticket = Ticket.objects.filter(user=user).order_by('-created_at').first()
    usage = detail.get('usage') or {}
    win = detail.get('windows') or {}
    android = detail.get('android') or {}
    return {
        'tab': 'overview',
        'label': TAB_LABELS['overview'],
        'insights': insights,
        'highlights': {
            'subscription': {
                'has_access': detail.get('has_active_license'),
                'plan': detail.get('license_plan'),
                'expires_jalali': detail.get('license_expires_jalali'),
                'access_label': detail.get('license_access_label'),
                'pending_activation': bool(detail.get('has_pending_bot_activation')),
            },
            'payments': {
                'total_paid': int(detail.get('total_spent') or 0),
                'paid_orders': int(detail.get('paid_orders_count') or 0),
                'pending_orders': int(detail.get('pending_orders_count') or 0),
            },
            'workspace': {
                'datasets_count': int(detail.get('datasets_count') or 0),
                'listings_total': int(detail.get('listings_total') or 0),
                'crm_contacts_count': int(detail.get('crm_contacts_count') or 0),
                'crm_deals_open': int(detail.get('crm_deals_open') or usage.get('crm_deals_open') or 0),
            },
            'engagement': {
                'last_login_jalali': detail.get('last_login_jalali'),
                'days_since_login': usage.get('days_since_login'),
                'days_since_join': usage.get('days_since_join'),
                'windows_downloaded': bool(win.get('downloaded')),
                'windows_activated': bool(win.get('activated')),
                'windows_launched': bool(win.get('first_launch')),
                'android_installed': bool(android.get('installed')),
                'android_devices': int(android.get('devices_count') or 0),
            },
            'usage_flags': win,
            'android': android,
            'tickets_open': tickets_open,
            'last_paid_jalali': detail.get('last_paid_at_jalali'),
            'last_order_product': (
                last_order.product.title if last_order and last_order.product_id else None
            ),
            'last_ticket_subject': last_ticket.subject if last_ticket else None,
            'last_ticket_at_jalali': _jalali(last_ticket.created_at) if last_ticket else None,
        },
        'charts': {
            'activity_daily': activity_series,
            'activity_days': activity_span,
            'orders_by_status': chart_orders_by_status(user),
            'revenue_monthly': chart_paid_revenue_monthly(user),
        },
        'recent_orders': (detail.get('orders') or [])[:5],
        'recent_licenses': (detail.get('licenses') or [])[:5],
    }


def tab_account(user, summary: Dict[str, Any], *, reveal_sensitive: bool = False, **_) -> Dict[str, Any]:
    profile = safe_profile(user)
    ref_name = ''
    if user.referred_by_id:
        ref_name = str(user.referred_by)
    national_raw = (user.national_id or '').strip()
    national_display = mask_national_id(national_raw, reveal=reveal_sensitive)
    return {
        'tab': 'account',
        'label': TAB_LABELS['account'],
        'sensitive': {
            'national_id_masked': bool(national_raw) and not reveal_sensitive,
            'national_id_present': bool(national_raw),
        },
        'identity': {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'phone': user.phone or '',
            'email': user.email or '',
            'national_id': national_display,
            'phone_verified': bool(user.phone_verified),
            'phone_verified_at_jalali': _jalali(user.phone_verified_at),
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_affiliate': bool(user.is_affiliate),
            'date_joined_jalali': summary.get('date_joined_jalali'),
            'last_login_jalali': summary.get('last_login_jalali'),
            'marketing_sms_opt_out': bool(user.marketing_sms_opt_out),
            'marketing_sms_opt_out_at_jalali': _jalali(user.marketing_sms_opt_out_at),
        },
        'profile': {
            'city': profile.city if profile else '',
            'address': profile.address if profile else '',
            'postal_code': profile.postal_code if profile else '',
            'bio': profile.bio if profile else '',
            'has_avatar': bool(profile and profile.avatar),
        },
        'referral': {
            'referred_by': ref_name or '—',
        },
    }


def tab_commerce(user, summary: Dict[str, Any], *, page: int = 1, page_size: int = 25, **_) -> Dict[str, Any]:
    qs = (
        Order.objects.filter(user=user)
        .select_related('product', 'plan', 'discount_code', 'renewal_license')
        .order_by('-created_at')
    )
    page_qs, pagination = paginate_qs(qs, page=page, page_size=page_size)
    rows = []
    for o in page_qs:
        paid_revenue = int(o.amount or 0) if o.status == 'paid' else 0
        rows.append({
            'id': str(o.id),
            'product': o.product.title if o.product_id else '—',
            'plan': o.plan.name if o.plan_id else '—',
            'amount': int(o.amount or 0),
            'original_price': int(o.original_price or 0) if o.original_price else None,
            'discount_amount': int(o.discount_amount or 0),
            'revenue_counted': paid_revenue,
            'status': o.status,
            'status_label': ORDER_STATUS_LABELS.get(o.status, o.status),
            'fulfillment_status': o.get_fulfillment_status_display(),
            'fulfillment_error': o.fulfillment_error or '',
            'payment_method': o.get_payment_method_display() if o.payment_method else '—',
            'discount_code': o.discount_code.code if o.discount_code_id else '',
            'is_renewal': bool(o.renewal_license_id),
            'paid_jalali': _jalali(o.paid_at) or '—',
            'created_jalali': _jalali(o.created_at),
        })

    paid_sum = (
        Order.objects.filter(user=user, status='paid').aggregate(s=Sum('amount'))['s'] or 0
    )
    granted_count = Order.objects.filter(user=user, status='granted').count()
    failed_count = Order.objects.filter(
        user=user, status__in=('failed', 'cancelled')
    ).count()
    pending_count = Order.objects.filter(
        user=user, status__in=('pending', 'pending_verification')
    ).count()
    total_orders = Order.objects.filter(user=user).count()

    txn_rows = []
    for tx in Transaction.objects.filter(order__user=user).select_related('order').order_by('-created_at')[:30]:
        txn_rows.append({
            'id': str(tx.id),
            'order_id': str(tx.order_id),
            'amount': int(tx.amount or 0),
            'status': tx.status,
            'status_label': transaction_status_fa(tx.status),
            'gateway_ref': (tx.zibal_ref_number or tx.zibal_track_id or '')[:32],
            'created_jalali': _jalali(tx.created_at),
        })

    card_rows = []
    for cs in CardTransferSubmission.objects.filter(order__user=user).select_related('order').order_by('-created_at')[:20]:
        card_rows.append({
            'id': cs.id,
            'order_id': str(cs.order_id),
            'status': cs.status,
            'status_label': cs.get_status_display(),
            'submitted_jalali': _jalali(cs.created_at),
            'reviewed_jalali': _jalali(cs.reviewed_at),
        })

    return {
        'tab': 'commerce',
        'label': TAB_LABELS['commerce'],
        'summary': {
            'total_revenue_paid_only': int(paid_sum),
            'paid_orders': summary.get('paid_orders_count'),
            'granted_orders': granted_count,
            'failed_orders': failed_count,
            'pending_orders': pending_count,
            'total_orders': total_orders,
            'note': 'درآمد فقط از سفارش‌های پرداخت‌شده است؛ هدیه و اعطایی در جمع مبلغ نیست.',
        },
        'orders': rows,
        'pagination': pagination,
        'transactions': txn_rows,
        'card_transfers': card_rows,
        'charts': {
            'orders_by_status': chart_orders_by_status(user),
            'revenue_monthly': chart_paid_revenue_monthly(user),
        },
    }


LICENSE_RELATION_LABELS = {
    'owner': 'خریدار / مالک',
    'assigned': 'اختصاص‌یافته',
}


def _activation_row(act: LicenseActivation) -> Dict[str, Any]:
    is_mobile = (act.notes or '').startswith('device_type=mobile')
    return {
        'id': act.id,
        'platform': 'اندروید' if is_mobile else 'ویندوز',
        'label': act.display_name,
        'is_active': act.is_active,
        'fingerprint_masked': act.masked_fingerprint,
        'activated_jalali': _jalali(act.activated_at),
    }


def _license_row(lic: License, *, relation: str) -> Dict[str, Any]:
    is_entitled = lic.status == 'active' and (
        not lic.expires_at or lic.expires_at > timezone.now()
    )
    acts = list(lic.activations.all()) if hasattr(lic, '_prefetched_objects_cache') else list(
        lic.activations.order_by('-activated_at')
    )
    assigned_to = '—'
    if lic.assigned_user_id:
        assigned_to = lic.assigned_user.get_full_name() or lic.assigned_user.username
    days_until_expiry = None
    if lic.expires_at:
        try:
            days_until_expiry = (lic.expires_at - timezone.now()).days
        except (TypeError, ValueError):
            days_until_expiry = None
    order_summary = None
    if lic.order_id and getattr(lic, 'order', None):
        order = lic.order
        order_summary = {
            'id': str(order.pk),
            'status': order.status,
            'status_label': ORDER_STATUS_LABELS.get(order.status, order.status),
            'created_jalali': _jalali(order.created_at),
            'paid_jalali': _jalali(order.paid_at) if order.paid_at else '',
            'amount': int(order.amount or 0),
            'product': order.product.title if getattr(order, 'product_id', None) and order.product_id else '',
            'sequence': int(lic.sequence or 1),
        }
    return {
        'id': lic.id,
        'relation': LICENSE_RELATION_LABELS.get(relation, relation),
        'plan': lic.plan.name if lic.plan_id else '—',
        'status': lic.status,
        'status_label': LICENSE_STATUS_LABELS.get(lic.status, lic.status),
        'max_activations': lic.max_activations,
        'slots_used': len(acts) if acts else lic.activations.count(),
        'slots_active': sum(1 for a in acts if a.is_active),
        'expires_jalali': _jalali(lic.expires_at) or 'نامحدود',
        'created_jalali': _jalali(lic.created_at),
        'assigned_user_id': lic.assigned_user_id,
        'assigned_to': assigned_to,
        'order_id': str(lic.order_id) if lic.order_id else '',
        'order': order_summary,
        'days_until_expiry': days_until_expiry,
        'entitlement_valid': is_entitled,
        'activations': [_activation_row(a) for a in acts],
    }


def tab_licenses(user, summary: Dict[str, Any], *, can_manage_licenses: bool = False, **_) -> Dict[str, Any]:
    act_qs = LicenseActivation.objects.order_by('-activated_at')
    owned = list(
        License.objects.filter(order__user=user)
        .select_related('plan', 'order', 'order__product', 'assigned_user')
        .prefetch_related(Prefetch('activations', queryset=act_qs))
        .order_by('-created_at')
    )
    assigned = list(
        License.objects.filter(assigned_user=user)
        .select_related('plan', 'order', 'order__product', 'assigned_user')
        .prefetch_related(Prefetch('activations', queryset=act_qs))
        .order_by('-created_at')
    )
    grants = list(
        LicenseCampaignGrant.objects.filter(user=user).order_by('-created_at')[:20]
    )
    rows = [_license_row(l, relation='owner') for l in owned]
    rows.extend(_license_row(l, relation='assigned') for l in assigned if l.id not in {x['id'] for x in rows})

    act_rows = []
    for row in rows:
        for act in row.get('activations') or []:
            act_rows.append(dict(act, plan=row.get('plan') or '—', license_id=row['id']))
    act_rows.sort(key=lambda item: item.get('activated_jalali') or '', reverse=True)
    act_rows = act_rows[:50]

    grant_rows = [
        {
            'campaign_key': g.campaign_key,
            'campaign_label': license_campaign_key_label(g.campaign_key),
            'status': g.status,
            'status_label': g.get_status_display(),
            'created_jalali': _jalali(g.created_at),
            'license_id': g.license_id,
        }
        for g in grants
    ]

    return {
        'tab': 'licenses',
        'label': TAB_LABELS['licenses'],
        'access_summary': {
            'has_bot_access': summary.get('has_active_license'),
            'access_label': summary.get('license_access_label'),
            'access_kind': summary.get('license_access_kind'),
            'plan': summary.get('license_plan'),
            'expires_jalali': summary.get('license_expires_jalali'),
            'pending_activation': summary.get('has_pending_bot_activation'),
            'license_count': len(rows),
            'activations_total': len(act_rows),
            'activations_active': sum(1 for a in act_rows if a.get('is_active')),
        },
        'licenses': rows,
        'activations': act_rows,
        'campaign_grants': grant_rows,
        'charts': {
            'license_status': chart_license_status_counts(rows),
        },
        'can_manage_licenses': bool(can_manage_licenses),
        'form_options': {
            'status': [
                {'key': key, 'label': LICENSE_STATUS_LABELS.get(key, label)}
                for key, label in License.STATUS_CHOICES
            ],
        },
    }


def tab_activity(user, summary: Dict[str, Any], *, page: int = 1, **kwargs) -> Dict[str, Any]:
    payload = build_activity_timeline(
        user,
        page=page,
        page_size=safe_query_int(kwargs.get('page_size'), 40, minimum=1, maximum=100),
        kind_filter=(kwargs.get('kind') or '').strip(),
        platform_filter=(kwargs.get('platform') or '').strip(),
        success_filter=(kwargs.get('success') or '').strip(),
        sort=(kwargs.get('sort') or '-at'),
        days=resolve_timeline_days_filter(kwargs.get('days')),
    )
    day_span = resolve_panel_activity_days(kwargs.get('days'))
    payload['tab'] = 'activity'
    payload['label'] = TAB_LABELS['activity']
    payload['charts'] = {'activity_daily': daily_activity_counts(user, days=day_span)}
    return payload


def extraction_usage_snapshot(user, usage: Dict[str, Any]) -> Tuple[bool, int, Any, str]:
    """استخراج از دیوار: اپ، ابری، و مسیر ویندوز/میزکار (فایل دارای آگهی)."""
    listings_total = int(usage.get('listings') or 0)
    mobile_qs = MobileExtractionRun.objects.filter(user=user)
    mobile_count = mobile_qs.count()
    cloud_qs = MobileCloudExtractionJob.objects.filter(user=user)
    cloud_count = cloud_qs.count()

    datasets_with_data = Dataset.objects.filter(
        user=user, is_active=True, row_count__gt=0,
    )
    datasets_with_data_count = datasets_with_data.count()

    channel_total = mobile_count + cloud_count
    count = channel_total
    if channel_total == 0 and listings_total > 0:
        count = max(datasets_with_data_count, 1)

    started = bool(channel_total or listings_total > 0 or datasets_with_data_count)

    note_parts = []
    if mobile_count:
        note_parts.append(f'اپ اندروید: {fa_digits(mobile_count)} اجرا')
    if cloud_count:
        note_parts.append(f'استخراج ابری: {fa_digits(cloud_count)}')
    if listings_total > 0 and channel_total == 0:
        files_label = fa_digits(max(datasets_with_data_count, 1))
        note_parts.append(f'ویندوز یا میزکار: {files_label} فایل')
    note = ' · '.join(note_parts)

    last_at = None
    for cand in (
        mobile_qs.order_by('-started_at').values_list('started_at', flat=True).first(),
        cloud_qs.order_by('-finished_at').values_list('finished_at', flat=True).first(),
        cloud_qs.order_by('-created_at').values_list('created_at', flat=True).first(),
        datasets_with_data.order_by('-updated_at').values_list('updated_at', flat=True).first(),
    ):
        if cand and (last_at is None or cand > last_at):
            last_at = cand

    return started, count, last_at, note


def tab_usage(user, summary: Dict[str, Any], **_) -> Dict[str, Any]:
    detail = get_user_management_detail(user.id) or summary
    usage = detail.get('usage') or {}
    win = detail.get('windows') or {}
    andr = detail.get('android') or {}

    listing_qs = UserListingActivity.objects.filter(user=user)
    listing_count = listing_qs.count()
    listing_last = listing_qs.order_by('-last_activity_at').values_list(
        'last_activity_at', flat=True,
    ).first()
    ext_started, ext_count, ext_last, ext_note = extraction_usage_snapshot(user, usage)
    sync_ops = MobileSyncOperation.objects.filter(user=user).count()
    reminders = Reminder.objects.filter(user=user).count()

    def feature(name, started: bool, count=0, last_at=None, note=''):
        return {
            'name': name,
            'started': started,
            'count': count,
            'last_at_jalali': _jalali(last_at) if last_at else ('—' if started else ''),
            'note': note,
        }

    features = [
        feature('ربات ویندوز', win.get('first_launch') or win.get('activated'), usage.get('windows_launches', 0)),
        feature('اپ اندروید', andr.get('installed'), andr.get('devices_count', 0), None),
        feature('استخراج آگهی', ext_started, ext_count, ext_last, ext_note),
        feature('دیتاست‌ها', usage.get('datasets', 0) > 0, usage.get('datasets', 0)),
        feature(
            'آگهی در بانک فایل',
            usage.get('listings', 0) > 0,
            usage.get('listings', 0),
            note='مجموع آگهی‌های ذخیره‌شده در فایل‌ها — شاخص حجم کار، نه تعداد دفعات استفاده',
        ),
        feature('مخاطبین', usage.get('crm_contacts', 0) > 0, usage.get('crm_contacts', 0)),
        feature('معاملات', usage.get('crm_deals', 0) > 0, usage.get('crm_deals', 0)),
        feature('یادآورها', reminders > 0, reminders),
        feature(
            'کار روی آگهی فایل',
            listing_count > 0,
            listing_count,
            listing_last,
            'بازدید، برچسب یا یادداشت روی آگهی در بانک فایل — نه انتشار آگهی در دیوار',
        ),
        feature(
            'همگام‌سازی موبایل',
            sync_ops > 0,
            sync_ops,
            note='جزئیات هر همگام‌سازی در لاگ جدا ثبت نمی‌شود' if sync_ops > 0 else '',
        ),
    ]
    return {
        'tab': 'usage',
        'label': TAB_LABELS['usage'],
        'features': features,
        'charts': {'feature_usage': chart_feature_usage(features)},
    }


def tab_devices(user, summary: Dict[str, Any], **_) -> Dict[str, Any]:
    from accounts.services.admin_users_management import get_user_management_detail

    detail = get_user_management_detail(user.id) or {}
    acts = (detail.get('activations') or [])[:30]
    plat = {'windows': 0, 'android': 0, 'other': 0}
    for a in acts:
        p = (a.get('platform') or '').lower()
        if p in plat:
            plat[p] += 1
        else:
            plat['other'] += 1
    device_charts = [
        {'label': 'ویندوز', 'count': plat['windows']},
        {'label': 'اندروید', 'count': plat['android']},
    ]
    if plat['other']:
        device_charts.append({'label': 'سایر', 'count': plat['other']})
    return {
        'tab': 'devices',
        'label': TAB_LABELS['devices'],
        'windows': {
            'flags': detail.get('windows') or summary.get('windows'),
            'downloads': detail.get('downloads') or [],
            'app_events': (detail.get('app_events') or [])[:25],
        },
        'android_devices': detail.get('android_devices') or [],
        'activations': acts,
        'charts': {'platform_activations': [c for c in device_charts if c['count']]},
    }


def tab_support(
    user,
    summary: Dict[str, Any],
    *,
    page: int = 1,
    include_internal_notes: bool = False,
    include_internal: bool = False,
    can_manage_tickets: bool = False,
    **_,
) -> Dict[str, Any]:
    show_internal = include_internal or include_internal_notes
    qs = Ticket.objects.filter(user=user).annotate(
        msg_count=Count('messages'),
    ).order_by('-last_message_at', '-created_at')
    page_qs, pagination = paginate_qs(qs, page=page, page_size=20)
    rows = []
    msg_qs = TicketMessage.objects.filter(ticket_id__in=[t.pk for t in page_qs]).select_related('author')
    if not show_internal:
        msg_qs = msg_qs.filter(is_internal=False)
    messages_by_ticket: Dict[int, list] = {}
    for msg in msg_qs.order_by('created_at'):
        messages_by_ticket.setdefault(msg.ticket_id, []).append(msg)

    for t in page_qs:
        preview_msgs = []
        for msg in (messages_by_ticket.get(t.pk) or [])[-1:]:
            preview_msgs.append({
                'author': (msg.author.get_full_name() or msg.author.username) if msg.author_id else '—',
                'is_staff': bool(msg.is_staff_reply),
                'is_internal': bool(msg.is_internal),
                'body_preview': (msg.body or '')[:240],
                'created_jalali': _jalali(msg.created_at),
            })
        rows.append({
            'ticket_id': t.pk,
            'ticket_number': t.ticket_number,
            'admin_url': reverse('admin:workspace_ticket_change', args=[t.pk]),
            'subject': t.subject,
            'category': t.get_category_display_fa(),
            'priority': t.get_priority_display_fa(),
            'priority_key': t.priority or '',
            'status': t.get_status_display_fa(),
            'status_key': t.status or '',
            'assigned_to': t.assigned_to.get_full_name() if t.assigned_to_id else '—',
            'created_jalali': _jalali(t.created_at),
            'last_message_jalali': _jalali(t.last_message_at),
            'closed_jalali': _jalali(t.closed_at),
            'messages_count': t.msg_count,
            'staff_unread': t.staff_has_unread,
            'recent_messages': preview_msgs,
        })

    open_c = Ticket.objects.filter(user=user).exclude(status='closed').count()
    closed_c = Ticket.objects.filter(user=user, status='closed').count()
    unread_c = Ticket.objects.filter(user=user, staff_has_unread=True).count()

    return {
        'tab': 'support',
        'label': TAB_LABELS['support'],
        'stats': {'total': open_c + closed_c, 'open': open_c, 'closed': closed_c, 'staff_unread': unread_c},
        'tickets': rows,
        'pagination': pagination,
        'include_internal_notes': show_internal,
        'charts': {'tickets_by_status': chart_ticket_status(user)},
        'can_manage_tickets': bool(can_manage_tickets),
        'form_options': support_form_options() if can_manage_tickets else {},
    }


def tab_workspace(user, summary: Dict[str, Any], *, page: int = 1, **_) -> Dict[str, Any]:
    detail = get_user_management_detail(user.id) or {}
    ds_qs = Dataset.objects.filter(user=user, is_active=True).order_by('-created_at')
    ds_all = Dataset.objects.filter(user=user, is_active=True)
    datasets_total = ds_all.count()
    listings_total = int(ds_all.aggregate(s=Sum('row_count'))['s'] or 0)
    ds_page, ds_pagination = paginate_qs(ds_qs, page=page, page_size=20)
    datasets = [
        {
            'id': str(d.id),
            'name': d.name,
            'row_count': d.row_count or 0,
            'city': d.city or '—',
            'created_jalali': _jalali(d.created_at),
        }
        for d in ds_page
    ]
    deals_open = CRMDeal.objects.filter(user=user).exclude(
        stage__in=('بسته شده', 'از دست رفته', 'لغو', 'بسته', 'won', 'lost')
    ).count()
    return {
        'tab': 'workspace',
        'label': TAB_LABELS['workspace'],
        'crm': {
            'contacts_count': summary.get('crm_contacts_count'),
            'deals_total': detail.get('crm_deals_total'),
            'deals_open': deals_open,
            'status_breakdown': detail.get('crm_status_breakdown') or [],
            'recent_contacts': detail.get('crm_recent_contacts') or [],
        },
        'datasets': datasets,
        'datasets_pagination': ds_pagination,
        'stats': {
            'contacts': int(summary.get('crm_contacts_count') or 0),
            'deals_open': deals_open,
            'deals_total': int(detail.get('crm_deals_total') or 0),
            'datasets_total': datasets_total,
            'listings_in_files': listings_total,
        },
        'note_team_data': 'عضویت آژانس و اشتراک تیمی در تب «فضای آژانس».',
        'charts': {
            'crm_contacts_status': chart_crm_status_breakdown(detail.get('crm_status_breakdown') or []),
        },
    }


def tab_marketing(user, summary: Dict[str, Any], **_) -> Dict[str, Any]:
    phone = normalize_phone(user.phone)
    sms_qs = SmsMessageLog.objects.filter(phone__icontains=phone[-10:]) if phone else SmsMessageLog.objects.none()
    sms_qs = sms_qs.order_by('-created_at')[:50]
    sms_rows = [
        {
            'id': s.pk,
            'purpose': sms_purpose_label(s.purpose),
            'status': s.get_status_display(),
            'channel': s.get_channel_display(),
            'message_body': resolve_sms_message_body(s),
            'message_preview': resolve_sms_log_preview(s),
            'message_detail': '\n'.join(sms_log_detail_lines(s)),
            'created_jalali': _jalali(s.created_at),
        }
        for s in sms_qs
    ]

    recipients = MarketingCampaignRecipient.objects.filter(
        Q(user=user) | Q(phone=user.phone),
    ).select_related('campaign').order_by('-created_at')[:40]
    camp_rows = [
        {
            'campaign': r.campaign.name if r.campaign_id else '—',
            'status': r.get_status_display(),
            'phone': r.phone,
            'created_jalali': _jalali(r.created_at),
        }
        for r in recipients
        if r.user_id == user.id or r.phone == user.phone
    ]

    attributions = RecoveryAttribution.objects.filter(user=user).order_by('-id')[:20]
    attr_rows = [
        {
            'model': a.get_attribution_model_display() if a.attribution_model else '—',
            'status': a.get_status_display(),
            'created_jalali': _jalali(a.created_at),
        }
        for a in attributions
    ]

    journey_qs = GrowthJourneyEvent.objects.filter(journey__user=user).order_by('-created_at')[:60]
    journey_rows = [
        {
            'event_type': growth_journey_event_label(j.event_type),
            'event_key': j.event_type or '',
            'created_jalali': _jalali(j.created_at),
        }
        for j in journey_qs
    ]
    journey_summary: Dict[str, Dict[str, Any]] = {}
    for row in journey_rows:
        key = row.get('event_key') or row['event_type']
        if key not in journey_summary:
            journey_summary[key] = {
                'event_type': row['event_type'],
                'event_key': row.get('event_key') or '',
                'count': 0,
                'last_jalali': row['created_jalali'],
            }
        journey_summary[key]['count'] += 1
    growth_journey_summary = list(journey_summary.values())

    discount_rows = [
        {
            'code': row.discount_code.code if row.discount_code_id else '—',
            'policy_key': row.policy_key,
            'source_type': row.get_source_type_display(),
            'issued_jalali': _jalali(row.issued_at),
        }
        for row in UserDiscountIssuance.objects.filter(user=user).select_related('discount_code').order_by('-issued_at')[:30]
    ]

    return {
        'tab': 'marketing',
        'label': TAB_LABELS['marketing'],
        'opt_out': bool(user.marketing_sms_opt_out),
        'sms_logs': sms_rows,
        'campaigns': camp_rows,
        'attributions': attr_rows,
        'growth_events': journey_rows[:20],
        'growth_journey_summary': growth_journey_summary,
        'discount_issuances': discount_rows,
        'stats': {
            'sms_count': len(sms_rows),
            'campaign_count': len(camp_rows),
            'discount_count': len(discount_rows),
            'attribution_count': len(attr_rows),
            'journey_event_count': len(journey_rows),
            'journey_type_count': len(growth_journey_summary),
        },
    }


def tab_agency(user, summary: Dict[str, Any], **_) -> Dict[str, Any]:
    memberships = list(
        CRMAgencyMember.objects.filter(user=user)
        .select_related('agency')
        .order_by('-joined_at')
    )
    if not memberships:
        return {
            'tab': 'agency',
            'label': TAB_LABELS['agency'],
            'empty': True,
            'message': 'این کاربر عضو فعال آژانس ثبت‌شده نیست.',
        }

    member_rows = []
    for m in memberships:
        sub = (
            AgencySubscription.objects.filter(agency=m.agency, status=AgencySubscription.STATUS_ACTIVE)
            .select_related('plan')
            .order_by('-expires_at')
            .first()
        )
        member_rows.append({
            'agency_name': m.agency.name,
            'agency_id': str(m.agency_id),
            'role': m.get_role_display(),
            'is_active': m.is_active,
            'joined_jalali': _jalali(m.joined_at),
            'subscription_expires_jalali': _jalali(sub.expires_at) if sub else '—',
            'subscription_plan': (sub.plan.name if sub and sub.plan_id else '—'),
        })

    owned_agencies = CRMAgency.objects.filter(owner=user).count()
    owner_subs = list(
        AgencySubscription.objects.filter(owner=user)
        .select_related('plan', 'agency')
        .order_by('-expires_at')[:10]
    )
    sub_rows = [
        {
            'agency_name': s.agency.name if s.agency_id else '—',
            'plan': s.plan.name if s.plan_id else '—',
            'status': s.get_status_display(),
            'seat_count': s.seat_count,
            'expires_jalali': _jalali(s.expires_at),
        }
        for s in owner_subs
    ]
    return {
        'tab': 'agency',
        'label': TAB_LABELS['agency'],
        'memberships': member_rows,
        'owned_agencies_count': owned_agencies,
        'owner_subscriptions': sub_rows,
    }


AUDIT_DETAIL_EVENT_LABELS = {
    'seat_registered': 'ثبت اسلات دستگاه',
    'seat_assigned': 'تخصیص اسلات به عضو',
    'seat_unassigned': 'لغو تخصیص اسلات',
    'seat_removed': 'حذف اسلات دستگاه',
    'desktop_bind': 'اتصال لایسنس به دسکتاپ',
    'desktop_account_bind': 'اتصال حساب کاربر به دسکتاپ',
    'desktop_session_validate': 'اعتبارسنجی نشست دسکتاپ',
    'license_renewed': 'تمدید لایسنس',
    'license_issued_on_payment': 'صدور لایسنس پس از پرداخت',
    'weekly_trial_grant': 'هدیه آزمایشی',
    'license_released_to_pool': 'آزادسازی لایسنس (بازگشت به استخر)',
    'license_activated_for_owner': 'فعال‌سازی لایسنس برای مالک',
    'license_assigned': 'تخصیص کلید لایسنس به عضو تیم',
    'license_unassigned': 'لغو تخصیص کلید لایسنس',
    'signup_welcome_gift_offer': 'پیشنهاد هدیه خوش‌آمدگویی',
    'admin_u360_set_status': 'تغییر وضعیت لایسنس (پرونده ۳۶۰)',
    'admin_u360_clear_expiry': 'حذف تاریخ انقضا (پرونده ۳۶۰)',
    'admin_u360_set_expiry': 'تنظیم تاریخ انقضا (پرونده ۳۶۰)',
    'admin_u360_adjust_expiry': 'تغییر تاریخ انقضا (پرونده ۳۶۰)',
    'admin_u360_set_max_activations': 'تغییر سقف اسلات (پرونده ۳۶۰)',
    'admin_u360_set_activation_active': 'تغییر وضعیت اسلات (پرونده ۳۶۰)',
    'admin_u360_remove_activation': 'حذف اسلات دستگاه (پرونده ۳۶۰)',
    'admin_u360_revoke_assignment': 'لغو تخصیص عضو (پرونده ۳۶۰)',
}

AUDIT_DETAIL_KEY_LABELS = {
    'event': 'رویداد',
    'hardware_fingerprint': 'شناسه دستگاه',
    'activation_id': 'شناسه اسلات',
    'assigned_to': 'تخصیص به',
    'assigned_by': 'انجام‌دهنده',
    'previous_user': 'کاربر قبلی',
    'username': 'نام کاربری',
    'user_id': 'شناسه کاربر',
    'order_id': 'شناسه سفارش',
    'license_id': 'شناسه لایسنس',
    'released_by': 'آزادسازی توسط',
    'activated_by': 'فعال‌سازی توسط',
    'removed_by': 'حذف توسط',
    'revoked_by': 'لغو توسط',
    'previous_status': 'وضعیت قبلی',
    'new_status': 'وضعیت جدید',
    'days_delta': 'تغییر (روز)',
    'new_expires_at': 'انقضای جدید',
    'previous_expires_at': 'انقضای قبلی',
    'previous_max': 'سقف قبلی اسلات',
    'new_max': 'سقف جدید اسلات',
    'is_active': 'فعال در ربات',
    'was_active': 'قبلاً فعال بود',
    'devices_deactivated': 'تعداد دستگاه قطع‌شده',
    'device_type': 'نوع دستگاه',
    'reactivated': 'فعال‌سازی مجدد',
    'staff_username': 'مدیر',
    'staff_id': 'شناسه مدیر',
    'source': 'منبع',
    'plan': 'پلن',
    'sequence': 'شماره در سفارش',
    'quantity': 'تعداد',
    'label': 'نام دستگاه',
}

_AUDIT_DETAIL_VALUE_MAP = {
    'device_type': {
        'desktop': 'دسکتاپ',
        'windows': 'ویندوز',
        'mobile': 'موبایل',
        'android': 'اندروید',
    },
    'source': {
        'admin_u360': 'پرونده ۳۶۰ مشتری',
    },
}


def _audit_event_label(event: str) -> str:
    key = (event or '').strip()
    if not key:
        return '—'
    if key in AUDIT_DETAIL_EVENT_LABELS:
        return AUDIT_DETAIL_EVENT_LABELS[key]
    return 'رویداد داخلی سیستم'


def _format_audit_value(value: Any) -> str:
    if isinstance(value, bool):
        return 'بله' if value else 'خیر'
    if value is None:
        return '—'
    if isinstance(value, (dict, list)):
        text = str(value)
        return text[:160] + ('…' if len(text) > 160 else '')
    text = str(value)
    return text[:200] + ('…' if len(text) > 200 else '')


def _audit_detail_value_display(key: str, value: Any) -> str:
    if value in (None, '', []):
        return '—'
    if key == 'event' and isinstance(value, str):
        return _audit_event_label(value)
    if key in ('previous_status', 'new_status') and isinstance(value, str):
        return LICENSE_STATUS_LABELS.get(value, value)
    mapped = _AUDIT_DETAIL_VALUE_MAP.get(key, {})
    if isinstance(value, str) and value in mapped:
        return mapped[value]
    if key == 'reactivated' and isinstance(value, bool):
        return 'بله' if value else 'خیر'
    return _format_audit_value(value)


def _audit_detail_summary(details: Any) -> str:
    if not isinstance(details, dict) or not details:
        return '—'
    event = details.get('event')
    if isinstance(event, str) and event.strip():
        label = _audit_event_label(event)
        extras = []
        for key, lbl in (
            ('assigned_to', 'تخصیص به'),
            ('assigned_by', 'توسط'),
            ('previous_user', 'کاربر قبلی'),
            ('username', 'کاربر'),
            ('hardware_fingerprint', 'دستگاه'),
            ('order_id', 'سفارش'),
            ('activation_id', 'اسلات'),
            ('released_by', 'آزادسازی توسط'),
            ('activated_by', 'فعال‌سازی توسط'),
        ):
            val = details.get(key)
            if val not in (None, '', []):
                extras.append(f'{lbl}: {_audit_detail_value_display(key, val)}')
        new_status = details.get('new_status')
        if new_status not in (None, '', []):
            extras.append('وضعیت جدید: ' + _audit_detail_value_display('new_status', new_status))
        if extras:
            return f'{label} — ' + ' · '.join(extras[:4])
        return label
    if details.get('hardware_fingerprint'):
        parts = ['فعال‌سازی دستگاه']
        fp = _audit_detail_value_display('hardware_fingerprint', details.get('hardware_fingerprint'))
        parts.append(f'شناسه: {fp}')
        if details.get('reactivated') is True:
            parts.append('فعال‌سازی مجدد')
        return ' — '.join(parts)
    parts = []
    for key, val in details.items():
        if val in (None, '', []):
            continue
        lbl = AUDIT_DETAIL_KEY_LABELS.get(str(key), str(key))
        parts.append(f'{lbl}: {_audit_detail_value_display(str(key), val)}')
        if len(parts) >= 3:
            break
    return ' · '.join(parts) if parts else '—'


def _audit_detail_lines(details: Any) -> list:
    if not isinstance(details, dict):
        return []
    skip_keys = frozenset()
    lines = []
    for key, val in details.items():
        if key in skip_keys or val in (None, '', []):
            continue
        lines.append({
            'key': AUDIT_DETAIL_KEY_LABELS.get(str(key), str(key)),
            'value': _audit_detail_value_display(str(key), val),
        })
    return lines[:16]


def tab_admin_log(user, summary: Dict[str, Any], *, page: int = 1, **kwargs) -> Dict[str, Any]:
    page_size = safe_query_int(kwargs.get('page_size'), 30, minimum=10, maximum=60)
    action_filter = (kwargs.get('kind') or '').strip()
    days_filter = resolve_timeline_days_filter(kwargs.get('days'))

    lic_ids = list(
        License.objects.filter(Q(order__user=user) | Q(assigned_user=user)).values_list('id', flat=True)
    )
    if not lic_ids:
        return {
            'tab': 'admin_log',
            'label': TAB_LABELS['admin_log'],
            'empty': True,
            'message': 'لایسنس مرتبط با این کاربر نیست؛ لاگ امنیتی برای نمایش وجود ندارد.',
            'stats': {'total': 0, 'license_count': 0, 'validation_count': 0, 'suspicious_count': 0},
            'audit_logs': [],
            'pagination': paginate_qs(AuditLog.objects.none(), page=1, page_size=page_size)[1],
            'filters': {'actions': [{'key': k, 'label': v} for k, v in AuditLog.ACTION_TYPES]},
            'charts': {'actions': [], 'daily': []},
        }

    qs = AuditLog.objects.filter(license_id__in=lic_ids).select_related('license', 'license__plan')
    if days_filter:
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days_filter))
    if action_filter:
        valid_actions = {k for k, _ in AuditLog.ACTION_TYPES}
        if action_filter in valid_actions:
            qs = qs.filter(action_type=action_filter)

    qs = qs.order_by('-created_at', '-id')

    total = qs.count()
    license_count = qs.values('license_id').distinct().count()
    validation_count = qs.filter(action_type='validation').count()
    suspicious_count = qs.filter(action_type='suspicious').count()
    last_log = qs.order_by('-created_at').values_list('created_at', flat=True).first()

    action_rows = list(
        qs.values('action_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    action_breakdown = [
        {
            'key': row['action_type'],
            'label': dict(AuditLog.ACTION_TYPES).get(row['action_type'], row['action_type']),
            'count': int(row['count'] or 0),
        }
        for row in action_rows
        if row['count']
    ]

    chart_span = days_filter if days_filter and days_filter <= 60 else 14
    if days_filter and days_filter > 60:
        chart_span = 30

    page_qs, pagination = paginate_qs(qs, page=page, page_size=page_size)
    rows = []
    for log in page_qs:
        lic = log.license
        plan_name = '—'
        status_label = '—'
        if lic:
            if lic.plan_id:
                plan_name = lic.plan.name
            status_label = LICENSE_STATUS_LABELS.get(lic.status, lic.status)
        ua = (log.user_agent or '').strip()
        rows.append({
            'id': log.pk,
            'action_type': log.get_action_type_display(),
            'action_key': log.action_type,
            'license_id': log.license_id,
            'license_plan': plan_name,
            'license_status': status_label,
            'detail_summary': _audit_detail_summary(log.details),
            'detail_lines': _audit_detail_lines(log.details),
            'ip': log.ip_address or '—',
            'user_agent_short': (ua[:96] + '…') if len(ua) > 96 else (ua or '—'),
            'created_jalali': _jalali(log.created_at),
            'created_at': log.created_at.isoformat() if log.created_at else None,
        })

    return {
        'tab': 'admin_log',
        'label': TAB_LABELS['admin_log'],
        'audit_logs': rows,
        'pagination': pagination,
        'stats': {
            'total': total,
            'license_count': license_count,
            'validation_count': validation_count,
            'suspicious_count': suspicious_count,
            'last_jalali': _jalali(last_log) if last_log else '—',
            'page_count': len(rows),
        },
        'filters': {'actions': [{'key': k, 'label': v} for k, v in AuditLog.ACTION_TYPES]},
        'charts': {
            'actions': chart_audit_action_counts(action_breakdown),
            'daily': chart_audit_log_daily(qs, span_days=chart_span),
        },
        'note': 'فقط تغییرات و رویدادهای امنیتی لایسنس‌های این کاربر — اعتبارسنجی‌های تکراری نشست، در لاگ ثبت می‌شوند.',
    }


TAB_BUILDERS = {
    'overview': tab_overview,
    'account': tab_account,
    'commerce': tab_commerce,
    'licenses': tab_licenses,
    'activity': tab_activity,
    'usage': tab_usage,
    'devices': tab_devices,
    'support': tab_support,
    'workspace': tab_workspace,
    'marketing': tab_marketing,
    'agency': tab_agency,
    'admin_log': tab_admin_log,
}
