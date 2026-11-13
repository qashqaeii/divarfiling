"""کدهای تخفیف شخصی — صادرشده از UserDiscountIssuance فقط برای همان کاربر."""
from __future__ import annotations

from typing import Optional

from django.contrib.auth.models import AnonymousUser

from shop.models import DiscountCode


def discount_exclusive_user_id(discount_code: DiscountCode) -> Optional[int]:
    """اگر کد از صدور اختصاصی است، شناسه صاحب را برمی‌گرداند."""
    from accounts.models import UserDiscountIssuance

    user_ids = list(
        UserDiscountIssuance.objects.filter(discount_code_id=discount_code.pk)
        .values_list('user_id', flat=True)
        .distinct()[:2]
    )
    if len(user_ids) != 1:
        return None
    return user_ids[0]


def validate_personal_discount_owner(discount_code: DiscountCode, user) -> tuple[bool, str]:
    owner_id = discount_exclusive_user_id(discount_code)
    if owner_id is None:
        return True, ''
    if not user or isinstance(user, AnonymousUser) or not getattr(user, 'is_authenticated', False):
        return False, 'برای استفاده از این کد تخفیف باید وارد حساب شوید.'
    if getattr(user, 'pk', None) != owner_id:
        return False, 'این کد تخفیف فقط برای صاحب آن قابل استفاده است.'
    return True, ''
