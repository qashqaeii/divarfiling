"""تخصیص Seat آژانس — با AgencyLicenseAssignmentLog."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from licenses.models import License, LicenseActivation
from workspace.models import AgencyLicenseAssignmentLog, CRMAgencyMember
from workspace.services.agency_entitlement import (
    can_manage_agency,
    get_subscription_for_agency,
    resolve_managed_agency,
)
from workspace.services.crm_scope import agency_members

User = get_user_model()


def _validate_subscription_seat(license_obj: License, subscription) -> None:
    if not subscription:
        raise ValidationError('اشتراک آژانس فعال نیست.')
    if license_obj.agency_subscription_id != subscription.pk:
        raise ValidationError('این صندلی متعلق به اشتراک آژانس شما نیست.')


def list_available_seats(actor, agency) -> list[License]:
    sub = get_subscription_for_agency(agency)
    if not sub or not can_manage_agency(actor, agency):
        return []
    return list(
        License.objects.filter(
            agency_subscription=sub,
            assigned_user__isnull=True,
            order__status='paid',
        )
        .exclude(status__in=['suspended', 'expired'])
        .select_related('plan')
        .order_by('sequence', 'pk')
    )


def get_member_seat(member: CRMAgencyMember) -> License | None:
    sub = get_subscription_for_agency(member.agency)
    if not sub:
        return None
    return License.objects.filter(
        assigned_user=member.user,
        agency_subscription=sub,
    ).select_related('plan').first()


@transaction.atomic
def assign_seat_to_member(actor, license_id: int, member_user_id: int) -> License:
    agency, sub = resolve_managed_agency(actor)
    if not agency or not can_manage_agency(actor, agency):
        raise PermissionDenied('دسترسی مدیریت آژانس ندارید')
    if not sub:
        raise ValidationError('اشتراک آژانس در حال حاضر فعال نیست.')

    try:
        license_obj = License.objects.select_related('order', 'plan').get(
            pk=license_id, order__status='paid',
        )
    except License.DoesNotExist as exc:
        raise ValidationError('صندلی یافت نشد.') from exc

    _validate_subscription_seat(license_obj, sub)
    if license_obj.assigned_user_id:
        raise ValidationError('این صندلی قبلاً تخصیص داده شده است.')

    try:
        assignee = User.objects.get(pk=member_user_id)
    except User.DoesNotExist as exc:
        raise ValidationError('عضو یافت نشد.') from exc

    member = agency.members.filter(user=assignee, is_active=True).first()
    if not member or member.role == 'owner':
        raise ValidationError('فقط اعضای پذیرفته‌شده قابل تخصیص صندلی هستند.')

    if not member.data_visibility_consent_at:
        raise ValidationError('عضو هنوز دعوت را پذیرش نکرده است.')

    existing = License.objects.filter(
        assigned_user=assignee,
        agency_subscription=sub,
    ).exclude(status__in=['suspended', 'expired']).exclude(pk=license_obj.pk).exists()
    if existing:
        raise ValidationError('این عضو از قبل یک صندلی فعال دارد.')

    license_obj.assigned_user = assignee
    license_obj.assigned_by = actor
    license_obj.assigned_at = timezone.now()
    if license_obj.status == 'inactive':
        license_obj.status = 'active'
    license_obj.save(update_fields=[
        'assigned_user', 'assigned_by', 'assigned_at', 'status',
    ])

    AgencyLicenseAssignmentLog.objects.create(
        agency=agency,
        subscription=sub,
        license=license_obj,
        member_user=assignee,
        action=AgencyLicenseAssignmentLog.ACTION_ASSIGN,
        actor=actor,
    )
    from workspace.services.agency_activity import EVENT_LICENSE_ASSIGNED, emit_agency_activity
    emit_agency_activity(
        agency, actor, EVENT_LICENSE_ASSIGNED,
        object_type='license', object_id=license_obj.pk,
        metadata={'member_user_id': assignee.pk},
    )
    return license_obj


@transaction.atomic
def unassign_seat(actor, license_id: int) -> License:
    agency, sub = resolve_managed_agency(actor)
    if not agency or not can_manage_agency(actor, agency):
        raise PermissionDenied('دسترسی مدیریت آژانس ندارید')
    if not sub:
        raise ValidationError('اشتراک آژانس فعال نیست.')

    try:
        license_obj = License.objects.get(pk=license_id, agency_subscription=sub)
    except License.DoesNotExist as exc:
        raise ValidationError('صندلی یافت نشد.') from exc

    if not license_obj.assigned_user_id:
        return license_obj

    prev_user = license_obj.assigned_user
    license_obj.assigned_user = None
    license_obj.assigned_by = None
    license_obj.assigned_at = None
    LicenseActivation.objects.filter(license=license_obj, is_active=True).update(is_active=False)
    if license_obj.status not in ('suspended', 'expired'):
        license_obj.status = 'inactive'
    license_obj.save(update_fields=[
        'assigned_user', 'assigned_by', 'assigned_at', 'status',
    ])

    AgencyLicenseAssignmentLog.objects.create(
        agency=agency,
        subscription=sub,
        license=license_obj,
        member_user=prev_user,
        action=AgencyLicenseAssignmentLog.ACTION_UNASSIGN,
        actor=actor,
    )
    from workspace.services.agency_activity import EVENT_LICENSE_UNASSIGNED, emit_agency_activity
    emit_agency_activity(
        agency, actor, EVENT_LICENSE_UNASSIGNED,
        object_type='license', object_id=license_obj.pk,
        metadata={'member_user_id': prev_user.pk if prev_user else None},
    )
    return license_obj
