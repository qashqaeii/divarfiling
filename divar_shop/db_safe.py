"""ابزارهای ایمن در برابر قطع/خطای اتصال DB در context processorها."""
from __future__ import annotations

from django.db import DatabaseError, InterfaceError

DB_CONTEXT_ERRORS = (DatabaseError, InterfaceError)


def db_context_safe(default=None):
    """Decorator — در صورت خطای DB مقدار default برمی‌گرداند."""
    default = default if default is not None else {}

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except DB_CONTEXT_ERRORS:
                if callable(default):
                    return default()
                return dict(default) if isinstance(default, dict) else default

        wrapper.__name__ = getattr(func, '__name__', 'wrapper')
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
