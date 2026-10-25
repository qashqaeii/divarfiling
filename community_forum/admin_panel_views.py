"""پنل مدیریت تالار در admin-panel."""
import json
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from accounts.admin_views import StaffRequiredMixin
from community_forum.models import ForumBan, ForumMessage, ForumReport
from community_forum.services.access import user_can_moderate_forum
from community_forum.services.messages import delete_message
from community_forum.services.members import get_or_create_member
from community_forum.services.moderation import log_audit
from community_forum.services.retention import visible_messages_qs


class ForumModerateRequiredMixin(StaffRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not user_can_moderate_forum(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AdminForumPanelView(ForumModerateRequiredMixin, TemplateView):
    template_name = 'accounts/admin_forum.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        ctx['forum_stats'] = {
            'messages_today': visible_messages_qs().filter(created_at__date=today).count(),
            'messages_7d': visible_messages_qs().filter(
                created_at__gte=timezone.now() - timedelta(days=7),
            ).count(),
            'pending_reports': ForumReport.objects.filter(status=ForumReport.Status.PENDING).count(),
            'active_bans': ForumBan.objects.filter(revoked_at__isnull=True).count(),
        }
        return ctx


class AdminForumReportsJsonView(ForumModerateRequiredMixin, View):
    def get(self, request):
        rows = (
            ForumReport.objects.filter(status=ForumReport.Status.PENDING)
            .select_related('message', 'reporter')
            .order_by('-created_at')[:50]
        )
        data = [
            {
                'id': r.pk,
                'reason': r.reason,
                'message_id': r.message_id,
                'created_at': r.created_at.isoformat(),
            }
            for r in rows
        ]
        return JsonResponse({'ok': True, 'reports': data})


class AdminForumBanView(ForumModerateRequiredMixin, View):
    def post(self, request):
        payload = json.loads(request.body.decode('utf-8') or '{}')
        member_id = int(payload.get('member_id', 0))
        hours = int(payload.get('hours', 24))
        from community_forum.models import ForumMember

        member = ForumMember.objects.filter(pk=member_id).first()
        if not member:
            return JsonResponse({'ok': False, 'error': 'عضو یافت نشد'}, status=404)
        ban = ForumBan.objects.create(
            member=member,
            reason=(payload.get('reason') or '')[:500],
            expires_at=timezone.now() + timedelta(hours=hours),
            created_by=request.user,
        )
        log_audit('ban_member', request.user, member_id=member.pk, meta={'ban_id': ban.pk})
        return JsonResponse({'ok': True})


class AdminForumDeleteMessageView(ForumModerateRequiredMixin, View):
    def post(self, request, message_id):
        mod_member = get_or_create_member(request.user)
        try:
            delete_message(mod_member, message_id, moderator_user=request.user)
        except Exception as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})
