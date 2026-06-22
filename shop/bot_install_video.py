"""ویدیوی آموزشی نصب و فعال‌سازی ربات — مسیر و متادیتای مرکزی."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings

# نسبت به MEDIA_ROOT — فایل: media/Video/ROBOT-INSTALLING.mp4
BOT_INSTALL_VIDEO_MEDIA = 'Video/ROBOT-INSTALLING.mp4'

BOT_INSTALL_VIDEO_META = {
    'title': 'آموزش ویدیویی نصب و فعال‌سازی ربات',
    'subtitle': 'از دانلود و نصب تا وارد کردن کلید لایسنس — گام‌به‌گام',
    'duration': '~۵ دقیقه',
    'poster': '',
}


def _media_path() -> Path:
    return Path(settings.MEDIA_ROOT) / BOT_INSTALL_VIDEO_MEDIA


def bot_install_video_exists() -> bool:
    return _media_path().is_file()


def get_bot_install_video_url() -> str:
    if not bot_install_video_exists():
        return ''
    return f"{settings.MEDIA_URL.rstrip('/')}/{BOT_INSTALL_VIDEO_MEDIA}"


def get_bot_install_video_context() -> dict:
    """Context برای قالب — available, mode, src, title, subtitle, duration."""
    meta = dict(BOT_INSTALL_VIDEO_META)
    url = get_bot_install_video_url()
    if url:
        return {
            'available': True,
            'mode': 'file',
            'src': url,
            **meta,
        }
    return {
        'available': False,
        'mode': 'none',
        'src': '',
        **meta,
    }


def resolve_guide_video(video_config: dict | None = None) -> tuple[str, str]:
    """
    تعیین mode و src برای راهنمای فعال‌سازی.
    اولویت: url سفارشی در محتوا → ویدیوی نصب پیش‌فرض.
    """
    video_config = video_config or {}
    custom = (video_config.get('url') or '').strip()
    if custom:
        if custom.startswith(('http://', 'https://')):
            return 'embed', custom
        if custom.startswith('media:'):
            rel = custom[6:].lstrip('/')
            path = Path(settings.MEDIA_ROOT) / rel
            if path.is_file():
                return 'file', f"{settings.MEDIA_URL.rstrip('/')}/{rel}"
            return 'none', ''
        # مسیر static (قدیمی)
        return 'file', custom

    ctx = get_bot_install_video_context()
    if ctx['available']:
        return ctx['mode'], ctx['src']
    return 'none', ''
