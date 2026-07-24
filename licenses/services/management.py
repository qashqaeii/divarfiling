"""مدیریت اسلات‌های چندسیستمی و تخصیص به اعضای تیم."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from licenses.models import AuditLog, License, LicenseActivation
from workspace.services.crm_scope import agency_members, can_manage_team, get_membership

User = get_user_model()


def _license_for_owner(user, license_id) -> License:
    try:
        return License.objects.select_related('order', 'plan', 'order__product').get(
            pk=license_id,
            order__user=user,
            order__status='paid',
        )
    except License.DoesNotExist as exc:
        raise ValidationError('لایسنس یافت نشد یا دسترسی ندارید.') from exc


def _validate_license_usable(license_obj: License) -> None:
    if license_obj.status in ('suspended', 'expired'):
        raise ValidationError('این لایسنس مسدود یا منقضی شده است.')
    if license_obj.expires_at and license_obj.expires_at < timezone.now():
        raise ValidationError('این لایسنس منقضی شده است.')


def _normalize_hw(hardware_fingerprint: str) -> str:
    hw = (hardware_fingerprint or '').strip()
    if len(hw) < 8:
        raise ValidationError('شناسه سخت‌افزاری نامعتبر است — حداقل ۸ کاراکتر.')
    return hw


def _team_member_users(owner) -> List[User]:
    membership = get_membership(owner)
    if not membership:
        return []
    return [m.user for m in agency_members(membership.agency) if m.user_id != owner.id]


def _assert_can_assign(actor, license_obj: License) -> None:
    if license_obj.order.user_id != actor.id and not can_manage_team(actor):
        raise PermissionDenied('فقط مالک لایسنس یا مدیر آژانس می‌تواند اسلات تخصیص دهد.')


def _assert_assignee_allowed(actor, assignee: User) -> None:
    membership = get_membership(actor)
    if not membership:
        raise ValidationError('برای تخصیص به اعضای تیم، ابتدا آژانس خود را در CRM بسازید.')
    member_ids = {m.user_id for m in agency_members(membership.agency)}
    if assignee.id not in member_ids:
        raise ValidationError('کاربر انتخاب‌شده عضو تیم شما نیست.')


@transaction.atomic
def register_device_slot(
    user,
    license_id,
    hardware_fingerprint: str,
    *,
    label: str = '',
) -> LicenseActivation:
    """ثبت سیستم جدید روی لایسنس (تا سقف max_activations)."""
    license_obj = _license_for_owner(user, license_id)
    _validate_license_usable(license_obj)
    hw = _normalize_hw(hardware_fingerprint)

    existing = LicenseActivation.objects.filter(license=license_obj, hardware_fingerprint=hw).first()
    if existing:
        if label and not existing.label:
            existing.label = label.strip()[:80]
            existing.save(update_fields=['label'])
        return existing

    if license_obj.slots_used >= license_obj.max_activations:
        raise ValidationError(
            f'تمام اسلات‌های این پلن ({license_obj.max_activations} سیستم) پر شده است.'
        )

    activation = LicenseActivation.objects.create(
        license=license_obj,
        hardware_fingerprint=hw,
        label=(label or '').strip()[:80],
        is_active=False,
    )
    AuditLog.objects.create(
        license=license_obj,
        action_type='activation',
        details={
            'event': 'seat_registered',
            'activation_id': activation.pk,
            'label': activation.label,
            'hardware_fingerprint': hw[:32],
        },
    )
    return activation


@transaction.atomic
def update_device_slot(
    user,
    activation_id: int,
    *,
    label: Optional[str] = None,
    notes: Optional[str] = None,
) -> LicenseActivation:
    activation = LicenseActivation.objects.select_related('license', 'license__order').get(pk=activation_id)
    if activation.license.order.user_id != user.id:
        raise PermissionDenied('دسترسی به این اسلات ندارید.')
    updates = []
    if label is not None:
        activation.label = label.strip()[:80]
        updates.append('label')
    if notes is not None:
        activation.notes = notes.strip()[:300]
        updates.append('notes')
    if updates:
        activation.save(update_fields=updates)
    return activation


@transaction.atomic
def assign_seat_to_member(
    actor,
    activation_id: int,
    member_user_id: int,
) -> LicenseActivation:
    activation = LicenseActivation.objects.select_related(
        'license', 'license__order',
    ).get(pk=activation_id)
    license_obj = activation.license
    _assert_can_assign(actor, license_obj)
    _validate_license_usable(license_obj)

    try:
        assignee = User.objects.get(pk=member_user_id)
    except User.DoesNotExist as exc:
        raise ValidationError('عضو تیم یافت نشد.') from exc

    if assignee.id == license_obj.order.user_id:
        raise ValidationError('مالک لایسنس نیازی به تخصیص ندارد — دسترسی کامل دارد.')

    _assert_assignee_allowed(actor, assignee)

    already = LicenseActivation.objects.filter(
        license=license_obj,
        assigned_user=assignee,
    ).exclude(pk=activation.pk).exists()
    if already:
        raise ValidationError('این عضو قبلاً یک اسلات از همین لایسنس دارد.')

    activation.assigned_user = assignee
    activation.assigned_by = actor
    activation.assigned_at = timezone.now()
    activation.save(update_fields=['assigned_user', 'assigned_by', 'assigned_at'])

    AuditLog.objects.create(
        license=license_obj,
        action_type='transfer',
        details={
            'event': 'seat_assigned',
            'activation_id': activation.pk,
            'assigned_to': assignee.username,
            'assigned_by': actor.username,
        },
    )
    return activation


@transaction.atomic
def revoke_seat_assignment(actor, activation_id: int) -> LicenseActivation:
    activation = LicenseActivation.objects.select_related('license', 'license__order').get(pk=activation_id)
    _assert_can_assign(actor, activation.license)
    if not activation.assigned_user_id:
        return activation

    prev_user = activation.assigned_user.username
    activation.assigned_user = None
    activation.assigned_by = None
    activation.assigned_at = None
    activation.save(update_fields=['assigned_user', 'assigned_by', 'assigned_at'])

    AuditLog.objects.create(
        license=activation.license,
        action_type='revoke',
        details={
            'event': 'seat_unassigned',
            'activation_id': activation.pk,
            'previous_user': prev_user,
        },
    )
    return activation


@transaction.atomic
def remove_device_slot(user, activation_id: int) -> None:
    activation = LicenseActivation.objects.select_related('license', 'license__order').get(pk=activation_id)
    if activation.license.order.user_id != user.id:
        raise PermissionDenied('دسترسی به این اسلات ندارید.')
    license_obj = activation.license
    was_active = activation.is_active
    is_mobile = (activation.notes or '').startswith('device_type=mobile')
    AuditLog.objects.create(
        license=license_obj,
        action_type='deactivation',
        details={
            'event': 'seat_removed',
            'activation_id': activation.pk,
            'hardware_fingerprint': activation.hardware_fingerprint[:32],
            'was_active': was_active,
            'device_type': 'mobile' if is_mobile else 'desktop',
            'removed_by': user.username,
        },
    )
    activation.delete()


def _agency_owner_for_actor(actor):
    """مالک آژانس مرتبط با کاربر (خودش یا عضویت فعلی)."""
    membership = get_membership(actor)
    if not membership:
        return None
    return membership.agency.owner


def _license_for_agency_actor(actor, license_id) -> License:
    """لایسنس قابل مدیریت توسط مالک سفارش یا مدیر همان آژانس."""
    try:
        license_obj = License.objects.select_related(
            'order', 'order__user', 'plan', 'assigned_user',
        ).get(pk=license_id, order__status='paid')
    except License.DoesNotExist as exc:
        raise ValidationError('لایسنس یافت نشد یا دسترسی ندارید.') from exc

    owner = license_obj.order.user
    if actor.id == owner.id:
        return license_obj

    if not can_manage_team(actor):
        raise PermissionDenied('فقط مالک لایسنس یا مدیر آژانس می‌تواند تخصیص دهد.')

    agency_owner = _agency_owner_for_actor(actor)
    if not agency_owner or agency_owner.id != owner.id:
        raise PermissionDenied('این لایسنس متعلق به آژانس شما نیست.')
    return license_obj


def _allocation_state(license_obj: License) -> str:
    if license_obj.assigned_user_id:
        return 'assigned'
    if license_obj.status == 'active':
        return 'owner_active'
    return 'available'


def _member_payload(user_obj) -> Dict[str, Any]:
    return {
        'id': user_obj.id,
        'username': user_obj.username,
        'name': user_obj.get_full_name() or user_obj.username,
    }


@transaction.atomic
def assign_license_to_member(actor, license_id, member_user_id: int) -> License:
    """تخصیص کلید کامل لایسنس به عضو فعال آژانس — دسترسی فوری."""
    license_obj = _license_for_agency_actor(actor, license_id)
    _validate_license_usable(license_obj)

    if license_obj.assigned_user_id:
        raise ValidationError('این لایسنس قبلاً تخصیص داده شده — ابتدا تخصیص را لغو کنید.')

    try:
        assignee = User.objects.get(pk=member_user_id)
    except User.DoesNotExist as exc:
        raise ValidationError('عضو تیم یافت نشد.') from exc

    owner = license_obj.order.user
    if assignee.id == owner.id:
        raise ValidationError('مالک لایسنس نیازی به تخصیص ندارد — از «فعال‌سازی برای خودم» استفاده کنید.')

    _assert_assignee_allowed(owner if actor.id == owner.id else actor, assignee)
    # اگر actor مدیر است، عضویت را نسبت به آژانس مالک هم چک کنیم
    owner_membership = get_membership(owner)
    actor_membership = get_membership(actor)
    if not owner_membership:
        raise ValidationError('برای تخصیص به اعضای تیم، ابتدا آژانس را در CRM بسازید.')
    if actor_membership and actor_membership.agency_id != owner_membership.agency_id:
        raise PermissionDenied('عضو و لایسنس در یک آژانس نیستند.')

    member_ids = {m.user_id for m in agency_members(owner_membership.agency)}
    if assignee.id not in member_ids:
        raise ValidationError('کاربر انتخاب‌شده عضو تیم آژانس مالک لایسنس نیست.')

    already = License.objects.filter(
        order__user=owner,
        order__status='paid',
        assigned_user=assignee,
    ).exclude(
        status__in=['suspended', 'expired'],
    ).exclude(pk=license_obj.pk).exists()
    if already:
        raise ValidationError('این عضو از قبل یک لایسنس از این آژانس دارد.')

    license_obj.assigned_user = assignee
    license_obj.assigned_by = actor
    license_obj.assigned_at = timezone.now()
    if license_obj.status == 'inactive':
        license_obj.status = 'active'
    elif license_obj.status not in ('active',):
        _validate_license_usable(license_obj)
        license_obj.status = 'active'
    license_obj.save(update_fields=[
        'assigned_user', 'assigned_by', 'assigned_at', 'status',
    ])

    AuditLog.objects.create(
        license=license_obj,
        action_type='transfer',
        details={
            'event': 'license_assigned',
            'assigned_to': assignee.username,
            'assigned_by': actor.username,
            'license_id': license_obj.pk,
        },
    )
    return license_obj


@transaction.atomic
def revoke_license_assignment(actor, license_id) -> License:
    """لغو تخصیص کلید از عضو تیم."""
    license_obj = _license_for_agency_actor(actor, license_id)
    if not license_obj.assigned_user_id:
        return license_obj

    prev_user = license_obj.assigned_user.username
    license_obj.assigned_user = None
    license_obj.assigned_by = None
    license_obj.assigned_at = None

    has_active_device = license_obj.activations.filter(is_active=True).exists()
    if license_obj.status not in ('suspended', 'expired'):
        # دستگاه فعال → active بماند؛ وگرنه برگردد به استخر (آماده تخصیص)
        license_obj.status = 'active' if has_active_device else 'inactive'

    license_obj.save(update_fields=[
        'assigned_user', 'assigned_by', 'assigned_at', 'status',
    ])

    AuditLog.objects.create(
        license=license_obj,
        action_type='revoke',
        details={
            'event': 'license_unassigned',
            'previous_user': prev_user,
            'revoked_by': actor.username,
            'license_id': license_obj.pk,
        },
    )
    return license_obj


@transaction.atomic
def activate_license_for_owner(actor, license_id) -> License:
    """فعال‌سازی کلید برای استفاده شخصی مالک سفارش."""
    try:
        license_obj = License.objects.select_related('order', 'plan').get(
            pk=license_id,
            order__user=actor,
            order__status='paid',
        )
    except License.DoesNotExist as exc:
        raise ValidationError('لایسنس یافت نشد یا دسترسی ندارید.') from exc

    if license_obj.assigned_user_id:
        raise ValidationError('این لایسنس به عضو تیم تخصیص شده — ابتدا تخصیص را لغو کنید.')

    _validate_license_usable(license_obj)
    if license_obj.status != 'active':
        license_obj.status = 'active'
        license_obj.save(update_fields=['status'])
        AuditLog.objects.create(
            license=license_obj,
            action_type='activation',
            details={
                'event': 'license_activated_for_owner',
                'activated_by': actor.username,
            },
        )
    return license_obj


def licenses_owned_by_agency_owner(owner) -> list[License]:
    return list(
        License.objects.filter(order__user=owner, order__status='paid')
        .select_related('order', 'plan', 'assigned_user')
        .exclude(status__in=['suspended', 'expired'])
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        .order_by('sequence', 'pk')
    )


def build_agency_license_pool(owner) -> Dict[str, Any]:
    """خلاصه استخر لایسنس‌های مالک آژانس برای UI تیم."""
    licenses = licenses_owned_by_agency_owner(owner)
    available = []
    assigned_by_user: Dict[int, Dict[str, Any]] = {}
    owner_active = 0
    assigned = 0
    for lic in licenses:
        state = _allocation_state(lic)
        item = {
            'id': lic.pk,
            'license_key': lic.license_key,
            'key_short': lic.license_key[-8:] if lic.license_key else '',
            'sequence': lic.sequence,
            'status': lic.status,
            'allocation_state': state,
            'plan_name': lic.plan.name if lic.plan_id else '',
        }
        if state == 'available':
            available.append(item)
        elif state == 'assigned' and lic.assigned_user_id:
            assigned += 1
            assigned_by_user[lic.assigned_user_id] = {
                **item,
                'assigned_member': _member_payload(lic.assigned_user),
            }
        elif state == 'owner_active':
            owner_active += 1

    return {
        'total': len(licenses),
        'owner_active': owner_active,
        'assigned': assigned,
        'available': len(available),
        'available_licenses': available,
        'assigned_by_user': assigned_by_user,
    }


def _license_expiry_meta(license_obj: License) -> Dict[str, Any]:
    """وضعیت انقضا برای نمایش در داشبورد."""
    license_obj.sync_expiration_status(save=True)
    now = timezone.now()

    if license_obj.status in ('suspended', 'inactive'):
        return {
            'has_expiry': bool(license_obj.expires_at),
            'is_expired': license_obj.status == 'expired',
            'expiring_soon': False,
            'days_remaining': None,
            'tone': 'inactive',
            'health_pct': 0,
            'remaining_label': license_obj.get_status_display(),
        }

    if not license_obj.expires_at:
        return {
            'has_expiry': False,
            'is_expired': license_obj.status == 'expired',
            'expiring_soon': False,
            'days_remaining': None,
            'tone': 'unlimited',
            'health_pct': 100,
            'remaining_label': 'نامحدود',
        }

    is_expired = license_obj.status == 'expired' or license_obj.expires_at <= now
    if is_expired:
        return {
            'has_expiry': True,
            'is_expired': True,
            'expiring_soon': False,
            'days_remaining': 0,
            'tone': 'expired',
            'health_pct': 0,
            'remaining_label': 'منقضی شده',
        }

    days_remaining = max(0, (license_obj.expires_at.date() - now.date()).days)
    if days_remaining <= 3:
        tone = 'critical'
    elif days_remaining <= 7:
        tone = 'warning'
    elif days_remaining <= 30:
        tone = 'stable'
    else:
        tone = 'healthy'

    duration = license_obj.plan.duration_days
    if not duration and license_obj.created_at and license_obj.expires_at:
        duration = max(1, (license_obj.expires_at - license_obj.created_at).days)
    if duration:
        health_pct = min(100, max(4, round(days_remaining / duration * 100)))
    else:
        health_pct = min(100, max(4, days_remaining))

    if days_remaining == 0:
        remaining_label = 'امروز'
    elif days_remaining == 1:
        remaining_label = '۱ روز مانده'
    else:
        remaining_label = f'{days_remaining} روز مانده'

    return {
        'has_expiry': True,
        'is_expired': False,
        'expiring_soon': days_remaining <= 7,
        'days_remaining': days_remaining,
        'tone': tone,
        'health_pct': health_pct,
        'remaining_label': remaining_label,
    }


def build_license_dashboard(user) -> Dict[str, Any]:
    """داده‌های کامل تب لایسنس در داشبورد."""
    licenses = list(
        License.objects.filter(order__user=user)
        .select_related('order', 'order__product', 'plan', 'assigned_user', 'assigned_by')
        .prefetch_related(
            Prefetch(
                'activations',
                queryset=LicenseActivation.objects.select_related(
                    'assigned_user', 'assigned_by',
                ).order_by('activated_at', 'pk'),
            ),
        )
        .order_by('-created_at')
    )

    team_members = []
    membership = get_membership(user)
    if membership:
        for m in agency_members(membership.agency):
            team_members.append({
                'id': m.user_id,
                'username': m.user.username,
                'name': m.user.get_full_name() or m.user.username,
                'role': m.get_role_display(),
                'is_self': m.user_id == user.id,
            })

    assignable_members = [m for m in team_members if not m['is_self']]

    assigned_to_me = list(
        LicenseActivation.objects.filter(
            assigned_user=user,
            license__order__status='paid',
        )
        .exclude(license__status__in=['suspended', 'expired'])
        .filter(Q(license__expires_at__isnull=True) | Q(license__expires_at__gt=timezone.now()))
        .select_related('license', 'license__order', 'license__order__product', 'license__plan')
        .order_by('-assigned_at')
    )

    # کلیدهایی که به این کاربر تخصیص داده شده (مسیر جدید)
    allocated_to_me = list(
        License.objects.filter(
            assigned_user=user,
            order__status='paid',
        )
        .exclude(status__in=['suspended', 'expired'])
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        .select_related('order', 'order__product', 'plan', 'order__user')
        .order_by('-assigned_at')
    )

    portfolios = []
    pool_available = 0
    pool_owner_active = 0
    pool_assigned = 0
    for lic in licenses:
        activations = list(lic.activations.all())
        active_count = sum(1 for a in activations if a.is_active)
        state = _allocation_state(lic)
        if state == 'available':
            pool_available += 1
        elif state == 'owner_active':
            pool_owner_active += 1
        elif state == 'assigned':
            pool_assigned += 1
        portfolios.append({
            'license': lic,
            'expiry': _license_expiry_meta(lic),
            'activations': activations,
            'slots_used': len(activations),
            'slots_available': max(0, lic.max_activations - len(activations)),
            'active_count': active_count,
            'pending_count': len(activations) - active_count,
            'is_multi': lic.max_activations > 1,
            'allocation_state': state,
            'assigned_member': (
                _member_payload(lic.assigned_user) if lic.assigned_user_id else None
            ),
            'key_short': lic.license_key[-8:] if lic.license_key else '',
        })

    from licenses.services.renewal import evaluate_license_renewal

    for portfolio in portfolios:
        lic = portfolio['license']
        expiry = portfolio['expiry']
        can_renew, _renew_message = evaluate_license_renewal(lic)
        portfolio['can_renew'] = can_renew and (
            expiry.get('is_expired') or expiry.get('expiring_soon')
        )

    return {
        'portfolios': portfolios,
        'team_members': team_members,
        'assignable_members': assignable_members,
        'has_agency': bool(membership),
        'can_assign_team': bool(membership and assignable_members),
        'assigned_seats': assigned_to_me,
        'allocated_licenses': allocated_to_me,
        'pool': {
            'total': len(portfolios),
            'available': pool_available,
            'owner_active': pool_owner_active,
            'assigned': pool_assigned,
        },
    }
