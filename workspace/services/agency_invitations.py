"""دعوت مشاور به آژانس — SMS، توکن امن، پذیرش/رد."""
from __future__ import annotations

import logging
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.phone_utils import find_user_by_phone, is_valid_iran_mobile, normalize_phone
from accounts.services.sms import SmsError, SmsSendError, send_pattern_sms
from workspace.models import AgencyInvitation, AgencySubscription, CRMAgencyMember
from workspace.services.agency_entitlement import (
    CONSENT_VERSION_CURRENT,
    can_manage_agency,
    get_subscription_for_agency,
    link_agency_to_subscription,
    resolve_managed_agency,
    seat_usage_summary,
)
from workspace.services.crm_agency import _attach_user_records, sync_agency_member_records
from workspace.services.crm_audit import log_agency_audit

logger = logging.getLogger(__name__)
User = get_user_model()

INVITE_TTL_DAYS = 7
SMS_RESEND_COOLDOWN_SECONDS = 120
SMS_RESEND_MAX_PER_INVITE = 5


class AgencyInviteCapacityError(ValueError):
    """ظرفیت دعوت آژانس تکمیل شده — invite_available == 0 یا درخواست بیش از ظرفیت."""

    code = 'agency_seat_capacity_reached'

    def __init__(self, message: str = '', *, available: int = 0, requested: int = 1):
        self.available = available
        self.requested = requested
        super().__init__(message or 'ظرفیت دعوت تکمیل شده است.')


def _count_pending_invitations(agency) -> int:
    return AgencyInvitation.objects.filter(
        agency=agency,
        status=AgencyInvitation.STATUS_PENDING,
        expires_at__gt=timezone.now(),
    ).count()


def _count_members_without_seat(agency, subscription) -> int:
    from licenses.models import License

    assigned_user_ids = License.objects.filter(
        agency_subscription=subscription,
        assigned_user__isnull=False,
    ).values_list('assigned_user_id', flat=True)
    return (
        CRMAgencyMember.objects.filter(agency=agency, is_active=True)
        .exclude(role='owner')
        .exclude(user_id__in=assigned_user_ids)
        .count()
    )


def get_agency_invite_capacity(agency, subscription) -> dict:
    """ظرفیت باقی‌مانده برای دعوت — pending + اعضای بدون seat + seat تخصیص‌یافته."""
    seats = seat_usage_summary(subscription)
    pending = _count_pending_invitations(agency)
    without_seat = _count_members_without_seat(agency, subscription)
    consumed = seats['assigned'] + pending + without_seat
    invite_available = max(0, seats['total'] - consumed)
    return {
        'total': seats['total'],
        'assigned': seats['assigned'],
        'available_seats': seats['available'],
        'pending_invitations': pending,
        'members_without_seat': without_seat,
        'consumed': consumed,
        'invite_available': invite_available,
    }


def can_create_agency_invitation(agency, subscription, *, count: int = 1) -> tuple[bool, str]:
    cap = get_agency_invite_capacity(agency, subscription)
    if count <= cap['invite_available']:
        return True, ''
    avail = cap['invite_available']
    if avail == 0:
        return False, f'تمام {cap["total"]} لایسنس این آژانس استفاده یا رزرو شده‌اند.'
    return False, f'فقط {avail} ظرفیت برای دعوت باقی مانده است.'


def _assert_invite_capacity(agency, subscription, *, count: int = 1) -> None:
    ok, msg = can_create_agency_invitation(agency, subscription, count=count)
    if ok:
        return
    cap = get_agency_invite_capacity(agency, subscription)
    raise AgencyInviteCapacityError(msg, available=cap['invite_available'], requested=count)


def _generate_invite_token() -> tuple[str, str]:
    from contracts.services.tokens import generate_bearer_token
    return generate_bearer_token()


def _build_invite_url(request, raw_token: str) -> str:
    path = reverse('workspace:agency_invite_accept', kwargs={'token': raw_token})
    if request:
        return request.build_absolute_uri(path)
    site = getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir'
    return f'{site.rstrip("/")}{path}'


_DIVAR_FILING_INVITE_HOSTS = frozenset({'divarfiling.ir', 'www.divarfiling.ir'})


def _allowed_invite_link_hosts() -> frozenset[str]:
    hosts = set(_DIVAR_FILING_INVITE_HOSTS)
    if settings.DEBUG:
        hosts.update({'localhost', '127.0.0.1'})
    return frozenset(hosts)


def _pattern_link_from_invite_url(invite_url: str) -> str:
    """مسیر نسبی (بدون اسلش ابتدایی) برای متغیر link پترن — دامنه در متن پترن ثبت شده است."""
    parsed = urlparse((invite_url or '').strip())
    if parsed.scheme not in ('http', 'https'):
        raise SmsSendError('لینک دعوت نامعتبر است.', code='agency_invite_invalid_link')
    host = (parsed.hostname or '').lower()
    if host not in _allowed_invite_link_hosts():
        raise SmsSendError('لینک دعوت نامعتبر است.', code='agency_invite_invalid_link')
    path = (parsed.path or '/').lstrip('/')
    if parsed.query:
        path = f'{path}?{parsed.query}'
    if not path:
        raise SmsSendError('لینک دعوت نامعتبر است.', code='agency_invite_invalid_link')
    return path


def _mask_phone(phone: str) -> str:
    p = normalize_phone(phone)
    if len(p) < 8:
        return '***'
    return f'{p[:4]}***{p[-4:]}'


def _send_invite_sms(invitation: AgencyInvitation, invite_url: str, *, is_resend: bool = False) -> None:
    meta = dict(invitation.sms_metadata or {})
    try:
        link_path = _pattern_link_from_invite_url(invite_url)
        send_pattern_sms(
            invitation.phone,
            attributes={
                'agency': invitation.agency.name,
                'link': link_path,
            },
            purpose='agency_invite',
        )
        invitation.sms_sent_at = timezone.now()
        meta['last_status'] = 'sent'
        meta['last_sent_at'] = invitation.sms_sent_at.isoformat()
        meta.pop('last_error', None)
    except SmsError as exc:
        meta['last_status'] = 'failed'
        meta['last_error'] = str(exc)[:200]
        logger.warning('agency invite SMS failed invitation=%s', invitation.pk)
    invitation.sms_metadata = meta
    invitation.save(update_fields=['sms_sent_at', 'sms_metadata'])


def list_agency_invitations(agency) -> list[AgencyInvitation]:
    return list(
        agency.invitations.select_related('inviter', 'accepted_user')
        .order_by('-created_at')[:100]
    )


def _validate_invite_phone(agency, phone: str) -> str:
    phone = normalize_phone(phone or '')
    if not is_valid_iran_mobile(phone):
        raise ValueError('شماره موبایل معتبر نیست.')
    pending = AgencyInvitation.objects.filter(
        agency=agency,
        phone=phone,
        status=AgencyInvitation.STATUS_PENDING,
        expires_at__gt=timezone.now(),
    ).exists()
    if pending:
        raise ValueError('دعوت در انتظار برای این شماره از قبل وجود دارد')
    if CRMAgencyMember.objects.filter(agency=agency, is_active=True).filter(
        user__phone=phone,
    ).exists():
        raise ValueError('این شماره از قبل عضو آژانس است')
    return phone


def _create_invitation_record(actor, agency, phone: str, role: str) -> tuple[AgencyInvitation, str]:
    raw, token_hash = _generate_invite_token()
    invitation = AgencyInvitation.objects.create(
        agency=agency,
        inviter=actor,
        phone=phone,
        role=role,
        token_hash=token_hash,
        expires_at=timezone.now() + timedelta(days=INVITE_TTL_DAYS),
    )
    log_agency_audit(
        agency, actor, 'agency_invite_created',
        {'phone': _mask_phone(phone), 'role': role, 'invitation_id': invitation.pk},
    )
    return invitation, raw


def create_agency_invitation(
    actor,
    phone: str,
    role: str = 'advisor',
    *,
    request=None,
) -> AgencyInvitation:
    agency, sub = resolve_managed_agency(actor)
    if not agency or not can_manage_agency(actor, agency):
        raise ValueError('دسترسی مدیریت آژانس ندارید')
    if not sub:
        raise ValueError('اشتراک آژانس در حال حاضر فعال نیست.')

    phone = _validate_invite_phone(agency, phone)

    with transaction.atomic():
        locked_sub = AgencySubscription.objects.select_for_update().get(pk=sub.pk)
        _assert_invite_capacity(agency, locked_sub, count=1)
        invitation, raw = _create_invitation_record(actor, agency, phone, role)

    invite_url = _build_invite_url(request, raw)
    _send_invite_sms(invitation, invite_url)
    return invitation


def create_bulk_agency_invitations(actor, phones: list[str], role: str = 'advisor', *, request=None) -> dict:
    agency, sub = resolve_managed_agency(actor)
    if not agency or not can_manage_agency(actor, agency):
        return {'created': [], 'errors': [{'phone': '', 'error': 'دسترسی مدیریت آژانس ندارید'}]}
    if not sub:
        return {'created': [], 'errors': [{'phone': '', 'error': 'اشتراک آژانس در حال حاضر فعال نیست.'}]}

    normalized: list[str] = []
    errors: list[dict] = []
    seen: set[str] = set()
    for phone in phones:
        raw = (phone or '').strip()
        if not raw:
            continue
        try:
            normalized_phone = _validate_invite_phone(agency, raw)
        except ValueError as exc:
            errors.append({'phone': raw, 'error': str(exc)})
            continue
        if normalized_phone in seen:
            errors.append({'phone': raw, 'error': 'این شماره قبلاً اضافه شده است.'})
            continue
        seen.add(normalized_phone)
        normalized.append(normalized_phone)

    if errors:
        return {'created': [], 'errors': errors}

    if not normalized:
        return {'created': [], 'errors': []}

    created: list[AgencyInvitation] = []
    pending_sms: list[tuple[AgencyInvitation, str]] = []
    try:
        with transaction.atomic():
            locked_sub = AgencySubscription.objects.select_for_update().get(pk=sub.pk)
            _assert_invite_capacity(agency, locked_sub, count=len(normalized))
            for phone in normalized:
                invitation, raw = _create_invitation_record(actor, agency, phone, role)
                created.append(invitation)
                pending_sms.append((invitation, raw))
    except AgencyInviteCapacityError as exc:
        return {
            'created': [],
            'errors': [{
                'phone': '',
                'error': str(exc),
                'code': exc.code,
            }],
            'capacity_error': True,
        }

    for invitation, raw in pending_sms:
        invite_url = _build_invite_url(request, raw)
        _send_invite_sms(invitation, invite_url)

    return {'created': created, 'errors': []}


def get_invitation_by_token(raw_token: str) -> AgencyInvitation | None:
    from contracts.services.tokens import hash_token

    if not raw_token:
        return None
    token_hash = hash_token(raw_token)
    return (
        AgencyInvitation.objects.filter(token_hash=token_hash)
        .select_related('agency', 'inviter')
        .first()
    )


def _expire_if_needed(invitation: AgencyInvitation) -> AgencyInvitation:
    if (
        invitation.status == AgencyInvitation.STATUS_PENDING
        and invitation.expires_at <= timezone.now()
    ):
        invitation.status = AgencyInvitation.STATUS_EXPIRED
        invitation.save(update_fields=['status'])
    return invitation


def invitation_accept_allowed(invitation: AgencyInvitation) -> tuple[bool, str]:
    invitation = _expire_if_needed(invitation)
    if invitation.status != AgencyInvitation.STATUS_PENDING:
        return False, 'این دعوت معتبر نیست'
    if not get_subscription_for_agency(invitation.agency):
        return False, 'اشتراک آژانس در حال حاضر فعال نیست.'
    return True, ''


@transaction.atomic
def accept_agency_invitation(
    invitation: AgencyInvitation,
    user,
    *,
    consent_acknowledged: bool = False,
) -> CRMAgencyMember:
    ok, msg = invitation_accept_allowed(invitation)
    if not ok:
        raise ValueError(msg)
    if not consent_acknowledged:
        raise ValueError('پذیرش رضایت دید داده الزامی است')

    user_phone = normalize_phone(getattr(user, 'phone', None) or user.username)
    if normalize_phone(invitation.phone) != user_phone:
        raise ValueError('این دعوت برای حساب شما نیست')

    from workspace.services.crm_scope import get_membership
    existing = get_membership(user)
    if existing and existing.agency_id != invitation.agency_id:
        raise ValueError('شما عضو آژانس دیگری هستید')

    invitation.status = AgencyInvitation.STATUS_ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.accepted_user = user
    invitation.save(update_fields=['status', 'accepted_at', 'accepted_user'])

    member, was_created = CRMAgencyMember.objects.get_or_create(
        agency=invitation.agency,
        user=user,
        defaults={
            'role': invitation.role,
            'data_visibility_consent_at': timezone.now(),
            'consent_version': CONSENT_VERSION_CURRENT,
            'is_active': True,
        },
    )
    if not was_created:
        member.is_active = True
        member.role = invitation.role
        member.data_visibility_consent_at = timezone.now()
        member.consent_version = CONSENT_VERSION_CURRENT
        member.save(update_fields=[
            'is_active', 'role', 'data_visibility_consent_at', 'consent_version',
        ])

    _attach_user_records(user, invitation.agency)
    sync_agency_member_records(invitation.agency)

    from workspace.services.agency_entitlement import get_active_subscription_for_owner
    sub = get_active_subscription_for_owner(invitation.agency.owner)
    if sub and not sub.agency_id:
        link_agency_to_subscription(invitation.agency, sub)

    log_agency_audit(
        invitation.agency, user, 'agency_invite_accepted',
        {'invitation_id': invitation.pk, 'role': invitation.role},
    )
    return member


@transaction.atomic
def decline_agency_invitation(invitation: AgencyInvitation, user=None) -> AgencyInvitation:
    invitation = _expire_if_needed(invitation)
    if invitation.status != AgencyInvitation.STATUS_PENDING:
        raise ValueError('این دعوت معتبر نیست')
    if user:
        user_phone = normalize_phone(getattr(user, 'phone', None) or user.username)
        if normalize_phone(invitation.phone) != user_phone:
            raise ValueError('این دعوت برای حساب شما نیست')
    invitation.status = AgencyInvitation.STATUS_DECLINED
    invitation.declined_at = timezone.now()
    invitation.save(update_fields=['status', 'declined_at'])
    log_agency_audit(
        invitation.agency,
        user or invitation.inviter,
        'agency_invite_declined',
        {'invitation_id': invitation.pk},
    )
    return invitation


@transaction.atomic
def cancel_agency_invitation(actor, invitation_id: int) -> AgencyInvitation:
    agency, _sub = resolve_managed_agency(actor)
    if not agency or not can_manage_agency(actor, agency):
        raise ValueError('دسترسی ندارید')
    invitation = AgencyInvitation.objects.filter(
        pk=invitation_id, agency=agency,
    ).first()
    if not invitation:
        raise ValueError('دعوت یافت نشد')
    if invitation.status != AgencyInvitation.STATUS_PENDING:
        raise ValueError('فقط دعوت‌های در انتظار قابل لغو هستند')
    invitation.status = AgencyInvitation.STATUS_CANCELLED
    invitation.save(update_fields=['status'])
    return invitation


def resend_invitation_sms(actor, invitation_id: int, *, request=None) -> AgencyInvitation:
    agency, sub = resolve_managed_agency(actor)
    if not agency or not can_manage_agency(actor, agency):
        raise ValueError('دسترسی ندارید')
    if not sub:
        raise ValueError('اشتراک آژانس فعال نیست')
    invitation = AgencyInvitation.objects.filter(
        pk=invitation_id, agency=agency,
    ).select_related('agency').first()
    if not invitation:
        raise ValueError('دعوت یافت نشد')
    if invitation.status != AgencyInvitation.STATUS_PENDING:
        raise ValueError('فقط دعوت‌های در انتظار قابل ارسال مجدد هستند')
    if invitation.sms_resend_count >= SMS_RESEND_MAX_PER_INVITE:
        raise ValueError('حداکثر ارسال مجدد پیامک انجام شده است')
    if invitation.sms_sent_at:
        delta = (timezone.now() - invitation.sms_sent_at).total_seconds()
        if delta < SMS_RESEND_COOLDOWN_SECONDS:
            raise ValueError('لطفاً کمی صبر کنید و دوباره تلاش کنید')

    raw, token_hash = _generate_invite_token()
    invitation.token_hash = token_hash
    invitation.expires_at = timezone.now() + timedelta(days=INVITE_TTL_DAYS)
    invitation.sms_resend_count += 1
    invitation.save(update_fields=['token_hash', 'expires_at', 'sms_resend_count'])

    invite_url = _build_invite_url(request, raw)
    _send_invite_sms(invitation, invite_url, is_resend=True)
    return invitation
