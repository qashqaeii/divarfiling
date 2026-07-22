"""سرویس‌های صفحه آکادمی."""
from __future__ import annotations

from workspace.academy.models import AcademyVideo, CuratedPath, LearningPath, UserVideoProgress
from workspace.academy.services.progress_service import compute_progress_summary, get_mission_progress, sync_mission_auto_confirm
from workspace.services.crm_scope import can_manage_team


def user_can_access_path(user, path: LearningPath) -> bool:
    if not path.is_active:
        return False
    if path.requires_role == 'agency_manager':
        return can_manage_team(user)
    if path.phase == 'v2' and path.slug == 'agency':
        return can_manage_team(user)
    return True


def get_home_context(user) -> dict:
    sync_mission_auto_confirm(user)
    summary = compute_progress_summary(user)
    paths = []
    views_total = 0
    for path in LearningPath.objects.filter(is_active=True).prefetch_related('videos'):
        locked = not user_can_access_path(user, path)
        videos = path.videos.filter(is_active=True)
        total = videos.count()
        done = UserVideoProgress.objects.filter(
            user=user, video__in=videos, completed=True,
        ).count()
        path_views = sum(int(v.views_count or 0) for v in videos)
        views_total += path_views
        paths.append({
            'path': path,
            'locked': locked,
            'video_count': total,
            'done_count': done,
            'percent': int(done / total * 100) if total else 0,
            'views_count': path_views,
        })
    traditional = CuratedPath.objects.filter(slug='traditional-advisor').prefetch_related('videos').first()
    return {
        'summary': summary,
        'paths': paths,
        'traditional_path': traditional,
        'academy_views_total': views_total,
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
        })
    return {
        'path': path,
        'items': items,
        'active_video': active,
        'active_player': active.to_player_context() if active else None,
    }


def get_mission_context(user) -> dict:
    from workspace.academy.services.progress_service import get_mission, start_mission_if_needed

    start_mission_if_needed(user)
    sync_mission_auto_confirm(user)
    mission = get_mission()
    progress = get_mission_progress(user)
    if not mission or not progress:
        return {'mission': None}
    steps = []
    for step in mission.steps.select_related('video').order_by('order'):
        state = (progress.step_states or {}).get(str(step.order), 'pending')
        steps.append({
            'step': step,
            'video': step.video,
            'player': step.video.to_player_context(),
            'state': state,
            'is_current': progress.current_step == step.order and not progress.completed,
            'is_done': state == 'done',
        })
    return {
        'mission': mission,
        'progress': progress,
        'steps': steps,
        'current_step': progress.current_step,
        'completed': progress.completed,
        'show_badge_modal': progress.completed and user.academy_badges.filter(badge__slug=mission.badge_slug).exists(),
    }


def get_video_context(user, video: AcademyVideo, *, public_ok: bool = False) -> dict | None:
    if not public_ok and not user.is_authenticated:
        return None
    if not video.is_public and not user.is_authenticated:
        return None
    path_ctx = get_path_context(user, video.path, active_slug=video.slug) if user.is_authenticated else None
    return {
        'video': video,
        'player': video.to_player_context(),
        'path_ctx': path_ctx,
    }


def get_traditional_context(user) -> dict:
    path = CuratedPath.objects.filter(slug='traditional-advisor').prefetch_related('videos').first()
    if not path:
        return {'path': None, 'items': []}
    videos = list(
        AcademyVideo.objects.filter(curatedpathvideo__path=path)
        .order_by('curatedpathvideo__order')
    )
    progress_map = {
        p.video_id: p
        for p in UserVideoProgress.objects.filter(user=user, video__in=videos)
    }
    items = []
    total_duration = 0
    for v in videos:
        total_duration += v.duration_seconds
        prog = progress_map.get(v.id)
        items.append({'video': v, 'completed': bool(prog and prog.completed)})
    return {
        'path': path,
        'items': items,
        'total_minutes': max(1, total_duration // 60),
    }
