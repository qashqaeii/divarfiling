"""ثبت رویدادهای قیف خرید پلن."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from shop.models import LicensePlan, PlanFunnelEvent, Product


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ''


def record_plan_funnel_event(
    request,
    event_type: str,
    *,
    product: Product | None = None,
    plan: LicensePlan | None = None,
    metadata: dict[str, Any] | None = None,
    dedupe_minutes: int = 30,
) -> PlanFunnelEvent | None:
    """ثبت رویداد با جلوگیری از تکرار پشت‌سرهم در یک نشست."""
    session_key = _session_key(request)
    since = timezone.now() - timedelta(minutes=dedupe_minutes)

    qs = PlanFunnelEvent.objects.filter(
        event_type=event_type,
        session_key=session_key,
        created_at__gte=since,
    )
    if product is not None:
        qs = qs.filter(product=product)
    if plan is not None and event_type == 'checkout_view':
        qs = qs.filter(plan=plan)
    if qs.exists():
        return None

    return PlanFunnelEvent.objects.create(
        event_type=event_type,
        user=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
        session_key=session_key,
        product=product,
        plan=plan,
        metadata=metadata or {},
    )
