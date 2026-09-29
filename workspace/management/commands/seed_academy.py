"""Seed academy — Curriculum فعال: ۲ مسیر، ۸ ویدیو."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.academy.media_utils import mp4_duration_seconds
from workspace.academy.models import AcademyVideo, LearningPath
from workspace.academy.seed_data import PATHS, VIDEOS
from workspace.academy.seed_ops import reset_academy_curriculum, reset_academy_curriculum_summary


class Command(BaseCommand):
    help = 'Seed academy curriculum (2 paths, 8 videos). Use --reset to wipe legacy data first.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete all legacy academy content before seeding',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Required with --reset for non-interactive confirmation',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            if not options['yes']:
                summary = reset_academy_curriculum_summary()
                self.stdout.write(self.style.WARNING(
                    'Reset will delete academy content. Summary: ' + str(summary)
                ))
                self.stdout.write('Re-run with --reset --yes to confirm.')
                return
            result = reset_academy_curriculum()
            self.stdout.write(self.style.WARNING(f'Reset complete. Before: {result["before"]}'))

        media_root = Path(settings.MEDIA_ROOT)
        path_map = {}
        for data in PATHS:
            obj, _ = LearningPath.objects.update_or_create(
                slug=data['slug'],
                defaults={
                    'title': data['title'],
                    'icon': data.get('icon', 'fa-graduation-cap'),
                    'description': data.get('description', ''),
                    'order': data.get('order', 0),
                    'is_public': data.get('is_public', True),
                    'requires_role': data.get('requires_role', ''),
                    'is_active': True,
                    'phase': data.get('phase', 'launch'),
                },
            )
            path_map[data['slug']] = obj
            self.stdout.write(f'Path: {obj.slug}')

        video_count = 0
        for row in VIDEOS:
            path = path_map[row['path_slug']]
            rel_folder = row['file_path'].strip('/\\')
            file_path = media_root / rel_folder / row['file_name']
            duration = row.get('duration_seconds') or 0
            probed = mp4_duration_seconds(file_path)
            if probed:
                duration = probed
            AcademyVideo.objects.update_or_create(
                slug=row['slug'],
                defaults={
                    'path': path,
                    'title': row['title'],
                    'subtitle': row['subtitle'],
                    'description': row.get('description', ''),
                    'file_name': row['file_name'],
                    'file_path': rel_folder,
                    'poster_path': row.get('poster_path', ''),
                    'duration_seconds': duration,
                    'order': row['order'],
                    'is_public': row.get('is_public', True),
                    'is_launch': False,
                    'action_url': row.get('action_url', ''),
                    'action_label': row.get('action_label', ''),
                    'mission_step': None,
                    'auto_confirm_event': '',
                    'is_active': True,
                },
            )
            video_count += 1
            self.stdout.write(f'Video: {row["slug"]} ({duration}s)')

        stale = AcademyVideo.objects.exclude(slug__in=[v['slug'] for v in VIDEOS])
        stale_count = stale.count()
        if stale_count:
            stale.delete()
            self.stdout.write(self.style.WARNING(f'Removed {stale_count} stale videos'))

        stale_paths = LearningPath.objects.exclude(slug__in=[p['slug'] for p in PATHS])
        sp_count = stale_paths.count()
        if sp_count:
            stale_paths.delete()
            self.stdout.write(self.style.WARNING(f'Removed {sp_count} stale paths'))

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(path_map)} paths, {video_count} videos'
        ))
