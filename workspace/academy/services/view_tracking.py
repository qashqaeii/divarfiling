"""ثبت بازدید ویدیوهای آکادمی برای آمار عمومی و پنل مدیریت."""
from __future__ import annotations

from django.db.models import F
from django.utils import timezone

from workspace.academy.models import AcademyVideo, AcademyVideoViewDaily


def record_video_view(video: AcademyVideo) -> int:
    """یک بازدید برای ویدیو در تاریخ محلی امروز ثبت می‌کند و views_count را برمی‌گرداند."""
    today = timezone.localdate()
    row, created = AcademyVideoViewDaily.objects.get_or_create(
        video=video,
        date=today,
        defaults={'views': 1},
    )
    if not created:
        AcademyVideoViewDaily.objects.filter(pk=row.pk).update(views=F('views') + 1)

    AcademyVideo.objects.filter(pk=video.pk).update(views_count=F('views_count') + 1)
    video.refresh_from_db(fields=['views_count'])
    return int(video.views_count)


def get_views_map(video_ids) -> dict[int, int]:
    """نقشه video_id → views_count برای نمایش در لیست‌ها."""
    if not video_ids:
        return {}
    return dict(
        AcademyVideo.objects.filter(id__in=video_ids).values_list('id', 'views_count')
    )
