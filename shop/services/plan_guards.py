"""شرایط خرید پلن‌های لایسنس."""
from __future__ import annotations

from urllib.parse import quote

from django.urls import reverse

from shop.models import LicensePlan


def is_daily_plan(plan: LicensePlan | None) -> bool:
    return bool(plan and plan.plan_type == 'daily')


def requires_phone_verification_for_plan(plan: LicensePlan | None) -> bool:
    """پلن آزمایشی یک‌روزه — تأیید موبایل الزامی."""
    return is_daily_plan(plan)


def user_meets_plan_requirements(user, plan: LicensePlan | None) -> tuple[bool, str | None]:
    if not requires_phone_verification_for_plan(plan):
        return True, None
    if not user or not user.is_authenticated:
        return False, 'برای خرید پلن آزمایشی یک‌روزه باید وارد حساب شوید.'
    if not getattr(user, 'phone_verified', False):
        return (
            False,
            'برای خرید پلن آزمایشی یک‌روزه، تأیید شماره موبایل با پیامک الزامی است.',
        )
    return True, None


def verify_phone_redirect_url(next_path: str) -> str:
    safe_next = next_path if next_path.startswith('/') and not next_path.startswith('//') else reverse('dashboard')
    return f"{reverse('otp_verify_phone')}?next={quote(safe_next, safe='')}"
