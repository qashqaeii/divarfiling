"""ویدیوی معرفی فایلینگ دیوار — بلوک خانه میزکار."""
from __future__ import annotations

from django.urls import reverse

from workspace.academy.models import AcademyVideo, UserVideoProgress

HOME_INTRO_VIDEO_SLUG = 'academy-what-is-divar-filing'


def get_home_intro_video_context(user) -> dict | None:
    video = (
        AcademyVideo.objects.filter(slug=HOME_INTRO_VIDEO_SLUG, is_active=True)
        .select_related('path')
        .first()
    )
    if not video:
        return None
    player = video.to_player_context()
    if not player.get('available'):
        return None
    progress = UserVideoProgress.objects.filter(user=user, video=video).first()
    return {
        'video': video,
        'player': player,
        'video_url': reverse('workspace:academy_video', kwargs={'slug': video.slug}),
        'academy_url': reverse('workspace:academy_home'),
        'completed': bool(progress and progress.completed),
    }
