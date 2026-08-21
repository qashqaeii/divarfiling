"""تکمیل ثبت‌نام و بازیابی رمز پس از تأیید OTP — منبع واحد برای وب و موبایل."""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import User, UserProfile
from accounts.phone_utils import normalize_phone, phone_username

logger = logging.getLogger(__name__)


class AccountCompletionError(Exception):
    def __init__(self, message: str, *, code: str = 'account_error'):
        self.message = message
        self.code = code
        super().__init__(message)


def create_user_from_verified_phone(phone: str, password: str, *, request=None) -> User:
    """ایجاد حساب پس از تأیید OTP ثبت‌نام — همان منطق ویوی وب."""
    phone = normalize_phone(phone or '')
    with transaction.atomic():
        if User.objects.select_for_update().filter(phone=phone).exists():
            raise AccountCompletionError(
                'این شماره قبلاً ثبت‌نام شده است. وارد شوید.',
                code='phone_taken',
            )

        username = phone_username(phone)
        base = username
        n = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}_{n}'
            n += 1

        user = User(
            username=username,
            phone=phone,
            phone_verified=True,
            phone_verified_at=timezone.now(),
        )
        user.set_password(password)
        try:
            user.save()
        except IntegrityError as exc:
            raise AccountCompletionError(
                'این شماره قبلاً ثبت‌نام شده است. وارد شوید.',
                code='phone_taken',
            ) from exc
    UserProfile.objects.get_or_create(user=user)

    try:
        from affiliates.services import assign_referred_user, capture_referral_from_request

        affiliate = capture_referral_from_request(request) if request is not None else None
        assign_referred_user(user, affiliate)
    except Exception:
        logger.exception('affiliate assignment failed during registration')

    try:
        from accounts.services.lead_attribution import attribute_signup

        attribute_signup(user=user, request=request)
    except Exception:
        logger.exception('lead acquisition signup attribution failed')

    return user


def set_password_for_phone(phone: str, password: str) -> User:
    """تنظیم رمز جدید پس از تأیید OTP بازیابی."""
    phone = normalize_phone(phone or '')
    user = User.objects.filter(phone=phone, is_active=True).first()
    if not user:
        raise AccountCompletionError('حساب کاربری یافت نشد.', code='user_not_found')
    user.set_password(password)
    user.save(update_fields=['password'])
    return user
