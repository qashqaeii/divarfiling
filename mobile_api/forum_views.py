"""API تالار گفتگو برای اپلیکیشن Android — JWT و همان سرویس‌های community_forum."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from community_forum.constants import MAX_BODY_LENGTH, REPORT_REASONS
from community_forum.models import ForumPinnedNotice
from community_forum.services.access import (
    is_forum_enabled,
    user_can_access_forum,
    user_can_moderate_forum,
)
from community_forum.services.identity import member_display_label
from community_forum.services.members import get_or_create_member, update_display_name
from community_forum.services.message_views import MAX_VIEW_BATCH, record_message_views
from community_forum.services.messages import (
    delete_message,
    edit_message,
    get_pinned_message,
    list_messages,
    list_sync_changes,
    report_message,
    search_messages,
    send_message,
    serialize_many,
    set_message_pinned,
    set_reaction,
    unread_count,
    update_read_cursor,
)
from community_forum.services.moderation import member_can_read
from community_forum.services.serialization import build_reactions_map, serialize_message
from mobile_api.authentication import MobileJWTAuthentication
from mobile_api.responses import api_error, api_ok
from mobile_api.views import _parse_body


def _validation_code(exc: ValidationError) -> str:
    code = getattr(exc, 'code', None)
    if not code and getattr(exc, 'error_list', None):
        code = exc.error_list[0].code
    return str(code or 'error')


def _validation_message(exc: ValidationError) -> str:
    msgs = exc.messages if hasattr(exc, 'messages') else [str(exc)]
    return msgs[0]


def _validation_status(code: str) -> int:
    if code.startswith('rate_'):
        return 429
    if code in ('forbidden', 'banned', 'banned_read'):
        return 403
    if code in ('not_found', 'reply_invalid'):
        return 404
    if code == 'duplicate':
        return 409
    return 400


def _forum_err(exc: ValidationError):
    code = _validation_code(exc)
    return api_error(
        _validation_message(exc),
        code=code,
        status=_validation_status(code),
    )


def _forum_gate(request):
    if not is_forum_enabled():
        return api_error('تالار گفتگو فعال نیست.', code='NOT_FOUND', status=404)
    if not user_can_access_forum(request.user):
        return api_error('دسترسی مجاز نیست.', code='NOT_FOUND', status=404)
    return None


def _member_or_error(request):
    gate = _forum_gate(request)
    if gate:
        return None, gate
    if not request.user.is_active:
        return None, api_error('دسترسی مجاز نیست.', code='FORBIDDEN', status=403)
    member = get_or_create_member(request.user)
    return member, None


def _active_member(request):
    member, err = _member_or_error(request)
    if err:
        return None, err
    if not member_can_read(member):
        return None, api_error('دسترسی محدود شده است.', code='FORBIDDEN', status=403)
    return member, None


class ForumMobileAPIView(APIView):
    authentication_classes = [MobileJWTAuthentication]
    permission_classes = [IsAuthenticated]


class ForumBootstrapView(ForumMobileAPIView):
    def get(self, request):
        member, err = _active_member(request)
        if err:
            return err
        notices = []
        now = timezone.now()
        for n in ForumPinnedNotice.objects.filter(is_active=True).order_by('-created_at')[:3]:
            if n.expires_at and n.expires_at < now:
                continue
            notices.append({'body': n.body, 'created_at': n.created_at.isoformat()})
        pinned = get_pinned_message()
        pinned_payload = serialize_message(pinned, viewer_member=member) if pinned else None
        return api_ok({
            'member': {
                'public_id': str(member.public_id),
                'display_label': member_display_label(member),
                'display_name': member.display_name if member.display_name_approved else '',
                'welcome_seen': bool(member.welcome_seen_at),
            },
            'limits': {'max_body': MAX_BODY_LENGTH},
            'report_reasons': [{'id': r[0], 'label': r[1]} for r in REPORT_REASONS],
            'pinned_notices': notices,
            'pinned_message': pinned_payload,
            'unread': unread_count(member),
            'can_moderate': user_can_moderate_forum(request.user),
        })


class ForumMessagesView(ForumMobileAPIView):
    def get(self, request):
        member, err = _active_member(request)
        if err:
            return err
        before_id = request.query_params.get('before_id')
        after_id = request.query_params.get('after_id')
        try:
            before_id = int(before_id) if before_id else None
            after_id = int(after_id) if after_id else None
        except ValueError:
            return api_error('پارامتر نامعتبر', code='VALIDATION_ERROR')
        items, next_before, has_more_after = list_messages(
            member, before_id=before_id, after_id=after_id,
        )
        return api_ok({
            'messages': serialize_many(items, member),
            'next_before_id': next_before,
            'has_more_after': has_more_after,
        })

    def post(self, request):
        member, err = _active_member(request)
        if err:
            return err
        data = _parse_body(request)
        try:
            msg = send_message(
                member,
                data.get('body', ''),
                reply_to_id=data.get('reply_to_id'),
                client_message_id=data.get('client_message_id'),
            )
        except ValidationError as exc:
            return _forum_err(exc)
        rx, mine = build_reactions_map([msg.pk], member)
        return api_ok({
            'message': serialize_message(
                msg, viewer_member=member, reactions_map=rx, my_reactions=mine,
            ),
        }, status=201)


class ForumMessageDetailView(ForumMobileAPIView):
    def patch(self, request, message_id):
        member, err = _active_member(request)
        if err:
            return err
        data = _parse_body(request)
        try:
            msg = edit_message(member, message_id, data.get('body', ''))
        except ValidationError as exc:
            return _forum_err(exc)
        return api_ok({'message': serialize_message(msg, viewer_member=member)})

    def delete(self, request, message_id):
        member, err = _active_member(request)
        if err:
            return err
        try:
            delete_message(member, message_id, moderator_user=request.user)
        except ValidationError as exc:
            return _forum_err(exc)
        return api_ok({})


class ForumMessagePinView(ForumMobileAPIView):
    def post(self, request, message_id):
        if not user_can_moderate_forum(request.user):
            return api_error('اجازه سنجاق پیام را ندارید.', code='FORBIDDEN', status=403)
        member, err = _active_member(request)
        if err:
            return err
        data = _parse_body(request)
        pinned = data.get('pin', True)
        if isinstance(pinned, str):
            pinned = pinned.lower() not in ('0', 'false', 'no')
        try:
            set_message_pinned(request.user, message_id, pinned=bool(pinned))
        except ValidationError as exc:
            return _forum_err(exc)
        current = get_pinned_message()
        return api_ok({
            'pinned_message': serialize_message(current, viewer_member=member) if current else None,
        })


class ForumMessageReactionView(ForumMobileAPIView):
    def post(self, request, message_id):
        member, err = _active_member(request)
        if err:
            return err
        data = _parse_body(request)
        try:
            payload = set_reaction(member, message_id, data.get('emoji'))
        except ValidationError as exc:
            return _forum_err(exc)
        return api_ok(payload)


class ForumMessageReportView(ForumMobileAPIView):
    def post(self, request, message_id):
        member, err = _active_member(request)
        if err:
            return err
        data = _parse_body(request)
        try:
            report_message(member, message_id, data.get('reason', ''), data.get('note', ''))
        except ValidationError as exc:
            return _forum_err(exc)
        return api_ok({})


class ForumReadView(ForumMobileAPIView):
    def post(self, request):
        member, err = _active_member(request)
        if err:
            return err
        data = _parse_body(request)
        try:
            mid = int(data.get('message_id', 0))
        except (TypeError, ValueError):
            return api_error('شناسه نامعتبر', code='VALIDATION_ERROR')
        update_read_cursor(member, mid)
        from community_forum.context_processors import invalidate_forum_unread_cache

        invalidate_forum_unread_cache(request.user.pk)
        return api_ok({'unread': unread_count(member)})


class ForumMessageViewsView(ForumMobileAPIView):
    def post(self, request):
        member, err = _active_member(request)
        if err:
            return err
        data = _parse_body(request)
        raw_ids = data.get('message_ids') or data.get('ids') or []
        if not isinstance(raw_ids, list):
            return api_error('فرمت نامعتبر', code='VALIDATION_ERROR')
        if len(raw_ids) > MAX_VIEW_BATCH:
            return api_error('حداکثر ۴۰ پیام در هر درخواست', code='VALIDATION_ERROR')
        counts = record_message_views(member, raw_ids)
        return api_ok({'views': counts})


class ForumSearchView(ForumMobileAPIView):
    def get(self, request):
        member, err = _active_member(request)
        if err:
            return err
        q = request.query_params.get('q', '')
        try:
            page = int(request.query_params.get('page', 1) or 1)
        except ValueError:
            return api_error('صفحه نامعتبر', code='VALIDATION_ERROR')
        try:
            items, total = search_messages(member, q, page=page)
        except ValidationError as exc:
            return _forum_err(exc)
        return api_ok({'messages': items, 'total': total, 'page': page})


class ForumProfileView(ForumMobileAPIView):
    def post(self, request):
        member, err = _active_member(request)
        if err:
            return err
        data = _parse_body(request)
        if data.get('welcome_ack'):
            if not member.welcome_seen_at:
                member.welcome_seen_at = timezone.now()
                member.save(update_fields=['welcome_seen_at', 'updated_at'])
            return api_ok({'welcome_seen': True})
        if 'display_name' in data:
            try:
                update_display_name(member, data.get('display_name', ''))
            except ValidationError as exc:
                return _forum_err(exc)
            return api_ok({
                'display_label': member_display_label(member),
                'display_name': member.display_name,
            })
        return api_error('درخواست نامعتبر', code='VALIDATION_ERROR')


class ForumUnreadView(ForumMobileAPIView):
    def get(self, request):
        member, err = _member_or_error(request)
        if err:
            return err
        return api_ok({'unread': unread_count(member)})


class ForumSyncView(ForumMobileAPIView):
    def get(self, request):
        member, err = _active_member(request)
        if err:
            return err
        since = request.query_params.get('since', '')
        try:
            anchor_id = int(request.query_params.get('anchor_id', 0) or 0)
            cursor_id = int(request.query_params.get('cursor', 0) or 0)
        except ValueError:
            return api_error('شناسه نامعتبر', code='VALIDATION_ERROR')
        try:
            page = list_sync_changes(
                member,
                anchor_id=anchor_id,
                since_iso=since,
                cursor_id=cursor_id,
            )
        except ValidationError as exc:
            return _forum_err(exc)
        return api_ok(page)
