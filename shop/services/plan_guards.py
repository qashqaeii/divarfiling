"""شرایط خرید پلن‌های لایسنس."""
from __future__ import annotations

from urllib.parse import quote

from django.urls import reverse

from shop.models import LicensePlan, Order

BLOCK_NONE = ''
BLOCK_PHONE_VERIFY = 'phone_verify'
BLOCK_DAILY_USED = 'daily_used'


def is_daily_plan(plan: LicensePlan | None) -> bool:
    return bool(plan and plan.plan_type == 'daily')


def requires_phone_verification_for_plan(plan: LicensePlan | None) -> bool:
    """پلن آزمایشی یک‌هفته‌ای — تأیید موبایل الزامی."""
    return is_daily_plan(plan)


def user_has_purchased_daily_plan(user) -> bool:
    """کاربر قبلاً پلن آزمایشی را خریده (حتی اگر منقضی شده باشد)."""
    if not user or not user.is_authenticated:
        return False
    return Order.objects.filter(
        user=user,
        status='paid',
        plan__plan_type='daily',
    ).exists()


def is_plan_visible_in_catalog(user, plan: LicensePlan | None) -> bool:
    """پلن آزمایشی پس از یک‌بار خرید در لیست پلن‌ها نمایش داده نمی‌شود."""
    if not plan:
        return False
    if is_daily_plan(plan) and user_has_purchased_daily_plan(user):
        return False
    return True


def filter_visible_plans(plans, user):
    return [plan for plan in plans if is_plan_visible_in_catalog(user, plan)]


def evaluate_plan_purchase(user, plan: LicensePlan | None) -> tuple[bool, str | None, str]:
    """بررسی امکان خرید پلن — (مجاز، پیام خطا، دلیل مسدودیت)."""
    if not is_daily_plan(plan):
        return True, None, BLOCK_NONE

    if not user or not user.is_authenticated:
        return False, 'برای خرید پلن آزمایشی یک‌هفته‌ای باید وارد حساب شوید.', BLOCK_DAILY_USED

    if user_has_purchased_daily_plan(user):
        return (
            False,
            'پلن آزمایشی یک‌هفته‌ای فقط یک‌بار قابل خرید است. لطفاً یکی از پلن‌های دیگر را انتخاب کنید.',
            BLOCK_DAILY_USED,
        )

    if not getattr(user, 'phone_verified', False):
        return (
            False,
            'برای خرید پلن آزمایشی یک‌هفته‌ای، تأیید شماره موبایل با پیامک الزامی است.',
            BLOCK_PHONE_VERIFY,
        )

    return True, None, BLOCK_NONE


def user_meets_plan_requirements(user, plan: LicensePlan | None) -> tuple[bool, str | None]:
    ok, message, _reason = evaluate_plan_purchase(user, plan)
    return ok, message


def verify_phone_redirect_url(next_path: str) -> str:
    safe_next = next_path if next_path.startswith('/') and not next_path.startswith('//') else reverse('dashboard')
    return f"{reverse('otp_verify_phone')}?next={quote(safe_next, safe='')}"
