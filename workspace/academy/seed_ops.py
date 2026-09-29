"""پاک‌سازی Curriculum قدیمی آکادمی."""
from __future__ import annotations

from django.db import transaction

from workspace.academy.models import (
    AcademyBadge,
    AcademyMission,
    AcademyMissionStep,
    AcademyVideo,
    AcademyVideoViewDaily,
    CuratedPath,
    CuratedPathVideo,
    LearningPath,
    UserAcademyBadge,
    UserMissionProgress,
    UserVideoProgress,
)
from workspace.academy.seed_data import CURRICULUM_VIDEO_SLUGS, LEGACY_PATH_SLUGS


def reset_academy_curriculum_summary() -> dict:
    return {
        'videos': AcademyVideo.objects.count(),
        'paths': LearningPath.objects.count(),
        'missions': AcademyMission.objects.count(),
        'mission_steps': AcademyMissionStep.objects.count(),
        'curated': CuratedPath.objects.count(),
        'badges': AcademyBadge.objects.count(),
        'user_video_progress': UserVideoProgress.objects.count(),
        'user_mission_progress': UserMissionProgress.objects.count(),
        'user_badges': UserAcademyBadge.objects.count(),
        'daily_views': AcademyVideoViewDaily.objects.count(),
    }


@transaction.atomic
def reset_academy_curriculum() -> dict:
    before = reset_academy_curriculum_summary()
    CuratedPathVideo.objects.all().delete()
    CuratedPath.objects.all().delete()
    AcademyMissionStep.objects.all().delete()
    UserMissionProgress.objects.all().delete()
    AcademyMission.objects.all().delete()
    UserAcademyBadge.objects.all().delete()
    AcademyBadge.objects.all().delete()
    AcademyVideoViewDaily.objects.all().delete()
    UserVideoProgress.objects.all().delete()
    AcademyVideo.objects.all().delete()
    LearningPath.objects.all().delete()
    after = reset_academy_curriculum_summary()
    return {'before': before, 'after': after, 'kept_slugs': list(CURRICULUM_VIDEO_SLUGS)}


def prune_legacy_paths() -> int:
    """حذف مسیرهای قدیمی در صورت باقی‌ماندن پس از seed جزئی."""
    deleted, _ = LearningPath.objects.filter(slug__in=LEGACY_PATH_SLUGS).delete()
    return deleted
