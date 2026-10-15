"""Agency Mobile Operations — /api/mobile/v1/agency/..."""
from __future__ import annotations

import logging

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from mobile_api.responses import api_error, api_ok
from mobile_api.views import _parse_body

logger = logging.getLogger(__name__)


def _require_membership(user):
    from workspace.services.crm_scope import get_membership

    membership = get_membership(user)
    if not membership:
        return None, api_error('آژانس یافت نشد.', code='NOT_FOUND', status=404)
    return membership, None


class AgencyHomeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.agency_mobile import agency_home_for_user

        return api_ok(agency_home_for_user(request.user))


class AgencyAdvisorsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.agency_mobile import list_advisors_for_user

        _, err = _require_membership(request.user)
        if err:
            return err
        q = (request.query_params.get('q') or '').strip()
        status = (request.query_params.get('status') or '').strip()
        return api_ok(list_advisors_for_user(request.user, q=q, status=status))


class AgencyAdvisorDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, member_id: int):
        from mobile_api.services.agency_mobile import advisor_detail_for_user

        _, err = _require_membership(request.user)
        if err:
            return err
        payload = advisor_detail_for_user(request.user, member_id)
        if not payload:
            return api_error('مشاور یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class AgencyAdvisorWorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, member_id: int):
        from mobile_api.services.agency_advisor_mobile import advisor_workspace_for_user

        _, err = _require_membership(request.user)
        if err:
            return err
        tab = (request.query_params.get('tab') or 'overview').strip()
        page = request.query_params.get('page') or '1'
        period_raw = request.query_params.get('period') or '30'
        try:
            page_i = int(page)
        except (TypeError, ValueError):
            page_i = 1
        try:
            period_i = int(period_raw)
        except (TypeError, ValueError):
            period_i = 30
        payload = advisor_workspace_for_user(
            request.user,
            member_id,
            tab=tab,
            page=page_i,
            q=(request.query_params.get('q') or '').strip(),
            status=(request.query_params.get('status') or '').strip(),
            stage=(request.query_params.get('stage') or '').strip(),
            dataset_id=(request.query_params.get('dataset_id') or '').strip() or None,
            period=period_i,
        )
        if not payload:
            return api_error('دسترسی به داده مشاور مجاز نیست.', code='FORBIDDEN', status=403)
        return api_ok(payload)


class AgencyInvitationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.agency_mobile import list_advisors_for_user

        _, err = _require_membership(request.user)
        if err:
            return err
        data = list_advisors_for_user(request.user, status='invited')
        return api_ok({'invitations': data.get('invitations') or []})

    def post(self, request):
        from workspace.services.agency_invitations import create_agency_invitation
        from workspace.services.agency_entitlement import can_manage_agency, resolve_managed_agency

        agency, _sub = resolve_managed_agency(request.user)
        if not agency or not can_manage_agency(request.user, agency):
            return api_error('دسترسی دعوت ندارید.', code='FORBIDDEN', status=403)
        data = _parse_body(request)
        phone = (data.get('phone') or '').strip()
        role = (data.get('role') or 'advisor').strip()
        if not phone:
            return api_error('شماره موبایل الزامی است.', code='VALIDATION_ERROR')
        try:
            inv = create_agency_invitation(request.user, phone, role, request=request)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        from mobile_api.services.agency_mobile import _invitation_to_dict

        return api_ok({'invitation': _invitation_to_dict(inv)}, status=201)


class AgencyInvitationActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, invitation_id: int):
        from workspace.services.agency_entitlement import can_manage_agency, resolve_managed_agency
        from workspace.services.agency_invitations import cancel_agency_invitation, resend_invitation_sms

        agency, _sub = resolve_managed_agency(request.user)
        if not agency or not can_manage_agency(request.user, agency):
            return api_error('دسترسی ندارید.', code='FORBIDDEN', status=403)
        data = _parse_body(request)
        action = (data.get('action') or '').strip()
        try:
            if action == 'resend':
                inv = resend_invitation_sms(request.user, invitation_id, request=request)
            elif action == 'cancel':
                inv = cancel_agency_invitation(request.user, invitation_id)
            else:
                return api_error('عملیات نامعتبر است.', code='VALIDATION_ERROR')
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        from mobile_api.services.agency_mobile import _invitation_to_dict

        return api_ok({'invitation': _invitation_to_dict(inv)})


class AgencySeatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.agency_mobile import seats_overview_for_user

        try:
            payload = seats_overview_for_user(request.user)
        except ValueError as exc:
            return api_error(str(exc), code='FORBIDDEN', status=403)
        return api_ok(payload)

    def post(self, request):
        from workspace.services.agency_entitlement import can_manage_agency, resolve_managed_agency
        from workspace.services.agency_seats import assign_seat_to_member, unassign_seat

        agency, _sub = resolve_managed_agency(request.user)
        if not agency or not can_manage_agency(request.user, agency):
            return api_error('دسترسی مدیریت صندلی ندارید.', code='FORBIDDEN', status=403)
        data = _parse_body(request)
        action = (data.get('action') or 'assign').strip()
        license_id = int(data.get('license_id') or 0)
        if not license_id:
            return api_error('شناسه صندلی الزامی است.', code='VALIDATION_ERROR')
        try:
            if action == 'assign':
                member_user_id = int(data.get('member_user_id') or 0)
                if not member_user_id:
                    return api_error('عضو الزامی است.', code='VALIDATION_ERROR')
                lic = assign_seat_to_member(request.user, license_id, member_user_id)
            elif action == 'unassign':
                lic = unassign_seat(request.user, license_id)
            else:
                return api_error('عملیات نامعتبر است.', code='VALIDATION_ERROR')
        except Exception as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'license_id': lic.pk, 'action': action})


class AgencyInvitePreviewView(APIView):
    """پیش‌نمایش دعوت — بدون افشای شماره کامل."""

    permission_classes = [AllowAny]

    def get(self, request):
        from mobile_api.services.agency_invite_mobile import invitation_preview

        token = (request.query_params.get('token') or '').strip()
        if not token:
            return api_error('توکن الزامی است.', code='VALIDATION_ERROR')
        user = request.user if request.user.is_authenticated else None
        return api_ok(invitation_preview(token, user))


class AgencyInviteRespondView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from mobile_api.services.agency_invite_mobile import respond_to_invitation

        data = _parse_body(request)
        token = (data.get('token') or '').strip()
        action = (data.get('action') or '').strip()
        consent = bool(data.get('consent_acknowledged'))
        if not token:
            return api_error('توکن الزامی است.', code='VALIDATION_ERROR')
        try:
            payload = respond_to_invitation(
                request.user,
                token,
                action=action,
                consent_acknowledged=consent,
            )
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok(payload)


class AgencySettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.agency_mobile import agency_settings_payload

        _, err = _require_membership(request.user)
        if err:
            return err
        payload = agency_settings_payload(request.user)
        if payload is None:
            return api_error('آژانس یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)

    def patch(self, request):
        from mobile_api.services.agency_mobile import agency_settings_update

        _, err = _require_membership(request.user)
        if err:
            return err
        data = _parse_body(request)
        try:
            payload = agency_settings_update(
                request.user,
                name=(data.get('name') or ''),
                lead_routing_policy=(data.get('lead_routing_policy') or ''),
            )
        except ValueError as exc:
            return api_error(str(exc), code='FORBIDDEN', status=403)
        return api_ok(payload)


class AgencyAuditView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.agency_mobile import agency_audit_payload

        _, err = _require_membership(request.user)
        if err:
            return err
        limit = int(request.query_params.get('limit') or 50)
        try:
            payload = agency_audit_payload(request.user, limit=limit)
        except ValueError as exc:
            return api_error(str(exc), code='FORBIDDEN', status=403)
        return api_ok(payload)


class AgencyActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.agency_mobile import agency_activity_for_user

        _, err = _require_membership(request.user)
        if err:
            return err
        advisor_raw = request.query_params.get('advisor')
        advisor_member_id = int(advisor_raw) if advisor_raw and advisor_raw.isdigit() else None
        event_type = (request.query_params.get('event_type') or '').strip()
        payload = agency_activity_for_user(
            request.user,
            advisor_member_id=advisor_member_id,
            event_type=event_type,
        )
        if payload is None:
            return api_error('آژانس یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class AgencyContractsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.pagination import clamp_page, clamp_page_size
        from mobile_api.services.agency_contracts_mobile import agency_contracts_for_user
        from workspace.services.agency_data_scope import AgencyDataScopeError

        _, err = _require_membership(request.user)
        if err:
            return err
        from django.core.exceptions import PermissionDenied
        from workspace.services.crm_rbac_guard import assert_crm_contracts_access_allowed

        try:
            assert_crm_contracts_access_allowed(request.user)
        except PermissionDenied as exc:
            return api_error(str(exc), code='FORBIDDEN', status=403)
        page = clamp_page(request.GET.get('page', 1))
        page_size = clamp_page_size(request.GET.get('page_size', 20), default=20, maximum=50)
        params = {
            'q': request.GET.get('q') or request.GET.get('search') or '',
            'status': request.GET.get('status') or '',
            'type': request.GET.get('type') or request.GET.get('contract_type') or '',
            'deal_id': request.GET.get('deal_id') or '',
            'deal_linked': request.GET.get('deal_linked') or '',
            'date_from': request.GET.get('date_from') or '',
            'date_to': request.GET.get('date_to') or '',
            'sort': request.GET.get('sort') or 'updated',
            'needs_action': request.GET.get('needs_action') or '',
            'advisor': request.GET.get('advisor') or request.GET.get('advisor_member_id') or '',
        }
        try:
            payload = agency_contracts_for_user(
                request.user,
                page=page,
                page_size=page_size,
                query=params,
            )
        except AgencyDataScopeError as exc:
            return api_error(str(exc), code='FORBIDDEN', status=403)
        if payload is None:
            return api_error('آژانس یافت نشد.', code='NOT_FOUND', status=404)
        meta = payload.pop('meta', {})
        return api_ok(payload, meta=meta)


class AgencyPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.agency_mobile import team_performance_for_user

        days = int(request.query_params.get('days') or 7)
        if days not in (1, 7, 30):
            days = 7
        try:
            payload = team_performance_for_user(request.user, days=days)
        except ValueError as exc:
            return api_error(str(exc), code='FORBIDDEN', status=403)
        return api_ok(payload)


class AgencyLeadAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, customer_id: int):
        from workspace.models import Customer
        from workspace.services.crm_agency import assign_lead_to_member
        from workspace.services.crm_scope import can_operate_team_leads, get_membership

        from workspace.services.agency_rbac import can_operate_team_inbox

        if not can_operate_team_inbox(request.user):
            return api_error('دسترسی تخصیص سرنخ ندارید.', code='FORBIDDEN', status=403)
        m = get_membership(request.user)
        if not m:
            return api_error('آژانس یافت نشد.', code='NOT_FOUND', status=404)
        data = _parse_body(request)
        member_id = int(data.get('member_id') or 0)
        if not member_id:
            return api_error('عضو تیم الزامی است.', code='VALIDATION_ERROR')
        customer = Customer.objects.filter(pk=customer_id, agency=m.agency).first()
        if not customer:
            return api_error('سرنخ یافت نشد.', code='NOT_FOUND', status=404)
        try:
            assign_lead_to_member(request.user, customer, member_id)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'assigned': True})


class AgencyLeadTransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, customer_id: int):
        from workspace.models import Customer
        from workspace.services.crm_agency import transfer_agency_lead
        from workspace.services.crm_scope import get_membership

        m = get_membership(request.user)
        if not m:
            return api_error('آژانس یافت نشد.', code='NOT_FOUND', status=404)
        customer = Customer.objects.filter(pk=customer_id, agency=m.agency).first()
        if not customer:
            return api_error('سرنخ یافت نشد.', code='NOT_FOUND', status=404)
        data = _parse_body(request)
        member_id = int(data.get('member_id') or 0)
        if not member_id:
            return api_error('عضو تیم الزامی است.', code='VALIDATION_ERROR')
        try:
            transfer_agency_lead(
                request.user,
                customer,
                member_id,
                note=(data.get('note') or '').strip(),
            )
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'transferred': True})


class AgencyAdvisorActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, member_id: int):
        from workspace.services.agency_members import remove_agency_member
        from workspace.services.crm_agency import update_member_role
        from workspace.services.agency_entitlement import can_manage_agency, resolve_managed_agency

        agency, _sub = resolve_managed_agency(request.user)
        if not agency or not can_manage_agency(request.user, agency):
            return api_error('دسترسی ندارید.', code='FORBIDDEN', status=403)
        data = _parse_body(request)
        action = (data.get('action') or '').strip()
        try:
            if action == 'deactivate':
                remove_agency_member(request.user, member_id)
            elif action == 'set_role':
                role = (data.get('role') or '').strip()
                if not role:
                    return api_error('نقش الزامی است.', code='VALIDATION_ERROR')
                update_member_role(request.user, member_id, role)
            else:
                return api_error('عملیات نامعتبر است.', code='VALIDATION_ERROR')
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'ok': True})
