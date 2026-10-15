"""ویدیوی دمو استخراج — صفحه ارتقا برای کاربران بدون لایسنس."""
from __future__ import annotations

from django.urls import reverse

from workspace.academy.models import AcademyVideo

EXTRACTION_DEMO_VIDEO_SLUG = 'academy-extract-divar-listings'

# قابلیت‌هایی که کاربر با قفل فایلینگ/استخراج به این صفحه می‌رسد
EXTRACTION_DEMO_FEATURE_KEYS = frozenset({
    'datasets',
    'upload',
    'analyze',
    'map',
    'compare',
    'tools',
    'crm_divar',
})


def _enrich_player(video: AcademyVideo, player: dict) -> dict:
    poster, poster_kind = video.get_poster_context()
    enriched = dict(player)
    if poster:
        enriched['poster'] = poster
        enriched['poster_kind'] = poster_kind
    enriched.setdefault('title', video.title)
    enriched.setdefault('subtitle', video.subtitle or video.description)
    enriched.setdefault('duration', video.duration_display)
    return enriched


def should_show_extraction_demo(feature_key: str) -> bool:
    key = (feature_key or '').strip()
    if not key:
        return True
    return key in EXTRACTION_DEMO_FEATURE_KEYS


def get_upgrade_extraction_demo(user, feature_key: str) -> dict | None:
    """بلوک دمو استخراج برای صفحه upgrade — None اگر نباید نمایش داده شود."""
    if not should_show_extraction_demo(feature_key):
        return None

    video = (
        AcademyVideo.objects.filter(slug=EXTRACTION_DEMO_VIDEO_SLUG, is_active=True)
        .select_related('path')
        .first()
    )
    if not video:
        return None

    player = _enrich_player(video, video.to_player_context())
    can_embed = bool(player.get('available') and player.get('src'))

    return {
        'video': video,
        'player': player,
        'can_embed': can_embed,
        'kicker': 'قبل از خرید، ببینید چطور کار می‌کند',
        'headline': video.title,
        'lead': (
            'از انتخاب فیلتر در دیوار تا ورود آگهی‌ها به فایلینگ — '
            'همین مسیر را بعد از فعال‌سازی لایسنس در میزکار ادامه می‌دهید.'
        ),
        'academy_url': reverse('workspace:academy_video', kwargs={'slug': video.slug}),
        'playlist_url': reverse('workspace:academy_home'),
    }
