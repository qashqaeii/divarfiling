"""سرویس درگاه پرداخت زیبال — request، verify و نگاشت خطاها."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

MIN_AMOUNT_RIAL = 1000
REQUEST_TIMEOUT = 15


class ZibalConfigurationError(Exception):
    """مرچنت یا تنظیمات درگاه ناقص است."""


class ZibalAPIError(Exception):
    """خطای برگشتی از API زیبال."""

    def __init__(self, result_code: int | None, message: str = ''):
        self.result_code = result_code
        self.message = message or get_result_message(result_code, 'request')
        super().__init__(self.message)


class ZibalVerifyError(ZibalAPIError):
    """خطا در تایید تراکنش."""


class ZibalAmountMismatchError(ZibalVerifyError):
    """مبلغ تایید‌شده با سفارش همخوانی ندارد."""


REQUEST_RESULT_MESSAGES: dict[int, str] = {
    100: 'درخواست پرداخت با موفقیت ثبت شد.',
    102: 'مرچنت یافت نشد. کد مرچنت را بررسی کنید.',
    103: 'مرچنت غیرفعال است.',
    104: 'مرچنت نامعتبر است.',
    105: 'مبلغ باید بیشتر از ۱,۰۰۰ ریال باشد.',
    106: 'آدرس callback نامعتبر است (باید با http یا https شروع شود).',
    113: 'مبلغ از سقف مجاز تراکنش بیشتر است.',
    201: 'تراکنش قبلاً تایید شده است.',
}

VERIFY_RESULT_MESSAGES: dict[int, str] = {
    100: 'پرداخت با موفقیت تایید شد.',
    102: 'مرچنت یافت نشد.',
    103: 'مرچنت غیرفعال است.',
    104: 'مرچنت نامعتبر است.',
    201: 'تراکنش قبلاً تایید شده است.',
    202: 'سفارش پرداخت نشده یا ناموفق بوده است.',
    203: 'کد پیگیری (trackId) نامعتبر است.',
}

CALLBACK_STATUS_MESSAGES: dict[str, str] = {
    '-1': 'در انتظار پرداخت',
    '1': 'پرداخت شده — در انتظار تایید',
    '2': 'پرداخت موفق در درگاه',
    '3': 'لغو شده توسط کاربر',
    '4': 'شماره کارت نامعتبر',
    '5': 'موجودی کافی نیست',
    '6': 'رمز اشتباه',
    '7': 'تعداد دفعات ورود رمز بیش از حد مجاز',
    '8': 'رمز کارت بیش از حد مجاز اشتباه وارد شده',
    '9': 'تراکنش نامعتبر',
    '10': 'زمان پرداخت به پایان رسید',
    '11': 'خطای درخواست تکراری',
}


@dataclass(frozen=True)
class ZibalRequestResult:
    track_id: str
    result_code: int
    message: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class ZibalVerifyResult:
    result_code: int
    message: str
    ref_number: str
    paid_amount_rial: int | None
    card_number: str
    raw: dict[str, Any]

    @property
    def is_success(self) -> bool:
        return self.result_code in (100, 201)


def get_merchant_id() -> str:
    merchant = (getattr(settings, 'ZIBAL_MERCHANT_ID', '') or '').strip()
    if not merchant:
        raise ZibalConfigurationError(
            'ZIBAL_MERCHANT_ID در فایل .env تنظیم نشده است. '
            'کد مرچنت را از panel.zibal.ir دریافت و قرار دهید.'
        )
    return merchant


def toman_to_rial(amount_toman: Decimal | int) -> int:
    return int(Decimal(str(amount_toman)) * 10)


def get_result_message(code: int | None, kind: str = 'request') -> str:
    if code is None:
        return 'خطای نامشخص در ارتباط با درگاه پرداخت.'
    messages = VERIFY_RESULT_MESSAGES if kind == 'verify' else REQUEST_RESULT_MESSAGES
    return messages.get(code, f'خطای درگاه (کد {code})')


def get_callback_status_message(status: str | None) -> str:
    if not status:
        return 'وضعیت پرداخت نامشخص است.'
    return CALLBACK_STATUS_MESSAGES.get(str(status), f'وضعیت پرداخت: {status}')


def build_callback_url(request) -> str:
    configured = (getattr(settings, 'ZIBAL_CALLBACK_URL', '') or '').strip()
    if configured.startswith('http'):
        return configured
    from django.urls import reverse
    return request.build_absolute_uri(reverse('payment:callback'))


def build_payment_payload(
    *,
    order,
    callback_url: str,
    mobile: str = '',
) -> dict[str, Any]:
    amount_rial = toman_to_rial(order.amount)
    if amount_rial < MIN_AMOUNT_RIAL:
        raise ZibalAPIError(
            105,
            'حداقل مبلغ پرداخت ۱۰۰ تومان است.',
        )

    payload: dict[str, Any] = {
        'merchant': get_merchant_id(),
        'amount': amount_rial,
        'callbackUrl': callback_url,
        'description': f'خرید {order.product.title} — پلن {order.plan.name}',
        'orderId': str(order.id),
    }
    mobile = (mobile or '').strip()
    if mobile:
        payload['mobile'] = mobile
    return payload


def request_payment(*, order, callback_url: str, mobile: str = '') -> ZibalRequestResult:
    payload = build_payment_payload(order=order, callback_url=callback_url, mobile=mobile)
    response = requests.post(
        settings.ZIBAL_REQUEST_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    result_code = data.get('result')
    message = data.get('message') or get_result_message(result_code, 'request')

    if result_code != 100:
        logger.warning('Zibal request failed for order %s: %s', order.id, data)
        raise ZibalAPIError(result_code, message)

    track_id = data.get('trackId')
    if not track_id:
        raise ZibalAPIError(None, 'پاسخ درگاه فاقد کد پیگیری است.')

    return ZibalRequestResult(
        track_id=str(track_id),
        result_code=result_code,
        message=message,
        raw=data,
    )


def verify_payment(*, track_id: str, expected_amount_rial: int | None = None) -> ZibalVerifyResult:
    payload = {
        'merchant': get_merchant_id(),
        'trackId': track_id,
    }
    response = requests.post(
        settings.ZIBAL_VERIFY_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    result_code = data.get('result')
    message = data.get('message') or get_result_message(result_code, 'verify')

    paid_amount = data.get('amount')
    if paid_amount is not None:
        paid_amount = int(paid_amount)

    result = ZibalVerifyResult(
        result_code=result_code,
        message=message,
        ref_number=str(data.get('refNumber') or ''),
        paid_amount_rial=paid_amount,
        card_number=str(data.get('cardNumber') or ''),
        raw=data,
    )

    if not result.is_success:
        logger.warning('Zibal verify failed for trackId %s: %s', track_id, data)
        raise ZibalVerifyError(result_code, message)

    if expected_amount_rial is not None and paid_amount is not None:
        if paid_amount != expected_amount_rial:
            logger.error(
                'Zibal amount mismatch trackId=%s expected=%s paid=%s',
                track_id,
                expected_amount_rial,
                paid_amount,
            )
            raise ZibalAmountMismatchError(
                result_code,
                'مبلغ پرداخت‌شده با سفارش همخوانی ندارد. با پشتیبانی تماس بگیرید.',
            )

    return result


def get_start_pay_url(track_id: str) -> str:
    base = getattr(settings, 'ZIBAL_START_PAY_URL', 'https://gateway.zibal.ir/start/')
    return f'{base}{track_id}'


def get_start_pay_bridge_url(track_id: str, request=None) -> str:
    """
    آدرس واسط روی دامنهٔ پذیرنده.

    برای اپ موبایل و بات‌ها که مستقیماً gateway.zibal.ir را باز می‌کنند،
    هدر Referer ارسال نمی‌شود. با عبور از این URL، مرورگر هنگام ریدایرکت
    به /start زیبال، Referer دامنهٔ ثبت‌شده را می‌فرستد (الزام شاپرک).
    """
    from django.urls import reverse

    path = reverse('payment:start', kwargs={'track_id': track_id})
    if request is not None:
        return request.build_absolute_uri(path)
    site = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    if site:
        return f'{site}{path}'
    return path
