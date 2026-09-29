"""حذف فایل‌های رسانه Curriculum قدیمی آکادمی (نه Video/ سیستمی)."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

LEGACY_ACADEMY_DIRS = (
    'academy/intro',
    'academy/quick_start',
    'academy/filing',
    'academy/crm',
    'academy/data',
    'academy/agency',
)

KEEP_POSTER_SUFFIXES = {'.webp'}


class Command(BaseCommand):
    help = 'Remove legacy academy MP4 files under media/academy/* (keeps new webp posters)'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true')

    def handle(self, *args, **options):
        if not options['yes']:
            self.stdout.write('Dry run — pass --yes to delete files')
        media = Path(settings.MEDIA_ROOT)
        removed = []
        for rel in LEGACY_ACADEMY_DIRS:
            folder = media / rel
            if not folder.is_dir():
                continue
            for f in folder.glob('*.mp4'):
                if options['yes']:
                    f.unlink()
                removed.append(str(f))
        poster_dir = media / 'academy' / 'posters'
        if poster_dir.is_dir():
            for f in poster_dir.iterdir():
                if f.suffix.lower() in {'.jpg', '.jpeg'}:
                    if options['yes']:
                        f.unlink()
                    removed.append(str(f))
        for path in removed:
            self.stdout.write(path)
        self.stdout.write(self.style.SUCCESS(f'{"Removed" if options["yes"] else "Would remove"} {len(removed)} files'))
