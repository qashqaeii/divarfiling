"""Facade یکپارچه ارسال پیامک — انتخاب provider از تنظیمات."""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone

from . import console, faraz
from .base import SmsConfigurationError, SmsError, SmsResult, SmsSendError

logger = logging.getLogger(__name__)


def _provider_name() -> str:
    name = (getattr(settings, 'SMS_PROVIDER', 'console') or 'console').strip().lower()
    if name in ('fake', 'dev', 'test'):
        return 'console'
    if name in ('faraz', 'farazsms', 'iranpayamak', 'payamak'):
        return 'faraz'
    return name


def _backend():
    name = _provider_name()
    if name == 'faraz':
        return faraz
    if name == 'console':
        return console
    raise SmsConfigurationError(f'ارائه‌دهنده پیامک ناشناخته: {name}')


def _prepare_phone(raw: str) -> str:
    phone = normalize_phone(raw)
    if not is_valid_iran_mobile(phone):
        raise SmsSendError('شماره موبایل معتبر نیست.', code='sms_invalid_phone')
    return phone


def send_pattern_sms(
    phone: str,
    *,
    pattern_code: str | None = None,
    attributes: dict[str, Any] | None = None,
    purpose: str = '',
) -> SmsResult:
    """
    ارسال پیامک الگو‌محور.
    اگر pattern_code خالی باشد، از نگاشت purpose در تنظیمات استفاده می‌شود.
    """
    if not getattr(settings, 'SMS_ENABLED', True):
        raise SmsSendError('ارسال پیامک غیرفعال است.', code='sms_disabled')

    normalized = _prepare_phone(phone)
    code = (pattern_code or '').strip()
    if not code and purpose:
        patterns = getattr(settings, 'FARAZSMS_PATTERNS', {}) or {}
        code = (patterns.get(purpose) or '').strip()
    if not code and _provider_name() == 'console':
        # توسعه/تست بدون نیاز به الگوی واقعی پنل
        code = purpose or 'console-dev'
    if not code:
        raise SmsConfigurationError(
            f'کد الگوی پیامک برای «{purpose or "ارسال"}» تنظیم نشده است.'
        )

    clean_attrs: dict[str, str] = {}
    for key, value in (attributes or {}).items():
        if value is None:
            continue
        clean_attrs[str(key)] = str(value)

    try:
        result = _backend().send_pattern(
            phone=normalized,
            pattern_code=code,
            attributes=clean_attrs,
        )
    except SmsError:
        raise
    except Exception as exc:  # noqa: BLE001 — لایه مرزی
        logger.exception('Unexpected SMS pattern failure')
        raise SmsSendError('خطای غیرمنتظره در ارسال پیامک.', code='sms_unexpected') from exc

    logger.info(
        'SMS pattern sent provider=%s phone=%s**** purpose=%s message_id=%s',
        result.provider,
        normalized[:4],
        purpose or '-',
        result.message_id or '-',
    )
    return result


def send_simple_sms(phone: str, text: str) -> SmsResult:
    """ارسال پیامک متنی ساده (اعلان‌های سیستمی بدون الگو)."""
    if not getattr(settings, 'SMS_ENABLED', True):
        raise SmsSendError('ارسال پیامک غیرفعال است.', code='sms_disabled')

    normalized = _prepare_phone(phone)
    try:
        result = _backend().send_simple(phone=normalized, text=text)
    except SmsError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception('Unexpected SMS simple failure')
        raise SmsSendError('خطای غیرمنتظره در ارسال پیامک.', code='sms_unexpected') from exc

    logger.info(
        'SMS simple sent provider=%s phone=%s**** message_id=%s',
        result.provider,
        normalized[:4],
        result.message_id or '-',
    )
    return result


def get_balance() -> Any:
    return _backend().get_balance()


def _as_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace(',', '').replace('٬', '').replace(' ', '')
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _extract_credit(raw: Any) -> float | None:
    """استخراج مبلغ موجودی (تومان) — فیلد رسمی: balanceAmount."""
    if raw is None:
        return None
    direct = _as_number(raw)
    if direct is not None and not isinstance(raw, dict):
        return direct

    if not isinstance(raw, dict):
        return None

    # مستندات: https://docs.iranpayamak.com/account-balance-13717911e0
    for key in (
        'balanceAmount', 'balance_amount', 'BalanceAmount',
        'credit', 'balance', 'remain', 'remaining',
        'credit_amount', 'account_credit', 'wallet',
    ):
        if key in raw and raw[key] is not None:
            num = _as_number(raw[key])
            if num is not None:
                return num

    # جمع amountهای details در صورت نبودن balanceAmount
    details = raw.get('details')
    if isinstance(details, list) and details:
        total = 0.0
        found = False
        for item in details:
            if not isinstance(item, dict):
                continue
            amount = _as_number(item.get('amount'))
            if amount is not None:
                total += amount
                found = True
        if found:
            return total

    nested = raw.get('data')
    if isinstance(nested, dict):
        return _extract_credit(nested)
    return None


def _extract_sms_count(raw: Any) -> int | None:
    """تعداد پیامک باقی‌مانده — فیلد رسمی: balanceCount."""
    if not isinstance(raw, dict):
        return None
    for key in (
        'balanceCount', 'balance_count', 'BalanceCount',
        'sms_count', 'remaining_count',
    ):
        if key in raw and raw[key] is not None:
            num = _as_number(raw[key])
            if num is not None:
                return int(num)

    details = raw.get('details')
    if isinstance(details, list) and details:
        total = 0
        found = False
        for item in details:
            if not isinstance(item, dict):
                continue
            count = _as_number(item.get('count'))
            if count is not None:
                total += int(count)
                found = True
        if found:
            return total

    nested = raw.get('data')
    if isinstance(nested, dict):
        return _extract_sms_count(nested)
    return None


def _raw_debug(raw: Any) -> str:
    """خلاصه امن از پاسخ برای نمایش در پنل ادمین."""
    if raw is None:
        return 'null'
    if isinstance(raw, dict):
        keys = ', '.join(sorted(str(k) for k in raw.keys())[:12])
        return f'dict[{keys}]'
    if isinstance(raw, list):
        return f'list(len={len(raw)})'
    return type(raw).__name__


def get_sms_balance_snapshot(*, use_cache: bool = True, cache_ttl: int = 60) -> dict[str, Any]:
    """
    موجودی پنل پیامک برای داشبورد ادمین.
    پاسخ رسمی: balanceAmount (تومان) + balanceCount (تعداد پیامک).
    """
    from django.core.cache import cache

    provider = _provider_name()
    provider_labels = {
        'faraz': 'فراز اس‌ام‌اس',
        'console': 'کنسول (تست)',
    }
    line = (getattr(settings, 'FARAZSMS_LINE_NUMBER', '') or '').strip()
    enabled = bool(getattr(settings, 'SMS_ENABLED', True))
    cache_key = f'admin:sms_balance:v3:{provider}'

    if use_cache:
        cached = cache.get(cache_key)
        if isinstance(cached, dict) and cached.get('provider') == provider:
            return cached

    base: dict[str, Any] = {
        'ok': False,
        'credit': None,
        'sms_count': None,
        'provider': provider,
        'provider_label': provider_labels.get(provider, provider),
        'line_number': line,
        'enabled': enabled,
        'is_low': False,
        'error': '',
        'raw': None,
    }

    if not enabled:
        base['error'] = 'ارسال پیامک در تنظیمات غیرفعال است.'
        return base

    try:
        raw = get_balance()
    except SmsConfigurationError as exc:
        base['error'] = str(exc.message or exc)
        return base
    except SmsSendError as exc:
        base['error'] = str(exc.message or exc)
        return base
    except Exception:  # noqa: BLE001
        logger.exception('SMS balance fetch failed')
        base['error'] = 'دریافت موجودی پنل پیامک ناموفق بود.'
        return base

    credit = _extract_credit(raw)
    sms_count = _extract_sms_count(raw) if isinstance(raw, dict) else None
    if credit is None and sms_count is None:
        logger.warning('SMS balance unreadable raw=%s', _raw_debug(raw))
        base['error'] = f'پاسخ موجودی از پنل قابل‌خواندن نبود ({_raw_debug(raw)}).'
        base['raw'] = raw if isinstance(raw, (dict, list, str, int, float)) else None
        return base

    if credit is None:
        credit = 0.0

    low_threshold = float(getattr(settings, 'FARAZSMS_LOW_BALANCE', 50_000) or 50_000)
    is_low = provider == 'faraz' and credit < low_threshold
    base.update({
        'ok': True,
        'credit': credit,
        'sms_count': sms_count,
        'is_low': is_low,
        'raw': raw if isinstance(raw, dict) else {'balanceAmount': credit},
        'error': '',
    })
    if use_cache and cache_ttl > 0:
        cache.set(cache_key, base, cache_ttl)
    return base
