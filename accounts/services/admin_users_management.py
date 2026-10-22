"""مدیریت و تحلیل کاربران — جدول خلاصه + جزئیات برای پنل ادمین."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import jdatetime
from django.contrib.auth import get_user_model
from django.db.models import (
    Count,
    DecimalField,
    Exists,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from licenses.models import ClientAppEvent, License, LicenseActivation
from mobile_api.models import MobileDevice
from shop.models import DownloadLog, Order
from workspace.models import CRMDeal, Customer, Dataset
from workspace.services.bot_license_query import (
    annotate_pending_bot_activation,
    annotate_user_bot_license_access,
    bot_access_display,
    license_entitlement_valid_q,
    resolve_bot_access_kind,
)
from workspace.services.jalali_input import to_persian_digits

User = get_user_model()

PAGE_SIZE_DEFAULT = 25
PAGE_SIZE_MAX = 100

WINDOWS_ACTIVATION_Q = Q(is_active=True) & ~Q(notes__startswith='device_type=mobile')

LICENSE_STATUS_LABELS = {
    'active': 'فعال',
    'inactive': 'غیرفعال',
    'suspended': 'مسدود',
    'expired': 'منقضی',
}

ORDER_STATUS_LABELS = {
    'pending': 'در انتظار',
    'pending_verification': 'در انتظار تایید',
    'paid': 'پرداخت‌شده',
    'failed': 'ناموفق',
    'cancelled': 'لغو',
}


def _jalali(dt) -> str:
    if not dt:
        return ''
    try:
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        jdt = jdatetime.datetime.fromgregorian(datetime=dt)
        if jdt.hour or jdt.minute:
            return to_persian_digits(jdt.strftime('%Y/%m/%d %H:%M'))
        return to_persian_digits(jdt.strftime('%Y/%m/%d'))
    except Exception:
        return to_persian_digits(str(dt))


def _user_display(user) -> str:
    return (user.get_full_name() or user.username or '').strip() or '—'


def _annotate_users_qs(qs=None):
    """Annotate User queryset with management metrics."""
    if qs is None:
        qs = User.objects.all()

    latest_owner_plan = (
        License.objects.filter(
            order__user=OuterRef('pk'),
            status='active',
        )
        .filter(license_entitlement_valid_q())
        .order_by('-expires_at', '-created_at')
        .values('plan__name')[:1]
    )
    latest_owner_expires = (
        License.objects.filter(
            order__user=OuterRef('pk'),
            status='active',
        )
        .filter(license_entitlement_valid_q())
        .order_by('-expires_at', '-created_at')
        .values('expires_at')[:1]
    )
    latest_assigned_plan = (
        License.objects.filter(assigned_user=OuterRef('pk'))
        .filter(license_entitlement_valid_q())
        .order_by('-expires_at', '-created_at')
        .values('plan__name')[:1]
    )
    latest_assigned_expires = (
        License.objects.filter(assigned_user=OuterRef('pk'))
        .filter(license_entitlement_valid_q())
        .order_by('-expires_at', '-created_at')
        .values('expires_at')[:1]
    )
    latest_seat_plan = (
        LicenseActivation.objects.filter(
            assigned_user=OuterRef('pk'),
            is_active=True,
            license__status='active',
        )
        .filter(license_entitlement_valid_q(prefix='license__'))
        .order_by('-license__expires_at', '-activated_at')
        .values('license__plan__name')[:1]
    )
    latest_seat_expires = (
        LicenseActivation.objects.filter(
            assigned_user=OuterRef('pk'),
            is_active=True,
            license__status='active',
        )
        .filter(license_entitlement_valid_q(prefix='license__'))
        .order_by('-license__expires_at', '-activated_at')
        .values('license__expires_at')[:1]
    )

    paid_count_sq = (
        Order.objects.filter(user_id=OuterRef('pk'), status='paid')
        .order_by()
        .values('user_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )
    paid_sum_sq = (
        Order.objects.filter(user_id=OuterRef('pk'), status='paid')
        .order_by()
        .values('user_id')
        .annotate(s=Sum('amount'))
        .values('s')[:1]
    )
    last_paid_sq = (
        Order.objects.filter(user_id=OuterRef('pk'), status='paid')
        .order_by()
        .values('user_id')
        .annotate(m=Max('paid_at'))
        .values('m')[:1]
    )
    pending_count_sq = (
        Order.objects.filter(
            user_id=OuterRef('pk'),
            status__in=('pending', 'pending_verification'),
        )
        .order_by()
        .values('user_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )
    android_count_sq = (
        MobileDevice.objects.filter(user_id=OuterRef('pk'))
        .order_by()
        .values('user_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )
    android_seen_sq = (
        MobileDevice.objects.filter(user_id=OuterRef('pk'))
        .order_by()
        .values('user_id')
        .annotate(m=Max('last_seen_at'))
        .values('m')[:1]
    )
    datasets_count_sq = (
        Dataset.objects.filter(user_id=OuterRef('pk'), is_active=True)
        .order_by()
        .values('user_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )
    listings_sum_sq = (
        Dataset.objects.filter(user_id=OuterRef('pk'), is_active=True)
        .order_by()
        .values('user_id')
        .annotate(s=Sum('row_count'))
        .values('s')[:1]
    )
    last_dataset_sq = (
        Dataset.objects.filter(user_id=OuterRef('pk'), is_active=True)
        .order_by()
        .values('user_id')
        .annotate(m=Max('created_at'))
        .values('m')[:1]
    )
    crm_contacts_sq = (
        Customer.objects.filter(user_id=OuterRef('pk'))
        .order_by()
        .values('user_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )
    crm_deals_sq = (
        CRMDeal.objects.filter(user_id=OuterRef('pk'))
        .order_by()
        .values('user_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )

    windows_download = DownloadLog.objects.filter(user_id=OuterRef('pk'))
    windows_activation = LicenseActivation.objects.filter(
        license__order__user_id=OuterRef('pk'),
    ).filter(WINDOWS_ACTIVATION_Q)
    windows_launch = ClientAppEvent.objects.filter(
        user_id=OuterRef('pk'),
        event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
    )
    android_device = MobileDevice.objects.filter(user_id=OuterRef('pk'))
    has_dataset = Dataset.objects.filter(user_id=OuterRef('pk'), is_active=True)
    has_crm = Customer.objects.filter(user_id=OuterRef('pk'))

    zero_int = Value(0, output_field=IntegerField())
    zero_dec = Value(0, output_field=DecimalField(max_digits=14, decimal_places=0))

    qs = qs.annotate(
        paid_orders_count=Coalesce(
            Subquery(paid_count_sq, output_field=IntegerField()),
            zero_int,
        ),
        total_spent=Coalesce(
            Subquery(paid_sum_sq, output_field=DecimalField(max_digits=14, decimal_places=0)),
            zero_dec,
        ),
        last_paid_at=Subquery(last_paid_sq),
        pending_orders_count=Coalesce(
            Subquery(pending_count_sq, output_field=IntegerField()),
            zero_int,
        ),
        license_plan_owner=Subquery(latest_owner_plan),
        license_plan_assigned=Subquery(latest_assigned_plan),
        license_plan_seat=Subquery(latest_seat_plan),
        license_expires_owner=Subquery(latest_owner_expires),
        license_expires_assigned=Subquery(latest_assigned_expires),
        license_expires_seat=Subquery(latest_seat_expires),
        windows_downloaded=Exists(windows_download),
        windows_activated=Exists(windows_activation),
        windows_first_launch=Exists(windows_launch),
        android_devices_count=Coalesce(
            Subquery(android_count_sq, output_field=IntegerField()),
            zero_int,
        ),
        android_last_seen=Subquery(android_seen_sq),
        has_android=Exists(android_device),
        datasets_count=Coalesce(
            Subquery(datasets_count_sq, output_field=IntegerField()),
            zero_int,
        ),
        listings_total=Coalesce(
            Subquery(listings_sum_sq, output_field=IntegerField()),
            zero_int,
        ),
        last_dataset_at=Subquery(last_dataset_sq),
        has_datasets=Exists(has_dataset),
        crm_contacts_count=Coalesce(
            Subquery(crm_contacts_sq, output_field=IntegerField()),
            zero_int,
        ),
        crm_deals_count=Coalesce(
            Subquery(crm_deals_sq, output_field=IntegerField()),
            zero_int,
        ),
        has_crm=Exists(has_crm),
    )
    qs = annotate_user_bot_license_access(qs)
    return annotate_pending_bot_activation(qs)


def _apply_filters(qs, *, q: str = '', filters: Optional[Dict[str, str]] = None):
    filters = filters or {}
    q = (q or '').strip()
    if q:
        qs = qs.filter(
            Q(phone__icontains=q)
            | Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )

    license_f = filters.get('license') or ''
    if license_f == 'active':
        qs = qs.filter(has_active_license=True)
    elif license_f == 'none':
        qs = qs.filter(has_active_license=False)
    elif license_f == 'paid_no_license':
        qs = qs.filter(has_active_license=False, paid_orders_count__gt=0)

    if filters.get('windows') == '1':
        qs = qs.filter(Q(windows_downloaded=True) | Q(windows_activated=True) | Q(windows_first_launch=True))
    elif filters.get('windows') == '0':
        qs = qs.filter(windows_downloaded=False, windows_activated=False, windows_first_launch=False)

    if filters.get('android') == '1':
        qs = qs.filter(has_android=True)
    elif filters.get('android') == '0':
        qs = qs.filter(has_android=False)

    if filters.get('datasets') == '1':
        qs = qs.filter(has_datasets=True)
    elif filters.get('datasets') == '0':
        qs = qs.filter(has_datasets=False)

    if filters.get('crm') == '1':
        qs = qs.filter(has_crm=True)
    elif filters.get('crm') == '0':
        qs = qs.filter(has_crm=False)

    if filters.get('paid') == '1':
        qs = qs.filter(paid_orders_count__gt=0)
    elif filters.get('paid') == '0':
        qs = qs.filter(paid_orders_count=0)

    return qs


def _sort_qs(qs, sort: str = '-date_joined'):
    allowed = {
        'date_joined', '-date_joined',
        'last_login', '-last_login',
        'total_spent', '-total_spent',
        'paid_orders_count', '-paid_orders_count',
        'datasets_count', '-datasets_count',
        'crm_contacts_count', '-crm_contacts_count',
        'listings_total', '-listings_total',
    }
    if sort not in allowed:
        sort = '-date_joined'
    return qs.order_by(sort, '-id')


def _primary_license_fields(u) -> tuple[str, Any, str]:
    kind = resolve_bot_access_kind(u)
    if kind == 'owner':
        return (
            getattr(u, 'license_plan_owner', None) or '',
            getattr(u, 'license_expires_owner', None),
            kind,
        )
    if kind == 'assigned':
        return (
            getattr(u, 'license_plan_assigned', None) or '',
            getattr(u, 'license_expires_assigned', None),
            kind,
        )
    if kind == 'seat':
        return (
            getattr(u, 'license_plan_seat', None) or '',
            getattr(u, 'license_expires_seat', None),
            kind,
        )
    return '', None, kind


def _row_from_user(u) -> Dict[str, Any]:
    plan, expires, _kind = _primary_license_fields(u)
    access = bot_access_display(u)
    has_access = access['has_bot_license_access']
    return {
        'id': u.id,
        'name': _user_display(u),
        'username': u.username or '',
        'phone': u.phone or '',
        'email': u.email or '',
        'is_active': bool(u.is_active),
        'phone_verified': bool(getattr(u, 'phone_verified', False)),
        'date_joined': u.date_joined.isoformat() if u.date_joined else None,
        'date_joined_jalali': _jalali(u.date_joined),
        'last_login': u.last_login.isoformat() if u.last_login else None,
        'last_login_jalali': _jalali(u.last_login) or '—',
        'has_active_license': has_access,
        'has_bot_license_access': has_access,
        'has_pending_bot_activation': bool(getattr(u, 'has_pending_bot_activation', False)),
        'license_access_kind': access['license_access_kind'],
        'license_access_label': access['license_access_label'],
        'license_plan': plan,
        'license_expires_at': expires.isoformat() if expires else None,
        'license_expires_jalali': _jalali(expires) if expires else ('نامحدود' if has_access else '—'),
        'paid_orders_count': int(getattr(u, 'paid_orders_count', 0) or 0),
        'pending_orders_count': int(getattr(u, 'pending_orders_count', 0) or 0),
        'total_spent': int(getattr(u, 'total_spent', 0) or 0),
        'last_paid_at_jalali': _jalali(getattr(u, 'last_paid_at', None)) or '—',
        'windows': {
            'downloaded': bool(getattr(u, 'windows_downloaded', False)),
            'activated': bool(getattr(u, 'windows_activated', False)),
            'first_launch': bool(getattr(u, 'windows_first_launch', False)),
        },
        'android': {
            'installed': bool(getattr(u, 'has_android', False)),
            'devices_count': int(getattr(u, 'android_devices_count', 0) or 0),
            'last_seen_jalali': _jalali(getattr(u, 'android_last_seen', None)) or '—',
        },
        'datasets_count': int(getattr(u, 'datasets_count', 0) or 0),
        'listings_total': int(getattr(u, 'listings_total', 0) or 0),
        'last_dataset_jalali': _jalali(getattr(u, 'last_dataset_at', None)) or '—',
        'crm_contacts_count': int(getattr(u, 'crm_contacts_count', 0) or 0),
        'crm_deals_count': int(getattr(u, 'crm_deals_count', 0) or 0),
    }


def list_users_management(
    *,
    q: str = '',
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
    sort: str = '-date_joined',
    filters: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or PAGE_SIZE_DEFAULT), PAGE_SIZE_MAX))

    qs = _annotate_users_qs(User.objects.all())
    qs = _apply_filters(qs, q=q, filters=filters)
    qs = _sort_qs(qs, sort=sort)

    total = qs.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages

    start = (page - 1) * page_size
    rows = [_row_from_user(u) for u in qs[start:start + page_size]]

    return {
        'ok': True,
        'page': page,
        'page_size': page_size,
        'total': total,
        'total_pages': total_pages,
        'has_next': page < total_pages,
        'has_prev': page > 1,
        'results': rows,
    }


def get_user_management_detail(user_id: int) -> Optional[Dict[str, Any]]:
    qs = _annotate_users_qs(User.objects.filter(pk=user_id))
    user = qs.first()
    if not user:
        return None

    row = _row_from_user(user)

    licenses = list(
        License.objects.filter(order__user=user)
        .select_related('plan', 'order', 'order__product')
        .order_by('-created_at')[:20]
    )
    license_rows = []
    for lic in licenses:
        license_rows.append({
            'id': lic.id,
            'key_masked': f'{lic.license_key[:8]}…{lic.license_key[-4:]}' if len(lic.license_key) > 14 else lic.license_key,
            'plan': lic.plan.name if lic.plan_id else '—',
            'product': lic.order.product.title if lic.order_id and lic.order.product_id else '—',
            'status': lic.status,
            'status_label': LICENSE_STATUS_LABELS.get(lic.status, lic.status),
            'max_activations': lic.max_activations,
            'slots_used': lic.activations.count(),
            'expires_jalali': _jalali(lic.expires_at) or 'نامحدود',
            'created_jalali': _jalali(lic.created_at),
            'is_valid': lic.status == 'active' and (
                not lic.expires_at or lic.expires_at > timezone.now()
            ),
        })

    activations = list(
        LicenseActivation.objects.filter(license__order__user=user)
        .select_related('license', 'license__plan')
        .order_by('-activated_at')[:30]
    )
    activation_rows = []
    for act in activations:
        is_mobile = (act.notes or '').startswith('device_type=mobile')
        activation_rows.append({
            'id': act.id,
            'label': act.display_name,
            'platform': 'android' if is_mobile else 'windows',
            'platform_label': 'اندروید' if is_mobile else 'ویندوز',
            'is_active': act.is_active,
            'fingerprint_masked': act.masked_fingerprint,
            'activated_jalali': _jalali(act.activated_at),
            'plan': act.license.plan.name if act.license_id and act.license.plan_id else '—',
        })

    orders = list(
        Order.objects.filter(user=user)
        .select_related('product', 'plan')
        .order_by('-created_at')[:25]
    )
    order_rows = []
    for o in orders:
        order_rows.append({
            'id': str(o.id),
            'product': o.product.title if o.product_id else '—',
            'plan': o.plan.name if o.plan_id else '—',
            'amount': int(o.amount or 0),
            'status': o.status,
            'status_label': ORDER_STATUS_LABELS.get(o.status, o.status),
            'payment_method': o.get_payment_method_display() if o.payment_method else '—',
            'paid_jalali': _jalali(o.paid_at) or '—',
            'created_jalali': _jalali(o.created_at),
        })

    downloads = list(
        DownloadLog.objects.filter(user=user)
        .select_related('order', 'order__plan')
        .order_by('-created_at')[:15]
    )
    download_rows = [
        {
            'created_jalali': _jalali(d.created_at),
            'plan': d.order.plan.name if d.order_id and d.order.plan_id else '—',
            'ip': d.ip_address or '—',
        }
        for d in downloads
    ]

    launches = list(
        ClientAppEvent.objects.filter(user=user)
        .order_by('-created_at')[:20]
    )
    launch_rows = [
        {
            'event_type': ev.event_type,
            'event_label': ev.get_event_type_display(),
            'platform': ev.platform,
            'app_version': ev.app_version or '—',
            'created_jalali': _jalali(ev.created_at),
        }
        for ev in launches
    ]

    devices = list(MobileDevice.objects.filter(user=user).order_by('-last_seen_at')[:15])
    device_rows = [
        {
            'device_model': d.device_model or '—',
            'os_version': d.os_version or '—',
            'app_version': d.app_version or '—',
            'registered_jalali': _jalali(d.registered_at),
            'last_seen_jalali': _jalali(d.last_seen_at),
        }
        for d in devices
    ]

    datasets = list(
        Dataset.objects.filter(user=user, is_active=True).order_by('-created_at')[:20]
    )
    dataset_rows = [
        {
            'id': str(ds.id),
            'name': ds.name,
            'row_count': ds.row_count or 0,
            'city': ds.city or '—',
            'format': ds.file_format,
            'created_jalali': _jalali(ds.created_at),
            'last_opened_jalali': _jalali(ds.last_opened_at) or '—',
        }
        for ds in datasets
    ]

    crm_by_status = list(
        Customer.objects.filter(user=user)
        .values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    recent_customers = list(
        Customer.objects.filter(user=user).order_by('-created_at')[:10]
    )
    customer_rows = [
        {
            'name': c.name,
            'phone': c.phone or '—',
            'status': c.status,
            'type': c.customer_type,
            'created_jalali': _jalali(c.created_at),
        }
        for c in recent_customers
    ]

    deals_open = CRMDeal.objects.filter(user=user).exclude(
        stage__in=('بسته شده', 'از دست رفته', 'لغو', 'بسته', 'won', 'lost')
    ).count()
    deals_total = CRMDeal.objects.filter(user=user).count()

    # Usage summary — جواب «چقدر استفاده کرده»
    usage = {
        'datasets': row['datasets_count'],
        'listings': row['listings_total'],
        'crm_contacts': row['crm_contacts_count'],
        'crm_deals': row['crm_deals_count'],
        'crm_deals_open': deals_open,
        'windows_launches': ClientAppEvent.objects.filter(user=user).count(),
        'android_devices': row['android']['devices_count'],
        'paid_total': row['total_spent'],
        'days_since_join': max(
            0,
            (timezone.now().date() - user.date_joined.date()).days,
        ) if user.date_joined else 0,
        'days_since_login': (
            max(0, (timezone.now().date() - user.last_login.date()).days)
            if user.last_login else None
        ),
    }

    row.update({
        'licenses': license_rows,
        'activations': activation_rows,
        'orders': order_rows,
        'downloads': download_rows,
        'app_events': launch_rows,
        'android_devices': device_rows,
        'datasets': dataset_rows,
        'crm_status_breakdown': [
            {'status': s['status'] or '—', 'count': s['count']} for s in crm_by_status
        ],
        'crm_recent_contacts': customer_rows,
        'crm_deals_total': deals_total,
        'crm_deals_open': deals_open,
        'usage': usage,
    })
    return row


def export_users_management_rows() -> Tuple[List[str], List[Dict[str, Any]]]:
    headers = [
        'نام', 'موبایل', 'ایمیل', 'فعال',
        'لایسنس فعال', 'نوع دسترسی', 'پلن', 'انقضای لایسنس',
        'سفارش پرداخت‌شده', 'مجموع پرداخت (تومان)', 'آخرین پرداخت',
        'دانلود ویندوز', 'فعال‌سازی ویندوز', 'اولین اجرای ویندوز',
        'اندروید نصب', 'تعداد دستگاه اندروید', 'آخرین بازدید اندروید',
        'تعداد دیتاست', 'تعداد آگهی', 'آخرین دیتاست',
        'مخاطب CRM', 'معامله CRM',
        'آخرین ورود', 'تاریخ عضویت',
    ]
    qs = _sort_qs(_annotate_users_qs(User.objects.all()), '-date_joined')
    rows = []
    for u in qs.iterator(chunk_size=200):
        r = _row_from_user(u)
        yes_no = lambda v: 'بله' if v else 'خیر'
        rows.append({
            'نام': r['name'],
            'موبایل': r['phone'],
            'ایمیل': r['email'],
            'فعال': yes_no(r['is_active']),
            'لایسنس فعال': yes_no(r['has_active_license']),
            'نوع دسترسی': r['license_access_label'],
            'پلن': r['license_plan'],
            'انقضای لایسنس': r['license_expires_jalali'],
            'سفارش پرداخت‌شده': r['paid_orders_count'],
            'مجموع پرداخت (تومان)': r['total_spent'],
            'آخرین پرداخت': r['last_paid_at_jalali'],
            'دانلود ویندوز': yes_no(r['windows']['downloaded']),
            'فعال‌سازی ویندوز': yes_no(r['windows']['activated']),
            'اولین اجرای ویندوز': yes_no(r['windows']['first_launch']),
            'اندروید نصب': yes_no(r['android']['installed']),
            'تعداد دستگاه اندروید': r['android']['devices_count'],
            'آخرین بازدید اندروید': r['android']['last_seen_jalali'],
            'تعداد دیتاست': r['datasets_count'],
            'تعداد آگهی': r['listings_total'],
            'آخرین دیتاست': r['last_dataset_jalali'],
            'مخاطب CRM': r['crm_contacts_count'],
            'معامله CRM': r['crm_deals_count'],
            'آخرین ورود': r['last_login_jalali'],
            'تاریخ عضویت': r['date_joined_jalali'],
        })
    return headers, rows
