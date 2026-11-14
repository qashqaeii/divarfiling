"""لینک یکپارچه پرونده ۳۶۰ در پنل مدیریت."""
from __future__ import annotations

from urllib.parse import urlencode

from django.urls import reverse


def admin_user_profile_url(
    user_id: int,
    *,
    return_path: str = '',
    tab: str = '',
    ticket_id: int | None = None,
) -> str:
    if not user_id:
        return ''
    path = reverse('admin_panel_user_360', args=[int(user_id)])
    params: dict[str, str] = {}
    tab_key = (tab or '').strip()
    if tab_key:
        params['tab'] = tab_key
    if ticket_id:
        params['ticket'] = str(int(ticket_id))
    if return_path:
        params['return'] = return_path
    if params:
        return path + '?' + urlencode(params)
    return path
