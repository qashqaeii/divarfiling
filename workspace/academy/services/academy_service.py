"""سرویس‌های صفحه آکادمی."""
from __future__ import annotations

from workspace.academy.curriculum import (
    active_paths_qs,
    adjacent_videos,
    curriculum_stats,
    global_index_for,
    mark_playlist_active,
    user_curriculum_summary,
    workspace_playlist_sections,
)
from workspace.academy.models import AcademyVideo, LearningPath, UserVideoProgress
from workspace.academy.search import academy_search_entries
from workspace.academy.services.progress_service import compute_progress_summary


def user_can_access_path(user, path: LearningPath) -> bool:
    if not path.is_active:
        return False
    return True


def get_home_context(user) -> dict:
    summary = compute_progress_summary(user)
    stats = curriculum_stats()
    paths = []
    for path in active_paths_qs().prefetch_related('videos'):
        videos = path.videos.filter(is_active=True)
        total = videos.count()
        done = UserVideoProgress.objects.filter(
            user=user, video__in=videos, completed=True,
        ).count()
        total_seconds = sum(v.duration_seconds for v in videos)
        paths.append({
            'path': path,
            'locked': False,
            'video_count': total,
            'done_count': done,
            'percent': int(done / total * 100) if total else 0,
            'total_minutes': max(1, total_seconds // 60),
            'views_count': sum(int(v.views_count or 0) for v in videos),
        })
    curriculum = user_curriculum_summary(user)
    return {
        'summary': summary,
        'curriculum': curriculum,
        'stats': stats,
        'paths': paths,
        'academy_views_total': sum(p['views_count'] for p in paths),
        'academy_search_entries': academy_search_entries(workspace=True),
    }


def get_path_context(user, path: LearningPath, active_slug: str | None = None) -> dict:
    videos = list(path.videos.filter(is_active=True).order_by('order'))
    progress_map = {
        p.video_id: p
        for p in UserVideoProgress.objects.filter(user=user, video__in=videos)
    }
    active = None
    if active_slug:
        active = next((v for v in videos if v.slug == active_slug), None)
    if not active:
        for v in videos:
            prog = progress_map.get(v.id)
            if not prog or not prog.completed:
                active = v
                break
    if not active and videos:
        active = videos[0]
    items = []
    for v in videos:
        prog = progress_map.get(v.id)
        items.append({
            'video': v,
            'progress': prog,
            'completed': bool(prog and prog.completed),
            'active': active and v.id == active.id,
            'global_index': global_index_for(v),
        })
    playlist = workspace_playlist_sections(user)
    mark_playlist_active(playlist, active.slug if active else active_slug)
    return {
        'path': path,
        'items': items,
        'active_video': active,
        'active_player': active.to_player_context() if active else None,
        'playlist_sections': playlist,
    }


def get_video_context(user, video: AcademyVideo, *, public_ok: bool = False) -> dict | None:
    if not public_ok and not user.is_authenticated:
        return None
    if not video.is_public and not user.is_authenticated:
        return None
    path_ctx = get_path_context(user, video.path, active_slug=video.slug) if user.is_authenticated else None
    prev_video, next_video = adjacent_videos(video)
    playlist = workspace_playlist_sections(user) if user.is_authenticated else []
    mark_playlist_active(playlist, video.slug)
    return {
        'video': video,
        'player': video.to_player_context(),
        'path_ctx': path_ctx,
        'playlist_sections': playlist,
        'global_index': global_index_for(video),
        'prev_video': prev_video,
        'next_video': next_video,
    }
