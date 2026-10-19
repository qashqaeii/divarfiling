"""Resolve AcademyVideo from DB or seed when media file exists on disk."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.db import transaction

from workspace.academy.cta import canonical_cta_path_for_slug, normalize_stored_action_url
from workspace.academy.models import AcademyVideo, LearningPath
from workspace.academy.seed_data import PATHS, VIDEOS


def _video_seed_row(slug: str) -> dict | None:
    slug = (slug or '').strip()
    if not slug:
        return None
    return next((row for row in VIDEOS if row['slug'] == slug), None)


def _path_seed_row(path_slug: str) -> dict | None:
    return next((row for row in PATHS if row['slug'] == path_slug), None)


def _seed_video_file_exists(row: dict) -> bool:
    rel_folder = row['file_path'].strip('/\\')
    return (Path(settings.MEDIA_ROOT) / rel_folder / row['file_name']).is_file()


@transaction.atomic
def ensure_academy_video_from_seed(slug: str) -> AcademyVideo | None:
    """
    اگر ویدیو در DB نیست اما در seed و روی MEDIA_ROOT هست، رکورد را می‌سازد/به‌روز می‌کند.
    """
    row = _video_seed_row(slug)
    if not row or not _seed_video_file_exists(row):
        return None

    path_row = _path_seed_row(row['path_slug'])
    if not path_row:
        return None

    path, _ = LearningPath.objects.update_or_create(
        slug=path_row['slug'],
        defaults={
            'title': path_row['title'],
            'icon': path_row.get('icon', 'fa-graduation-cap'),
            'description': path_row.get('description', ''),
            'order': path_row.get('order', 0),
            'is_public': path_row.get('is_public', True),
            'requires_role': path_row.get('requires_role', ''),
            'is_active': True,
            'phase': path_row.get('phase', 'launch'),
        },
    )

    rel_folder = row['file_path'].strip('/\\')
    action_url = row.get('action_url', '')
    canonical = canonical_cta_path_for_slug(row['slug'])
    if canonical:
        action_url = canonical
    else:
        action_url = normalize_stored_action_url(action_url)

    video, _ = AcademyVideo.objects.update_or_create(
        slug=row['slug'],
        defaults={
            'path': path,
            'title': row['title'],
            'subtitle': row['subtitle'],
            'description': row.get('description', ''),
            'file_name': row['file_name'],
            'file_path': rel_folder,
            'poster_path': row.get('poster_path', ''),
            'duration_seconds': row.get('duration_seconds') or 0,
            'order': row['order'],
            'is_public': row.get('is_public', True),
            'is_launch': False,
            'action_url': action_url,
            'action_label': row.get('action_label', ''),
            'mission_step': None,
            'auto_confirm_event': '',
            'is_active': True,
        },
    )
    return video


def resolve_academy_video(slug: str) -> AcademyVideo | None:
    slug = (slug or '').strip()
    if not slug:
        return None
    video = (
        AcademyVideo.objects.filter(slug=slug, is_active=True)
        .select_related('path')
        .first()
    )
    if video:
        return video
    return ensure_academy_video_from_seed(slug)
