"""سرویس احراز هویت دسکتاپ — reuse از mobile/JWT."""
from __future__ import annotations

from django.contrib.auth import authenticate

from accounts.phone_utils import find_user_by_phone
from rest_framework_simplejwt.tokens import RefreshToken


def tokens_for_user(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'expires_in': int(refresh.access_token.lifetime.total_seconds()),
    }


def authenticate_credentials(username: str, password: str, request=None):
    username = (username or '').strip()
    password = password or ''
    if not username or not password:
        return None, 'نام کاربری و رمز عبور الزامی است.'

    user = authenticate(request, username=username, password=password)
    if user is None:
        user = find_user_by_phone(username)
        if not user or not user.check_password(password):
            return None, 'نام کاربری یا رمز عبور اشتباه است.'
    return user, None
