"""لینک یکپارچه پرونده ۳۶۰ در پنل مدیریت."""
from __future__ import annotations

from urllib.parse import urlencode

from django.urls import reverse


def admin_user_profile_url(user_id: int, *, return_path: str = '') -> str:
    if not user_id:
        return ''
    path = reverse('admin_panel_user_360', args=[int(user_id)])
    if return_path:
        return path + '?' + urlencode({'return': return_path})
    return path
