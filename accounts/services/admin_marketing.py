"""سگمنت‌ها و ابزارهای کمپین بازاریابی پیامکی."""
from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from licenses.models import License
from shop.models import DiscountCode, Order, Product

User = get_user_model()

from accounts.services.pending_orders import PENDING_ORDER_STATUSES, pending_orders_queryset
MARKETING_BATCH_LIMIT = 200
DEFAULT_DEDUPE_DAYS = 7

SEGMENT_DEFAULT_TEMPLATES = {
    'pending_orders': (
        'سلام{name_part}، سفارش «{product}» هنوز پرداخت نشده. '
        'با کد {code} تخفیف بگیرید و همین الان تکمیل کنید: {link}'
    ),
    'failed_orders': (
        'سلام{name_part}، پرداخت سفارش «{product}» ناموفق بود. '
        'با کد {code} دوباره امتحان کنید: {link}'
    ),
    'users_without_license': (
        'سلام{name_part}، هنوز لایسنس فعالی ندارید. '
        'با کد {code} از میزکار شروع کنید: {link}'
    ),
}


@dataclass
class SegmentRecipient:
    user: Any
    phone: str
    context: Dict[str, str] = field(default_factory=dict)


SEGMENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    'pending_orders': {
        'title': 'سفارش‌های پرداخت‌نشده',
        'description': 'کاربرانی که سفارش در انتظار پرداخت یا تأیید دارند',
        'icon': 'fa-clock',
        'accent': 'amber',
        'supports_stale_hours': True,
        'supports_days_lookback': False,
        'supports_product': True,
    },
    'failed_orders': {
        'title': 'پرداخت ناموفق اخیر',
        'description': 'سفارش‌هایی که پرداختشان در بازه اخیر ناموفق شده',
        'icon': 'fa-circle-xmark',
        'accent': 'rose',
        'supports_stale_hours': False,
        'supports_days_lookback': True,
        'supports_product': True,
    },
    'users_without_license': {
        'title': 'بدون لایسنس فعال',
        'description': 'کاربران فعال بدون لایسنس — فرصت فروش',
        'icon': 'fa-user-slash',
        'accent': 'cyan',
        'supports_stale_hours': False,
        'supports_days_lookback': False,
        'supports_product': False,
    },
}


def get_segment_catalog() -> List[Dict[str, Any]]:
    return [
        {'key': key, **meta}
        for key, meta in SEGMENT_REGISTRY.items()
    ]


def _site_url() -> str:
    return (getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir').rstrip('/')


def _checkout_url(order_id) -> str:
    return f'{_site_url()}/payment/checkout/{order_id}/'


def _shop_url() -> str:
    return f'{_site_url()}/'


def _user_first_name(user) -> str:
    return (getattr(user, 'first_name', '') or '').strip()


def _format_amount(amount) -> str:
    try:
        return f'{int(amount):,}'
    except (TypeError, ValueError):
        return str(amount or '')


def _phone_ok(raw: str) -> str:
    phone = normalize_phone(raw or '')
    if not is_valid_iran_mobile(phone):
        return ''
    return phone


def build_segment_recipients(
    segment_key: str,
    *,
    stale_hours: Optional[int] = None,
    days_lookback: Optional[int] = None,
    product_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[SegmentRecipient]:
    """ساخت لیست گیرندگان یکتا بر اساس سگمنت (یک شماره = یک ردیف)."""
    if segment_key not in SEGMENT_REGISTRY:
        raise ValueError(f'سگمنت ناشناخته: {segment_key}')

    if segment_key == 'pending_orders':
        items = _segment_pending_orders(
            stale_hours=stale_hours, product_id=product_id,
        )
    elif segment_key == 'failed_orders':
        items = _segment_failed_orders(
            days_lookback=days_lookback or 14, product_id=product_id,
        )
    else:
        items = _segment_users_without_license()

    # dedupe by phone — keep first (newest)
    seen: set[str] = set()
    out: List[SegmentRecipient] = []
    for item in items:
        phone = _phone_ok(item.phone)
        if not phone or phone in seen:
            continue
        seen.add(phone)
        item.phone = phone
        out.append(item)
        if limit and len(out) >= limit:
            break
    return out


def _segment_pending_orders(
    *,
    stale_hours: Optional[int] = None,
    product_id: Optional[int] = None,
) -> List[SegmentRecipient]:
    qs = (
        pending_orders_queryset(dedupe_by_user=True)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')
    )
    # کاربرانی که بعداً سفارش پرداخت‌شده یا لایسنس فعال گرفته‌اند نباید هدف پیگیری باشند
    paid_order_q = Order.objects.filter(user=OuterRef('user'), status='paid')
    active_license_q = License.objects.filter(
        order__user=OuterRef('user'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
    qs = qs.annotate(
        _has_paid_order=Exists(paid_order_q),
        _has_active_license=Exists(active_license_q),
    ).filter(_has_paid_order=False, _has_active_license=False)
    if stale_hours and stale_hours > 0:
        cutoff = timezone.now() - timedelta(hours=stale_hours)
        qs = qs.filter(created_at__lte=cutoff)
    if product_id:
        qs = qs.filter(product_id=product_id)

    rows: List[SegmentRecipient] = []
    for order in qs:
        user = order.user
        name = _user_first_name(user)
        rows.append(SegmentRecipient(
            user=user,
            phone=user.phone or '',
            context={
                'name': name,
                'name_part': f' {name}' if name else '',
                'product': order.product.title if order.product_id else '',
                'plan': order.plan.name if order.plan_id else '',
                'amount': _format_amount(order.amount),
                'link': _checkout_url(order.id),
                'order_id': str(order.id),
                'code': '',
            },
        ))
    return rows


def _segment_failed_orders(
    *,
    days_lookback: int = 14,
    product_id: Optional[int] = None,
) -> List[SegmentRecipient]:
    since = timezone.now() - timedelta(days=max(1, days_lookback))
    qs = (
        Order.objects.filter(status='failed', created_at__gte=since)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')
    )
    if product_id:
        qs = qs.filter(product_id=product_id)

    rows: List[SegmentRecipient] = []
    for order in qs:
        user = order.user
        name = _user_first_name(user)
        rows.append(SegmentRecipient(
            user=user,
            phone=user.phone or '',
            context={
                'name': name,
                'name_part': f' {name}' if name else '',
                'product': order.product.title if order.product_id else '',
                'plan': order.plan.name if order.plan_id else '',
                'amount': _format_amount(order.amount),
                'link': _checkout_url(order.id),
                'order_id': str(order.id),
                'code': '',
            },
        ))
    return rows


def _segment_users_without_license() -> List[SegmentRecipient]:
    active_license = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
    qs = (
        User.objects.filter(is_active=True)
        .annotate(has_active_license=Exists(active_license))
        .filter(has_active_license=False)
        .order_by('-date_joined')
    )
    rows: List[SegmentRecipient] = []
    for user in qs:
        name = _user_first_name(user)
        rows.append(SegmentRecipient(
            user=user,
            phone=user.phone or '',
            context={
                'name': name,
                'name_part': f' {name}' if name else '',
                'product': 'میزکار',
                'plan': '',
                'amount': '',
                'link': _shop_url(),
                'order_id': '',
                'code': '',
            },
        ))
    return rows


def preview_segment(
    segment_key: str,
    *,
    stale_hours: Optional[int] = None,
    days_lookback: Optional[int] = None,
    product_id: Optional[int] = None,
    sample_size: int = 10,
) -> Dict[str, Any]:
    recipients = build_segment_recipients(
        segment_key,
        stale_hours=stale_hours,
        days_lookback=days_lookback,
        product_id=product_id,
    )
    meta = SEGMENT_REGISTRY[segment_key]
    capped = recipients[:MARKETING_BATCH_LIMIT]
    sample = recipients[:sample_size]

    def _row(r: SegmentRecipient) -> Dict[str, str]:
        ctx = r.context or {}
        return {
            'phone': r.phone,
            'name': ctx.get('name') or '',
            'name_part': ctx.get('name_part') or '',
            'product': ctx.get('product') or '',
            'plan': ctx.get('plan') or '',
            'amount': ctx.get('amount') or '',
            'link': ctx.get('link') or '',
            'order_id': ctx.get('order_id') or '',
            'code': ctx.get('code') or '',
        }

    return {
        'key': segment_key,
        'title': meta['title'],
        'description': meta['description'],
        'count': len(recipients),
        'capped_count': len(capped),
        'batch_limit': MARKETING_BATCH_LIMIT,
        'sample': [_row(r) for r in sample],
        'recipients': [_row(r) for r in capped],
        'default_template': SEGMENT_DEFAULT_TEMPLATES.get(segment_key, ''),
    }


def render_message(template: str, context: Dict[str, str]) -> str:
    """جایگزینی امن placeholderها — کلیدهای ناشناخته خالی می‌مانند."""
    class _Safe(dict):
        def __missing__(self, key):
            return ''

    text = (template or '').strip()
    if not text:
        return ''
    try:
        return text.format_map(_Safe({k: str(v or '') for k, v in (context or {}).items()}))
    except Exception:
        return text


def recently_marketed_phones(phones: List[str], *, days: int = DEFAULT_DEDUPE_DAYS) -> set[str]:
    """شماره‌هایی که اخیراً پیام بازاریابی گرفته‌اند."""
    from accounts.models import SmsMessageLog

    if not phones or days <= 0:
        return set()
    since = timezone.now() - timedelta(days=days)
    return set(
        SmsMessageLog.objects.filter(
            phone__in=phones,
            purpose='marketing',
            status__in=('sent', 'fake'),
            created_at__gte=since,
        ).values_list('phone', flat=True)
    )


def _unique_code(prefix: str = 'MK') -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(40):
        suffix = ''.join(secrets.choice(alphabet) for _ in range(6))
        code = f'{prefix}-{suffix}'
        if not DiscountCode.objects.filter(code=code).exists():
            return code
    raise RuntimeError('نتوانستیم کد تخفیف یکتا بسازیم.')


def create_shared_discount(
    *,
    code: str,
    discount_type: str,
    discount_value: Decimal | int | float,
    max_uses: Optional[int],
    valid_days: int,
    description: str = '',
) -> DiscountCode:
    code = (code or '').strip().upper()
    if not code:
        code = _unique_code('SHARE')
    if DiscountCode.objects.filter(code=code).exists():
        raise ValueError(f'کد تخفیف «{code}» از قبل وجود دارد.')
    now = timezone.now()
    return DiscountCode.objects.create(
        code=code,
        discount_type=discount_type if discount_type in ('percentage', 'fixed') else 'percentage',
        discount_value=Decimal(int(discount_value)),
        max_uses=max_uses,
        valid_from=now,
        valid_until=now + timedelta(days=max(1, valid_days)),
        is_active=True,
        description=description or 'کمپین بازاریابی',
    )


def create_unique_discount(
    *,
    discount_type: str,
    discount_value: Decimal | int | float,
    valid_days: int,
    description: str = '',
) -> DiscountCode:
    now = timezone.now()
    return DiscountCode.objects.create(
        code=_unique_code('MK'),
        discount_type=discount_type if discount_type in ('percentage', 'fixed') else 'percentage',
        discount_value=Decimal(int(discount_value)),
        max_uses=1,
        valid_from=now,
        valid_until=now + timedelta(days=max(1, valid_days)),
        is_active=True,
        description=description or 'کد یکتای کمپین بازاریابی',
    )


def active_products_for_filter() -> List[Dict[str, Any]]:
    return list(
        Product.objects.filter(is_active=True)
        .order_by('title')
        .values('id', 'title')
    )


SEGMENT_SUGGESTIONS = {
    'pending_orders': 'ارسال کد تخفیف ۱۵٪ — پیامک احساسی در ساعت ۲۰',
    'failed_orders': 'یادآوری پرداخت با کد ۱۰٪ — ارسال بعد از ۲۴ ساعت',
    'users_without_license': 'معرفی میزکار + تخفیف خوش‌آمد — ارسال عصر',
}

MESSAGE_TEMPLATE_CATALOG = [
    {
        'key': 'payment_reminder',
        'title': 'یادآوری پرداخت',
        'icon': 'fa-clock',
        'accent': 'amber',
        'text': 'سلام{name_part}، سفارش «{product}» هنوز پرداخت نشده. با کد {code} تخفیف بگیرید: {link}',
    },
    {
        'key': 'license_renewal',
        'title': 'تمدید لایسنس',
        'icon': 'fa-rotate',
        'accent': 'cyan',
        'text': 'سلام{name_part}، لایسنس «{product}» به‌زودی منقضی می‌شود. تمدید با کد {code}: {link}',
    },
    {
        'key': 'special_discount',
        'title': 'تخفیف ویژه',
        'icon': 'fa-gift',
        'accent': 'violet',
        'text': 'سلام{name_part}، پیشنهاد ویژه فقط برای شما! {product} با {code} — {link}',
    },
    {
        'key': 'welcome',
        'title': 'خوش‌آمد',
        'icon': 'fa-hand-sparkles',
        'accent': 'emerald',
        'text': 'سلام{name_part}، به فایلینگ دیوار خوش آمدید! با کد {code} شروع کنید: {link}',
    },
    {
        'key': 'new_version',
        'title': 'معرفی نسخه جدید',
        'icon': 'fa-rocket',
        'accent': 'blue',
        'text': 'سلام{name_part}، نسخه جدید {product} منتشر شد. جزئیات: {link}',
    },
    {
        'key': 'birthday',
        'title': 'تولد',
        'icon': 'fa-cake-candles',
        'accent': 'rose',
        'text': 'سلام{name_part}، تولدت مبارک! هدیه ما کد {code} برای {product}: {link}',
    },
    {
        'key': 'inactive',
        'title': 'عدم فعالیت',
        'icon': 'fa-user-clock',
        'accent': 'slate',
        'text': 'سلام{name_part}، مدتی است سراغ میزکار نیامده‌اید. با {code} برگردید: {link}',
    },
    {
        'key': 'abandoned_cart',
        'title': 'سبد خرید رها شده',
        'icon': 'fa-cart-shopping',
        'accent': 'amber',
        'text': 'سلام{name_part}، سفارش «{product}» ({amount} ت) منتظر شماست. کد {code}: {link}',
    },
]

AUTOMATION_FLOWS = [
    {
        'key': 'pending_recovery',
        'title': 'بازیابی سفارش پرداخت‌نشده',
        'segment_key': 'pending_orders',
        'steps': [
            {'type': 'trigger', 'label': 'سفارش پرداخت نشد', 'icon': 'fa-bolt'},
            {'type': 'wait', 'label': 'بعد از ۲ ساعت', 'icon': 'fa-hourglass-half'},
            {'type': 'action', 'label': 'ارسال پیام یادآوری', 'icon': 'fa-comment-sms'},
            {'type': 'branch', 'label': 'اگر خرید نکرد', 'icon': 'fa-code-branch'},
            {'type': 'wait', 'label': '۲۴ ساعت بعد', 'icon': 'fa-hourglass-half'},
            {'type': 'action', 'label': 'ارسال تخفیف ۱۵٪', 'icon': 'fa-gift'},
            {'type': 'branch', 'label': 'اگر باز هم نخرید', 'icon': 'fa-code-branch'},
            {'type': 'wait', 'label': '۳ روز بعد', 'icon': 'fa-hourglass-half'},
            {'type': 'action', 'label': 'تماس مدیر / CRM', 'icon': 'fa-phone'},
        ],
        'status': 'draft',
    },
    {
        'key': 'license_onboarding',
        'title': 'خوش‌آمدگویی بدون لایسنس',
        'segment_key': 'users_without_license',
        'steps': [
            {'type': 'trigger', 'label': 'ثبت‌نام بدون لایسنس', 'icon': 'fa-user-plus'},
            {'type': 'wait', 'label': '۱ ساعت بعد', 'icon': 'fa-hourglass-half'},
            {'type': 'action', 'label': 'پیام خوش‌آمد + کد', 'icon': 'fa-comment-sms'},
            {'type': 'wait', 'label': '۳ روز بعد', 'icon': 'fa-hourglass-half'},
            {'type': 'action', 'label': 'یادآوری + تخفیف', 'icon': 'fa-gift'},
        ],
        'status': 'draft',
    },
]


def _marketing_attribution() -> Dict[str, Any]:
    """خرید و درآمد نسبت‌داده‌شده به کدهای تخفیف کمپین‌های بازاریابی."""
    from django.db.models import Sum

    from accounts.models import MarketingCampaignRecipient
    from shop.models import Order

    code_ids = list(
        MarketingCampaignRecipient.objects.filter(
            status=MarketingCampaignRecipient.Status.SENT,
            discount_code_id__isnull=False,
        ).values_list('discount_code_id', flat=True).distinct()
    )
    if not code_ids:
        return {'purchases': 0, 'revenue': 0, 'engaged_users': 0}

    paid = Order.objects.filter(status='paid', discount_code_id__in=code_ids)
    revenue = int(paid.aggregate(total=Sum('amount'))['total'] or 0)
    purchases = paid.count()

    engaged = 0
    sent_recipients = (
        MarketingCampaignRecipient.objects.filter(status=MarketingCampaignRecipient.Status.SENT)
        .select_related('sms_log', 'user')
    )
    for recipient in sent_recipients.iterator(chunk_size=200):
        if not recipient.user_id:
            continue
        sms_time = recipient.sms_log.created_at if recipient.sms_log_id else recipient.created_at
        if Order.objects.filter(
            user_id=recipient.user_id,
            created_at__gte=sms_time,
            created_at__lte=sms_time + timedelta(days=7),
        ).exists():
            engaged += 1

    return {'purchases': purchases, 'revenue': revenue, 'engaged_users': engaged}


def get_segment_insights(segment_key: str) -> Dict[str, Any]:
    """آمار تکمیلی هر سگمنت برای کارت‌های حرفه‌ای."""
    meta = SEGMENT_REGISTRY.get(segment_key, {})
    count = 0
    avg_value = None
    last_activity = None

    try:
        recipients = build_segment_recipients(segment_key)
        count = len(recipients)
        amounts = []
        for r in recipients:
            raw = (r.context or {}).get('amount', '')
            if raw:
                try:
                    amounts.append(int(str(raw).replace(',', '')))
                except (TypeError, ValueError):
                    pass
        if amounts:
            avg_value = int(sum(amounts) / len(amounts))
    except Exception:
        pass

    if segment_key == 'pending_orders':
        latest = (
            pending_orders_queryset(dedupe_by_user=True)
            .order_by('-created_at')
            .values_list('created_at', flat=True)
            .first()
        )
        last_activity = latest
    elif segment_key == 'failed_orders':
        latest = (
            Order.objects.filter(status='failed')
            .order_by('-created_at')
            .values_list('created_at', flat=True)
            .first()
        )
        last_activity = latest
    elif segment_key == 'users_without_license':
        latest = (
            User.objects.filter(is_active=True)
            .order_by('-date_joined')
            .values_list('date_joined', flat=True)
            .first()
        )
        last_activity = latest

    return {
        'key': segment_key,
        'title': meta.get('title', segment_key),
        'description': meta.get('description', ''),
        'icon': meta.get('icon', 'fa-bullhorn'),
        'accent': meta.get('accent', 'violet'),
        'count': count,
        'avg_value': avg_value,
        'last_activity': last_activity,
        'suggestion': SEGMENT_SUGGESTIONS.get(segment_key, 'ارسال پیام شخصی‌سازی‌شده با کد تخفیف'),
    }


def get_all_segment_insights() -> List[Dict[str, Any]]:
    return [get_segment_insights(key) for key in SEGMENT_REGISTRY]


def get_ai_campaign_suggestion(segment_key: str, *, count: int = 0) -> Dict[str, Any]:
    """پیشنهاد هوشمند کمپین بر اساس سگمنت (قوانین ساده — بدون API خارجی)."""
    insights = get_segment_insights(segment_key)
    n = count or insights['count']
    if segment_key == 'pending_orders':
        discount = '۱۵٪'
        tone = 'متن احساسی — تأکید بر تکمیل سفارش'
        send_hour = '۲۰:۰۰'
        conversion = min(62, max(18, 28 + n * 2))
    elif segment_key == 'failed_orders':
        discount = '۱۰٪'
        tone = 'متن حمایتی — راهنمای پرداخت مجدد'
        send_hour = '۱۸:۰۰'
        conversion = min(55, max(15, 22 + n))
    else:
        discount = '۲۰٪'
        tone = 'متن خوش‌آمد — معرفی ارزش میزکار'
        send_hour = '۱۹:۰۰'
        conversion = min(48, max(12, 18 + n // 2))

    return {
        'segment_key': segment_key,
        'audience_size': n,
        'discount': discount,
        'tone': tone,
        'send_hour': send_hour,
        'conversion_estimate': conversion,
        'message': (
            f'این سگمنت {n} مخاطب دارد. پیشنهاد: تخفیف {discount}، {tone}، ارسال ساعت {send_hour}.'
        ),
    }


def get_marketing_analytics(*, days: int = 30) -> Dict[str, Any]:
    """داده نمودارهای تب Analytics."""
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate

    from accounts.models import MarketingCampaign, MarketingCampaignRecipient, SmsMessageLog

    days = max(7, min(365, int(days or 30)))
    since = timezone.now() - timedelta(days=days)

    daily_qs = (
        SmsMessageLog.objects.filter(
            purpose='marketing',
            status__in=('sent', 'fake'),
            created_at__gte=since,
        )
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    daily_labels = []
    daily_values = []
    for row in daily_qs:
        daily_labels.append(row['day'].isoformat() if row['day'] else '')
        daily_values.append(int(row['count'] or 0))

    attribution = _marketing_attribution()
    completed = MarketingCampaign.objects.filter(status=MarketingCampaign.Status.COMPLETED)
    sent_total = int(completed.aggregate(s=Sum('sent_count'))['s'] or 0)
    conversion_rate = (
        round(100 * attribution['purchases'] / sent_total) if sent_total else None
    )
    engagement_rate = (
        round(100 * attribution['engaged_users'] / sent_total) if sent_total else None
    )

    top_campaign = (
        completed.order_by('-sent_count').values('name', 'sent_count').first()
    )
    best_segment_key = None
    best_segment_count = 0
    for key in SEGMENT_REGISTRY:
        c = MarketingCampaign.objects.filter(
            segment_key=key, status=MarketingCampaign.Status.COMPLETED,
        ).aggregate(s=Sum('sent_count'))['s'] or 0
        if int(c) > best_segment_count:
            best_segment_count = int(c)
            best_segment_key = key

    best_discount = (
        MarketingCampaignRecipient.objects.filter(
            status=MarketingCampaignRecipient.Status.SENT,
            discount_code_id__isnull=False,
        )
        .values('discount_code__code')
        .annotate(uses=Count('id'))
        .order_by('-uses')
        .first()
    )

    return {
        'days': days,
        'daily_labels': daily_labels,
        'daily_values': daily_values,
        'conversion_rate': conversion_rate,
        'engagement_rate': engagement_rate,
        'revenue': attribution['revenue'],
        'purchases': attribution['purchases'],
        'top_campaign': top_campaign,
        'best_segment_key': best_segment_key,
        'best_segment_title': SEGMENT_REGISTRY.get(best_segment_key or '', {}).get('title', '—'),
        'best_discount_code': (best_discount or {}).get('discount_code__code') or '—',
    }


def enrich_campaign_row(campaign) -> None:
    """افزودن فیلدهای نمایشی به آبجکت کمپین برای جدول تاریخچه."""
    from django.db.models import Sum

    from accounts.models import MarketingCampaignRecipient
    from shop.models import Order

    attempted = campaign.sent_count + campaign.failed_count
    campaign.success_pct = (
        round(100 * campaign.sent_count / attempted) if attempted else None
    )
    campaign.delivery_pct = campaign.success_pct
    seg_meta = SEGMENT_REGISTRY.get(campaign.segment_key, {})
    campaign.segment_icon = seg_meta.get('icon', 'fa-bullhorn')
    campaign.segment_accent = seg_meta.get('accent', 'violet')
    campaign.segment_title = seg_meta.get('title', campaign.segment_key)

    code_ids = list(
        MarketingCampaignRecipient.objects.filter(
            campaign=campaign,
            status=MarketingCampaignRecipient.Status.SENT,
            discount_code_id__isnull=False,
        ).values_list('discount_code_id', flat=True)
    )
    if code_ids:
        paid = Order.objects.filter(status='paid', discount_code_id__in=code_ids)
        campaign.purchase_count = paid.count()
        campaign.revenue = int(paid.aggregate(total=Sum('amount'))['total'] or 0)
        campaign.conversion_pct = (
            round(100 * campaign.purchase_count / campaign.sent_count)
            if campaign.sent_count else None
        )
    else:
        campaign.purchase_count = 0
        campaign.revenue = 0
        campaign.conversion_pct = None

    campaign.click_pct = campaign.conversion_pct


def campaign_timeline_events(campaign) -> List[Dict[str, Any]]:
    """رویدادهای Timeline برای یک کمپین."""
    events = []
    if campaign.created_at:
        events.append({
            'time': campaign.created_at,
            'label': 'کمپین شروع شد',
            'icon': 'fa-play',
        })
    if campaign.sent_count:
        t = campaign.completed_at or campaign.created_at
        events.append({
            'time': t,
            'label': f'{campaign.sent_count} پیام ارسال شد',
            'icon': 'fa-paper-plane',
        })
        events.append({
            'time': t,
            'label': 'تحویل کامل',
            'icon': 'fa-check-double',
        })
    if getattr(campaign, 'purchase_count', 0):
        events.append({
            'time': campaign.completed_at or campaign.created_at,
            'label': f'{campaign.purchase_count} خرید',
            'icon': 'fa-cart-shopping',
        })
    if getattr(campaign, 'revenue', 0):
        events.append({
            'time': campaign.completed_at or campaign.created_at,
            'label': f'درآمد: {campaign.revenue:,} تومان',
            'icon': 'fa-coins',
            'highlight': True,
        })
    return events


def get_marketing_dashboard_stats(*, sms_credit: Optional[int] = None) -> Dict[str, Any]:
    """آمار خلاصه پنل بازاریابی برای KPIها و کارت سگمنت‌ها."""
    from django.db.models import Count, Sum

    from accounts.models import MarketingCampaign, SmsMessageLog

    completed = MarketingCampaign.objects.filter(status=MarketingCampaign.Status.COMPLETED)
    agg = completed.aggregate(
        campaigns=Count('id'),
        sent=Sum('sent_count'),
        failed=Sum('failed_count'),
        skipped=Sum('skipped_count'),
    )
    sent_total = int(agg['sent'] or 0)
    failed_total = int(agg['failed'] or 0)
    delivered_total = sent_total
    attempted = sent_total + failed_total
    delivery_rate = round(100 * sent_total / attempted) if attempted else None
    success_rate = delivery_rate

    pending_send = SmsMessageLog.objects.filter(
        purpose='marketing',
        status=SmsMessageLog.Status.PENDING,
    ).count()

    since_30 = timezone.now() - timedelta(days=30)
    sms_30d = SmsMessageLog.objects.filter(
        purpose='marketing',
        status__in=('sent', 'fake'),
        created_at__gte=since_30,
    ).count()

    segment_sizes: Dict[str, int] = {}
    for key in SEGMENT_REGISTRY:
        try:
            segment_sizes[key] = len(build_segment_recipients(key))
        except Exception:
            segment_sizes[key] = 0

    attribution = _marketing_attribution()
    click_rate = (
        round(100 * attribution['engaged_users'] / sent_total) if sent_total else None
    )
    conversion_rate = (
        round(100 * attribution['purchases'] / sent_total) if sent_total else None
    )

    return {
        'campaigns_total': int(agg['campaigns'] or 0),
        'sent_total': sent_total,
        'delivered_total': delivered_total,
        'failed_total': failed_total,
        'skipped_total': int(agg['skipped'] or 0),
        'success_rate': success_rate,
        'delivery_rate': delivery_rate,
        'click_rate': click_rate,
        'conversion_rate': conversion_rate,
        'purchases': attribution['purchases'],
        'revenue': attribution['revenue'],
        'pending_send': pending_send,
        'sms_credit': sms_credit,
        'sms_marketing_30d': sms_30d,
        'segment_sizes': segment_sizes,
    }
