"""ویدیوهای آموزشی اپ اندروید — مسیر media و متادیتا."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings

# ترجیح: media/Video/android/ — جایگزین: media/Video/ (همان پوشه ویدیوهای ربات)
ANDROID_VIDEO_SUBDIR = 'Video/android'
ANDROID_VIDEO_FALLBACK_SUBDIR = 'Video'

ANDROID_VIDEOS = {
    'overview': {
        'file': 'ANDROID-OVERVIEW.mp4',
        'title': 'معرفی کامل اپ فایلینگ دیوار',
        'subtitle': 'از نصب تا اولین استخراج — نمای کلی همه بخش‌ها',
        'duration': '~۸ دقیقه',
        'poster': 'images/android/posters/android-video-overview.jpg',
    },
    'install': {
        'file': 'ANDROID-INSTALL.mp4',
        'title': 'نصب APK و عبور از Play Protect',
        'subtitle': 'دانلود، اجازه منابع ناشناخته و اولین باز کردن اپ',
        'duration': '~۴ دقیقه',
        'poster': 'images/android/posters/android-video-install.jpg',
    },
    'login': {
        'file': 'ANDROID-LOGIN.mp4',
        'title': 'ورود و فعال‌سازی خودکار لایسنس',
        'subtitle': 'با همان حساب میزکار — بدون کپی کلید',
        'duration': '~۳ دقیقه',
        'poster': 'images/android/posters/android-video-login.jpg',
    },
    'extract': {
        'file': 'ANDROID-EXTRACT.mp4',
        'title': 'استخراج آگهی از دیوار',
        'subtitle': 'انتخاب شهر، فیلترها و زمان‌بندی خودکار',
        'duration': '~۶ دقیقه',
        'poster': 'images/android/posters/android-video-extract.jpg',
    },
    'filing': {
        'file': 'ANDROID-FILING.mp4',
        'title': 'فایلینگ و مرور آگهی‌ها',
        'subtitle': 'لیست فایل‌ها، جزئیات آگهی و جستجو',
        'duration': '~۵ دقیقه',
        'poster': 'images/android/posters/android-video-filing.jpg',
    },
    'crm': {
        'file': 'ANDROID-CRM.mp4',
        'title': 'CRM موبایل — مشتری و معامله',
        'subtitle': 'ثبت مشتری، پیگیری معامله و فایل ملک',
        'duration': '~۷ دقیقه',
        'poster': 'images/android/posters/android-video-crm.jpg',
    },
    'notifications': {
        'file': 'ANDROID-NOTIFICATIONS.mp4',
        'title': 'اعلان‌ها و کارهای امروز',
        'subtitle': 'تطبیق ملک، یادآور تماس و برنامه روزانه',
        'duration': '~۴ دقیقه',
        'poster': 'images/android/posters/android-video-notifications.jpg',
    },
}


def _media_path(rel: str) -> Path:
    return Path(settings.MEDIA_ROOT) / rel


def _resolve_video_rel(filename: str) -> str | None:
    """مسیر نسبی فایل — اول android/ سپس Video/ مستقیم."""
    candidates = (
        f'{ANDROID_VIDEO_SUBDIR}/{filename}',
        f'{ANDROID_VIDEO_FALLBACK_SUBDIR}/{filename}',
    )
    for rel in candidates:
        if _media_path(rel).is_file():
            return rel
    return None


def android_video_exists(key: str) -> bool:
    meta = ANDROID_VIDEOS.get(key)
    if not meta:
        return False
    return _resolve_video_rel(meta['file']) is not None


def get_android_video_url(key: str) -> str:
    meta = ANDROID_VIDEOS.get(key)
    if not meta:
        return ''
    rel = _resolve_video_rel(meta['file'])
    if not rel:
        return ''
    return f"{settings.MEDIA_URL.rstrip('/')}/{rel}"


def _poster_exists(static_rel: str) -> bool:
    if not static_rel:
        return False
    from django.contrib.staticfiles.finders import find
    return find(static_rel) is not None


def get_android_video_context(key: str) -> dict:
    """Context برای قالب — available, poster_available, state, src, ..."""
    meta = ANDROID_VIDEOS.get(key)
    if not meta:
        return {
            'available': False,
            'poster_available': False,
            'state': 'soon',
            'mode': 'none',
            'src': '',
            'key': key,
        }
    url = get_android_video_url(key)
    poster = meta.get('poster', '')
    poster_available = _poster_exists(poster)
    ctx = {
        'key': key,
        'title': meta['title'],
        'subtitle': meta['subtitle'],
        'duration': meta['duration'],
        'poster': poster,
        'poster_available': poster_available,
        'filename': meta['file'],
    }
    if url:
        return {'available': True, 'state': 'video', 'mode': 'file', 'src': url, **ctx}
    if poster_available:
        return {'available': False, 'state': 'poster', 'mode': 'poster', 'src': '', **ctx}
    return {'available': False, 'state': 'soon', 'mode': 'none', 'src': '', **ctx}


def get_all_android_videos_context() -> list[dict]:
    return [get_android_video_context(key) for key in ANDROID_VIDEOS]


def resolve_android_video(video_config: dict | None = None) -> tuple[str, str]:
    """تعیین mode و src — پشتیبانی embed / media: / پیش‌فرض overview."""
    video_config = video_config or {}
    custom = (video_config.get('url') or '').strip()
    if custom:
        if custom.startswith(('http://', 'https://')):
            return 'embed', custom
        if custom.startswith('media:'):
            rel = custom[6:].lstrip('/')
            if _media_path(rel).is_file():
                return 'file', f"{settings.MEDIA_URL.rstrip('/')}/{rel}"
            return 'none', ''
        return 'file', custom

    ctx = get_android_video_context('overview')
    if ctx['available']:
        return ctx['mode'], ctx['src']
    return 'none', ''
