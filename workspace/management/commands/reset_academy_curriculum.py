"""پاک‌سازی Curriculum قدیمی و seed مجدد آکادمی."""
from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand

from workspace.academy.seed_ops import reset_academy_curriculum, reset_academy_curriculum_summary


class Command(BaseCommand):
    help = 'Reset legacy academy curriculum and seed the current 12-video curriculum'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Confirm destructive reset')

    def handle(self, *args, **options):
        if not options['yes']:
            self.stdout.write(self.style.WARNING(
                'Will delete all academy paths, videos, missions, badges, and user progress.'
            ))
            self.stdout.write(str(reset_academy_curriculum_summary()))
            self.stdout.write('Re-run with --yes')
            return
        result = reset_academy_curriculum()
        self.stdout.write(self.style.WARNING(f'Deleted: {result["before"]}'))
        call_command('seed_academy')
        self.stdout.write(self.style.SUCCESS('Academy curriculum reset and reseeded.'))
