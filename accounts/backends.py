"""
Authentication Backend — ورود با شماره موبایل
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

from accounts.phone_utils import normalize_phone

User = get_user_model()


class PhoneAuthBackend(ModelBackend):
    """احراز هویت با شماره موبایل نرمال‌شده."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('username')

        if username is None or password is None:
            return None

        phone = normalize_phone(username)
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None
