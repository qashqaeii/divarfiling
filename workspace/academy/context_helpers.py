"""Context helpers for academy banners in workspace views."""
from __future__ import annotations

from workspace.academy.services.contextual_service import get_contextual_banner


def inject_academy_context(ctx: dict, user, key: str) -> dict:
    banner = get_contextual_banner(user, key)
    if banner:
        ctx['academy_contextual'] = banner
    return ctx


def inject_datasets_empty_banner(ctx: dict, user) -> dict:
    """بنر آموزش استخراج وقتی کاربر هنوز دیتاست ندارد."""
    stats = ctx.get('stats') or {}
    if int(stats.get('files') or 0) != 0:
        return ctx
    return inject_academy_context(ctx, user, 'datasets_empty')
