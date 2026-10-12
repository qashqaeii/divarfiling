"""Viewهای Team / Agency برای Mobile API."""
from __future__ import annotations

import logging

from rest_framework.permissions import IsAuthenticated
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


def _require_feature(user, feature: str):
    from workspace.services.crm_agency_features import is_agency_feature_enabled

    membership, err = _require_membership(user)
    if err:
        return None, err
    if not is_agency_feature_enabled(feature, membership.agency):
        return None, api_error('این قابلیت غیرفعال است.', code='FEATURE_DISABLED', status=403)
    return membership, None


class TeamOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.team_mobile import team_overview_for_user

        return api_ok(team_overview_for_user(request.user))


class TeamMembersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.team_mobile import serialize_members

        membership, err = _require_membership(request.user)
        if err:
            return err
        exclude_self = request.query_params.get('exclude_self') == '1'
        members = serialize_members(
            membership.agency,
            exclude_user_id=request.user.pk if exclude_self else None,
        )
        return api_ok({'members': members, 'count': len(members)})


class TeamUnreadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.team_mobile import team_overview_for_user

        overview = team_overview_for_user(request.user)
        return api_ok(overview.get('unread') or {})


class TeamMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from workspace.services.crm_agency_messages import list_threads_for_user

        membership, err = _require_feature(request.user, 'messages')
        if err:
            return err
        folder = (request.query_params.get('folder') or 'inbox').strip()
        if folder not in ('inbox', 'starred', 'archived'):
            folder = 'inbox'
        page = max(1, int(request.query_params.get('page') or 1))
        items, total = list_threads_for_user(request.user, folder=folder, page=page)
        return api_ok({'threads': items, 'total': total, 'page': page, 'folder': folder})

    def post(self, request):
        from workspace.services.crm_agency_messages import (
            get_thread_detail,
            send_broadcast_message,
            send_direct_message,
        )

        membership, err = _require_feature(request.user, 'messages')
        if err:
            return err
        data = _parse_body(request)
        kind = (data.get('kind') or 'direct').strip()
        body = (data.get('body') or '').strip()
        try:
            if kind == 'broadcast':
                roles = data.get('target_roles') or []
                if isinstance(roles, str):
                    roles = [roles]
                thread = send_broadcast_message(
                    request.user,
                    body,
                    subject=(data.get('subject') or '').strip(),
                    target_roles=[r for r in roles if r],
                )
            else:
                recipient_id = int(data.get('recipient_member_id') or 0)
                if not recipient_id:
                    return api_error('گیرنده الزامی است.', code='VALIDATION_ERROR')
                thread = send_direct_message(
                    request.user,
                    recipient_id,
                    body,
                    reply_thread_id=data.get('thread_id'),
                )
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        except Exception:
            logger.exception('team message send failed user=%s', request.user.pk)
            return api_error('ارسال پیام ناموفق بود.', code='ERROR', status=500)

        detail = get_thread_detail(request.user, thread.pk)
        return api_ok(detail or {'thread_id': thread.pk}, status=201)


class TeamMessageDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, thread_id):
        from workspace.services.crm_agency_messages import get_thread_detail

        membership, err = _require_feature(request.user, 'messages')
        if err:
            return err
        detail = get_thread_detail(request.user, thread_id)
        if not detail:
            return api_error('پیام یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(detail)

    def patch(self, request, thread_id):
        from workspace.services.crm_agency_messages import update_thread_state

        membership, err = _require_feature(request.user, 'messages')
        if err:
            return err
        data = _parse_body(request)
        ok = update_thread_state(
            request.user,
            thread_id,
            is_starred=data.get('is_starred'),
            is_archived=data.get('is_archived'),
        )
        if not ok:
            return api_error('پیام یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok({'updated': True})

    def post(self, request, thread_id):
        from workspace.services.crm_agency_messages import get_thread_detail, reply_to_thread

        membership, err = _require_feature(request.user, 'messages')
        if err:
            return err
        data = _parse_body(request)
        body = (data.get('body') or '').strip()
        try:
            reply_to_thread(request.user, thread_id, body)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        detail = get_thread_detail(request.user, thread_id)
        return api_ok(detail or {'updated': True})


class TeamAnnouncementsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from workspace.services.crm_agency_announcements import (
            list_announcements,
            unread_announcement_count,
        )

        membership, err = _require_feature(request.user, 'announcements')
        if err:
            return err
        unread_only = request.query_params.get('unread') == '1'
        important_only = request.query_params.get('important') == '1'
        page = max(1, int(request.query_params.get('page') or 1))
        items, total = list_announcements(
            request.user,
            unread_only=unread_only,
            important_only=important_only,
            page=page,
        )
        return api_ok({
            'announcements': items,
            'total': total,
            'unread': unread_announcement_count(request.user),
        })

    def post(self, request):
        from workspace.services.crm_agency_announcements import create_announcement, parse_announcement_datetime

        membership, err = _require_feature(request.user, 'announcements')
        if err:
            return err
        data = _parse_body(request)
        try:
            ann = create_announcement(
                request.user,
                title=data.get('title', ''),
                body=data.get('body', ''),
                importance=data.get('importance', 'normal'),
                is_pinned=data.get('is_pinned') in (True, '1', 'true', 1),
                target_roles=data.get('target_roles') or [],
                published_at=parse_announcement_datetime(data.get('published_at')),
                expires_at=parse_announcement_datetime(data.get('expires_at')),
            )
        except (TypeError, ValueError) as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'id': ann.pk})


class TeamAnnouncementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, announcement_id):
        from workspace.services.crm_agency_announcements import get_announcement, mark_announcement_read

        membership, err = _require_feature(request.user, 'announcements')
        if err:
            return err
        item = get_announcement(request.user, announcement_id)
        if not item:
            return api_error('اطلاعیه یافت نشد.', code='NOT_FOUND', status=404)
        # Opening detail marks as read for mobile-first UX.
        try:
            mark_announcement_read(request.user, announcement_id)
            item['is_read'] = True
        except Exception:
            pass
        return api_ok({'announcement': item})

    def post(self, request, announcement_id):
        from workspace.services.crm_agency_announcements import mark_announcement_read

        membership, err = _require_feature(request.user, 'announcements')
        if err:
            return err
        data = _parse_body(request)
        if (data.get('action') or 'read') != 'read':
            return api_error('اقدام نامعتبر است.', code='VALIDATION_ERROR')
        try:
            mark_announcement_read(request.user, announcement_id)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'read': True})


class TeamPanelNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from workspace.services.crm_panel_notifications import (
            list_panel_notifications,
            unread_panel_count,
        )

        membership, err = _require_membership(request.user)
        if err:
            return err
        unread_only = request.query_params.get('unread') == '1'
        items = list_panel_notifications(request.user, unread_only=unread_only)
        return api_ok({
            'notifications': items,
            'unread': unread_panel_count(request.user),
        })

    def post(self, request):
        from workspace.services.crm_panel_notifications import (
            mark_all_notifications_read,
            mark_notification_read,
        )

        membership, err = _require_membership(request.user)
        if err:
            return err
        data = _parse_body(request)
        try:
            if data.get('action') == 'read_all':
                count = mark_all_notifications_read(request.user)
            else:
                nid = int(data.get('notification_id') or 0)
                if not nid:
                    return api_error('شناسه اعلان الزامی است.', code='VALIDATION_ERROR')
                mark_notification_read(request.user, nid)
                count = 1
        except (TypeError, ValueError) as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'marked': count})


class TeamLeadInboxView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from mobile_api.services.agency_mobile import serialize_inbox_leads_enriched
        from workspace.services.crm_scope import can_operate_team_leads

        membership, err = _require_membership(request.user)
        if err:
            return err
        if not can_operate_team_leads(request.user):
            return api_error('دسترسی به صندوق سرنخ ندارید.', code='FORBIDDEN', status=403)
        filter_key = (request.query_params.get('filter') or 'all').strip()
        if filter_key not in ('all', 'fresh', 'stale'):
            filter_key = 'all'
        leads = serialize_inbox_leads_enriched(membership.agency, filter_key=filter_key)
        return api_ok({'leads': leads, 'count': len(leads), 'filter': filter_key})

    def post(self, request):
        from workspace.services.crm_agency import bulk_assign_leads
        from workspace.services.crm_scope import can_operate_team_leads

        if not can_operate_team_leads(request.user):
            return api_error('دسترسی به تخصیص سرنخ ندارید.', code='FORBIDDEN', status=403)
        data = _parse_body(request)
        try:
            member_id = int(data.get('member_id') or 0)
            ids = data.get('customer_ids') or []
            if not member_id or not ids:
                return api_error('عضو و لیست سرنخ الزامی است.', code='VALIDATION_ERROR')
            count = bulk_assign_leads(request.user, [int(i) for i in ids], member_id)
        except (TypeError, ValueError) as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'assigned': count})


class ContactAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contact_id):
        from workspace.services.crm_agency import assign_customer
        from workspace.services.crm_scope import customer_for_user, is_customer_owner

        customer = customer_for_user(request.user, contact_id)
        if not customer:
            return api_error('مخاطب یافت نشد.', code='NOT_FOUND', status=404)
        if not is_customer_owner(request.user, customer):
            return api_error('فقط مالک می‌تواند تخصیص دهد.', code='FORBIDDEN', status=403)
        data = _parse_body(request)
        try:
            member_id = int(data.get('member_id') or 0)
            if not member_id:
                return api_error('عضو تیم الزامی است.', code='VALIDATION_ERROR')
            assign_customer(request.user, customer, member_id)
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'assigned': True})


class ContactTransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contact_id):
        from workspace.services.crm_agency import transfer_customer
        from workspace.services.crm_scope import customer_for_user, is_customer_owner

        customer = customer_for_user(request.user, contact_id)
        if not customer:
            return api_error('مخاطب یافت نشد.', code='NOT_FOUND', status=404)
        if not is_customer_owner(request.user, customer):
            return api_error('فقط مالک می‌تواند پرونده را منتقل کند.', code='FORBIDDEN', status=403)
        data = _parse_body(request)
        try:
            member_id = int(data.get('member_id') or 0)
            if not member_id:
                return api_error('عضو تیم الزامی است.', code='VALIDATION_ERROR')
            transfer_customer(
                request.user,
                customer,
                member_id,
                note=(data.get('note') or '').strip(),
            )
        except ValueError as exc:
            return api_error(str(exc), code='VALIDATION_ERROR')
        return api_ok({'transferred': True})
