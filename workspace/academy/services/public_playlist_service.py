"""سرویس پلی‌لیست عمومی ویدیوهای آکادمی."""
from __future__ import annotations

from django.urls import reverse

from workspace.academy.models import AcademyVideo, LearningPath


def duration_iso8601(seconds: int) -> str:
    if seconds <= 0:
        return 'PT0S'
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    parts = ['PT']
    if hours:
        parts.append(f'{hours}H')
    if minutes:
        parts.append(f'{minutes}M')
    if secs or parts == ['PT']:
        parts.append(f'{secs}S')
    return ''.join(parts)


def _poster_absolute(player: dict, site_url: str) -> str:
    poster = player.get('poster') or ''
    if not poster:
        return f'{site_url}/static/logo.png'
    if poster.startswith(('http://', 'https://')):
        return poster
    if player.get('poster_kind') == 'static':
        return f'{site_url}/static/{poster.lstrip("/")}'
    return f'{site_url}{poster}' if poster.startswith('/') else f'{site_url}/{poster}'


def get_public_playlist_sections() -> list[dict]:
    sections = []
    global_index = 0
    paths = LearningPath.objects.filter(is_public=True, is_active=True).order_by('order', 'id')
    for path in paths:
        videos = list(path.videos.filter(is_public=True, is_active=True).order_by('order', 'id'))
        if not videos:
            continue
        items = []
        for index, video in enumerate(videos, start=1):
            global_index += 1
            player = video.to_player_context()
            items.append({
                'video': video,
                'player': player,
                'index': index,
                'global_index': global_index,
                'url': reverse('public_academy_video', kwargs={'slug': video.slug}),
            })
        total_seconds = sum(v.duration_seconds for v in videos)
        sections.append({
            'path': path,
            'videos': items,
            'video_count': len(items),
            'total_minutes': max(1, total_seconds // 60),
        })
    return sections


def flatten_public_videos(sections: list[dict]) -> list[dict]:
    flat = []
    global_index = 0
    for section in sections:
        for item in section['videos']:
            global_index += 1
            flat.append({
                **item,
                'path': section['path'],
                'global_index': global_index,
            })
    return flat


def resolve_public_video(sections: list[dict], slug: str | None = None) -> tuple[dict | None, list[dict]]:
    flat = flatten_public_videos(sections)
    if not flat:
        return None, flat
    if slug:
        for item in flat:
            if item['video'].slug == slug:
                return item, flat
        return None, flat
    return flat[0], flat


def playlist_stats(sections: list[dict]) -> dict:
    flat = flatten_public_videos(sections)
    total_seconds = sum(item['video'].duration_seconds for item in flat)
    return {
        'video_count': len(flat),
        'section_count': len(sections),
        'total_minutes': max(1, total_seconds // 60),
        'paths': [s['path'].title for s in sections],
    }


def video_item_seo(item: dict, *, site_url: str) -> dict:
    video = item['video']
    player = item['player']
    return {
        'poster_url': _poster_absolute(player, site_url),
        'duration_iso': duration_iso8601(video.duration_seconds),
        'embed_url': player.get('src') or '',
    }
