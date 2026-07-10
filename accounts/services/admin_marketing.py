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

PENDING_ORDER_STATUSES = ('pending', 'pending_verification')
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
        Order.objects.filter(status__in=PENDING_ORDER_STATUSES)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')
    )
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
