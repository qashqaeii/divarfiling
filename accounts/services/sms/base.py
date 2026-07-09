"""انواع مشترک و خطاهای لایه پیامک."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class SmsError(Exception):
    """خطای پایه سرویس پیامک."""

    def __init__(self, message: str = '', *, code: str = 'sms_error'):
        self.message = message or 'خطا در ارسال پیامک.'
        self.code = code
        super().__init__(self.message)


class SmsConfigurationError(SmsError):
    """تنظیمات پنل پیامک ناقص است."""

    def __init__(self, message: str = ''):
        super().__init__(
            message or 'تنظیمات پنل پیامک ناقص است.',
            code='sms_config',
        )


class SmsSendError(SmsError):
    """ارسال پیامک ناموفق بود (API، timeout، پاسخ خطا)."""

    def __init__(
        self,
        message: str = '',
        *,
        code: str = 'sms_send_failed',
        provider_status: str | None = None,
        http_status: int | None = None,
    ):
        self.provider_status = provider_status
        self.http_status = http_status
        super().__init__(message or 'ارسال پیامک ناموفق بود.', code=code)


@dataclass(frozen=True)
class SmsResult:
    """نتیجه ارسال پیامک — بدون متن حساس."""

    success: bool
    provider: str
    phone: str
    message_id: str = ''
    status: str = 'sent'
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_fake(self) -> bool:
        return self.provider == 'console'
