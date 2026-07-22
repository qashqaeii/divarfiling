"""سرویس پلی‌لیست عمومی ویدیوهای آکادمی."""
from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.urls import reverse

from workspace.academy.models import AcademyVideo, LearningPath

# تاریخ پایدار برای ویدیوهایی که فایل/تاریخ محلی ندارند (الزام Google Video rich results)
_FALLBACK_UPLOAD_DATE = datetime(2026, 4, 23, 8, 0, 0, tzinfo=dt_timezone.utc)


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


def video_upload_date_iso(video: AcademyVideo) -> str:
    """ISO-8601 uploadDate for Schema.org VideoObject (Google rich results)."""
    mtimes: list[float] = []
    if not video.video_url:
        local = Path(settings.MEDIA_ROOT) / str(video.file_path).strip('/') / video.file_name
        if local.is_file():
            mtimes.append(local.stat().st_mtime)
    if video.poster_image:
        try:
            mtimes.append(Path(video.poster_image.path).stat().st_mtime)
        except (ValueError, OSError):
            pass
    if mtimes:
        dt = datetime.fromtimestamp(min(mtimes), tz=dt_timezone.utc)
    else:
        dt = _FALLBACK_UPLOAD_DATE
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def _poster_absolute(player: dict, site_url: str) -> str:
    poster = player.get('poster') or ''
    if not poster:
        return f'{site_url}/static/logo.png'
    if poster.startswith(('http://', 'https://')):
        return poster
    if player.get('poster_kind') == 'static':
        return f'{site_url}/static/{poster.lstrip("/")}'
    return f'{site_url}{poster}' if poster.startswith('/') else f'{site_url}/{poster}'


def public_playlist_videos():
    """ویدیوهایی که تیک «عمومی» دارند — مسیر والد لازم نیست عمومی باشد."""
    return AcademyVideo.objects.filter(
        is_public=True,
        is_active=True,
        path__is_active=True,
        path__requires_role='',
    ).order_by('path__order', 'order', 'id')


def get_public_playlist_sections() -> list[dict]:
    sections = []
    global_index = 0
    path_ids = public_playlist_videos().values_list('path_id', flat=True).distinct()
    paths = LearningPath.objects.filter(id__in=path_ids, is_active=True).order_by('order', 'id')
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
    views_total = sum(int(getattr(item['video'], 'views_count', 0) or 0) for item in flat)
    return {
        'video_count': len(flat),
        'section_count': len(sections),
        'total_minutes': max(1, total_seconds // 60),
        'views_total': views_total,
        'paths': [s['path'].title for s in sections],
    }


def video_item_seo(item: dict, *, site_url: str) -> dict:
    video = item['video']
    player = item['player']
    return {
        'poster_url': _poster_absolute(player, site_url),
        'duration_iso': duration_iso8601(video.duration_seconds),
        'embed_url': player.get('src') or '',
        'upload_date': video_upload_date_iso(video),
    }
