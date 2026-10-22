"""کوئری‌های دسترسی لایسنس ربات — هم‌تراز workspace.services.access برای ادمین و KPI."""
from __future__ import annotations

from typing import Any, Dict

from django.db.models import BooleanField, Exists, ExpressionWrapper, OuterRef, Q, QuerySet
from django.utils import timezone

from licenses.models import License, LicenseActivation
from shop.services.license_entitlement import LICENSE_ACCESS_ORDER_STATUSES

BOT_ACCESS_KIND_LABELS = {
    'owner': 'مالک',
    'assigned': 'تخصیصی تیم',
    'seat': 'صندلی آژانس',
    'pending': 'در انتظار فعال‌سازی',
    'none': 'بدون دسترسی',
}


def license_entitlement_valid_q(prefix: str = '') -> Q:
    """سفارش معتبر + انقضا + بدون تعلیق/منقضی."""
    p = f'{prefix}' if prefix else ''
    now = timezone.now()
    return (
        Q(**{f'{p}order__status__in': LICENSE_ACCESS_ORDER_STATUSES})
        & (Q(**{f'{p}expires_at__isnull': True}) | Q(**{f'{p}expires_at__gt': now}))
        & ~Q(**{f'{p}status__in': ['suspended', 'expired']})
    )


def owner_active_license_exists():
    return Exists(
        License.objects.filter(
            order__user=OuterRef('pk'),
            status='active',
        ).filter(license_entitlement_valid_q())
    )


def assigned_license_exists():
    return Exists(
        License.objects.filter(
            assigned_user=OuterRef('pk'),
        ).filter(license_entitlement_valid_q())
    )


def assigned_seat_exists():
    return Exists(
        LicenseActivation.objects.filter(
            assigned_user=OuterRef('pk'),
            is_active=True,
            license__status='active',
        ).filter(license_entitlement_valid_q(prefix='license__'))
    )


def annotate_user_bot_license_access(qs: QuerySet) -> QuerySet:
    """Annotate: _bot_lic_* flags, has_bot_license_access, has_active_license (alias)."""
    qs = qs.annotate(
        _bot_lic_owner=owner_active_license_exists(),
        _bot_lic_assigned=assigned_license_exists(),
        _bot_lic_seat=assigned_seat_exists(),
    )
    return qs.annotate(
        has_bot_license_access=ExpressionWrapper(
            Q(_bot_lic_owner=True) | Q(_bot_lic_assigned=True) | Q(_bot_lic_seat=True),
            output_field=BooleanField(),
        ),
        has_active_license=ExpressionWrapper(
            Q(_bot_lic_owner=True) | Q(_bot_lic_assigned=True) | Q(_bot_lic_seat=True),
            output_field=BooleanField(),
        ),
    )


def annotate_pending_bot_activation(qs: QuerySet) -> QuerySet:
    """پس از annotate_user_bot_license_access و paid_orders_count."""
    return qs.annotate(
        has_pending_bot_activation=ExpressionWrapper(
            Q(paid_orders_count__gt=0) & ~Q(has_bot_license_access=True),
            output_field=BooleanField(),
        ),
    )


def resolve_bot_access_kind(user) -> str:
    if getattr(user, '_bot_lic_owner', False):
        return 'owner'
    if getattr(user, '_bot_lic_assigned', False):
        return 'assigned'
    if getattr(user, '_bot_lic_seat', False):
        return 'seat'
    if getattr(user, 'has_pending_bot_activation', False):
        return 'pending'
    return 'none'


def bot_access_display(user) -> Dict[str, Any]:
    kind = resolve_bot_access_kind(user)
    has_access = bool(getattr(user, 'has_bot_license_access', False))
    label = BOT_ACCESS_KIND_LABELS.get(kind, '—')
    if has_access and kind != 'none':
        plan = (
            getattr(user, 'license_plan_owner', None)
            or getattr(user, 'license_plan_assigned', None)
            or getattr(user, 'license_plan_seat', None)
            or getattr(user, 'license_plan_name', None)
            or ''
        )
        if plan:
            label = f'{label} — {plan}'
    elif kind == 'pending':
        label = BOT_ACCESS_KIND_LABELS['pending']
    elif not has_access:
        label = BOT_ACCESS_KIND_LABELS['none']
    return {
        'has_bot_license_access': has_access,
        'license_access_kind': kind,
        'license_access_label': label,
    }


def users_without_bot_license_qs(base_qs: QuerySet | None = None) -> QuerySet:
    from django.contrib.auth import get_user_model

    qs = base_qs if base_qs is not None else get_user_model().objects.all()
    return annotate_user_bot_license_access(qs).filter(has_bot_license_access=False)
