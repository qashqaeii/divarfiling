"""سرویس پیشرفت، ماموریت، نشان‌ها و TTLV."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from workspace.academy.models import (
    AcademyBadge,
    AcademyEvent,
    AcademyMission,
    AcademyVideo,
    UserAcademyBadge,
    UserAcademySettings,
    UserMissionProgress,
    UserVideoProgress,
)
from workspace.models import CRMProperty, Customer, ListingMeta, Reminder


def get_or_create_academy_settings(user) -> UserAcademySettings:
    obj, _ = UserAcademySettings.objects.get_or_create(user=user)
    return obj


def get_mission() -> AcademyMission | None:
    return AcademyMission.objects.filter(slug='day-one', is_active=True).first()


def get_mission_progress(user) -> UserMissionProgress | None:
    mission = get_mission()
    if not mission:
        return None
    progress, _ = UserMissionProgress.objects.get_or_create(
        user=user,
        mission=mission,
        defaults={'step_states': {}},
    )
    return progress


def _step_state(progress: UserMissionProgress, step: int) -> str:
    return (progress.step_states or {}).get(str(step), 'pending')


def _set_step_state(progress: UserMissionProgress, step: int, state: str) -> None:
    states = dict(progress.step_states or {})
    states[str(step)] = state
    progress.step_states = states


def check_action_complete(user, key: str) -> bool:
    if key == 'first_file_found':
        if ListingMeta.objects.filter(user=user, is_favorite=True).exists():
            return True
        if CRMProperty.objects.filter(user=user).exists():
            return True
        from workspace.models import CustomerListing
        return CustomerListing.objects.filter(customer__user=user).exists()
    if key == 'first_contact_created':
        return Customer.objects.filter(user=user).exists()
    if key == 'first_followup_set':
        has_reminder = Reminder.objects.filter(user=user).exists()
        has_followup = Customer.objects.filter(user=user, next_follow_up__isnull=False).exists()
        has_prop_followup = CRMProperty.objects.filter(user=user, next_follow_up__isnull=False).exists()
        return has_reminder or has_followup or has_prop_followup
    return False


def record_ttlv(user) -> None:
    settings_obj = get_or_create_academy_settings(user)
    if settings_obj.first_file_at:
        return
    if not check_action_complete(user, 'first_file_found'):
        return
    now = timezone.now()
    settings_obj.first_file_at = now
    joined = user.date_joined
    if joined:
        settings_obj.ttlv_seconds = max(0, int((now - joined).total_seconds()))
    settings_obj.save(update_fields=['first_file_at', 'ttlv_seconds'])
    AcademyEvent.objects.create(
        user=user,
        event_type='academy_ttlv_reached',
        metadata={'ttlv_seconds': settings_obj.ttlv_seconds},
    )


def sync_mission_auto_confirm(user) -> UserMissionProgress | None:
    progress = get_mission_progress(user)
    if not progress or progress.completed:
        return progress
    mission = progress.mission
    steps = list(mission.steps.select_related('video').order_by('order'))
    changed = False
    for step in steps:
        order = step.order
        state = _step_state(progress, order)
        video_done = state in ('video_done', 'done')
        action_done = state == 'done'
        if step.confirm_type in ('video', 'both') and not video_done:
            vp = UserVideoProgress.objects.filter(user=user, video=step.video, completed=True).first()
            if vp:
                _set_step_state(progress, order, 'video_done' if step.confirm_type == 'video' else 'video_done')
                changed = True
                video_done = True
        if step.confirm_type in ('action', 'both') and step.auto_confirm_key:
            if check_action_complete(user, step.auto_confirm_key):
                if step.confirm_type == 'both' and _step_state(progress, order) == 'video_done':
                    _set_step_state(progress, order, 'done')
                    changed = True
                elif step.confirm_type == 'action':
                    _set_step_state(progress, order, 'done')
                    changed = True
                if step.auto_confirm_key == 'first_file_found':
                    record_ttlv(user)
    if changed:
        progress.save(update_fields=['step_states'])
    _refresh_mission_current_step(progress, steps)
    if not progress.completed and all(_step_state(progress, s.order) == 'done' for s in steps):
        complete_mission(user, progress)
    return progress


def _refresh_mission_current_step(progress: UserMissionProgress, steps) -> None:
    for step in steps:
        if _step_state(progress, step.order) != 'done':
            if progress.current_step != step.order:
                progress.current_step = step.order
                progress.save(update_fields=['current_step'])
            return


def complete_mission_step_video(user, step_order: int) -> None:
    progress = get_mission_progress(user)
    if not progress:
        return
    step = progress.mission.steps.filter(order=step_order).first()
    if not step:
        return
    state = _step_state(progress, step_order)
    if step.confirm_type == 'video':
        _set_step_state(progress, step_order, 'done')
    elif state != 'done':
        _set_step_state(progress, step_order, 'video_done')
    progress.save(update_fields=['step_states'])
    AcademyEvent.objects.create(
        user=user,
        event_type='academy_mission_step_video_done',
        video=step.video,
        metadata={'step': step_order},
    )
    sync_mission_auto_confirm(user)


def complete_mission_step_manual(user, step_order: int) -> bool:
    progress = get_mission_progress(user)
    if not progress:
        return False
    step = progress.mission.steps.filter(order=step_order).first()
    if not step:
        return False
    if step.confirm_type == 'both' and _step_state(progress, step_order) != 'video_done':
        return False
    _set_step_state(progress, step_order, 'done')
    progress.save(update_fields=['step_states'])
    AcademyEvent.objects.create(
        user=user,
        event_type='academy_mission_step_action_done',
        video=step.video,
        metadata={'step': step_order, 'manual': True},
    )
    sync_mission_auto_confirm(user)
    return True


@transaction.atomic
def complete_mission(user, progress: UserMissionProgress) -> None:
    if progress.completed:
        return
    progress.completed = True
    progress.completed_at = timezone.now()
    progress.save(update_fields=['completed', 'completed_at'])
    badge = AcademyBadge.objects.filter(slug=progress.mission.badge_slug).first()
    if badge:
        _, created = UserAcademyBadge.objects.get_or_create(user=user, badge=badge)
        if created:
            AcademyEvent.objects.create(
                user=user,
                event_type='academy_badge_earned',
                metadata={'badge_slug': badge.slug},
            )
    settings_obj = get_or_create_academy_settings(user)
    settings_obj.learning_level = max(settings_obj.learning_level, 2)
    settings_obj.save(update_fields=['learning_level'])
    duration = None
    if settings_obj.mission_started_at:
        duration = int((progress.completed_at - settings_obj.mission_started_at).total_seconds())
    AcademyEvent.objects.create(
        user=user,
        event_type='academy_mission_completed',
        metadata={'duration_seconds': duration},
    )


def update_video_progress(user, video: AcademyVideo, watched_seconds: int, completed: bool = False) -> UserVideoProgress:
    progress, _ = UserVideoProgress.objects.get_or_create(user=user, video=video)
    progress.watched_seconds = max(progress.watched_seconds, watched_seconds)
    progress.last_position = watched_seconds
    threshold = max(int(video.duration_seconds * 0.9), video.duration_seconds - 10)
    mark_complete = completed or watched_seconds >= threshold
    if mark_complete and not progress.completed:
        progress.completed = True
        progress.completed_at = timezone.now()
        AcademyEvent.objects.create(
            user=user,
            event_type='academy_video_completed',
            video=video,
            metadata={'duration_seconds': video.duration_seconds},
        )
        if video.mission_step:
            complete_mission_step_video(user, video.mission_step)
        _check_badges(user)
        _check_path_completion(user, video)
    progress.save()
    return progress


def _check_path_completion(user, video: AcademyVideo) -> None:
    path = video.path
    total = path.videos.filter(is_active=True).count()
    done = UserVideoProgress.objects.filter(
        user=user, video__path=path, completed=True,
    ).count()
    if done == 1:
        AcademyEvent.objects.create(
            user=user,
            event_type='academy_path_started',
            metadata={'path_slug': path.slug},
        )
    if total and done >= total:
        AcademyEvent.objects.create(
            user=user,
            event_type='academy_path_completed',
            metadata={'path_slug': path.slug},
        )


def _check_badges(user) -> None:
    settings_obj = get_or_create_academy_settings(user)
    mission_done = UserMissionProgress.objects.filter(user=user, completed=True).exists()
    if mission_done:
        settings_obj.learning_level = max(settings_obj.learning_level, 2)
    pro = (
        CRMProperty.objects.filter(user=user).exists()
        and Customer.objects.filter(user=user).exists()
        and check_action_complete(user, 'first_followup_set')
    )
    if pro:
        badge = AcademyBadge.objects.filter(slug='pro-advisor').first()
        if badge:
            UserAcademyBadge.objects.get_or_create(user=user, badge=badge)
            settings_obj.learning_level = max(settings_obj.learning_level, 3)
    ai_slug = 'data-ai-assistant'
    market_slug = 'data-market-analysis'
    tools_used = not settings_obj.tools_first_visit
    ai_done = UserVideoProgress.objects.filter(user=user, video__slug=ai_slug, completed=True).exists()
    market_done = UserVideoProgress.objects.filter(user=user, video__slug=market_slug, completed=True).exists()
    if ai_done and market_done and tools_used:
        badge = AcademyBadge.objects.filter(slug='data-advisor').first()
        if badge:
            UserAcademyBadge.objects.get_or_create(user=user, badge=badge)
            settings_obj.learning_level = max(settings_obj.learning_level, 4)
    all_mvp = _mvp_videos_complete(user)
    if all_mvp:
        settings_obj.learning_level = 5
    settings_obj.save(update_fields=['learning_level', 'tools_first_visit'])


def _mvp_videos_complete(user) -> bool:
    slugs = list(
        AcademyVideo.objects.filter(is_active=True, path__phase__in=['launch', 'mvp'])
        .exclude(path__slug='agency')
        .values_list('slug', flat=True)
    )
    if not slugs:
        return False
    done = UserVideoProgress.objects.filter(user=user, video__slug__in=slugs, completed=True).count()
    return done >= len(slugs)


def get_continue_watching(user):
    return (
        UserVideoProgress.objects.filter(user=user, completed=False, last_position__gt=0)
        .select_related('video', 'video__path')
        .order_by('-updated_at')
        .first()
    )


def compute_progress_summary(user) -> dict:
    sync_mission_auto_confirm(user)
    settings_obj = get_or_create_academy_settings(user)
    mission_progress = get_mission_progress(user)
    badges = list(
        UserAcademyBadge.objects.filter(user=user)
        .select_related('badge')
        .order_by('badge__level')
    )
    all_badges = list(AcademyBadge.objects.all().order_by('level'))
    earned_slugs = {b.badge.slug for b in badges}
    level = settings_obj.learning_level
    level_labels = {
        1: 'مشاور تازه‌کار',
        2: 'مشاور آماده فایلینگ',
        3: 'مشاور حرفه‌ای',
        4: 'مشاور داده‌محور',
        5: 'مشاور سیستماتیک',
    }
    remaining = AcademyVideo.objects.filter(is_active=True).exclude(
        user_progress__user=user,
        user_progress__completed=True,
    ).count()
    avg_duration = 300
    eta_minutes = max(1, (remaining * avg_duration) // 60)
    continue_item = get_continue_watching(user)
    mission_data = None
    if mission_progress and not mission_progress.completed:
        total_steps = mission_progress.mission.steps.count()
        done_steps = sum(
            1 for k, v in (mission_progress.step_states or {}).items() if v == 'done'
        )
        mission_data = {
            'current_step': mission_progress.current_step,
            'total_steps': total_steps,
            'done_steps': done_steps,
            'percent': int(done_steps / total_steps * 100) if total_steps else 0,
        }
    return {
        'level': level,
        'level_label': level_labels.get(level, 'مشاور تازه‌کار'),
        'max_level': 5,
        'eta_minutes': eta_minutes,
        'badges_earned': badges,
        'badges_all': all_badges,
        'earned_slugs': earned_slugs,
        'mission': mission_data,
        'mission_completed': bool(mission_progress and mission_progress.completed),
        'continue_watching': continue_item,
        'ttlv_seconds': settings_obj.ttlv_seconds,
    }


def track_event(user, event_type: str, video=None, metadata=None) -> None:
    AcademyEvent.objects.create(
        user=user,
        event_type=event_type,
        video=video,
        metadata=metadata or {},
    )


def start_mission_if_needed(user) -> None:
    settings_obj = get_or_create_academy_settings(user)
    if not settings_obj.mission_started_at:
        settings_obj.mission_started_at = timezone.now()
        settings_obj.save(update_fields=['mission_started_at'])
        track_event(user, 'academy_mission_started')
