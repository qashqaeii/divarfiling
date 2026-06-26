"""نگاشت نوع فعالیت API موبایل ↔ workspace."""
from __future__ import annotations

from typing import Optional

# کلیدهای API انگلیسی → مقدار ذخیره‌شده در workspace
API_TO_WORKSPACE = {
    'call': 'تماس',
    'whatsapp': 'واتساپ',
    'visit': 'بازدید',
    'followup': 'پیگیری',
    'note': 'یادداشت',
    'contract': 'جلسه',
    'other': 'پیام',
}

WORKSPACE_TO_API = {v: k for k, v in API_TO_WORKSPACE.items()}


def api_type_to_workspace(api_type: str) -> Optional[str]:
    key = (api_type or '').strip().lower()
    if key in API_TO_WORKSPACE:
        return API_TO_WORKSPACE[key]
    # اگر فارسی ارسال شد
    if key in {v.lower() for v in API_TO_WORKSPACE.values()}:
        for ws in API_TO_WORKSPACE.values():
            if ws.lower() == key:
                return ws
    return None


def workspace_type_to_api(workspace_type: str) -> str:
    return WORKSPACE_TO_API.get(workspace_type, 'other')
