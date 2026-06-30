"""فیلترهای لاگ — کاهش نویز اسکنرها در django.log"""
import logging


class SkipDisallowedHostFilter(logging.Filter):
    """درخواست‌های Host نامعتبر (اسکنر/bot) را در فایل لاگ ثبت نکن."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            if exc_type is not None and exc_type.__name__ == 'DisallowedHost':
                return False
        message = record.getMessage()
        if 'Invalid HTTP_HOST header' in message or 'DisallowedHost' in message:
            return False
        return True
