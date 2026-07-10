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


def _extract_credit(raw: Any) -> float | None:
    """استخراج مبلغ موجودی از پاسخ پنل (عدد یا دیکشنری)."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        s = raw.strip().replace(',', '').replace('٬', '')
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    if isinstance(raw, dict):
        for key in (
            'credit', 'balance', 'amount', 'remain', 'remaining',
            'credit_amount', 'account_credit', 'wallet',
        ):
            if key in raw and raw[key] is not None:
                credit = _extract_credit(raw[key])
                if credit is not None:
                    return credit
        # بعضی پاسخ‌ها credit را داخل data تو در تو می‌گذارند
        nested = raw.get('data')
        if nested is not None and nested is not raw:
            return _extract_credit(nested)
    return None


def get_sms_balance_snapshot(*, use_cache: bool = True, cache_ttl: int = 60) -> dict[str, Any]:
    """
    موجودی پنل پیامک برای داشبورد ادمین.
    خطا را می‌بلعد تا صفحه مدیریت از کار نیفتد.
    """
    from django.core.cache import cache

    provider = _provider_name()
    provider_labels = {
        'faraz': 'فراز اس‌ام‌اس',
        'console': 'کنسول (تست)',
    }
    line = (getattr(settings, 'FARAZSMS_LINE_NUMBER', '') or '').strip()
    enabled = bool(getattr(settings, 'SMS_ENABLED', True))
    cache_key = f'admin:sms_balance:{provider}'

    if use_cache:
        cached = cache.get(cache_key)
        if isinstance(cached, dict) and cached.get('provider') == provider:
            return cached

    base: dict[str, Any] = {
        'ok': False,
        'credit': None,
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
    if credit is None:
        base['error'] = 'پاسخ موجودی از پنل قابل‌خواندن نبود.'
        base['raw'] = raw if isinstance(raw, (dict, list, str, int, float)) else None
        return base

    low_threshold = float(getattr(settings, 'FARAZSMS_LOW_BALANCE', 50_000) or 50_000)
    is_low = provider == 'faraz' and credit < low_threshold
    base.update({
        'ok': True,
        'credit': credit,
        'is_low': is_low,
        'raw': raw if isinstance(raw, dict) else {'credit': credit},
        'error': '',
    })
    if use_cache and cache_ttl > 0:
        cache.set(cache_key, base, cache_ttl)
    return base
