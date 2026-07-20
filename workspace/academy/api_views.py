"""API آکادمی workspace."""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from workspace.academy.models import AcademyVideo
from workspace.academy.services.contextual_service import dismiss_contextual
from workspace.academy.services.progress_service import (
    complete_mission_step_manual,
    compute_progress_summary,
    get_mission,
    get_mission_progress,
    start_mission_if_needed,
    sync_mission_auto_confirm,
    track_event,
    update_video_progress,
)
from workspace.academy.services.academy_service import get_mission_context
from workspace.mixins import WorkspaceLoginMixin


class AcademyProgressAPIView(WorkspaceLoginMixin, View):
    def get(self, request):
        summary = compute_progress_summary(request.user)
        continue_item = summary.get('continue_watching')
        continue_data = None
        if continue_item:
            continue_data = {
                'slug': continue_item.video.slug,
                'title': continue_item.video.title,
                'percent': min(
                    100,
                    int(continue_item.last_position / max(continue_item.video.duration_seconds, 1) * 100),
                ),
                'url': continue_item.video.slug,
            }
        return JsonResponse({
            'ok': True,
            'level': summary['level'],
            'level_label': summary['level_label'],
            'max_level': summary['max_level'],
            'eta_minutes': summary['eta_minutes'],
            'mission': summary['mission'],
            'mission_completed': summary['mission_completed'],
            'earned_slugs': list(summary['earned_slugs']),
            'continue_watching': continue_data,
            'ttlv_seconds': summary['ttlv_seconds'],
        })


class AcademyMissionAPIView(WorkspaceLoginMixin, View):
    def get(self, request):
        start_mission_if_needed(request.user)
        sync_mission_auto_confirm(request.user)
        ctx = get_mission_context(request.user)
        if not ctx.get('mission'):
            return JsonResponse({'ok': False, 'error': 'ماموریت یافت نشد.'}, status=404)
        steps = []
        for item in ctx['steps']:
            step = item['step']
            steps.append({
                'order': step.order,
                'title': step.video.title,
                'state': item['state'],
                'is_current': item['is_current'],
                'is_done': item['is_done'],
                'action_url': step.action_url,
                'action_label': step.action_label,
                'video_slug': step.video.slug,
            })
        return JsonResponse({
            'ok': True,
            'completed': ctx['completed'],
            'current_step': ctx['current_step'],
            'steps': steps,
        })


class AcademyMissionStepCompleteAPIView(WorkspaceLoginMixin, View):
    def post(self, request, step_order: int):
        ok = complete_mission_step_manual(request.user, step_order)
        if not ok:
            return JsonResponse({
                'ok': False,
                'error': 'ابتدا ویدیو را تماشا کنید یا عمل را انجام دهید.',
            }, status=400)
        progress = get_mission_progress(request.user)
        return JsonResponse({
            'ok': True,
            'completed': bool(progress and progress.completed),
            'current_step': progress.current_step if progress else step_order,
        })


class AcademyVideoProgressAPIView(WorkspaceLoginMixin, View):
    def post(self, request, slug: str):
        video = get_object_or_404(AcademyVideo, slug=slug, is_active=True)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = request.POST
        watched = int(payload.get('watched_seconds', 0) or 0)
        completed = bool(payload.get('completed'))
        progress = update_video_progress(request.user, video, watched, completed=completed)
        return JsonResponse({
            'ok': True,
            'completed': progress.completed,
            'watched_seconds': progress.watched_seconds,
        })


class AcademyContextualDismissAPIView(WorkspaceLoginMixin, View):
    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = request.POST
        key = (payload.get('key') or '').strip()
        if not key:
            return JsonResponse({'ok': False, 'error': 'key required'}, status=400)
        dismiss_contextual(request.user, key)
        track_event(request.user, 'academy_contextual_dismissed', metadata={'page_key': key})
        return JsonResponse({'ok': True})


class AcademyContextualAPIView(WorkspaceLoginMixin, View):
    def get(self, request):
        key = request.GET.get('key', '').strip()
        if not key:
            return JsonResponse({'ok': False, 'error': 'key required'}, status=400)
        from workspace.academy.services.contextual_service import get_contextual_banner
        banner = get_contextual_banner(request.user, key)
        if not banner:
            return JsonResponse({'ok': True, 'banner': None})
        return JsonResponse({
            'ok': True,
            'banner': {
                'key': banner['key'],
                'title': banner['title'],
                'message': banner['message'],
                'video_slug': banner['video'].slug,
                'video_url': banner['video_url'],
                'duration_display': banner['duration_display'],
            },
        })


class AcademyEventsAPIView(WorkspaceLoginMixin, View):
    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            payload = request.POST
        events = payload.get('events') or [payload]
        for ev in events:
            event_type = (ev.get('event_type') or ev.get('type') or '').strip()
            if not event_type:
                continue
            video = None
            slug = ev.get('video_slug') or ev.get('slug')
            if slug:
                video = AcademyVideo.objects.filter(slug=slug).first()
            track_event(request.user, event_type, video=video, metadata=ev.get('metadata') or {})
        return JsonResponse({'ok': True})


class AcademyVideoMetaAPIView(View):
    def get(self, request, slug: str):
        video = get_object_or_404(AcademyVideo, slug=slug, is_active=True)
        if not video.is_public and not request.user.is_authenticated:
            return JsonResponse({'ok': False}, status=403)
        return JsonResponse({
            'ok': True,
            'video': {
                'slug': video.slug,
                'title': video.title,
                'subtitle': video.subtitle,
                'duration_seconds': video.duration_seconds,
                'stream_url': video.get_stream_url(),
                'action_url': video.action_url,
                'action_label': video.action_label,
            },
        })
