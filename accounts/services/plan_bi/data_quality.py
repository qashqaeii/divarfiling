"""پنل کیفیت داده و پوشش Tracking برای Plan BI."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import jdatetime
from django.db.models import Max, Min
from django.utils import timezone

from accounts.services.plan_bi import (
    EMPTY_MSG,
    SCHEMA_VERSION,
    conversion_rate,
    get_tracking_start,
    jalali_iso,
    pct,
    to_local_date,
)
from licenses.models import ClientAppEvent, LicenseActivation
from shop.models import Order, PlanFunnelEvent
from workspace.models import Customer, Dataset
from workspace.services.jalali_input import to_persian_digits


def _status(coverage: float | None, *, has_signal: bool) -> str:
    if coverage is None and not has_signal:
        return 'insufficient'
    if coverage is None:
        return 'partial'
    if coverage >= 70:
        return 'good'
    if coverage >= 30:
        return 'partial'
    if coverage > 0:
        return 'insufficient'
    return 'broken' if has_signal is False else 'insufficient'


def _item(
    key: str,
    label: str,
    *,
    status: str,
    coverage: float | None = None,
    detail: str = '',
    value: Any = None,
) -> dict[str, Any]:
    return {
        'key': key,
        'label': label,
        'status': status,
        'coverage': coverage,
        'detail': detail,
        'value': value,
        'display': detail or (EMPTY_MSG if status in ('insufficient', 'broken') else ''),
    }


def classify_order_statuses(*, since, until=None, stale_hours: int = 24) -> dict[str, Any]:
    """تفکیک pending_recent / pending_stale / abandoned / failed / paid."""
    now = timezone.now()
    stale_before = now - timedelta(hours=stale_hours)

    paid_qs = Order.objects.filter(status='paid', created_at__gte=since)
    failed_qs = Order.objects.filter(status='failed', created_at__gte=since)
    pending_qs = Order.objects.filter(
        status__in=('pending', 'pending_verification'),
        created_at__gte=since,
    )
    if until:
        paid_qs = paid_qs.filter(created_at__lt=until)
        failed_qs = failed_qs.filter(created_at__lt=until)
        pending_qs = pending_qs.filter(created_at__lt=until)

    paid_count = paid_qs.count()
    failed_count = failed_qs.count()

    pending_orders = list(pending_qs.select_related('user', 'plan'))
    pending_recent = 0
    pending_stale = 0
    abandoned = 0

    abandon_events = PlanFunnelEvent.objects.filter(
        event_type='checkout_abandon',
        created_at__gte=since,
    )
    if until:
        abandon_events = abandon_events.filter(created_at__lt=until)
    abandon_event_count = abandon_events.count()

    for order in pending_orders:
        is_stale = order.created_at <= stale_before
        uid = order.user_id
        has_later_paid = False
        if uid:
            later = Order.objects.filter(
                user_id=uid,
                status='paid',
                created_at__gt=order.created_at,
            )
            if until:
                later = later.filter(created_at__lt=until)
            has_later_paid = later.exists()

        if not is_stale:
            pending_recent += 1
            continue
        pending_stale += 1
        # abandoned فقط اگر stale + بدون paid جایگزین + (اختیاری) event تأیید
        if not has_later_paid:
            abandoned += 1

    return {
        'paid': paid_count,
        'failed': failed_count,
        'pending_recent': pending_recent,
        'pending_stale': pending_stale,
        'abandoned': abandoned if abandon_event_count > 0 else 0,
        'abandoned_available': abandon_event_count > 0,
        'abandoned_display': (
            f'{abandoned}'
            if abandon_event_count > 0
            else 'داده کافی وجود ندارد — Event رها کردن Checkout ثبت نشده'
        ),
        'pending_stale_label': 'سفارش معلق قدیمی',
        'stale_hours': stale_hours,
        'checkout_abandon_events': abandon_event_count,
    }


def build_purchase_conversions(
    *,
    pricing_views: int,
    checkout_views: int,
    paid_count: int,
    paid_in_tracking_window: int,
    linked_paid_count: int,
    tracking_reliable: bool,
) -> dict[str, Any]:
    """Conversionهای قیف خرید؛ هرگز >100٪؛ بدون پوشش کافی → null."""
    if not tracking_reliable:
        null = {
            'value': None,
            'available': False,
            'display': EMPTY_MSG,
        }
        return {
            'overall_conversion': {**null},
            'checkout_conversion': {**null},
            'funnel_conversion': {**null},
            'pricing_to_checkout': {**null},
            'checkout_to_paid': {**null},
            'pricing_to_paid': {**null},
        }

    # فقط سفارش‌های داخل پنجره Tracking و قابل اتصال
    paid_for_funnel = linked_paid_count

    def make(num, den):
        rate = conversion_rate(num, den, 2)
        return {
            'value': rate,
            'available': rate is not None,
            'display': f'{rate}٪' if rate is not None else EMPTY_MSG,
        }

    return {
        'overall_conversion': make(paid_for_funnel, pricing_views),
        'checkout_conversion': make(paid_for_funnel, checkout_views),
        'funnel_conversion': make(paid_for_funnel, pricing_views),
        'pricing_to_checkout': make(checkout_views, pricing_views),
        'checkout_to_paid': make(paid_for_funnel, checkout_views),
        'pricing_to_paid': make(paid_for_funnel, pricing_views),
        'paid_raw': paid_count,
        'paid_in_tracking_window': paid_in_tracking_window,
        'linked_paid_count': linked_paid_count,
    }


def build_data_quality(
    *,
    since,
    until=None,
    buyers: dict,
    pricing_views: int,
    checkout_views: int,
) -> dict[str, Any]:
    tracking_start = get_tracking_start()
    now = timezone.now()
    period_paid = buyers['paid_count']
    unique_buyers = buyers['unique_buyers']
    first_paid = buyers['first_paid']
    user_ids = buyers['user_ids']

    # سفارش‌های پرداخت‌شده بعد از شروع Tracking
    if tracking_start:
        paid_in_window = sum(
            1 for o in buyers['orders']
            if o.effective_paid and o.effective_paid >= tracking_start
        )
    else:
        paid_in_window = 0

    # قابل اتصال: کاربر حداقل یک pricing/checkout/payment event دارد
    linked_uids = set()
    if user_ids and tracking_start:
        ev_users = set(
            PlanFunnelEvent.objects.filter(
                user_id__in=user_ids,
                created_at__gte=tracking_start,
            ).exclude(user_id__isnull=True).values_list('user_id', flat=True)
        )
        linked_uids = ev_users & set(user_ids)
        # همچنین payment_success با order metadata
        linked_paid_count = sum(
            1 for o in buyers['orders']
            if o.effective_paid and tracking_start
            and o.effective_paid >= tracking_start
            and o.user_id in linked_uids
        )
        # اگر payment_success event برای order ثبت شده
        pay_success_users = set(
            PlanFunnelEvent.objects.filter(
                event_type='payment_success',
                user_id__in=user_ids,
            ).values_list('user_id', flat=True)
        )
        linked_uids |= pay_success_users
        linked_paid_count = sum(
            1 for o in buyers['orders']
            if o.user_id in linked_uids
            and o.effective_paid
            and tracking_start
            and o.effective_paid >= tracking_start
        )
    else:
        linked_paid_count = 0

    paid_link_coverage = pct(linked_paid_count, period_paid, 1) if period_paid else None
    # Conversion فقط وقتی Tracking مشترک و مخرج ≥ صورت (هرگز >100٪)
    tracking_reliable = bool(
        tracking_start
        and pricing_views > 0
        and checkout_views > 0
        and linked_paid_count > 0
        and linked_paid_count <= pricing_views
        and linked_paid_count <= checkout_views
        and (paid_link_coverage or 0) >= 50
    )
    # سفارش‌های دوره بیشتر از Eventها ⇒ پوشش ناقص — Conversion غیرفعال
    if period_paid > pricing_views or period_paid > checkout_views:
        tracking_reliable = False

    # Coverage signals post-purchase
    act_users = set()
    ds_users = set()
    crm_users = set()
    launch_users = set()
    if user_ids:
        act_users = set(
            LicenseActivation.objects.filter(license__order__user_id__in=user_ids)
            .values_list('license__order__user_id', flat=True).distinct()
        )
        ds_users = set(
            Dataset.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True).distinct()
        )
        crm_users = set(
            Customer.objects.filter(user_id__in=user_ids).values_list('user_id', flat=True).distinct()
        )
        launch_users = set(
            ClientAppEvent.objects.filter(
                user_id__in=user_ids,
                event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
            ).values_list('user_id', flat=True).distinct()
        )

    def cov(subset: set) -> float | None:
        if unique_buyers < 1:
            return None
        return pct(len(subset & set(user_ids)), unique_buyers, 1)

    last_event = PlanFunnelEvent.objects.aggregate(m=Max('created_at'))['m']
    first_launch_first = (
        ClientAppEvent.objects.filter(event_type=ClientAppEvent.EventType.FIRST_LAUNCH)
        .aggregate(m=Min('created_at'))['m']
    )

    # first_launch coverage: اگر activations زیاد و launch کم → insufficient
    act_n = len(act_users & set(user_ids)) if user_ids else 0
    launch_n = len(launch_users & set(user_ids)) if user_ids else 0
    first_launch_coverage = cov(launch_users)
    if act_n >= 5 and launch_n < max(1, act_n * 0.25):
        fl_status = 'insufficient'
        fl_detail = 'پوشش Event اولین اجرا ناکافی است.'
    elif first_launch_first and tracking_start and first_launch_first > tracking_start:
        fl_status = 'partial'
        fl_detail = 'Event اولین اجرا اخیراً اضافه شده؛ داده تاریخی ناقص است.'
    else:
        fl_status = _status(first_launch_coverage, has_signal=launch_n > 0)
        fl_detail = f'پوشش {first_launch_coverage}٪' if first_launch_coverage is not None else EMPTY_MSG

    ts_jalali = None
    if tracking_start:
        local = timezone.localtime(tracking_start)
        ts_jalali = to_persian_digits(
            jdatetime.datetime.fromgregorian(datetime=local).strftime('%Y/%m/%d %H:%M')
        )

    coverage_msg = (
        f"Tracking قیف خرید از تاریخ {ts_jalali or 'نامشخص'} آغاز شده و فقط "
        f"{paid_link_coverage if paid_link_coverage is not None else 0}٪ "
        f"سفارش‌های این دوره قابل اتصال به Event هستند."
        if tracking_start else
        'هنوز هیچ Event قیف خریدی ثبت نشده است.'
    )

    items = [
        _item(
            'tracking_start',
            'شروع Tracking',
            status='good' if tracking_start else 'broken',
            detail=ts_jalali or EMPTY_MSG,
            value=tracking_start.isoformat() if tracking_start else None,
        ),
        _item(
            'pricing_events',
            'پوشش بازدید قیمت',
            status=_status(pct(pricing_views, max(period_paid, 1), 1) if pricing_views else 0, has_signal=pricing_views > 0),
            coverage=None,
            detail=f'{pricing_views} رویداد',
            value=pricing_views,
        ),
        _item(
            'checkout_events',
            'پوشش Checkout',
            status=_status(None, has_signal=checkout_views > 0),
            detail=f'{checkout_views} رویداد',
            value=checkout_views,
        ),
        _item(
            'paid_linked',
            'سفارش‌های متصل به قیف',
            status=_status(paid_link_coverage, has_signal=linked_paid_count > 0),
            coverage=paid_link_coverage,
            detail=coverage_msg,
            value=linked_paid_count,
        ),
        _item(
            'license_activation',
            'پوشش فعال‌سازی لایسنس',
            status=_status(cov(act_users), has_signal=act_n > 0),
            coverage=cov(act_users),
            detail=f'{act_n} از {unique_buyers} خریدار',
        ),
        _item(
            'first_launch',
            'پوشش اولین اجرا',
            status=fl_status,
            coverage=first_launch_coverage,
            detail=fl_detail,
        ),
        _item(
            'dataset',
            'پوشش دیتاست',
            status=_status(cov(ds_users), has_signal=bool(ds_users)),
            coverage=cov(ds_users),
        ),
        _item(
            'crm',
            'پوشش CRM',
            status=_status(cov(crm_users), has_signal=bool(crm_users)),
            coverage=cov(crm_users),
        ),
        _item(
            'cohort_maturity',
            'بلوغ کوهورت',
            status='partial',
            detail='شاخص‌های ۷روزه/۳۰روزه فقط برای کوهورت‌های بالغ محاسبه می‌شوند',
        ),
        _item(
            'excluded_test',
            'رکوردهای داخلی/تست',
            status='good',
            detail='فیلتر اختصاصی تست در V1 اعمال نشده',
            value=0,
        ),
        _item(
            'last_event',
            'آخرین Event دریافتی',
            status='good' if last_event else 'broken',
            detail=(
                to_persian_digits(
                    jdatetime.datetime.fromgregorian(
                        datetime=timezone.localtime(last_event),
                    ).strftime('%Y/%m/%d %H:%M')
                ) if last_event else EMPTY_MSG
            ),
            value=last_event.isoformat() if last_event else None,
        ),
        _item(
            'schema_version',
            'نسخه Schema',
            status='good',
            detail=SCHEMA_VERSION,
            value=SCHEMA_VERSION,
        ),
    ]

    conversions = build_purchase_conversions(
        pricing_views=pricing_views,
        checkout_views=checkout_views,
        paid_count=period_paid,
        paid_in_tracking_window=paid_in_window,
        linked_paid_count=linked_paid_count,
        tracking_reliable=tracking_reliable,
    )

    return {
        'tracking_start': tracking_start.isoformat() if tracking_start else None,
        'tracking_start_jalali': ts_jalali,
        'schema_version': SCHEMA_VERSION,
        'coverage_message': coverage_msg,
        'paid_link_coverage': paid_link_coverage,
        'linked_paid_count': linked_paid_count,
        'paid_in_tracking_window': paid_in_window,
        'tracking_reliable': tracking_reliable,
        'first_launch_coverage': {
            'status': fl_status,
            'coverage': first_launch_coverage,
            'detail': fl_detail,
            'available': fl_status == 'good',
        },
        'items': items,
        'conversions': conversions,
        'funnel_conversions_available': tracking_reliable,
    }
