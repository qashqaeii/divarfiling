"""پنل کیفیت داده و پوشش Tracking برای Plan BI."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import jdatetime
from django.db.models import Max, Min
from django.utils import timezone

from accounts.services.plan_bi import (
    EMPTY_MSG,
    POST_TRACKING_COVERAGE_GOOD_PCT,
    POST_TRACKING_COVERAGE_LOCK_PCT,
    POST_TRACKING_COVERAGE_MIN_PCT,
    POST_TRACKING_MIN_SAMPLE,
    SCHEMA_VERSION,
    conversion_rate,
    get_tracking_start,
    jalali_iso,
    pct,
    to_local_date,
)
from licenses.models import ClientAppEvent, LicenseActivation
from shop.models import Order, PlanFunnelEvent
from shop.services.plan_funnel import is_bi_production_order
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
    conversion_provisional: bool = False,
) -> dict[str, Any]:
    """Conversionهای قیف خرید؛ هرگز >100٪؛ بدون پوشش کافی → null."""
    if not tracking_reliable and not conversion_provisional:
        null = {
            'value': None,
            'available': False,
            'display': EMPTY_MSG,
            'provisional': False,
        }
        return {
            'overall_conversion': {**null},
            'checkout_conversion': {**null},
            'funnel_conversion': {**null},
            'pricing_to_checkout': {**null},
            'checkout_to_paid': {**null},
            'pricing_to_paid': {**null},
        }

    paid_for_funnel = linked_paid_count
    warn = ' — موقت و کم‌اطمینان' if conversion_provisional else ''

    def make(num, den):
        rate = conversion_rate(num, den, 2)
        return {
            'value': rate,
            'available': rate is not None,
            'display': (f'{rate}٪{warn}' if rate is not None else EMPTY_MSG),
            'provisional': conversion_provisional,
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
        'provisional': conversion_provisional,
    }


def _order_linked_to_funnel(order, *, linked_user_ids: set, payment_success_order_ids: set) -> bool:
    """اتصال معتبر: Event payment_success برای همان order_id."""
    return str(order.pk) in payment_success_order_ids


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

    # فقط سفارش‌های Production (بدون staff / FAKE-)
    prod_orders = [o for o in buyers['orders'] if is_bi_production_order(o)]
    period_paid = len(prod_orders)
    user_ids = list({o.user_id for o in prod_orders if o.user_id})
    unique_buyers = len(user_ids)
    first_paid = {
        uid: min(o.effective_paid for o in prod_orders if o.user_id == uid and o.effective_paid)
        for uid in user_ids
    }

    payment_success_order_ids: set[str] = set()
    linked_user_ids: set = set()
    if tracking_start:
        ps_qs = PlanFunnelEvent.objects.filter(event_type='payment_success')
        for row in ps_qs.values_list('order_id', 'metadata', 'user_id'):
            oid, meta, uid = row
            if oid:
                payment_success_order_ids.add(str(oid))
            elif isinstance(meta, dict) and meta.get('order_id'):
                payment_success_order_ids.add(str(meta['order_id']))
            if uid:
                linked_user_ids.add(uid)
        linked_user_ids |= set(
            PlanFunnelEvent.objects.filter(
                created_at__gte=tracking_start,
            ).exclude(user_id__isnull=True).values_list('user_id', flat=True)
        )

    # Historical: همه paid دوره (Production)
    hist_linked = sum(
        1 for o in prod_orders
        if _order_linked_to_funnel(
            o, linked_user_ids=linked_user_ids, payment_success_order_ids=payment_success_order_ids,
        )
    )
    historical_coverage = pct(hist_linked, period_paid, 1) if period_paid else None

    # Post-tracking: فقط بعد از tracking_start
    if tracking_start:
        post_orders = [
            o for o in prod_orders
            if o.effective_paid and o.effective_paid >= tracking_start
        ]
    else:
        post_orders = []
    paid_in_window = len(post_orders)
    post_linked = sum(
        1 for o in post_orders
        if _order_linked_to_funnel(
            o, linked_user_ids=linked_user_ids, payment_success_order_ids=payment_success_order_ids,
        )
    )
    post_tracking_coverage = pct(post_linked, paid_in_window, 1) if paid_in_window else None

    sample_sufficient = paid_in_window >= POST_TRACKING_MIN_SAMPLE
    cov_pct = post_tracking_coverage or 0.0
    coverage_locked = cov_pct < POST_TRACKING_COVERAGE_LOCK_PCT
    coverage_good = cov_pct >= POST_TRACKING_COVERAGE_GOOD_PCT
    # provisional: نمونه کافی + پوشش ۵۰–۷۰٪
    conversion_provisional = bool(
        tracking_start
        and pricing_views > 0
        and checkout_views > 0
        and sample_sufficient
        and not coverage_locked
        and not coverage_good
        and post_linked > 0
        and post_linked <= pricing_views
        and post_linked <= checkout_views
    )
    # good/reliable: نمونه کافی + پوشش ≥۷۰٪
    tracking_reliable = bool(
        tracking_start
        and pricing_views > 0
        and checkout_views > 0
        and sample_sufficient
        and coverage_good
        and post_linked > 0
        and post_linked <= pricing_views
        and post_linked <= checkout_views
    )

    linked_paid_count = post_linked
    paid_link_coverage = post_tracking_coverage

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
        fl_status = _status(first_launch_coverage, has_signal=bool(launch_users))
        fl_detail = ''

    ts_jalali = ''
    if tracking_start:
        ts_jalali = to_persian_digits(
            jdatetime.datetime.fromgregorian(
                datetime=timezone.localtime(tracking_start),
            ).strftime('%Y/%m/%d %H:%M')
        )

    if not tracking_start:
        coverage_msg = 'هنوز هیچ Event قیف خرید ثبت نشده است.'
    elif not sample_sufficient:
        coverage_msg = (
            f'Tracking از {ts_jalali} — پس از شروع Tracking فقط '
            f'{to_persian_digits(paid_in_window)} سفارش Production '
            f'(حداقل نمونه: {to_persian_digits(POST_TRACKING_MIN_SAMPLE)}). '
            f'Conversion تا تکمیل نمونه قفل است. '
            f'پوشش تاریخی کل بازه: {to_persian_digits(historical_coverage or 0)}٪ '
            f'({to_persian_digits(hist_linked)} از {to_persian_digits(period_paid)}).'
        )
    else:
        coverage_msg = (
            f'Tracking از {ts_jalali}. '
            f'پوشش پس از Tracking: {to_persian_digits(post_tracking_coverage or 0)}٪ '
            f'({to_persian_digits(post_linked)} از {to_persian_digits(paid_in_window)}). '
            f'پوشش تاریخی (شامل قبل از Tracking): {to_persian_digits(historical_coverage or 0)}٪ '
            f'({to_persian_digits(hist_linked)} از {to_persian_digits(period_paid)}) — فقط توضیح گذشته.'
        )

    hist_status = _status(historical_coverage, has_signal=period_paid > 0)
    if paid_in_window == 0:
        post_status = 'insufficient'
        post_detail = 'هنوز سفارش Production پس از شروع Tracking وجود ندارد.'
    elif not sample_sufficient:
        post_status = 'partial'
        post_detail = (
            f'نمونه ناکافی: {to_persian_digits(post_linked)} از '
            f'{to_persian_digits(paid_in_window)} متصل '
            f'(حداقل {to_persian_digits(POST_TRACKING_MIN_SAMPLE)} سفارش لازم است). '
            f'Conversion قفل است.'
        )
    elif coverage_locked:
        post_status = 'insufficient'
        post_detail = (
            f'{to_persian_digits(post_linked)} از {to_persian_digits(paid_in_window)} '
            f'({to_persian_digits(post_tracking_coverage or 0)}٪) — زیر از '
            f'{to_persian_digits(int(POST_TRACKING_COVERAGE_LOCK_PCT))}٪؛ Conversion قفل است.'
        )
    elif conversion_provisional:
        post_status = 'partial'
        post_detail = (
            f'{to_persian_digits(post_linked)} از {to_persian_digits(paid_in_window)} '
            f'({to_persian_digits(post_tracking_coverage or 0)}٪) — موقت و کم‌اطمینان. '
            f'هدف عملیاتی ≥{to_persian_digits(int(POST_TRACKING_COVERAGE_GOOD_PCT))}٪ است.'
        )
    else:
        post_status = 'good'
        post_detail = (
            f'{to_persian_digits(post_linked)} از {to_persian_digits(paid_in_window)} '
            f'سفارش پس از Tracking متصل‌اند (≥'
            f'{to_persian_digits(int(POST_TRACKING_COVERAGE_GOOD_PCT))}٪) — قابل اتکا.'
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
            'historical_coverage',
            'پوشش تاریخی (کل بازه)',
            status=hist_status,
            coverage=historical_coverage,
            detail=(
                f'{to_persian_digits(hist_linked)} از {to_persian_digits(period_paid)} '
                f'سفارش کل بازه — شامل قبل از Tracking. فقط برای توضیح گذشته؛ '
                f'Conversion را قفل نمی‌کند.'
            ),
            value={
                'linked': hist_linked,
                'total': period_paid,
                'coverage': historical_coverage,
            },
        ),
        _item(
            'post_tracking_coverage',
            'پوشش پس از Tracking',
            status=post_status,
            coverage=post_tracking_coverage,
            detail=post_detail,
            value={
                'linked': post_linked,
                'total': paid_in_window,
                'coverage': post_tracking_coverage,
                'min_sample': POST_TRACKING_MIN_SAMPLE,
                'min_coverage_pct': POST_TRACKING_COVERAGE_GOOD_PCT,
                'lock_coverage_pct': POST_TRACKING_COVERAGE_LOCK_PCT,
                'sample_sufficient': sample_sufficient,
                'provisional': conversion_provisional,
            },
        ),
        _item(
            'pricing_coverage',
            'پوشش بازدید قیمت',
            status=_status(None, has_signal=pricing_views > 0) if pricing_views else 'insufficient',
            detail=f'{to_persian_digits(pricing_views)} رویداد' if pricing_views else EMPTY_MSG,
            value=pricing_views,
        ),
        _item(
            'checkout_coverage',
            'پوشش Checkout',
            status=_status(None, has_signal=checkout_views > 0) if checkout_views else 'insufficient',
            detail=f'{to_persian_digits(checkout_views)} رویداد' if checkout_views else EMPTY_MSG,
            value=checkout_views,
        ),
        _item(
            'paid_link',
            'سفارش‌های متصل به قیف (پس از Tracking)',
            status=post_status,
            coverage=post_tracking_coverage,
            detail=post_detail,
            value={
                'linked': post_linked,
                'total': paid_in_window,
            },
        ),
        _item(
            'activation',
            'پوشش فعال‌سازی لایسنس',
            status=_status(cov(act_users), has_signal=bool(act_users)),
            coverage=cov(act_users),
            detail=(
                f'{to_persian_digits(len(act_users & set(user_ids)))} از '
                f'{to_persian_digits(unique_buyers)} خریدار'
                if unique_buyers else EMPTY_MSG
            ),
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
            detail=(
                'از BI Production حذف می‌شوند: کاربران staff/superuser و '
                'سفارش‌هایی با zibal_track_id پیشوند FAKE-'
            ),
            value=len(buyers['orders']) - period_paid,
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
        conversion_provisional=conversion_provisional,
    )

    return {
        'tracking_start': tracking_start.isoformat() if tracking_start else None,
        'tracking_start_jalali': ts_jalali,
        'schema_version': SCHEMA_VERSION,
        'coverage_message': coverage_msg,
        'paid_link_coverage': paid_link_coverage,
        'linked_paid_count': linked_paid_count,
        'paid_in_tracking_window': paid_in_window,
        'historical_coverage': {
            'linked': hist_linked,
            'total': period_paid,
            'coverage': historical_coverage,
        },
        'post_tracking_coverage': {
            'linked': post_linked,
            'total': paid_in_window,
            'coverage': post_tracking_coverage,
            'min_sample': POST_TRACKING_MIN_SAMPLE,
            'min_coverage_pct': POST_TRACKING_COVERAGE_GOOD_PCT,
            'lock_coverage_pct': POST_TRACKING_COVERAGE_LOCK_PCT,
            'sample_sufficient': sample_sufficient,
            'provisional': conversion_provisional,
        },
        'tracking_reliable': tracking_reliable,
        'conversion_provisional': conversion_provisional,
        'first_launch_coverage': {
            'status': fl_status,
            'coverage': first_launch_coverage,
            'detail': fl_detail,
            'available': fl_status == 'good',
        },
        'items': items,
        'conversions': conversions,
        'funnel_conversions_available': tracking_reliable or conversion_provisional,
    }
