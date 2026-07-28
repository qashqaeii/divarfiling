"""Suppression یکپارچه برای جذب، Activation، Recovery و تمدید لایسنس."""
from __future__ import annotations

from typing import Optional

from accounts.models import GrowthJourney, SuppressionEntry
from accounts.phone_utils import find_user_by_phone, is_valid_iran_mobile, normalize_phone

# purposes: acquisition | activation | recovery | license_renewal | marketing
PURPOSE_ACQUISITION = 'acquisition'
PURPOSE_ACTIVATION = 'activation'
PURPOSE_RECOVERY = 'recovery'
PURPOSE_LICENSE_RENEWAL = 'license_renewal'
PURPOSE_MARKETING = 'marketing'
PURPOSE_LICENSED_MARKETING = 'licensed_marketing'


def _has_active_pending_order(user) -> bool:
    if not user:
        return False
    from shop.models import Order
    return Order.objects.filter(
        user=user,
        status__in=('pending', 'pending_verification'),
    ).exists()


def _has_active_license(user) -> bool:
    if not user:
        return False
    from django.db.models import Q
    from django.utils import timezone
    from licenses.models import License
    return License.objects.filter(
        order__user=user,
        order__status='paid',
        status='active',
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).exists()


def is_send_allowed(
    phone: str,
    *,
    purpose: str,
    user=None,
) -> bool:
    """
    قوانین اولویت پایپلاین رشد:
    1) opt-out / suppression مطلق
    2) pending_checkout → فقط recovery
    3) registered بدون سفارش معلق → فقط activation (نه acquisition)
    4) customer با لایسنس فعال → فقط license_renewal در پنجره انقضا
    """
    phone = normalize_phone(phone or '')
    if not phone or not is_valid_iran_mobile(phone):
        return False

    if SuppressionEntry.objects.filter(phone_normalized=phone).exists():
        return False

    journey = GrowthJourney.objects.filter(phone_normalized=phone).first()
    if journey and (journey.suppressed or journey.nurture_paused):
        return False
    if journey and journey.stage == GrowthJourney.Stage.SUPPRESSED:
        return False

    user = user or (journey.user if journey else None) or find_user_by_phone(phone)
    if user and getattr(user, 'marketing_sms_opt_out', False):
        return False

    stage = journey.stage if journey else None
    pending = (
        stage == GrowthJourney.Stage.PENDING_CHECKOUT
        or _has_active_pending_order(user)
    )

    if pending:
        return purpose == PURPOSE_RECOVERY

    if stage in (
        GrowthJourney.Stage.CUSTOMER,
        GrowthJourney.Stage.RENEWED,
    ) or _has_active_license(user):
        if purpose == PURPOSE_LICENSE_RENEWAL:
            return stage in (
                GrowthJourney.Stage.EXPIRING_SOON,
                GrowthJourney.Stage.CHURN_RISK,
                GrowthJourney.Stage.CUSTOMER,
                GrowthJourney.Stage.RENEWED,
                None,
            )
        if purpose == PURPOSE_LICENSED_MARKETING:
            return True
        return False

    if stage == GrowthJourney.Stage.EXPIRING_SOON:
        return purpose == PURPOSE_LICENSE_RENEWAL

    if stage == GrowthJourney.Stage.CHURN_RISK:
        return purpose in (PURPOSE_LICENSE_RENEWAL, PURPOSE_MARKETING)

    if stage in (
        GrowthJourney.Stage.REGISTERED,
        GrowthJourney.Stage.ACTIVATED,
        GrowthJourney.Stage.NURTURE_UNPAID,
    ):
        return purpose == PURPOSE_ACTIVATION

    if purpose == PURPOSE_ACQUISITION:
        return stage in (
            None,
            GrowthJourney.Stage.COLD_LEAD,
            GrowthJourney.Stage.ENGAGED,
        )

    if purpose == PURPOSE_ACTIVATION:
        return False

    if purpose == PURPOSE_MARKETING:
        return stage not in (
            GrowthJourney.Stage.COLD_LEAD,
            GrowthJourney.Stage.ENGAGED,
            GrowthJourney.Stage.PENDING_CHECKOUT,
        )

    if purpose == PURPOSE_RECOVERY:
        return False

    if purpose == PURPOSE_LICENSE_RENEWAL:
        return False

    return False


def sync_opt_out_to_suppression(phone: str, *, reason: str = 'opt_out', notes: str = '') -> Optional[SuppressionEntry]:
    phone = normalize_phone(phone or '')
    if not phone:
        return None
    entry, _ = SuppressionEntry.objects.get_or_create(
        phone_normalized=phone,
        defaults={'reason': reason, 'notes': notes[:255]},
    )
    journey = GrowthJourney.objects.filter(phone_normalized=phone).first()
    if journey and not journey.suppressed:
        from accounts.services.growth_journey import transition
        transition(
            phone=phone,
            event_type='opt_out',
            stage=GrowthJourney.Stage.SUPPRESSED,
            metadata={'reason': reason},
        )
    return entry
