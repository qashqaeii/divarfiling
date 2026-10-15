"""Discount Engine — صدور هوشمند کد تخفیف اختصاصی برای اتوماسیون‌ها."""
from __future__ import annotations

import logging
import secrets
import string
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from shop.models import DiscountCode

logger = logging.getLogger(__name__)

POLICY_ABANDONED_CHECKOUT = 'abandoned_checkout'
POLICY_EXPIRED_RENEWAL = 'expired_renewal'
POLICY_RETURNING_CUSTOMER = 'returning_customer'
POLICY_DIRECT_REQUEST = 'direct_request'
POLICY_ONBOARDING = 'onboarding'

DEFAULT_POLICIES: Dict[str, Dict[str, Any]] = {
    POLICY_ABANDONED_CHECKOUT: {
        'label': 'خرید نیمه‌کاره',
        'percent': 10,
        'valid_hours': 48,
        'enabled': True,
    },
    POLICY_EXPIRED_RENEWAL: {
        'label': 'بازگشت مشتری منقضی',
        'percent': 15,
        'valid_hours': 48,
        'enabled': True,
    },
    POLICY_RETURNING_CUSTOMER: {
        'label': 'مشتری برگشته',
        'percent': 15,
        'valid_hours': 48,
        'enabled': True,
    },
    POLICY_DIRECT_REQUEST: {
        'label': 'درخواست مستقیم تخفیف',
        'percent': 10,
        'valid_hours': 48,
        'enabled': True,
    },
    POLICY_ONBOARDING: {
        'label': 'خوش‌آمدگویی',
        'percent': 10,
        'valid_hours': 48,
        'enabled': False,
    },
}

DEFAULT_GLOBAL_SETTINGS: Dict[str, Any] = {
    'max_codes_per_user_days': 30,
    'code_prefix': 'DF',
}

RULE_DISCOUNT_POLICIES: Dict[str, str] = {
    'pending_recovery_discount': POLICY_ABANDONED_CHECKOUT,
    'expired_renewal_campaign': POLICY_EXPIRED_RENEWAL,
    'returning_customer_renewal': POLICY_RETURNING_CUSTOMER,
}


@dataclass
class DiscountIssueResult:
    ok: bool
    code: str = ''
    discount_code_id: Optional[int] = None
    discount_percent: str = ''
    discount_amount: str = ''
    discount_expiry: str = ''
    checkout_link: str = ''
    reused: bool = False
    reason: str = ''


def _site_base() -> str:
    return (getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir').rstrip('/')


def _format_expiry(dt) -> str:
    if not dt:
        return ''
    try:
        import jdatetime
        from workspace.services.jalali_input import to_persian_digits

        local = timezone.localtime(dt)
        j = jdatetime.datetime.fromgregorian(datetime=local)
        return to_persian_digits(j.strftime('%Y/%m/%d %H:%M'))
    except Exception:
        return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M')


def _unique_discount_code(prefix: str = 'DF') -> str:
    alphabet = string.ascii_uppercase + string.digits
    prefix = (prefix or 'DF').strip().upper()
    for _ in range(40):
        suffix = ''.join(secrets.choice(alphabet) for _ in range(6))
        code = f'{prefix}-{suffix}'
        if not DiscountCode.objects.filter(code=code).exists():
            return code
    raise RuntimeError('نتوانستیم کد تخفیف یکتا بسازیم.')


def get_discount_policy_config() -> Dict[str, Any]:
    """خواندن سیاست‌های تخفیف از DB یا پیش‌فرض."""
    from accounts.models import DiscountPolicyConfig

    row = DiscountPolicyConfig.objects.filter(singleton_key='default').first()
    if not row:
        return {
            'policies': {k: dict(v) for k, v in DEFAULT_POLICIES.items()},
            'global': dict(DEFAULT_GLOBAL_SETTINGS),
        }
    policies = {k: dict(v) for k, v in DEFAULT_POLICIES.items()}
    stored = row.policies or {}
    for key, values in stored.items():
        if key == '_global':
            continue
        if key in policies and isinstance(values, dict):
            policies[key].update(values)
        elif isinstance(values, dict):
            policies[key] = values
    global_settings = dict(DEFAULT_GLOBAL_SETTINGS)
    global_settings.update(stored.get('_global') or row.global_settings or {})
    return {'policies': policies, 'global': global_settings}


def update_discount_policy_config(
    *,
    policies: Optional[Dict[str, Any]] = None,
    global_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from accounts.models import DiscountPolicyConfig

    row, _ = DiscountPolicyConfig.objects.get_or_create(singleton_key='default')
    merged = dict(row.policies or {})
    if policies:
        for key, values in policies.items():
            if key == '_global':
                continue
            base = merged.get(key, {})
            if not isinstance(base, dict):
                base = {}
            base.update(values or {})
            merged[key] = base
    if global_settings:
        gs = dict(row.global_settings or {})
        gs.update(global_settings)
        row.global_settings = gs
        merged['_global'] = gs
    row.policies = merged
    row.save(update_fields=['policies', 'global_settings', 'updated_at'])
    return get_discount_policy_config()


def checkout_link_with_code(code: str, *, order_id: Optional[int] = None) -> str:
    from accounts.services.growth_links import abs_url, renewal_or_buy_landing_url

    code = (code or '').strip().upper()
    if order_id:
        return abs_url(f'/payment/checkout/{order_id}/?code={code}')
    renewal = renewal_or_buy_landing_url()
    sep = '&' if '?' in renewal else '?'
    return f'{renewal}{sep}code={code}'


def _policy_for_rule(rule_key: str) -> Optional[str]:
    return RULE_DISCOUNT_POLICIES.get(rule_key)


def _active_issuance_for_user(user_id: int):
    from accounts.models import UserDiscountIssuance

    now = timezone.now()
    return (
        UserDiscountIssuance.objects.filter(
            user_id=user_id,
            discount_code__is_active=True,
            discount_code__valid_until__gt=now,
        )
        .select_related('discount_code')
        .order_by('-issued_at')
        .first()
    )


def _recent_issuance_count(user_id: int, *, days: int) -> int:
    from accounts.models import UserDiscountIssuance

    since = timezone.now() - timedelta(days=max(1, days))
    return UserDiscountIssuance.objects.filter(user_id=user_id, issued_at__gte=since).count()


def _user_has_paid_since(user_id: int, since) -> bool:
    from shop.models import Order

    return Order.objects.filter(user_id=user_id, status='paid', paid_at__gte=since).exists()


def check_eligibility(
    *,
    user_id: int,
    policy_key: str,
    source_rule: str = '',
) -> Tuple[bool, str]:
    if not user_id:
        return False, 'کاربر نامعتبر'

    config = get_discount_policy_config()
    policy = config['policies'].get(policy_key)
    if not policy or not policy.get('enabled', True):
        return False, 'سیاست تخفیف غیرفعال است'

    active = _active_issuance_for_user(user_id)
    if active and active.discount_code_id:
        is_valid, _ = active.discount_code.is_valid()
        if is_valid:
            return True, 'active_exists'

    global_settings = config['global']
    max_days = int(global_settings.get('max_codes_per_user_days') or 30)
    if _recent_issuance_count(user_id, days=max_days) >= 1:
        return False, 'سقف صدور کد در بازه زمانی'

    return True, ''


def issue_discount(
    *,
    user,
    policy_key: str,
    source_rule: str = '',
    source_type: str = 'automation',
    order_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> DiscountIssueResult:
    """صدور یا بازگرداندن کد تخفیف اختصاصی."""
    from accounts.models import UserDiscountIssuance

    user_id = getattr(user, 'pk', None)
    if not user_id:
        return DiscountIssueResult(ok=False, reason='کاربر نامعتبر')

    eligible, reason = check_eligibility(user_id=user_id, policy_key=policy_key, source_rule=source_rule)
    if not eligible:
        return DiscountIssueResult(ok=False, reason=reason)

    if reason == 'active_exists':
        active = _active_issuance_for_user(user_id)
        if active and active.discount_code_id:
            dc = active.discount_code
            return DiscountIssueResult(
                ok=True,
                code=dc.code,
                discount_code_id=dc.pk,
                discount_percent=str(int(dc.discount_value)) if dc.discount_type == 'percentage' else '',
                discount_amount=str(int(dc.discount_value)) if dc.discount_type == 'fixed' else '',
                discount_expiry=_format_expiry(dc.valid_until),
                checkout_link=checkout_link_with_code(dc.code, order_id=order_id),
                reused=True,
            )

    config = get_discount_policy_config()
    policy = config['policies'].get(policy_key) or DEFAULT_POLICIES.get(policy_key, {})
    if not policy.get('enabled', True):
        return DiscountIssueResult(ok=False, reason='سیاست غیرفعال')

    percent = int(policy.get('percent') or 10)
    valid_hours = int(policy.get('valid_hours') or 48)
    prefix = (config['global'].get('code_prefix') or 'DF').strip().upper()

    try:
        with transaction.atomic():
            dc = DiscountCode.objects.create(
                code=_unique_discount_code(prefix),
                discount_type='percentage',
                discount_value=Decimal(percent),
                max_uses=1,
                valid_from=timezone.now(),
                valid_until=timezone.now() + timedelta(hours=max(1, valid_hours)),
                is_active=True,
                description=f'auto:{policy_key}:user:{user_id}',
            )
            UserDiscountIssuance.objects.create(
                user_id=user_id,
                discount_code=dc,
                policy_key=policy_key,
                source_rule=source_rule or '',
                source_type=source_type,
                metadata=metadata or {},
            )
    except Exception as exc:
        logger.exception('discount issue failed user=%s policy=%s', user_id, policy_key)
        return DiscountIssueResult(ok=False, reason=str(exc)[:200])

    return DiscountIssueResult(
        ok=True,
        code=dc.code,
        discount_code_id=dc.pk,
        discount_percent=str(percent),
        discount_amount='',
        discount_expiry=_format_expiry(dc.valid_until),
        checkout_link=checkout_link_with_code(dc.code, order_id=order_id),
        reused=False,
    )


def enrich_context_with_discount(
    context: Dict[str, str],
    *,
    rule_key: str,
    user,
    order_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, str], Optional[str]]:
    """در صورت نیاز Rule، context را با متغیرهای تخفیف غنی می‌کند."""
    policy_key = _policy_for_rule(rule_key)
    if not policy_key or not user:
        return context, None

    result = issue_discount(
        user=user,
        policy_key=policy_key,
        source_rule=rule_key,
        order_id=order_id,
        metadata=metadata,
    )
    if not result.ok:
        return context, result.reason

    ctx = dict(context or {})
    ctx['code'] = result.code
    ctx['discount_code'] = result.code
    ctx['discount_percent'] = result.discount_percent
    ctx['discount_amount'] = result.discount_amount
    ctx['discount_expiry'] = result.discount_expiry
    ctx['checkout_link'] = result.checkout_link
    if result.checkout_link and not ctx.get('link'):
        ctx['link'] = result.checkout_link
    return ctx, None


def discount_context_for_preview(rule_key: str, *, order_id: Optional[int] = None) -> Dict[str, str]:
    """نمونه context تخفیف برای preview."""
    policy_key = _policy_for_rule(rule_key)
    if not policy_key:
        return {}
    config = get_discount_policy_config()
    policy = config['policies'].get(policy_key) or {}
    percent = str(int(policy.get('percent') or 10))
    sample_code = f"{config['global'].get('code_prefix', 'DF')}-H7K4P2"
    expiry = _format_expiry(timezone.now() + timedelta(hours=int(policy.get('valid_hours') or 48)))
    link = checkout_link_with_code(sample_code, order_id=order_id)
    return {
        'code': sample_code,
        'discount_code': sample_code,
        'discount_percent': percent,
        'discount_amount': '',
        'discount_expiry': expiry,
        'checkout_link': link,
        'link': link,
    }


def active_discount_context_for_user(user, *, order_id: Optional[int] = None) -> Dict[str, str]:
    """کد تخفیف فعال موجود کاربر — بدون صدور جدید."""
    user_id = getattr(user, 'pk', None)
    if not user_id:
        return {}
    active = _active_issuance_for_user(user_id)
    if not active or not active.discount_code_id:
        return {}
    dc = active.discount_code
    is_valid, _ = dc.is_valid(user)
    if not is_valid:
        return {}
    code = dc.code
    link = checkout_link_with_code(code, order_id=order_id)
    return {
        'code': code,
        'discount_code': code,
        'discount_percent': (
            str(int(dc.discount_value)) if dc.discount_type == 'percentage' else ''
        ),
        'discount_amount': (
            str(int(dc.discount_value)) if dc.discount_type == 'fixed' else ''
        ),
        'discount_expiry': _format_expiry(dc.valid_until),
        'checkout_link': link,
        'link': link,
    }


def enrich_preview_discount_context(
    context: Dict[str, str],
    *,
    rule_key: str,
    user=None,
    order_id: Optional[int] = None,
) -> tuple[Dict[str, str], List[str]]:
    """غنی‌سازی preview — بدون صدور کد جدید."""
    if rule_key not in RULE_DISCOUNT_POLICIES:
        return dict(context or {}), []

    ctx = dict(context or {})
    warnings: List[str] = []

    if user is not None:
        active_ctx = active_discount_context_for_user(user, order_id=order_id)
        if active_ctx:
            ctx.update(active_ctx)
            return ctx, warnings

    ctx.update(discount_context_for_preview(rule_key, order_id=order_id))
    warnings.append(
        'ℹ️ کد و درصد تخفیف در Preview نمایشی است؛ هنگام ارسال واقعی کد اختصاصی صادر می‌شود.'
    )
    return ctx, warnings
