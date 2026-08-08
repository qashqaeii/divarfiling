"""Long-running worker: poll AcquisitionRun queue and run phone-detector."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Poll queued acquisition runs and execute phone-detector '
        '(requires PHONE_DETECTOR_DIR pointing at phone-detector checkout).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--poll-interval',
            type=float,
            default=float(os.environ.get('ACQUISITION_WORKER_POLL_SECONDS', 30)),
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process at most one queued run then exit',
        )
        parser.add_argument(
            '--phone-detector-dir',
            type=str,
            default='',
            help='Override PHONE_DETECTOR_DIR (default: env or /root/phone-detector)',
        )

    def handle(self, *args, **options):
        pd_dir = (options.get('phone_detector_dir') or os.environ.get('PHONE_DETECTOR_DIR') or '').strip()
        if not pd_dir:
            for candidate in (
                Path('/root/phone-detector'),
                Path.home() / 'phone-detector',
                Path(__file__).resolve().parents[4] / 'phone-detector',
            ):
                if (candidate / 'engine.py').is_file():
                    pd_dir = str(candidate)
                    break
        if not pd_dir:
            self.stderr.write(
                self.style.ERROR(
                    'phone-detector not found. Set PHONE_DETECTOR_DIR or deploy to /root/phone-detector',
                ),
            )
            sys.exit(1)

        pd_path = Path(pd_dir).resolve()
        if not (pd_path / 'engine.py').is_file():
            self.stderr.write(self.style.ERROR(f'Invalid phone-detector dir: {pd_path}'))
            sys.exit(1)

        os.environ.setdefault('PHONE_DETECTOR_DIR', str(pd_path))
        os.environ.setdefault('DIVARFILING_DJANGO_DIR', str(Path.cwd()))

        if str(pd_path) not in sys.path:
            sys.path.insert(0, str(pd_path))

        from automation.worker import worker_loop

        worker_loop(
            poll_seconds=float(options['poll_interval']),
            once=bool(options.get('once')),
        )
