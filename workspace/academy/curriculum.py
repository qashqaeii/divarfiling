"""Curriculum فعال آکادمی — ۲ مسیر، ۸ ویدیو."""
from __future__ import annotations

from django.conf import settings
from django.db.models import Prefetch
from django.urls import reverse

from workspace.academy.models import AcademyVideo, LearningPath, UserVideoProgress

ACTIVE_PATH_SLUGS = ('getting-started', 'extracting-and-managing-files')


def active_paths_qs():
    return LearningPath.objects.filter(
        slug__in=ACTIVE_PATH_SLUGS,
        is_active=True,
    ).order_by('order', 'id')


def active_videos_qs():
    return AcademyVideo.objects.filter(
        path__slug__in=ACTIVE_PATH_SLUGS,
        path__is_active=True,
        is_active=True,
    ).select_related('path').order_by('path__order', 'order', 'id')


def ordered_videos() -> list[AcademyVideo]:
    return list(active_videos_qs())


def global_index_for(video: AcademyVideo) -> int:
    for i, v in enumerate(ordered_videos(), start=1):
        if v.id == video.id:
            return i
    return 0


def adjacent_videos(video: AcademyVideo) -> tuple[AcademyVideo | None, AcademyVideo | None]:
    items = ordered_videos()
    for i, v in enumerate(items):
        if v.id == video.id:
            prev_v = items[i - 1] if i > 0 else None
            next_v = items[i + 1] if i + 1 < len(items) else None
            return prev_v, next_v
    return None, None


def curriculum_stats() -> dict:
    videos = ordered_videos()
    total_seconds = sum(v.duration_seconds for v in videos)
    return {
        'video_count': len(videos),
        'path_count': active_paths_qs().count(),
        'total_seconds': total_seconds,
        'total_minutes': max(1, total_seconds // 60),
    }


def user_progress_map(user) -> dict[int, UserVideoProgress]:
    if not user or not user.is_authenticated:
        return {}
    vids = [v.id for v in ordered_videos()]
    return {
        p.video_id: p
        for p in UserVideoProgress.objects.filter(user=user, video_id__in=vids)
    }


def user_curriculum_summary(user) -> dict:
    videos = ordered_videos()
    pmap = user_progress_map(user)
    done = sum(1 for v in videos if pmap.get(v.id) and pmap[v.id].completed)
    total = len(videos) or 1
    stats = curriculum_stats()
    continue_item = None
    if user and user.is_authenticated:
        from workspace.academy.services.progress_service import get_continue_watching
        continue_item = get_continue_watching(user)
    first_incomplete = None
    for v in videos:
        prog = pmap.get(v.id)
        if not prog or not prog.completed:
            first_incomplete = v
            break
    return {
        'completed_count': done,
        'total_count': len(videos),
        'percent': int(done / total * 100) if videos else 0,
        'total_minutes': stats['total_minutes'],
        'path_count': stats['path_count'],
        'continue_watching': continue_item,
        'start_video': first_incomplete or (videos[0] if videos else None),
    }


def workspace_playlist_sections(user) -> list[dict]:
    pmap = user_progress_map(user)
    sections = []
    global_index = 0
    paths = active_paths_qs().prefetch_related(
        Prefetch('videos', queryset=AcademyVideo.objects.filter(is_active=True).order_by('order', 'id')),
    )
    for path in paths:
        items = []
        for video in path.videos.all():
            if not video.is_active:
                continue
            global_index += 1
            prog = pmap.get(video.id)
            items.append({
                'video': video,
                'global_index': global_index,
                'completed': bool(prog and prog.completed),
                'progress': prog,
            })
        if not items:
            continue
        total_seconds = sum(i['video'].duration_seconds for i in items)
        sections.append({
            'path': path,
            'items': items,
            'video_count': len(items),
            'total_minutes': max(1, total_seconds // 60),
        })
    return sections


def mark_playlist_active(sections: list[dict], active_slug: str | None) -> None:
    for section in sections:
        for item in section['items']:
            item['active'] = bool(active_slug and item['video'].slug == active_slug)


def video_workspace_url(slug: str) -> str:
    return reverse('workspace:academy_video', kwargs={'slug': slug})
