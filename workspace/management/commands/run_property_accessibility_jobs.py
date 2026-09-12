"""Process queued CRM property accessibility jobs (Overpass/POI)."""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from workspace.services.property_accessibility_jobs import process_property_accessibility_jobs


class Command(BaseCommand):
    help = 'Run DB-backed property accessibility jobs (cron/worker safe).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process one batch then exit',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Max jobs per batch (default: 10)',
        )
        parser.add_argument(
            '--poll-interval',
            type=float,
            default=15.0,
            help='Seconds between batches when not using --once',
        )

    def handle(self, *args, **options):
        limit = max(1, int(options['limit']))
        once = bool(options['once'])
        poll = max(1.0, float(options['poll_interval']))

        while True:
            processed = process_property_accessibility_jobs(limit=limit)
            if processed:
                self.stdout.write(self.style.SUCCESS(f'processed {processed} accessibility job(s)'))
            if once:
                return
            time.sleep(poll)
