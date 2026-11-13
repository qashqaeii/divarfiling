"""رابط واحد پرونده ۳۶۰."""
from __future__ import annotations

from typing import Any, Dict, Optional

from accounts.services.admin_user_360.common import TAB_KEYS, get_user_360_user, safe_query_int, user_summary_row
from accounts.services.admin_user_360.shell import build_user_360_shell
from accounts.services.admin_user_360.tabs import TAB_BUILDERS

__all__ = ['TAB_KEYS', 'build_user_360_shell', 'build_user_360_tab', 'get_user_360_user']


def build_user_360_tab(
    user_id: int,
    tab: str,
    *,
    reveal_sensitive: bool = False,
    include_internal_notes: bool = False,
    **query,
) -> Optional[Dict[str, Any]]:
    if tab not in TAB_BUILDERS:
        return None
    user = get_user_360_user(user_id)
    if not user:
        return None
    summary = user_summary_row(user)
    builder = TAB_BUILDERS[tab]
    payload = builder(
        user,
        summary,
        reveal_sensitive=reveal_sensitive,
        include_internal_notes=include_internal_notes,
        page=safe_query_int(query.get('page'), 1, minimum=1, maximum=10_000),
        page_size=safe_query_int(query.get('page_size'), 25, minimum=1, maximum=100),
        kind=query.get('kind', ''),
        platform=query.get('platform', ''),
        success=query.get('success', ''),
        sort=query.get('sort', '-at'),
        days=query.get('days'),
    )
    return {'ok': True, 'tab': tab, 'data': payload}
