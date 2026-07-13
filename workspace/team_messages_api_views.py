"""REST API صندوق پیام داخلی آژانس."""
from __future__ import annotations

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from workspace.constants import AGENCY_ROLES
from workspace.services.crm_agency_features import is_agency_feature_enabled
from workspace.services.crm_agency_messages import (
    get_thread_detail,
    list_threads_for_user,
    reply_to_thread,
    send_broadcast_message,
    send_direct_message,
    unread_message_count,
    update_thread_state,
)
from workspace.services.crm_panel_notifications import (
    list_panel_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    unread_panel_count,
)
from workspace.services.crm_scope import agency_members, get_membership


class _TeamHubAPIBase(LoginRequiredMixin, View):
    def _deny(self, msg='دسترسی مجاز نیست', code=403):
        return JsonResponse({'ok': False, 'error': msg}, status=code)

    def _check_feature(self, feature: str):
        m = get_membership(self.request.user)
        if not m:
            return None, self._deny('آژانس یافت نشد', 404)
        if not is_agency_feature_enabled(feature, m.agency):
            return None, self._deny('این قابلیت غیرفعال است', 403)
        return m, None

    def _membership_only(self):
        m = get_membership(self.request.user)
        if not m:
            return None, self._deny('آژانس یافت نشد', 404)
        return m, None


class _MessagesAPIBase(_TeamHubAPIBase):
    def _check_messages(self):
        return self._check_feature('messages')


class TeamMessagesAPIView(_MessagesAPIBase):
    def get(self, request):
        m, err = self._check_messages()
        if err:
            return err
        folder = request.GET.get('folder', 'inbox')
        if folder not in ('inbox', 'starred', 'archived'):
            folder = 'inbox'
        page = max(1, int(request.GET.get('page', 1) or 1))
        items, total = list_threads_for_user(request.user, folder=folder, page=page)
        return JsonResponse({'ok': True, 'threads': items, 'total': total, 'page': page})

    def post(self, request):
        m, err = self._check_messages()
        if err:
            return err
        try:
            if request.content_type and 'multipart' in request.content_type:
                payload = request.POST
                files = request.FILES.getlist('attachments')
            else:
                payload = json.loads(request.body.decode('utf-8') or '{}')
                files = []
            kind = payload.get('kind', 'direct')
            body = payload.get('body', '')
            if kind == 'broadcast':
                thread = send_broadcast_message(
                    request.user,
                    body,
                    subject=payload.get('subject', ''),
                    target_roles=payload.get('target_roles') or [],
                    attachments=files,
                )
            else:
                recipient_id = int(payload.get('recipient_member_id', 0))
                thread = send_direct_message(
                    request.user,
                    recipient_id,
                    body,
                    attachments=files,
                    reply_thread_id=payload.get('thread_id'),
                )
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        detail = get_thread_detail(request.user, thread.pk)
        return JsonResponse({'ok': True, 'thread': detail})


class TeamMessageDetailAPIView(_MessagesAPIBase):
    def get(self, request, thread_id):
        m, err = self._check_messages()
        if err:
            return err
        detail = get_thread_detail(request.user, thread_id)
        if not detail:
            return self._deny('پیام یافت نشد', 404)
        return JsonResponse({'ok': True, **detail})

    def patch(self, request, thread_id):
        m, err = self._check_messages()
        if err:
            return err
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            ok = update_thread_state(
                request.user,
                thread_id,
                is_starred=payload.get('is_starred'),
                is_archived=payload.get('is_archived'),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        if not ok:
            return self._deny('پیام یافت نشد', 404)
        return JsonResponse({'ok': True})

    def post(self, request, thread_id):
        """پاسخ به رشته پیام."""
        m, err = self._check_messages()
        if err:
            return err
        try:
            if request.content_type and 'multipart' in request.content_type:
                body = request.POST.get('body', '')
                files = request.FILES.getlist('attachments')
            else:
                payload = json.loads(request.body.decode('utf-8') or '{}')
                body = payload.get('body', '')
                files = []
            message = reply_to_thread(request.user, thread_id, body, attachments=files)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        detail = get_thread_detail(request.user, message.thread_id)
        return JsonResponse({'ok': True, **detail})


class TeamMessagesUnreadAPIView(_MessagesAPIBase):
    def get(self, request):
        m, err = self._check_messages()
        if err:
            return err
        return JsonResponse({
            'ok': True,
            'unread_messages': unread_message_count(request.user),
            'unread_notifications': unread_panel_count(request.user),
        })


class TeamMessagesMembersAPIView(_MessagesAPIBase):
    def get(self, request):
        m, err = self._check_messages()
        if err:
            return err
        members = [
            {
                'id': mem.pk,
                'user_id': mem.user_id,
                'name': mem.user.get_full_name() or mem.user.phone or mem.user.username,
                'role': mem.role,
                'role_label': dict(AGENCY_ROLES).get(mem.role, mem.role),
            }
            for mem in agency_members(m.agency)
            if mem.user_id != request.user.pk
        ]
        return JsonResponse({'ok': True, 'members': members})


class TeamPanelNotificationsAPIView(_TeamHubAPIBase):
    def get(self, request):
        m, err = self._membership_only()
        if err:
            return err
        unread_only = request.GET.get('unread') == '1'
        items = list_panel_notifications(request.user, unread_only=unread_only)
        return JsonResponse({
            'ok': True,
            'notifications': items,
            'unread': unread_panel_count(request.user),
        })

    def post(self, request):
        m, err = self._membership_only()
        if err:
            return err
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            if payload.get('action') == 'read_all':
                count = mark_all_notifications_read(request.user)
            else:
                nid = int(payload.get('notification_id', 0))
                mark_notification_read(request.user, nid)
                count = 1
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'marked': count})


class TeamAnnouncementsAPIView(_TeamHubAPIBase):
    def get(self, request):
        m, err = self._check_feature('announcements')
        if err:
            return err
        from workspace.services.crm_agency_announcements import list_announcements, unread_announcement_count
        unread_only = request.GET.get('unread') == '1'
        page = max(1, int(request.GET.get('page', 1) or 1))
        items, total = list_announcements(request.user, unread_only=unread_only, page=page)
        return JsonResponse({
            'ok': True, 'announcements': items, 'total': total,
            'unread': unread_announcement_count(request.user),
        })

    def post(self, request):
        m, err = self._check_feature('announcements')
        if err:
            return err
        from workspace.services.crm_agency_announcements import create_announcement
        try:
            if request.content_type and 'multipart' in request.content_type:
                p = request.POST
                attachment = request.FILES.get('attachment')
            else:
                p = json.loads(request.body.decode('utf-8') or '{}')
                attachment = None
            roles = p.getlist('target_roles') if hasattr(p, 'getlist') else (p.get('target_roles') or [])
            ann = create_announcement(
                request.user,
                title=p.get('title', ''),
                body=p.get('body', ''),
                importance=p.get('importance', 'normal'),
                is_pinned=p.get('is_pinned') in (True, '1', 'true', 'on'),
                target_roles=roles,
                attachment=attachment,
            )
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'id': ann.pk})


class TeamAnnouncementDetailAPIView(_TeamHubAPIBase):
    def patch(self, request, announcement_id):
        m, err = self._check_feature('announcements')
        if err:
            return err
        from workspace.services.crm_agency_announcements import mark_announcement_read, update_announcement
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            if payload.get('action') == 'read':
                mark_announcement_read(request.user, announcement_id)
                return JsonResponse({'ok': True})
            update_announcement(request.user, announcement_id, **payload)
        except (json.JSONDecodeError, ValueError) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})

    def delete(self, request, announcement_id):
        m, err = self._check_feature('announcements')
        if err:
            return err
        from workspace.services.crm_agency_announcements import delete_announcement
        try:
            delete_announcement(request.user, announcement_id)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})
