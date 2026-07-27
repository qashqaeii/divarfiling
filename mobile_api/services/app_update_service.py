"""سرویس متادیتای نسخه اپ اندروید برای آپدیت داخلی."""
from __future__ import annotations

from typing import Any, Dict, Optional

from shop.services.app_downloads import build_android_update_payload


def parse_current_build(raw) -> Optional[int]:
    if raw is None or raw == '':
        return None
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def app_version_payload(request) -> Dict[str, Any]:
    current = parse_current_build(request.query_params.get('current_build'))
    if current is None:
        # هدر اختیاری از کلاینت‌های قدیمی‌تر
        header_build = request.headers.get('X-App-Build') or request.META.get('HTTP_X_APP_BUILD')
        current = parse_current_build(header_build)
    return build_android_update_payload(request=request, current_build=current)
