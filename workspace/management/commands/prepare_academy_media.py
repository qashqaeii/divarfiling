"""Prepare academy media directories and placeholder/copy launch videos."""
from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from workspace.academy.models import AcademyVideo
from workspace.academy.seed_data import LAUNCH_VIDEO_FILES

# Map launch files to existing media when available
FALLBACK_SOURCES = {
    'quick_start_04_upload_file.mp4': 'Video/divar-filing.mp4',
    'crm_01_create_contact.mp4': 'Video/CRM.mp4',
    'crm_02_follow_up.mp4': 'Video/CRM.mp4',
    'filing_06_share_with_client.mp4': 'Video/divar-filing.mp4',
    'data_04_ai_assistant.mp4': 'Video/divar-filing.mp4',
    'quick_start_02_workspace_tour.mp4': 'Video/divar-filing.mp4',
    'quick_start_03_find_first_file.mp4': 'Video/divar-filing.mp4',
    'quick_start_01_first_value.mp4': 'Video/divar-filing.mp4',
}

FOLDERS = [
    'academy/posters',
    'academy/intro',
    'academy/quick_start',
    'academy/filing',
    'academy/crm',
    'academy/data',
    'academy/agency',
]

MINIMAL_MP4 = (
    b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x08free'
)


class Command(BaseCommand):
    help = 'Create academy media folders and place launch video files'

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        for folder in FOLDERS:
            (media_root / folder).mkdir(parents=True, exist_ok=True)
            self.stdout.write(f'Created {folder}')

        for video in AcademyVideo.objects.filter(is_launch=True):
            dest_dir = media_root / video.file_path
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / video.file_name
            if dest.is_file():
                self.stdout.write(f'Exists: {dest.name}')
                continue
            fallback = FALLBACK_SOURCES.get(video.file_name)
            if fallback:
                src = media_root / fallback
                if src.is_file():
                    shutil.copy2(src, dest)
                    self.stdout.write(self.style.SUCCESS(f'Copied {video.file_name} from {fallback}'))
                    continue
            dest.write_bytes(MINIMAL_MP4)
            self.stdout.write(self.style.WARNING(f'Placeholder: {video.file_name}'))

        for fname in LAUNCH_VIDEO_FILES:
            found = AcademyVideo.objects.filter(file_name=fname).first()
            if not found:
                self.stdout.write(self.style.WARNING(f'No DB record for {fname}'))

        self.stdout.write(self.style.SUCCESS('Academy media preparation complete'))
