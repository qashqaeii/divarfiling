"""Seed academy paths, videos, mission, badges."""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.academy.models import (
    AcademyBadge,
    AcademyMission,
    AcademyMissionStep,
    AcademyVideo,
    CuratedPath,
    CuratedPathVideo,
    LearningPath,
)
from workspace.academy.seed_data import (
    BADGES,
    MISSION_STEPS,
    PATHS,
    TRADITIONAL_PATH,
    VIDEOS,
)


class Command(BaseCommand):
    help = 'Seed academy learning paths, videos, mission and badges'

    @transaction.atomic
    def handle(self, *args, **options):
        path_map = {}
        for data in PATHS:
            obj, _ = LearningPath.objects.update_or_create(
                slug=data['slug'],
                defaults={
                    'title': data['title'],
                    'icon': data.get('icon', 'fa-graduation-cap'),
                    'description': data.get('description', ''),
                    'order': data.get('order', 0),
                    'is_public': data.get('is_public', False),
                    'requires_role': data.get('requires_role', ''),
                    'is_active': True,
                    'phase': data.get('phase', 'launch'),
                },
            )
            path_map[data['slug']] = obj
            self.stdout.write(f'Path: {obj.slug}')

        video_map = {}
        for row in VIDEOS:
            (
                path_slug, order, slug, title, subtitle, file_name, folder,
                duration, is_public, is_launch, action_url, action_label,
                mission_step, auto_confirm,
            ) = row
            path = path_map[path_slug]
            obj, _ = AcademyVideo.objects.update_or_create(
                slug=slug,
                defaults={
                    'path': path,
                    'title': title,
                    'subtitle': subtitle,
                    'file_name': file_name,
                    'file_path': folder,
                    'duration_seconds': duration,
                    'order': order,
                    'is_public': is_public,
                    'is_launch': is_launch,
                    'action_url': action_url,
                    'action_label': action_label,
                    'mission_step': mission_step,
                    'auto_confirm_event': auto_confirm,
                    'is_active': True,
                },
            )
            video_map[slug] = obj

        for data in BADGES:
            AcademyBadge.objects.update_or_create(
                slug=data['slug'],
                defaults=data,
            )

        mission, _ = AcademyMission.objects.update_or_create(
            slug='day-one',
            defaults={
                'title': 'ماموریت روز اول',
                'description': 'در ۱۵ دقیقه اولین فایل و مشتری را ثبت کنید.',
                'badge_slug': 'ready-advisor',
                'is_active': True,
            },
        )
        AcademyMissionStep.objects.filter(mission=mission).delete()
        for i, (video_slug, action_url, action_label, confirm_type, auto_key) in enumerate(MISSION_STEPS, start=1):
            AcademyMissionStep.objects.create(
                mission=mission,
                video=video_map[video_slug],
                order=i,
                action_url=action_url,
                action_label=action_label,
                confirm_type=confirm_type,
                auto_confirm_key=auto_key,
            )

        curated, _ = CuratedPath.objects.update_or_create(
            slug=TRADITIONAL_PATH['slug'],
            defaults={
                'title': TRADITIONAL_PATH['title'],
                'description': TRADITIONAL_PATH['description'],
            },
        )
        CuratedPathVideo.objects.filter(path=curated).delete()
        for order, slug in enumerate(TRADITIONAL_PATH['video_slugs'], start=1):
            CuratedPathVideo.objects.create(
                path=curated,
                video=video_map[slug],
                order=order,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(path_map)} paths, {len(video_map)} videos, mission, badges, curated path'
        ))
