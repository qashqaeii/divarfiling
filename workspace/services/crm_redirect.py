"""ریدایرکت امن پس از عملیات CRM."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def safe_crm_next_url(request, next_url: str, *, fallback_name: str = 'workspace:crm_contacts') -> str:
    nxt = (next_url or '').strip()
    if nxt and url_has_allowed_host_and_scheme(
        nxt,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return nxt
    return reverse(fallback_name)


def append_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    pairs = [(k, v) for k, v in pairs if k != key]
    pairs.append((key, value))
    new_query = urlencode(pairs)
    return urlunparse(parsed._replace(query=new_query))
