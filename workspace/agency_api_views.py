"""API مدیریت آژانس — دعوت، Seat، اعضا."""
from __future__ import annotations

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from workspace.models import AgencyInvitation
from workspace.services.agency_entitlement import (
    can_manage_agency,
    has_assigned_agency_seat,
    resolve_managed_agency,
)
from workspace.services.agency_invitations import (
    cancel_agency_invitation,
    create_agency_invitation,
    resend_invitation_sms,
)
from workspace.services.agency_members import build_members_dashboard, remove_agency_member
from workspace.services.agency_seats import assign_seat_to_member, list_available_seats, unassign_seat
class _AgencyOwnerAPIBase(LoginRequiredMixin, View):
    def _deny(self, msg='دسترسی مجاز نیست', code=403):
        return JsonResponse({'ok': False, 'error': msg}, status=code)

    def _agency(self):
        agency, _sub = resolve_managed_agency(self.request.user)
        return agency

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if has_assigned_agency_seat(request.user) and not can_manage_agency(request.user):
                return self._deny('مشاوران به این API دسترسی ندارند')
            agency = self._agency()
            if not can_manage_agency(request.user, agency):
                return self._deny()
        return super().dispatch(request, *args, **kwargs)


class AgencyMembersDashboardAPIView(_AgencyOwnerAPIBase):
    def get(self, request):
        agency = self._agency()
        if not agency:
            return self._deny('آژانس یافت نشد', 404)
        data = build_members_dashboard(request.user, agency)
        return JsonResponse({'ok': True, 'data': _serialize_dashboard(data)})


class AgencyInvitationsAPIView(_AgencyOwnerAPIBase):
    def get(self, request):
        agency = self._agency()
        if not agency:
            return self._deny('آژانس یافت نشد', 404)
        from workspace.services.agency_invitations import list_agency_invitations
        invites = [
            _serialize_invitation(i) for i in list_agency_invitations(agency)
        ]
        return JsonResponse({'ok': True, 'invitations': invites})

    def post(self, request):
        agency = self._agency()
        if not agency:
            return self._deny('آژانس یافت نشد', 404)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)
        phones = payload.get('phones') or [payload.get('phone', '')]
        phones = [p for p in phones if (p or '').strip()]
        if not phones:
            return JsonResponse({'ok': False, 'error': 'شماره موبایل الزامی است'}, status=400)
        from workspace.services.agency_invitations import create_bulk_agency_invitations
        result = create_bulk_agency_invitations(
            request.user, phones,
            role=payload.get('role', 'advisor'),
            request=request,
        )
        if result.get('capacity_error'):
            err = result['errors'][0] if result['errors'] else {}
            return JsonResponse({
                'ok': False,
                'error': err.get('error', 'ظرفیت دعوت تکمیل شده است.'),
                'code': err.get('code', 'agency_seat_capacity_reached'),
            }, status=409)
        if result['errors'] and not result['created']:
            return JsonResponse({'ok': False, 'errors': result['errors']}, status=400)
        return JsonResponse({
            'ok': True,
            'created': [_serialize_invitation(i) for i in result['created']],
            'errors': result['errors'],
        })


class AgencyInvitationActionAPIView(_AgencyOwnerAPIBase):
    def post(self, request, invitation_id: int):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = {}
        action = payload.get('action', request.POST.get('action', ''))
        try:
            if action == 'resend':
                inv = resend_invitation_sms(request.user, invitation_id, request=request)
            elif action == 'cancel':
                inv = cancel_agency_invitation(request.user, invitation_id)
            else:
                return JsonResponse({'ok': False, 'error': 'عملیات نامعتبر'}, status=400)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'invitation': _serialize_invitation(inv)})


class AgencySeatAssignAPIView(_AgencyOwnerAPIBase):
    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)
        action = payload.get('action', 'assign')
        license_id = int(payload.get('license_id', 0) or 0)
        try:
            if action == 'assign':
                member_user_id = int(payload.get('member_user_id', 0) or 0)
                lic = assign_seat_to_member(request.user, license_id, member_user_id)
            elif action == 'unassign':
                lic = unassign_seat(request.user, license_id)
            else:
                return JsonResponse({'ok': False, 'error': 'عملیات نامعتبر'}, status=400)
        except Exception as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'license_id': lic.pk})


class AgencyMemberRemoveAPIView(_AgencyOwnerAPIBase):
    def post(self, request, member_id: int):
        try:
            member = remove_agency_member(request.user, member_id)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'member_id': member.pk})


class AgencyAvailableSeatsAPIView(_AgencyOwnerAPIBase):
    def get(self, request):
        agency = self._agency()
        if not agency:
            return self._deny('آژانس یافت نشد', 404)
        seats = list_available_seats(request.user, agency)
        return JsonResponse({
            'ok': True,
            'seats': [
                {'id': s.pk, 'sequence': s.sequence, 'plan': s.plan.name if s.plan_id else ''}
                for s in seats
            ],
        })


def _serialize_invitation(inv: AgencyInvitation) -> dict:
    return {
        'id': inv.pk,
        'phone': inv.phone,
        'role': inv.role,
        'status': inv.status,
        'expires_at': inv.expires_at.isoformat() if inv.expires_at else None,
        'accepted_at': inv.accepted_at.isoformat() if inv.accepted_at else None,
        'sms_sent_at': inv.sms_sent_at.isoformat() if inv.sms_sent_at else None,
        'sms_resend_count': inv.sms_resend_count,
        'sms_metadata': inv.sms_metadata or {},
        'created_at': inv.created_at.isoformat() if inv.created_at else None,
    }


def _serialize_dashboard(data: dict) -> dict:
    members = []
    for row in data.get('members', []):
        m = row['member']
        seat = row.get('seat')
        members.append({
            'id': m.pk,
            'user_id': m.user_id,
            'name': m.user.get_full_name() or m.user.phone or m.user.username,
            'phone': m.user.phone or m.user.username,
            'role': m.role,
            'is_active': m.is_active,
            'has_seat': row.get('has_seat', False),
            'seat_expires': seat.expires_at.isoformat() if seat and seat.expires_at else None,
            'joined_at': m.joined_at.isoformat() if m.joined_at else None,
        })
    return {
        'members': members,
        'invitations': [_serialize_invitation(i) for i in data.get('invitations', [])],
        'seats': data.get('seats'),
        'active_count': data.get('active_count', 0),
        'without_seat': data.get('without_seat', 0),
        'pending_invites': data.get('pending_invites', 0),
    }
