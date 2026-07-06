"""ویدیوی آموزشی CRM میزکار — مسیر و متادیتای مرکزی."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings

# نسبت به MEDIA_ROOT — فایل: media/Video/CRM.mp4
CRM_VIDEO_MEDIA = 'Video/CRM.mp4'

CRM_VIDEO_META = {
    'title': 'آموزش کامل CRM میزکار',
    'subtitle': 'مخاطبین، املاک، معاملات، تقویم، قالب پیام، اتوماسیون و تیم آژانس — گام‌به‌گام',
    'duration': 'آموزش کامل',
    'poster': '',
}


def _media_path() -> Path:
    return Path(settings.MEDIA_ROOT) / CRM_VIDEO_MEDIA


def crm_video_exists() -> bool:
    return _media_path().is_file()


def get_crm_video_url() -> str:
    if not crm_video_exists():
        return ''
    return f"{settings.MEDIA_URL.rstrip('/')}/{CRM_VIDEO_MEDIA}"


def get_crm_video_context() -> dict:
    meta = dict(CRM_VIDEO_META)
    url = get_crm_video_url()
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
