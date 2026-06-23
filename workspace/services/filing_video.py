"""ویدیوی آموزشی فایلینگ میزکار — مسیر و متادیتای مرکزی."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings

# نسبت به MEDIA_ROOT — فایل: media/Video/divar-filing.mp4
FILING_VIDEO_MEDIA = 'Video/divar-filing.mp4'

FILING_VIDEO_META = {
    'title': 'آموزش فایلینگ، نقشه و تحلیل',
    'subtitle': 'مدیریت فایل‌های استخراج‌شده، جدول آگهی‌ها، نقشه و تحلیل بازار در میزکار',
    'duration': '~۱۰ دقیقه',
    'poster': '',
}


def _media_path() -> Path:
    return Path(settings.MEDIA_ROOT) / FILING_VIDEO_MEDIA


def filing_video_exists() -> bool:
    return _media_path().is_file()


def get_filing_video_url() -> str:
    if not filing_video_exists():
        return ''
    return f"{settings.MEDIA_URL.rstrip('/')}/{FILING_VIDEO_MEDIA}"


def get_filing_video_context() -> dict:
    meta = dict(FILING_VIDEO_META)
    url = get_filing_video_url()
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
