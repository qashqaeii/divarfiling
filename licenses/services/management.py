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
    if activation.is_active:
        raise ValidationError(
            'این سیستم در ربات فعال است. ابتدا از داخل ربات لایسنس را غیرفعال کنید.'
        )
    license_obj = activation.license
    AuditLog.objects.create(
        license=license_obj,
        action_type='deactivation',
        details={
            'event': 'seat_removed',
            'activation_id': activation.pk,
            'hardware_fingerprint': activation.hardware_fingerprint[:32],
        },
    )
    activation.delete()


def build_license_dashboard(user) -> Dict[str, Any]:
    """داده‌های کامل تب لایسنس در داشبورد."""
    licenses = list(
        License.objects.filter(order__user=user)
        .select_related('order', 'order__product', 'plan')
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

    portfolios = []
    for lic in licenses:
        activations = list(lic.activations.all())
        active_count = sum(1 for a in activations if a.is_active)
        portfolios.append({
            'license': lic,
            'activations': activations,
            'slots_used': len(activations),
            'slots_available': max(0, lic.max_activations - len(activations)),
            'active_count': active_count,
            'pending_count': len(activations) - active_count,
            'is_multi': lic.max_activations > 1,
        })

    return {
        'portfolios': portfolios,
        'team_members': team_members,
        'has_agency': bool(membership),
        'can_assign_team': bool(membership and team_members),
        'assigned_seats': assigned_to_me,
    }
