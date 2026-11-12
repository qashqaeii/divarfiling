"""خروجی گزارش‌های پنل مدیریت — CSV و Excel."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Tuple

import jdatetime
from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, Max, OuterRef, Q, Sum
from django.http import HttpResponse
from django.utils import timezone

from affiliates.models import AffiliateSale, Withdrawal
from licenses.models import License
from shop.models import CardTransferSubmission, Order
from workspace.models import Ticket

from workspace.services.jalali_input import to_persian_digits

User = get_user_model()

from accounts.services.pending_orders import PENDING_ORDER_STATUSES


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
    return user.get_full_name() or user.username or ''


ExportRow = Dict[str, Any]
ExportBuilder = Callable[[], Tuple[List[str], Iterable[ExportRow]]]


def _pending_orders_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'شناسه سفارش', 'نام کاربر', 'موبایل', 'ایمیل', 'محصول', 'پلن',
        'مبلغ (تومان)', 'وضعیت', 'روش پرداخت', 'تاریخ ایجاد',
    ]
    qs = (
        Order.objects.filter(status__in=PENDING_ORDER_STATUSES)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')
    )
    rows = [
        {
            'شناسه سفارش': str(o.id),
            'نام کاربر': _user_display(o.user),
            'موبایل': o.user.phone or '',
            'ایمیل': o.user.email or '',
            'محصول': o.product.title,
            'پلن': o.plan.name,
            'مبلغ (تومان)': int(o.amount),
            'وضعیت': o.get_status_display(),
            'روش پرداخت': o.get_payment_method_display(),
            'تاریخ ایجاد': _jalali(o.created_at),
        }
        for o in qs
    ]
    return headers, rows


def _users_with_pending_orders_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'نام', 'موبایل', 'ایمیل', 'تعداد سفارش معلق', 'مجموع مبلغ معلق (تومان)',
        'آخرین سفارش', 'محصولات', 'تاریخ عضویت',
    ]
    qs = (
        User.objects.filter(orders__status__in=PENDING_ORDER_STATUSES)
        .annotate(
            pending_count=Count('orders', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
            pending_total=Sum('orders__amount', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
            last_pending=Max('orders__created_at', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
        )
        .distinct()
        .order_by('-last_pending')
    )
    rows = []
    for u in qs:
        products = (
            Order.objects.filter(user=u, status__in=PENDING_ORDER_STATUSES)
            .values_list('product__title', flat=True)
            .distinct()
        )
        rows.append({
            'نام': _user_display(u),
            'موبایل': u.phone or '',
            'ایمیل': u.email or '',
            'تعداد سفارش معلق': u.pending_count,
            'مجموع مبلغ معلق (تومان)': int(u.pending_total or 0),
            'آخرین سفارش': _jalali(u.last_pending),
            'محصولات': ' | '.join(products),
            'تاریخ عضویت': _jalali(u.date_joined),
        })
    return headers, rows


def _paid_orders_rows(days: int | None = None) -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'شناسه سفارش', 'نام کاربر', 'موبایل', 'محصول', 'پلن', 'مبلغ (تومان)',
        'تخفیف (تومان)', 'روش پرداخت', 'تاریخ پرداخت', 'تاریخ ایجاد',
    ]
    from accounts.services.admin_dashboard import paid_orders_queryset_for_panel_days

    qs = Order.objects.filter(status='paid', paid_at__isnull=False).select_related('user', 'product', 'plan')
    if days is not None:
        qs = paid_orders_queryset_for_panel_days(days)
    qs = qs.order_by('-paid_at')
    rows = [
        {
            'شناسه سفارش': str(o.id),
            'نام کاربر': _user_display(o.user),
            'موبایل': o.user.phone or '',
            'محصول': o.product.title,
            'پلن': o.plan.name,
            'مبلغ (تومان)': int(o.amount),
            'تخفیف (تومان)': int(o.discount_amount or 0),
            'روش پرداخت': o.get_payment_method_display(),
            'تاریخ پرداخت': _jalali(o.paid_at),
            'تاریخ ایجاد': _jalali(o.created_at),
        }
        for o in qs
    ]
    return headers, rows


def _failed_orders_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'شناسه سفارش', 'نام کاربر', 'موبایل', 'محصول', 'پلن', 'مبلغ (تومان)',
        'وضعیت', 'روش پرداخت', 'تاریخ',
    ]
    qs = (
        Order.objects.filter(status__in=('failed', 'cancelled'))
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')
    )
    rows = [
        {
            'شناسه سفارش': str(o.id),
            'نام کاربر': _user_display(o.user),
            'موبایل': o.user.phone or '',
            'محصول': o.product.title,
            'پلن': o.plan.name,
            'مبلغ (تومان)': int(o.amount),
            'وضعیت': o.get_status_display(),
            'روش پرداخت': o.get_payment_method_display(),
            'تاریخ': _jalali(o.created_at),
        }
        for o in qs
    ]
    return headers, rows


def _all_users_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'نام', 'نام کاربری', 'موبایل', 'ایمیل', 'فعال', 'staff',
        'تعداد سفارش پرداخت‌شده', 'لایسنس فعال', 'تاریخ عضویت',
    ]
    from workspace.services.bot_license_query import annotate_user_bot_license_access

    qs = annotate_user_bot_license_access(
        User.objects.annotate(
            paid_orders=Count('orders', filter=Q(orders__status='paid')),
        )
    ).order_by('-date_joined')
    rows = [
        {
            'نام': _user_display(u),
            'نام کاربری': u.username,
            'موبایل': u.phone or '',
            'ایمیل': u.email or '',
            'فعال': 'بله' if u.is_active else 'خیر',
            'staff': 'بله' if u.is_staff else 'خیر',
            'تعداد سفارش پرداخت‌شده': u.paid_orders,
            'لایسنس فعال': 'بله' if u.has_active_license else 'خیر',
            'تاریخ عضویت': _jalali(u.date_joined),
        }
        for u in qs
    ]
    return headers, rows


def _new_users_rows(days: int = 30) -> Tuple[List[str], Iterable[ExportRow]]:
    headers = ['نام', 'موبایل', 'ایمیل', 'سفارش پرداخت‌شده', 'تاریخ عضویت']
    from accounts.services.admin_dashboard import all_time_start_date, is_all_time_range

    if is_all_time_range(days):
        since = timezone.make_aware(
            datetime.combine(all_time_start_date(), datetime.min.time()),
            timezone.get_current_timezone(),
        )
    else:
        since = timezone.now() - timedelta(days=days)
    qs = (
        User.objects.filter(date_joined__gte=since)
        .annotate(paid_orders=Count('orders', filter=Q(orders__status='paid')))
        .order_by('-date_joined')
    )
    rows = [
        {
            'نام': _user_display(u),
            'موبایل': u.phone or '',
            'ایمیل': u.email or '',
            'سفارش پرداخت‌شده': u.paid_orders,
            'تاریخ عضویت': _jalali(u.date_joined),
        }
        for u in qs
    ]
    return headers, rows


def _users_without_license_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'نام', 'موبایل', 'ایمیل', 'سفارش پرداخت‌شده', 'سفارش معلق',
        'تاریخ عضویت',
    ]
    from workspace.services.bot_license_query import users_without_bot_license_qs

    qs = (
        users_without_bot_license_qs(User.objects.filter(is_active=True))
        .annotate(
            paid_orders=Count('orders', filter=Q(orders__status='paid')),
            pending_orders=Count('orders', filter=Q(orders__status__in=PENDING_ORDER_STATUSES)),
        )
        .order_by('-date_joined')
    )
    rows = [
        {
            'نام': _user_display(u),
            'موبایل': u.phone or '',
            'ایمیل': u.email or '',
            'سفارش پرداخت‌شده': u.paid_orders,
            'سفارش معلق': u.pending_orders,
            'تاریخ عضویت': _jalali(u.date_joined),
        }
        for u in qs
    ]
    return headers, rows


def _active_licenses_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'کلید لایسنس', 'نام کاربر', 'موبایل', 'پلن', 'وضعیت',
        'حداکثر فعال‌سازی', 'دستگاه‌های فعال', 'تاریخ انقضا', 'تاریخ ایجاد',
    ]
    now = timezone.now()
    qs = (
        License.objects.filter(status='active')
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .select_related('order__user', 'plan')
        .prefetch_related('activations')
        .order_by('-created_at')
    )
    rows = []
    for lic in qs:
        active_devices = lic.activations.filter(is_active=True).count()
        rows.append({
            'کلید لایسنس': lic.license_key,
            'نام کاربر': _user_display(lic.order.user),
            'موبایل': lic.order.user.phone or '',
            'پلن': lic.plan.name,
            'وضعیت': lic.get_status_display(),
            'حداکثر فعال‌سازی': lic.max_activations,
            'دستگاه‌های فعال': active_devices,
            'تاریخ انقضا': _jalali(lic.expires_at) or 'نامحدود',
            'تاریخ ایجاد': _jalali(lic.created_at),
        })
    return headers, rows


def _expiring_licenses_rows(days: int = 14) -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'کلید لایسنس', 'نام کاربر', 'موبایل', 'ایمیل', 'پلن',
        'روز تا انقضا', 'تاریخ انقضا',
    ]
    now = timezone.now()
    deadline = now + timedelta(days=days)
    qs = (
        License.objects.filter(
            status='active',
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=deadline,
        )
        .select_related('order__user', 'plan')
        .order_by('expires_at')
    )
    rows = []
    for lic in qs:
        days_left = (lic.expires_at - now).days
        rows.append({
            'کلید لایسنس': lic.license_key,
            'نام کاربر': _user_display(lic.order.user),
            'موبایل': lic.order.user.phone or '',
            'ایمیل': lic.order.user.email or '',
            'پلن': lic.plan.name,
            'روز تا انقضا': to_persian_digits(days_left),
            'تاریخ انقضا': _jalali(lic.expires_at),
        })
    return headers, rows


def _expired_licenses_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'کلید لایسنس', 'نام کاربر', 'موبایل', 'پلن', 'تاریخ انقضا',
    ]
    qs = (
        License.objects.filter(status='expired')
        .select_related('order__user', 'plan')
        .order_by('-expires_at')
    )
    rows = [
        {
            'کلید لایسنس': lic.license_key,
            'نام کاربر': _user_display(lic.order.user),
            'موبایل': lic.order.user.phone or '',
            'پلن': lic.plan.name,
            'تاریخ انقضا': _jalali(lic.expires_at),
        }
        for lic in qs
    ]
    return headers, rows


def _card_transfers_pending_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'شناسه سفارش', 'نام کاربر', 'موبایل', 'مبلغ (تومان)', 'شماره پیگیری',
        'نام پرداخت‌کننده', 'تاریخ ثبت',
    ]
    qs = (
        CardTransferSubmission.objects.filter(status='pending')
        .select_related('order__user', 'order')
        .order_by('-created_at')
    )
    rows = [
        {
            'شناسه سفارش': str(ct.order_id),
            'نام کاربر': _user_display(ct.order.user),
            'موبایل': ct.order.user.phone or '',
            'مبلغ (تومان)': int(ct.order.amount),
            'شماره پیگیری': ct.reference_number,
            'نام پرداخت‌کننده': ct.payer_name or '',
            'تاریخ ثبت': _jalali(ct.created_at),
        }
        for ct in qs
    ]
    return headers, rows


def _open_tickets_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'شماره تیکت', 'موضوع', 'کاربر', 'موبایل', 'دسته', 'اولویت', 'وضعیت',
        'خوانده‌نشده', 'آخرین پیام', 'تاریخ ایجاد',
    ]
    qs = (
        Ticket.objects.exclude(status='closed')
        .select_related('user')
        .order_by('-staff_has_unread', '-last_message_at')
    )
    rows = [
        {
            'شماره تیکت': t.ticket_number,
            'موضوع': t.subject,
            'کاربر': _user_display(t.user),
            'موبایل': t.user.phone or '',
            'دسته': t.get_category_display_fa(),
            'اولویت': t.get_priority_display_fa(),
            'وضعیت': t.get_status_display_fa(),
            'خوانده‌نشده': 'بله' if t.staff_has_unread else 'خیر',
            'آخرین پیام': _jalali(t.last_message_at or t.updated_at),
            'تاریخ ایجاد': _jalali(t.created_at),
        }
        for t in qs
    ]
    return headers, rows


def _affiliate_sales_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'کد مشاور', 'نام مشاور', 'مبلغ سفارش', 'کمیسیون', 'وضعیت', 'تاریخ',
    ]
    qs = (
        AffiliateSale.objects.select_related('affiliate__user', 'order')
        .order_by('-created_at')
    )
    rows = [
        {
            'کد مشاور': s.affiliate.code,
            'نام مشاور': _user_display(s.affiliate.user),
            'مبلغ سفارش': int(s.order.amount),
            'کمیسیون': int(s.commission_amount),
            'وضعیت': s.get_status_display(),
            'تاریخ': _jalali(s.created_at),
        }
        for s in qs
    ]
    return headers, rows


def _pending_withdrawals_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    headers = [
        'کاربر', 'موبایل', 'مبلغ (تومان)', 'بانک', 'شماره حساب', 'تاریخ درخواست',
    ]
    qs = (
        Withdrawal.objects.filter(status='pending')
        .select_related('wallet__user')
        .order_by('-created_at')
    )
    rows = [
        {
            'کاربر': _user_display(w.wallet.user),
            'موبایل': w.wallet.user.phone or '',
            'مبلغ (تومان)': int(w.amount),
            'بانک': w.bank_name,
            'شماره حساب': w.bank_account,
            'تاریخ درخواست': _jalali(w.created_at),
        }
        for w in qs
    ]
    return headers, rows


def _windows_downloads_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    from shop.models import DownloadLog

    headers = ['کاربر', 'موبایل', 'پلن', 'محصول', 'IP', 'User Agent', 'تاریخ دانلود']
    qs = (
        DownloadLog.objects.select_related('user', 'order', 'order__plan', 'order__product')
        .order_by('-created_at')
    )
    rows = [
        {
            'کاربر': _user_display(log.user),
            'موبایل': log.user.phone or '',
            'پلن': log.order.plan.name if log.order.plan_id else '',
            'محصول': log.order.product.title if log.order.product_id else '',
            'IP': log.ip_address or '',
            'User Agent': log.user_agent or '',
            'تاریخ دانلود': _jalali(log.created_at),
        }
        for log in qs
    ]
    return headers, rows


def _windows_first_launches_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    from licenses.models import ClientAppEvent

    headers = ['کاربر', 'موبایل', 'پلن', 'نسخه اپ', 'شناسه دستگاه', 'IP', 'تاریخ']
    qs = (
        ClientAppEvent.objects.filter(event_type=ClientAppEvent.EventType.FIRST_LAUNCH)
        .select_related('user', 'license', 'license__plan')
        .order_by('-created_at')
    )
    rows = [
        {
            'کاربر': _user_display(ev.user),
            'موبایل': ev.user.phone or '',
            'پلن': ev.license.plan.name if ev.license.plan_id else '',
            'نسخه اپ': ev.app_version or '',
            'شناسه دستگاه': ev.hardware_fingerprint,
            'IP': ev.ip_address or '',
            'تاریخ': _jalali(ev.created_at),
        }
        for ev in qs
    ]
    return headers, rows


def _android_devices_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    from mobile_api.models import MobileDevice

    headers = [
        'کاربر', 'موبایل', 'مدل دستگاه', 'اندروید', 'نسخه اپ',
        'فعال', 'تاریخ ثبت', 'آخرین استفاده', 'پلن',
    ]
    qs = (
        MobileDevice.objects.select_related(
            'user',
            'license_activation',
            'license_activation__license',
            'license_activation__license__plan',
        )
        .order_by('-registered_at')
    )
    rows = []
    for device in qs:
        activation = device.license_activation
        plan_name = ''
        if activation and activation.license_id and activation.license.plan_id:
            plan_name = activation.license.plan.name
        rows.append({
            'کاربر': _user_display(device.user),
            'موبایل': device.user.phone or '',
            'مدل دستگاه': device.device_model or '',
            'اندروید': device.os_version or '',
            'نسخه اپ': device.app_version or '',
            'فعال': 'بله' if device.is_active else 'خیر',
            'تاریخ ثبت': _jalali(device.registered_at),
            'آخرین استفاده': _jalali(device.last_seen_at),
            'پلن': plan_name,
        })
    return headers, rows


def _android_active_devices_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    from mobile_api.models import MobileDevice

    headers = ['کاربر', 'موبایل', 'مدل دستگاه', 'نسخه اپ', 'آخرین استفاده']
    qs = (
        MobileDevice.objects.filter(is_active=True)
        .select_related('user')
        .order_by('-last_seen_at')
    )
    rows = [
        {
            'کاربر': _user_display(device.user),
            'موبایل': device.user.phone or '',
            'مدل دستگاه': device.device_model or '',
            'نسخه اپ': device.app_version or '',
            'آخرین استفاده': _jalali(device.last_seen_at),
        }
        for device in qs
    ]
    return headers, rows


def _users_management_export_rows() -> Tuple[List[str], Iterable[ExportRow]]:
    from accounts.services.admin_users_management import export_users_management_rows
    return export_users_management_rows()


def _growth_journeys_rows(stage: str | None = None) -> Tuple[List[str], Iterable[ExportRow]]:
    from accounts.models import GrowthJourney
    from accounts.services.growth_journey import journey_display_name, journey_extraction_district

    headers = ['شماره تماس', 'نام یا نام آژانس', 'منطقه استخراج']
    qs = GrowthJourney.objects.select_related(
        'user',
        'lead',
        'lead__first_batch',
        'user__workspace_settings',
    ).order_by(
        'phone_normalized',
    )
    if stage:
        qs = qs.filter(stage=stage)
    rows = [
        {
            'شماره تماس': j.phone_normalized,
            'نام یا نام آژانس': journey_display_name(j),
            'منطقه استخراج': journey_extraction_district(j),
        }
        for j in qs.iterator(chunk_size=500)
    ]
    return headers, rows


EXPORT_REGISTRY: Dict[str, Dict[str, Any]] = {
    'pending_orders': {
        'title': 'سفارش‌های پرداخت‌نشده',
        'description': 'تمام سفارش‌های در انتظار پرداخت یا تایید',
        'category': 'orders',
        'icon': 'fa-clock',
        'accent': 'amber',
        'builder': _pending_orders_rows,
    },
    'users_pending_payment': {
        'title': 'کاربران با سفارش معلق',
        'description': 'کاربرانی که سفارش پرداخت‌نشده یا در انتظار تایید دارند',
        'category': 'users',
        'icon': 'fa-user-clock',
        'accent': 'rose',
        'builder': _users_with_pending_orders_rows,
    },
    'paid_orders': {
        'title': 'سفارش‌های پرداخت‌شده',
        'description': 'فروش موفق — قابل فیلتر بر اساس بازه زمانی',
        'category': 'orders',
        'icon': 'fa-circle-check',
        'accent': 'emerald',
        'builder': lambda: _paid_orders_rows(),
        'supports_days': True,
    },
    'failed_orders': {
        'title': 'سفارش‌های ناموفق / لغوشده',
        'description': 'سفارش‌های failed و cancelled',
        'category': 'orders',
        'icon': 'fa-circle-xmark',
        'accent': 'red',
        'builder': _failed_orders_rows,
    },
    'all_users': {
        'title': 'همه کاربران',
        'description': 'لیست کامل کاربران با وضعیت لایسنس',
        'category': 'users',
        'icon': 'fa-users',
        'accent': 'violet',
        'builder': _all_users_rows,
    },
    'users_management': {
        'title': 'مدیریت کاربران (تحلیل کامل)',
        'description': 'لایسنس، پرداخت، ویندوز/اندروید، دیتاست و CRM',
        'category': 'users',
        'icon': 'fa-users-gear',
        'accent': 'indigo',
        'builder': _users_management_export_rows,
    },
    'new_users': {
        'title': 'کاربران جدید',
        'description': 'ثبت‌نام‌های اخیر',
        'category': 'users',
        'icon': 'fa-user-plus',
        'accent': 'blue',
        'builder': lambda: _new_users_rows(30),
        'supports_days': True,
    },
    'users_without_license': {
        'title': 'کاربران بدون لایسنس فعال',
        'description': 'مناسب برای پیگیری فروش و بازاریابی',
        'category': 'users',
        'icon': 'fa-user-slash',
        'accent': 'cyan',
        'builder': _users_without_license_rows,
    },
    'active_licenses': {
        'title': 'لایسنس‌های فعال',
        'description': 'کلید، پلن، انقضا و دستگاه‌های فعال',
        'category': 'licenses',
        'icon': 'fa-key',
        'accent': 'emerald',
        'builder': _active_licenses_rows,
    },
    'expiring_licenses': {
        'title': 'لایسنس‌های در شرف انقضا',
        'description': '۱۴ روز آینده — برای تمدید و پیگیری',
        'category': 'licenses',
        'icon': 'fa-hourglass-half',
        'accent': 'amber',
        'builder': lambda: _expiring_licenses_rows(14),
    },
    'expired_licenses': {
        'title': 'لایسنس‌های منقضی',
        'description': 'فرصت تمدید و بازگشت مشتری',
        'category': 'licenses',
        'icon': 'fa-ban',
        'accent': 'red',
        'builder': _expired_licenses_rows,
    },
    'card_transfers_pending': {
        'title': 'کارت‌به‌کارت در انتظار',
        'description': 'رسیدهای نیازمند تایید دستی',
        'category': 'finance',
        'icon': 'fa-money-check',
        'accent': 'amber',
        'builder': _card_transfers_pending_rows,
    },
    'open_tickets': {
        'title': 'تیکت‌های باز',
        'description': 'پشتیبانی — تیکت‌های بسته‌نشده',
        'category': 'support',
        'icon': 'fa-headset',
        'accent': 'blue',
        'builder': _open_tickets_rows,
    },
    'affiliate_sales': {
        'title': 'فروش‌های افیلیت',
        'description': 'کمیسیون مشاوران فروش',
        'category': 'finance',
        'icon': 'fa-handshake',
        'accent': 'violet',
        'builder': _affiliate_sales_rows,
    },
    'pending_withdrawals': {
        'title': 'درخواست‌های برداشت',
        'description': 'برداشت‌های در انتظار تایید',
        'category': 'finance',
        'icon': 'fa-wallet',
        'accent': 'rose',
        'builder': _pending_withdrawals_rows,
    },
    'windows_downloads': {
        'title': 'دانلود اپ ویندوز',
        'description': 'کاربرانی که فایل نصب را از سایت دانلود کرده‌اند',
        'category': 'licenses',
        'icon': 'fa-download',
        'accent': 'blue',
        'builder': _windows_downloads_rows,
    },
    'windows_first_launches': {
        'title': 'اولین اجرای اپ ویندوز',
        'description': 'اولین اجرای موفق اپ پس از فعال‌سازی لایسنس',
        'category': 'licenses',
        'icon': 'fa-play',
        'accent': 'emerald',
        'builder': _windows_first_launches_rows,
    },
    'android_devices': {
        'title': 'دستگاه‌های اندروید',
        'description': 'ثبت دستگاه، نسخه اپ و آخرین استفاده',
        'category': 'licenses',
        'icon': 'fa-mobile-alt',
        'accent': 'green',
        'builder': _android_devices_rows,
    },
    'android_active_devices': {
        'title': 'دستگاه‌های فعال اندروید',
        'description': 'کاربران با دستگاه فعال و آخرین بازدید',
        'category': 'licenses',
        'icon': 'fa-signal',
        'accent': 'teal',
        'builder': _android_active_devices_rows,
    },
    'ai_usage': {
        'title': 'مصرف هوش مصنوعی',
        'description': 'خلاصه، قابلیت‌ها، مدل‌ها، کاربران برتر و لاگ AI',
        'category': 'analytics',
        'icon': 'fa-brain',
        'accent': 'violet',
        'builder': None,
        'supports_days': True,
        'multisheet': True,
    },
    'growth_journeys': {
        'title': 'پرونده‌های پایپلاین رشد',
        'description': 'همه سرنخ‌ها و مسیرهای رشد — شماره و نام/آژانس',
        'category': 'marketing',
        'icon': 'fa-route',
        'accent': 'violet',
        'builder': lambda: _growth_journeys_rows(),
        'supports_stage': True,
    },
}


def get_export_count(export_key: str, days: int | None = None) -> int:
    """تعداد ردیف هر گزارش برای نمایش در داشبورد."""
    from accounts.services.admin_dashboard import all_time_start_date, is_all_time_range

    meta = EXPORT_REGISTRY.get(export_key)
    if not meta:
        return 0
    if export_key == 'paid_orders' and days is not None:
        from accounts.services.admin_dashboard import paid_orders_queryset_for_panel_days

        return paid_orders_queryset_for_panel_days(days).count()
    if export_key == 'new_users' and days is not None:
        if is_all_time_range(days):
            since = timezone.make_aware(
                datetime.combine(all_time_start_date(), datetime.min.time()),
                timezone.get_current_timezone(),
            )
        else:
            since = timezone.now() - timedelta(days=days)
        return User.objects.filter(date_joined__gte=since).count()
    if export_key == 'growth_journeys':
        from accounts.models import GrowthJourney

        return GrowthJourney.objects.count()
    if meta.get('multisheet') and days is not None:
        from accounts.services.admin_ai_center import _logs_in_range

        return _logs_in_range(days).count()
    if not meta.get('builder'):
        return 0
    _, rows = meta['builder']()
    if isinstance(rows, list):
        return len(rows)
    return len(list(rows))


def get_export_catalog(days: int = 30) -> List[Dict[str, Any]]:
    """کاتالوگ گزارش‌ها با تعداد ردیف."""
    catalog = []
    for key, meta in EXPORT_REGISTRY.items():
        d = days if meta.get('supports_days') else None
        catalog.append({
            'key': key,
            'title': meta['title'],
            'description': meta['description'],
            'category': meta['category'],
            'icon': meta['icon'],
            'accent': meta['accent'],
            'count': get_export_count(key, days=d),
            'supports_days': meta.get('supports_days', False),
        })
    return catalog


def build_export(
    export_key: str,
    fmt: str = 'xlsx',
    days: int | None = None,
    stage: str | None = None,
) -> HttpResponse:
    meta = EXPORT_REGISTRY.get(export_key)
    if not meta:
        return HttpResponse('گزارش یافت نشد', status=404)

    if meta.get('multisheet'):
        if fmt == 'csv':
            return HttpResponse('این گزارش فقط Excel است', status=400)
        from accounts.services.admin_dashboard import ALL_TIME_DAYS, is_all_time_range
        from accounts.services.admin_ai_center import ai_usage_export_sheets

        export_days = days if days is not None else ALL_TIME_DAYS
        sheets = ai_usage_export_sheets(export_days)
        filename_base = f'filing-divar-{export_key}'
        filename_base += '-all' if is_all_time_range(export_days) else f'-{export_days}d'
        return _build_multisheet_xlsx_response(sheets, filename_base, meta['title'])

    builder = meta['builder']
    if export_key == 'growth_journeys':
        headers, rows = _growth_journeys_rows(stage=stage)
    elif meta.get('supports_days') and days is not None:
        if export_key == 'paid_orders':
            headers, rows = _paid_orders_rows(days=days)
        elif export_key == 'new_users':
            headers, rows = _new_users_rows(days=days)
        else:
            headers, rows = builder()
    else:
        headers, rows = builder()

    if not isinstance(rows, list):
        rows = list(rows)

    filename_base = f'filing-divar-{export_key}'
    if days is not None and meta.get('supports_days'):
        from accounts.services.admin_dashboard import is_all_time_range

        filename_base += '-all' if is_all_time_range(days) else f'-{days}d'
    if stage and meta.get('supports_stage'):
        filename_base += f'-{stage}'

    if fmt == 'csv':
        return _build_csv_response(headers, rows, filename_base)
    return _build_xlsx_response(headers, rows, filename_base, meta['title'])


def _build_csv_response(headers: List[str], rows: List[ExportRow], filename_base: str) -> HttpResponse:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    response = HttpResponse('\ufeff' + buffer.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
    return response


def _build_multisheet_xlsx_response(
    sheets: List[tuple],
    filename_base: str,
    workbook_title: str,
) -> HttpResponse:
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    for idx, (title, headers, rows) in enumerate(sheets):
        ws = wb.create_sheet(title=title[:31], index=idx)
        ws.sheet_view.rightToLeft = True
        _write_xlsx_sheet(ws, headers, rows if isinstance(rows, list) else list(rows))
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename_base}.xlsx"'
    return response


def _write_xlsx_sheet(ws, headers: List[str], rows: List[ExportRow]) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    header_fill = PatternFill(start_color='7C3AED', end_color='7C3AED', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF', name='Tahoma', size=10)
    body_font = Font(name='Tahoma', size=10)

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')

    for row_idx, row in enumerate(rows, 2):
        for col_idx, header in enumerate(headers, 1):
            val = row.get(header, '')
            if hasattr(val, 'tzinfo') and val.tzinfo is not None:
                val = timezone.localtime(val).replace(tzinfo=None)
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = body_font
            cell.alignment = Alignment(horizontal='right', vertical='center')

    for col_idx, header in enumerate(headers, 1):
        max_len = len(str(header))
        for row in rows[:200]:
            val = str(row.get(header, ''))
            max_len = max(max_len, len(val))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 48)

    ws.freeze_panes = 'A2'


def _build_xlsx_response(
    headers: List[str],
    rows: List[ExportRow],
    filename_base: str,
    sheet_title: str,
) -> HttpResponse:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    ws.sheet_view.rightToLeft = True
    _write_xlsx_sheet(ws, headers, rows)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename_base}.xlsx"'
    return response
