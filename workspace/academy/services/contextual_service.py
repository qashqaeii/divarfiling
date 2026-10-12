"""بنرهای Contextual Academy."""
from __future__ import annotations

from django.urls import reverse

from workspace.academy.models import AcademyVideo
from workspace.academy.seed_data import CONTEXTUAL_BANNERS
from workspace.academy.services.progress_service import get_or_create_academy_settings


def get_contextual_banner(user, key: str) -> dict | None:
    if not user or not user.is_authenticated:
        return None
    meta = CONTEXTUAL_BANNERS.get(key)
    if not meta:
        return None
    settings_obj = get_or_create_academy_settings(user)
    if key in (settings_obj.dismissed_contextual or []):
        return None
    video = AcademyVideo.objects.filter(slug=meta['video_slug'], is_active=True).first()
    if not video:
        return None
    poster, poster_kind = video.get_poster_context()
    return {
        'key': key,
        'title': meta['title'],
        'message': meta['message'],
        'video': video,
        'duration_display': video.duration_display,
        'video_url': reverse('workspace:academy_video', kwargs={'slug': video.slug}) + f'?context={key}',
        'poster': poster,
        'poster_kind': poster_kind,
    }


def dismiss_contextual(user, key: str) -> None:
    settings_obj = get_or_create_academy_settings(user)
    dismissed = list(settings_obj.dismissed_contextual or [])
    if key not in dismissed:
        dismissed.append(key)
        settings_obj.dismissed_contextual = dismissed
        settings_obj.save(update_fields=['dismissed_contextual'])


def mark_tools_visited(user) -> None:
    settings_obj = get_or_create_academy_settings(user)
    if settings_obj.tools_first_visit:
        settings_obj.tools_first_visit = False
        settings_obj.save(update_fields=['tools_first_visit'])
