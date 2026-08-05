"""تب‌های داشبورد پروفایل — slug، اعتبارسنجی و ساخت URL."""
from __future__ import annotations

from urllib.parse import urlencode

from django.urls import reverse

DEFAULT_TAB = 'overview'

DASHBOARD_TAB_SLUGS = (
    'overview',
    'orders',
    'licenses',
    'downloads',
    'transactions',
    'affiliate',
    'profile',
)

VALID_TABS = frozenset(DASHBOARD_TAB_SLUGS)


def resolve_dashboard_tab(
    *,
    tab_from_path: str | None = None,
    tab_from_query: str | None = None,
    has_paid_orders: bool = False,
) -> str:
    raw = (tab_from_path or tab_from_query or DEFAULT_TAB).strip().lower()
    if raw not in VALID_TABS:
        return DEFAULT_TAB
    if raw == 'affiliate' and not has_paid_orders:
        return DEFAULT_TAB
    return raw


def dashboard_tab_url(tab: str, *, query=None) -> str:
    tab = (tab or DEFAULT_TAB).strip().lower()
    if tab not in VALID_TABS or tab == DEFAULT_TAB:
        base = reverse('dashboard')
    else:
        base = reverse('dashboard_tab', kwargs={'tab': tab})
    if query:
        if hasattr(query, 'urlencode'):
            qs = query.urlencode()
        else:
            filtered = {k: v for k, v in query.items() if v not in (None, '')}
            qs = urlencode(filtered) if filtered else ''
        if qs:
            return f'{base}?{qs}'
    return base


def dashboard_tab_urls() -> dict[str, str]:
    return {slug: dashboard_tab_url(slug) for slug in DASHBOARD_TAB_SLUGS}
