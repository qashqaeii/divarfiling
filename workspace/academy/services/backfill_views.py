"""بازسازی views_count از پیشرفت کاربران و رویدادهای تاریخی."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from workspace.academy.models import (
    AcademyEvent,
    AcademyVideo,
    AcademyVideoViewDaily,
    UserVideoProgress,
)


def _slug_map() -> dict[str, int]:
    return dict(AcademyVideo.objects.values_list('slug', 'id'))


def _resolve_event_video_id(event: AcademyEvent, slug_to_id: dict[str, int]) -> int | None:
    if event.video_id:
        return event.video_id
    meta = event.metadata or {}
    if not isinstance(meta, dict):
        return None
    slug = meta.get('video_slug') or meta.get('slug')
    if not slug:
        return None
    return slug_to_id.get(str(slug))


def collect_historical_view_hits() -> tuple[dict[int, dict[date, int]], dict[int, int]]:
    """
    بازدیدهای تاریخی بدون دوباره‌شماری:
    1) رویداد academy_video_started (با resolve کردن slug از metadata)
    2) اگر برای ویدیو رویدادی نبود → از UserVideoProgress به‌عنوان کف استفاده می‌شود
    """
    hits: dict[int, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    event_totals: dict[int, int] = defaultdict(int)
    slug_to_id = _slug_map()

    for event in AcademyEvent.objects.filter(event_type='academy_video_started').iterator(chunk_size=500):
        video_id = _resolve_event_video_id(event, slug_to_id)
        if not video_id:
            continue
        day = timezone.localtime(event.created_at).date()
        hits[video_id][day] += 1
        event_totals[video_id] += 1

    progress_totals = {
        row['video_id']: int(row['count'] or 0)
        for row in UserVideoProgress.objects.values('video_id').annotate(count=Count('id'))
        if row['video_id']
    }

    progress_daily = (
        UserVideoProgress.objects
        .annotate(day=TruncDate('updated_at'))
        .values('video_id', 'day')
        .annotate(count=Count('id'))
    )
    for row in progress_daily:
        video_id = row['video_id']
        day = row['day']
        if not video_id or not day:
            continue
        # فقط وقتی رویداد شروع برای این ویدیو نداریم، از progress برای سری روزانه استفاده کن
        if event_totals.get(video_id, 0) == 0:
            hits[video_id][day] += int(row['count'] or 0)

    return hits, progress_totals


def backfill_academy_views(*, replace_daily: bool = True) -> dict[str, Any]:
    """views_count و ردیف‌های روزانه را از داده تاریخی بازسازی می‌کند."""
    hits, progress_totals = collect_historical_view_hits()
    videos = {v.id: v for v in AcademyVideo.objects.all()}

    updated_videos = 0
    daily_upserts = 0
    total_historical = 0

    all_video_ids = set(hits.keys()) | set(progress_totals.keys())
    for video_id in all_video_ids:
        video = videos.get(video_id)
        if not video:
            continue

        day_map = hits.get(video_id) or {}
        hist_from_days = sum(day_map.values())
        progress_floor = progress_totals.get(video_id, 0)
        hist_total = max(hist_from_days, progress_floor)
        total_historical += hist_total

        new_total = max(int(video.views_count or 0), hist_total)
        if new_total != int(video.views_count or 0):
            AcademyVideo.objects.filter(pk=video_id).update(views_count=new_total)
            updated_videos += 1

        # اگر سری روزانه خالی بود ولی progress داریم، یک سطل روی آخرین updated بگذار
        if not day_map and progress_floor:
            last = (
                UserVideoProgress.objects.filter(video_id=video_id)
                .order_by('-updated_at')
                .values_list('updated_at', flat=True)
                .first()
            )
            if last:
                day_map = {timezone.localtime(last).date(): progress_floor}

        if replace_daily:
            AcademyVideoViewDaily.objects.filter(video_id=video_id).delete()
            bulk = [
                AcademyVideoViewDaily(video_id=video_id, date=day, views=count)
                for day, count in day_map.items()
                if count > 0
            ]
            if bulk:
                AcademyVideoViewDaily.objects.bulk_create(bulk, ignore_conflicts=True)
                daily_upserts += len(bulk)
        else:
            for day, count in day_map.items():
                row, created = AcademyVideoViewDaily.objects.get_or_create(
                    video_id=video_id,
                    date=day,
                    defaults={'views': count},
                )
                if created:
                    daily_upserts += 1
                elif count > row.views:
                    AcademyVideoViewDaily.objects.filter(pk=row.pk).update(views=count)
                    daily_upserts += 1

    views_sum = AcademyVideo.objects.aggregate(t=Sum('views_count'))['t'] or 0
    return {
        'videos_touched': updated_videos,
        'daily_rows': daily_upserts,
        'historical_hits': total_historical,
        'views_total': views_sum,
        'videos_with_progress': len(progress_totals),
        'event_started': AcademyEvent.objects.filter(event_type='academy_video_started').count(),
    }
