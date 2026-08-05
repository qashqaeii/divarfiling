"""محدودیت نرخ درخواست برای API دسکتاپ."""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class DesktopLoginThrottle(AnonRateThrottle):
    scope = 'desktop_login'


class DesktopRefreshThrottle(AnonRateThrottle):
    scope = 'desktop_refresh'


class DesktopBindThrottle(UserRateThrottle):
    scope = 'desktop_bind'


class DesktopValidateThrottle(UserRateThrottle):
    scope = 'desktop_validate'
