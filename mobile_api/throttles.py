"""محدودیت نرخ درخواست برای API موبایل."""
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle


class MobileLoginThrottle(AnonRateThrottle):
    scope = 'mobile_login'


class MobileRefreshThrottle(AnonRateThrottle):
    scope = 'mobile_refresh'


class MobileUserThrottle(UserRateThrottle):
    scope = 'mobile_user'


class MobileExtractionThrottle(ScopedRateThrottle):
    scope = 'mobile_extraction'
