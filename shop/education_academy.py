"""ویدیوی هیرو و آمار آکادمی برای صفحه آموزش عمومی."""
from __future__ import annotations

from django.urls import reverse

# اولویت ویدیو برای هیرو — کوتاه‌ترین معرفی عمومی اول
HERO_VIDEO_SLUG_PREFERENCE = (
    'intro-what-is-divar-filing',
    'quick-start-first-value',
    'intro-consultant-pain-points',
    'intro-before-after-day',
)


def get_education_academy_hero() -> dict:
    from workspace.academy.services.public_playlist_service import (
        flatten_public_videos,
        get_public_playlist_sections,
        playlist_stats,
    )

    sections = get_public_playlist_sections()
    stats = playlist_stats(sections)
    flat = flatten_public_videos(sections)
    by_slug = {item['video'].slug: item for item in flat}

    chosen = None
    for slug in HERO_VIDEO_SLUG_PREFERENCE:
        item = by_slug.get(slug)
        if item and item['player'].get('available'):
            chosen = item
            break

    if not chosen:
        for item in flat:
            if item['player'].get('available'):
                chosen = item
                break

    if not chosen and flat:
        chosen = flat[0]

    playlist_url = reverse('public_academy_playlist')
    empty_player = {
        'available': False,
        'mode': 'none',
        'src': '',
        'title': 'آکادمی ویدیویی فایلینگ دیوار',
        'subtitle': 'آموزش رایگان مشاوران املاک',
        'duration': '',
        'poster': '',
        'poster_kind': '',
        'slug': '',
    }

    if not chosen:
        return {
            'player': empty_player,
            'stats': stats,
            'video': None,
            'video_url': playlist_url,
            'playlist_url': playlist_url,
            'has_videos': False,
        }

    return {
        'player': chosen['player'],
        'stats': stats,
        'video': chosen['video'],
        'video_url': chosen['url'],
        'playlist_url': playlist_url,
        'has_videos': True,
    }
