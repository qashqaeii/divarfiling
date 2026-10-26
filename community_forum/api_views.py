"""REST API تالار گفتگو."""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect

from community_forum.constants import MAX_BODY_LENGTH, REPORT_REASONS
from community_forum.models import ForumPinnedNotice
from community_forum.services.access import (
    is_forum_enabled,
    user_can_access_forum,
    user_can_moderate_forum,
)
from community_forum.services.members import get_or_create_member, update_display_name
from community_forum.services.message_views import MAX_VIEW_BATCH, record_message_views
from community_forum.services.messages import (
    delete_message,
    edit_message,
    list_messages,
    list_sync_changes,
    report_message,
    get_pinned_message,
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
from community_forum.services.identity import member_display_label


class ForumAPIBase(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if not is_forum_enabled():
            return JsonResponse({'ok': False, 'error': 'تالار گفتگو فعال نیست.'}, status=404)
        if request.user.is_authenticated and not user_can_access_forum(request.user):
            return JsonResponse({'ok': False, 'error': 'دسترسی مجاز نیست.'}, status=404)
        return super().dispatch(request, *args, **kwargs)

    def _member(self, request):
        if not request.user.is_active:
            raise PermissionError('inactive')
        return get_or_create_member(request.user)

    def _json_body(self, request) -> dict:
        if request.content_type and 'application/json' in request.content_type:
            try:
                return json.loads(request.body.decode('utf-8') or '{}')
            except json.JSONDecodeError:
                return {}
        return {}

    def _err(self, exc: ValidationError, status=None):
        msgs = exc.messages if hasattr(exc, 'messages') else [str(exc)]
        code = getattr(exc, 'code', None)
        if not code and getattr(exc, 'error_list', None):
            code = exc.error_list[0].code
        code = code or 'error'
        if status is None:
            if str(code).startswith('rate_'):
                status = 429
            elif code in ('forbidden', 'banned', 'banned_read'):
                status = 403
            elif code in ('not_found', 'reply_invalid'):
                status = 404
            elif code == 'duplicate':
                status = 409
            else:
                status = 400
        return JsonResponse({'ok': False, 'error': msgs[0], 'code': code}, status=status)

    def _active_member(self, request):
        try:
            member = self._member(request)
        except PermissionError:
            return None, JsonResponse({'ok': False, 'error': 'دسترسی مجاز نیست.'}, status=403)
        if not member_can_read(member):
            return None, JsonResponse({'ok': False, 'error': 'دسترسی محدود شده است.'}, status=403)
        return member, None


@method_decorator(csrf_protect, name='dispatch')
class ForumBootstrapAPIView(ForumAPIBase):
    def get(self, request):
        try:
            member = self._member(request)
        except PermissionError:
            return JsonResponse({'ok': False, 'error': 'دسترسی مجاز نیست.'}, status=403)
        if not member_can_read(member):
            return JsonResponse({'ok': False, 'error': 'دسترسی محدود شده است.'}, status=403)
        notices = []
        now = timezone.now()
        for n in ForumPinnedNotice.objects.filter(is_active=True).order_by('-created_at')[:3]:
            if n.expires_at and n.expires_at < now:
                continue
            notices.append({'body': n.body, 'created_at': n.created_at.isoformat()})
        pinned = get_pinned_message()
        pinned_payload = None
        if pinned:
            pinned_payload = serialize_message(pinned, viewer_member=member)
        return JsonResponse({
            'ok': True,
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


@method_decorator(csrf_protect, name='dispatch')
class ForumMessagesAPIView(ForumAPIBase):
    def get(self, request):
        member, err = self._active_member(request)
        if err:
            return err
        before_id = request.GET.get('before_id')
        after_id = request.GET.get('after_id')
        try:
            before_id = int(before_id) if before_id else None
            after_id = int(after_id) if after_id else None
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'پارامتر نامعتبر'}, status=400)
        items, next_before, has_more_after = list_messages(
            member, before_id=before_id, after_id=after_id,
        )
        return JsonResponse({
            'ok': True,
            'messages': serialize_many(items, member),
            'next_before_id': next_before,
            'has_more_after': has_more_after,
        })

    def post(self, request):
        member, err = self._active_member(request)
        if err:
            return err
        data = self._json_body(request)
        try:
            msg = send_message(
                member,
                data.get('body', ''),
                reply_to_id=data.get('reply_to_id'),
                client_message_id=data.get('client_message_id'),
            )
        except ValidationError as exc:
            return self._err(exc)
        rx, mine = build_reactions_map([msg.pk], member)
        return JsonResponse({
            'ok': True,
            'message': serialize_message(
                msg, viewer_member=member, reactions_map=rx, my_reactions=mine,
            ),
        })


@method_decorator(csrf_protect, name='dispatch')
class ForumMessageDetailAPIView(ForumAPIBase):
    def patch(self, request, message_id):
        member, err = self._active_member(request)
        if err:
            return err
        data = self._json_body(request)
        try:
            msg = edit_message(member, message_id, data.get('body', ''))
        except ValidationError as exc:
            return self._err(exc)
        return JsonResponse({'ok': True, 'message': serialize_message(msg, viewer_member=member)})

    def delete(self, request, message_id):
        member, err = self._active_member(request)
        if err:
            return err
        try:
            delete_message(member, message_id, moderator_user=request.user)
        except ValidationError as exc:
            return self._err(exc)
        return JsonResponse({'ok': True})


@method_decorator(csrf_protect, name='dispatch')
@method_decorator(csrf_protect, name='dispatch')
class ForumMessagePinAPIView(ForumAPIBase):
    def post(self, request, message_id):
        if not user_can_moderate_forum(request.user):
            return JsonResponse({'ok': False, 'error': 'اجازه سنجاق پیام را ندارید.'}, status=403)
        member, err = self._active_member(request)
        if err:
            return err
        data = self._json_body(request)
        pinned = data.get('pin', True)
        if isinstance(pinned, str):
            pinned = pinned.lower() not in ('0', 'false', 'no')
        try:
            set_message_pinned(request.user, message_id, pinned=bool(pinned))
        except ValidationError as exc:
            return self._err(exc)
        current = get_pinned_message()
        return JsonResponse({
            'ok': True,
            'pinned_message': serialize_message(current, viewer_member=member) if current else None,
        })


@method_decorator(csrf_protect, name='dispatch')
class ForumReactionAPIView(ForumAPIBase):
    def post(self, request, message_id):
        member, err = self._active_member(request)
        if err:
            return err
        data = self._json_body(request)
        try:
            payload = set_reaction(member, message_id, data.get('emoji'))
        except ValidationError as exc:
            return self._err(exc)
        return JsonResponse({'ok': True, **payload})


@method_decorator(csrf_protect, name='dispatch')
class ForumReportAPIView(ForumAPIBase):
    def post(self, request, message_id):
        member, err = self._active_member(request)
        if err:
            return err
        data = self._json_body(request)
        try:
            report_message(member, message_id, data.get('reason', ''), data.get('note', ''))
        except ValidationError as exc:
            return self._err(exc)
        return JsonResponse({'ok': True})


@method_decorator(csrf_protect, name='dispatch')
@method_decorator(csrf_protect, name='dispatch')
class ForumMessageViewsAPIView(ForumAPIBase):
    def post(self, request):
        member, err = self._active_member(request)
        if err:
            return err
        data = self._json_body(request)
        raw_ids = data.get('message_ids') or data.get('ids') or []
        if not isinstance(raw_ids, list):
            return JsonResponse({'ok': False, 'error': 'فرمت نامعتبر'}, status=400)
        if len(raw_ids) > MAX_VIEW_BATCH:
            return JsonResponse({'ok': False, 'error': 'حداکثر ۴۰ پیام در هر درخواست'}, status=400)
        counts = record_message_views(member, raw_ids)
        return JsonResponse({'ok': True, 'views': counts})


@method_decorator(csrf_protect, name='dispatch')
class ForumReadAPIView(ForumAPIBase):
    def post(self, request):
        member, err = self._active_member(request)
        if err:
            return err
        data = self._json_body(request)
        try:
            mid = int(data.get('message_id', 0))
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'شناسه نامعتبر'}, status=400)
        update_read_cursor(member, mid)
        from community_forum.context_processors import invalidate_forum_unread_cache

        invalidate_forum_unread_cache(request.user.pk)
        return JsonResponse({'ok': True, 'unread': unread_count(member)})


@method_decorator(csrf_protect, name='dispatch')
class ForumSearchAPIView(ForumAPIBase):
    def get(self, request):
        member, err = self._active_member(request)
        if err:
            return err
        q = request.GET.get('q', '')
        try:
            page = int(request.GET.get('page', 1) or 1)
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'صفحه نامعتبر'}, status=400)
        try:
            items, total = search_messages(member, q, page=page)
        except ValidationError as exc:
            return self._err(exc)
        return JsonResponse({'ok': True, 'messages': items, 'total': total, 'page': page})


@method_decorator(csrf_protect, name='dispatch')
class ForumProfileAPIView(ForumAPIBase):
    def post(self, request):
        member, err = self._active_member(request)
        if err:
            return err
        data = self._json_body(request)
        if data.get('welcome_ack'):
            from django.utils import timezone

            member.welcome_seen_at = timezone.now()
            member.save(update_fields=['welcome_seen_at', 'updated_at'])
            return JsonResponse({'ok': True})
        if 'display_name' in data:
            try:
                update_display_name(member, data.get('display_name', ''))
            except ValidationError as exc:
                return self._err(exc)
            return JsonResponse({
                'ok': True,
                'display_label': member_display_label(member),
                'display_name': member.display_name,
            })
        return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)


@method_decorator(csrf_protect, name='dispatch')
class ForumSyncAPIView(ForumAPIBase):
    """همگام‌سازی ویرایش/حذف پس از قطع WebSocket."""

    def get(self, request):
        member, err = self._active_member(request)
        if err:
            return err
        since = request.GET.get('since', '')
        try:
            anchor_id = int(request.GET.get('anchor_id', 0) or 0)
            cursor_id = int(request.GET.get('cursor', 0) or 0)
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'شناسه نامعتبر'}, status=400)
        try:
            page = list_sync_changes(
                member,
                anchor_id=anchor_id,
                since_iso=since,
                cursor_id=cursor_id,
            )
        except ValidationError as exc:
            return self._err(exc)
        return JsonResponse({'ok': True, **page})


class ForumUnreadAPIView(ForumAPIBase):
    def get(self, request):
        try:
            member = self._member(request)
        except PermissionError:
            return JsonResponse({'ok': False, 'error': 'دسترسی مجاز نیست.'}, status=403)
        return JsonResponse({'ok': True, 'unread': unread_count(member)})
