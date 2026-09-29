"""API آکادمی workspace."""
from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from workspace.academy.models import AcademyVideo
from workspace.academy.services.contextual_service import dismiss_contextual
from workspace.academy.services.progress_service import (
    compute_progress_summary,
    track_event,
    update_video_progress,
)
from workspace.academy.services.view_tracking import record_video_view
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
            'completed_count': summary['completed_count'],
            'total_count': summary['total_count'],
            'percent': summary['percent'],
            'eta_minutes': summary['eta_minutes'],
            'continue_watching': continue_data,
            'ttlv_seconds': summary['ttlv_seconds'],
        })


class AcademyMissionAPIView(WorkspaceLoginMixin, View):
    def get(self, request):
        return JsonResponse({'ok': True, 'mission': None, 'deprecated': True})


class AcademyMissionStepCompleteAPIView(WorkspaceLoginMixin, View):
    def post(self, request, step_order: int):
        return JsonResponse({'ok': False, 'deprecated': True}, status=410)


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
            meta = ev.get('metadata') or {}
            if not isinstance(meta, dict):
                meta = {}
            slug = ev.get('video_slug') or ev.get('slug') or meta.get('video_slug') or meta.get('slug')
            if slug:
                video = AcademyVideo.objects.filter(slug=slug, is_active=True).first()
            track_event(request.user, event_type, video=video, metadata=meta)
            if event_type == 'academy_video_started' and video:
                record_video_view(video)
        return JsonResponse({'ok': True})


class AcademyVideoViewAPIView(View):
    """ثبت بازدید پخش ویدیو — عمومی و میزکار (بدون نیاز به لاگین)."""

    def post(self, request, slug: str):
        video = get_object_or_404(AcademyVideo, slug=slug, is_active=True)
        if not video.is_public and not request.user.is_authenticated:
            return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
        views = record_video_view(video)
        user = request.user if request.user.is_authenticated else None
        track_event(
            user,
            'academy_video_started',
            video=video,
            metadata={'source': 'view_api', 'video_slug': slug},
        )
        return JsonResponse({'ok': True, 'views_count': views})


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
                'views_count': video.views_count,
            },
        })
