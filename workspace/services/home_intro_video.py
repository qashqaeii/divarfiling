"""ویدیوی معرفی فایلینگ دیوار — بلوک صفحه عمومی (خانه marketing)."""
from __future__ import annotations

from django.urls import reverse

from workspace.academy.models import AcademyVideo, UserVideoProgress

HOME_INTRO_VIDEO_SLUG = 'academy-what-is-divar-filing'


def _enrich_player(video: AcademyVideo, player: dict) -> dict:
    poster, poster_kind = video.get_poster_context()
    enriched = dict(player)
    if poster:
        enriched['poster'] = poster
        enriched['poster_kind'] = poster_kind
    if not enriched.get('duration'):
        enriched['duration'] = video.duration_display
    if not enriched.get('title'):
        enriched['title'] = video.title
    if not enriched.get('subtitle'):
        enriched['subtitle'] = video.subtitle
    return enriched


def get_intro_video_showcase(user=None, *, public_site: bool = False) -> dict | None:
    """داده بلوک معرفی — حتی اگر فایل MP4 روی سرور نباشد (پوستر + لینک آکادمی)."""
    video = (
        AcademyVideo.objects.filter(slug=HOME_INTRO_VIDEO_SLUG, is_active=True)
        .select_related('path')
        .first()
    )
    if not video:
        return None

    player = _enrich_player(video, video.to_player_context())
    can_embed = bool(player.get('available') and player.get('src'))

    if public_site:
        video_url = reverse('public_academy_video', kwargs={'slug': video.slug})
        academy_url = reverse('public_academy_playlist')
    else:
        video_url = reverse('workspace:academy_video', kwargs={'slug': video.slug})
        academy_url = reverse('workspace:academy_home')

    completed = False
    if user is not None and getattr(user, 'is_authenticated', False):
        progress = UserVideoProgress.objects.filter(user=user, video=video).first()
        completed = bool(progress and progress.completed)

    return {
        'video': video,
        'player': player,
        'video_url': video_url,
        'academy_url': academy_url,
        'completed': completed,
        'can_embed': can_embed,
    }

