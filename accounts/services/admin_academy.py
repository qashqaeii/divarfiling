"""آمار و لیست ویدیوهای آکادمی برای پنل مدیریت."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from workspace.academy.models import (
    AcademyEvent,
    AcademyMission,
    AcademyVideo,
    AcademyVideoViewDaily,
    LearningPath,
    UserMissionProgress,
    UserVideoProgress,
)

SCHEMA_VERSION = '1.0'


def get_academy_dashboard_stats() -> dict[str, Any]:
    now = timezone.now()
    month_ago = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)

    qs = AcademyVideo.objects.all()
    active_qs = qs.filter(is_active=True)
    public_qs = active_qs.filter(is_public=True)

    views_total = qs.aggregate(total=Sum('views_count'))['total'] or 0
    public_views = public_qs.aggregate(total=Sum('views_count'))['total'] or 0

    learners = UserVideoProgress.objects.values('user_id').distinct().count()
    completions_total = UserVideoProgress.objects.filter(completed=True).count()
    completions_month = UserVideoProgress.objects.filter(
        completed=True, completed_at__gte=month_ago,
    ).count()
    starts_week = AcademyEvent.objects.filter(
        event_type='academy_video_started',
        created_at__gte=week_ago,
    ).count()

    mission = AcademyMission.objects.filter(is_active=True).first()
    mission_started = 0
    mission_completed = 0
    if mission:
        mission_started = UserMissionProgress.objects.filter(mission=mission).count()
        mission_completed = UserMissionProgress.objects.filter(
            mission=mission, completed=True,
        ).count()

    top_videos = list(
        active_qs.select_related('path')
        .order_by('-views_count')[:8]
        .values(
            'id', 'title', 'slug', 'views_count', 'is_public', 'is_active',
            'path__title', 'duration_seconds',
        )
    )

    paths = list(
        LearningPath.objects.filter(is_active=True)
        .annotate(
            video_count=Count('videos', filter=Q(videos__is_active=True)),
            views=Sum('videos__views_count', filter=Q(videos__is_active=True)),
        )
        .order_by('order', 'id')
        .values('id', 'title', 'slug', 'video_count', 'views')[:12]
    )

    return {
        'videos_total': qs.count(),
        'videos_active': active_qs.count(),
        'videos_public': public_qs.count(),
        'videos_private': active_qs.filter(is_public=False).count(),
        'views_total': views_total,
        'views_public': public_views,
        'avg_views': round(views_total / max(active_qs.count(), 1)),
        'learners_total': learners,
        'completions_total': completions_total,
        'completions_month': completions_month,
        'starts_week': starts_week,
        'paths_total': LearningPath.objects.filter(is_active=True).count(),
        'mission_started': mission_started,
        'mission_completed': mission_completed,
        'mission_rate': round(
            (mission_completed / mission_started * 100) if mission_started else 0,
            1,
        ),
        'top_videos': top_videos,
        'paths': paths,
    }


def get_academy_videos_table(*, limit: int = 80, status: str = 'all') -> list[dict[str, Any]]:
    qs = AcademyVideo.objects.select_related('path')
    if status == 'public':
        qs = qs.filter(is_active=True, is_public=True)
    elif status == 'private':
        qs = qs.filter(is_active=True, is_public=False)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)

    rows = []
    for video in qs.order_by('-views_count', 'path__order', 'order')[:limit]:
        try:
            public_url = reverse('public_academy_video', kwargs={'slug': video.slug}) if video.is_public else ''
        except Exception:
            public_url = ''
        try:
            workspace_url = reverse('workspace:academy_video', kwargs={'slug': video.slug})
        except Exception:
            workspace_url = f'/workspace/academy/video/{video.slug}/'
        rows.append({
            'id': video.id,
            'title': video.title,
            'slug': video.slug,
            'path': video.path.title if video.path_id else '—',
            'path_slug': video.path.slug if video.path_id else '',
            'is_public': video.is_public,
            'is_active': video.is_active,
            'views_count': video.views_count,
            'duration_seconds': video.duration_seconds,
            'duration_display': video.duration_display,
            'completions': UserVideoProgress.objects.filter(video=video, completed=True).count(),
            'public_url': public_url,
            'workspace_url': workspace_url,
            'admin_edit_url': f'/admin/workspace/academyvideo/{video.id}/change/',
        })
    return rows


def _pct_change(current: int, previous: int) -> float | None:
    if previous > 0:
        return round((current - previous) / previous * 100, 1)
    if current > 0:
        return 100.0
    return None


def _build_date_series(*, start, end, day_map: dict) -> tuple[list[str], list[int]]:
    labels: list[str] = []
    counts: list[int] = []
    day = start
    while day <= end:
        labels.append(day.isoformat())
        counts.append(int(day_map.get(day, 0)))
        day += timedelta(days=1)
    return labels, counts


def _daily_views_map(*, start, end) -> dict:
    rows = (
        AcademyVideoViewDaily.objects.filter(date__gte=start, date__lte=end)
        .values('date')
        .annotate(total=Sum('views'))
    )
    return {row['date']: int(row['total'] or 0) for row in rows}


def get_academy_traffic_pulse() -> dict[str, Any]:
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=6)
    prev_week_start = today - timedelta(days=13)
    prev_week_end = today - timedelta(days=7)

    today_views = _daily_views_map(start=today, end=today).get(today, 0)
    yesterday_views = _daily_views_map(start=yesterday, end=yesterday).get(yesterday, 0)

    week_map = _daily_views_map(start=week_start, end=today)
    prev_week_map = _daily_views_map(start=prev_week_start, end=prev_week_end)

    week_views = sum(week_map.values())
    prev_week_views = sum(prev_week_map.values())

    month_start = today - timedelta(days=29)
    month_views = sum(_daily_views_map(start=month_start, end=today).values())

    first_tracked = (
        AcademyVideoViewDaily.objects.order_by('date').values_list('date', flat=True).first()
    )

    return {
        'today': today_views,
        'yesterday': yesterday_views,
        'today_vs_yesterday_pct': _pct_change(today_views, yesterday_views),
        'week': week_views,
        'prev_week': prev_week_views,
        'week_vs_prev_pct': _pct_change(week_views, prev_week_views),
        'month': month_views,
        'avg_daily_month': round(month_views / 30, 1),
        'tracking_since': first_tracked.isoformat() if first_tracked else None,
        'has_tracking_data': AcademyVideoViewDaily.objects.exists(),
    }


def get_academy_traffic_analytics(*, days: int = 30) -> dict[str, Any]:
    days = max(7, min(days, 90))
    today = timezone.localdate()
    since = today - timedelta(days=days - 1)
    prev_since = since - timedelta(days=days)
    prev_until = since - timedelta(days=1)

    current_map = _daily_views_map(start=since, end=today)
    prev_map = _daily_views_map(start=prev_since, end=prev_until)

    labels, counts = _build_date_series(start=since, end=today, day_map=current_map)
    _, prev_counts = _build_date_series(start=prev_since, end=prev_until, day_map=prev_map)

    period_total = sum(counts)
    prev_period_total = sum(prev_counts)
    has_daily_in_period = any(counts) or AcademyVideoViewDaily.objects.filter(
        date__gte=since, date__lte=today,
    ).exists()

    by_path = list(
        AcademyVideoViewDaily.objects.filter(date__gte=since, date__lte=today)
        .values('video__path__title', 'video__path__slug')
        .annotate(views=Sum('views'))
        .order_by('-views')[:10]
    )
    path_mode = 'daily'
    if not by_path or not has_daily_in_period:
        by_path = list(
            LearningPath.objects.filter(is_active=True)
            .annotate(views=Sum('videos__views_count', filter=Q(videos__is_active=True)))
            .filter(views__gt=0)
            .order_by('-views')
            .values('title', 'slug', 'views')[:10]
        )
        by_path = [
            {
                'video__path__title': row['title'],
                'video__path__slug': row['slug'],
                'views': int(row['views'] or 0),
            }
            for row in by_path
        ]
        path_mode = 'cumulative'

    for row in by_path:
        if not row.get('video__path__title'):
            row['video__path__title'] = 'بدون مسیر'
            row['video__path__slug'] = ''

    top_videos_period = list(
        AcademyVideoViewDaily.objects.filter(date__gte=since, date__lte=today)
        .values('video__id', 'video__title', 'video__slug')
        .annotate(views=Sum('views'))
        .order_by('-views')[:10]
    )
    period_mode = 'daily'
    if not top_videos_period or not has_daily_in_period:
        top_videos_period = [
            {
                'video__id': row['id'],
                'video__title': row['title'],
                'video__slug': row['slug'],
                'views': int(row['views_count'] or 0),
            }
            for row in AcademyVideo.objects.filter(is_active=True)
            .order_by('-views_count')
            .values('id', 'title', 'slug', 'views_count')[:10]
        ]
        period_mode = 'cumulative'

    completions_daily = (
        UserVideoProgress.objects.filter(
            completed=True,
            completed_at__isnull=False,
            completed_at__date__gte=since,
            completed_at__date__lte=today,
        )
        .annotate(day=TruncDate('completed_at'))
        .values('day')
        .annotate(count=Count('id'))
    )
    done_map = {row['day']: int(row['count'] or 0) for row in completions_daily if row['day']}
    _, completion_counts = _build_date_series(start=since, end=today, day_map=done_map)

    return {
        'days': days,
        'period_total': period_total,
        'prev_period_total': prev_period_total,
        'period_delta_pct': _pct_change(period_total, prev_period_total),
        'avg_daily': round(period_total / days, 1) if days else 0,
        'has_daily_in_period': has_daily_in_period,
        'views_by_path_mode': path_mode,
        'top_videos_period_mode': period_mode,
        'views_daily': {
            'labels': labels,
            'counts': counts,
            'prev_counts': prev_counts,
            'completions': completion_counts,
        },
        'views_by_path': [
            {
                'name': row['video__path__title'],
                'slug': row['video__path__slug'],
                'views': int(row['views'] or 0),
            }
            for row in by_path
        ],
        'top_videos_period': [
            {
                'id': row['video__id'],
                'title': row['video__title'],
                'slug': row['video__slug'],
                'views': int(row['views'] or 0),
            }
            for row in top_videos_period
        ],
    }


def get_academy_analytics_chart(days: int = 30) -> dict[str, Any]:
    days = max(7, min(days, 90))
    traffic = get_academy_traffic_analytics(days=days)
    pulse = get_academy_traffic_pulse()
    stats = get_academy_dashboard_stats()

    top_views = list(
        AcademyVideo.objects.filter(is_active=True)
        .order_by('-views_count')[:10]
        .values('title', 'slug', 'views_count')
    )

    return {
        'days': days,
        'top_views': top_views,
        'traffic': traffic,
        'pulse': pulse,
        'summary': {
            'views_total': stats['views_total'],
            'videos_active': stats['videos_active'],
            'learners_total': stats['learners_total'],
            'completions_total': stats['completions_total'],
            'mission_rate': stats['mission_rate'],
        },
    }


def build_academy_stats_json(
    *,
    days: int = 30,
    status: str = 'all',
    videos_limit: int = 1000,
) -> dict[str, Any]:
    if status not in ('all', 'public', 'private', 'inactive'):
        status = 'all'

    now = timezone.now()
    stats = get_academy_dashboard_stats()
    analytics = get_academy_analytics_chart(days=days)
    videos = get_academy_videos_table(limit=videos_limit, status=status)

    return {
        'ok': True,
        'meta': {
            'generated_at': now.isoformat(),
            'source': 'admin_panel_academy',
            'version': SCHEMA_VERSION,
            'analytics_days': analytics['days'],
            'videos_status_filter': status,
            'videos_limit': videos_limit,
            'videos_exported': len(videos),
        },
        'summary': stats,
        'analytics': analytics,
        'traffic': analytics.get('traffic'),
        'pulse': analytics.get('pulse'),
        'videos': videos,
    }
