"""Cron: همگام‌سازی نشست فایلینگ با خطوط استخراج phone-detector."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from accounts.services.extraction_lines_reconcile import reconcile_extraction_lines


class Command(BaseCommand):
    help = 'Reconcile filing Divar sessions with Phone Detector extraction lines (idempotent).'

    def handle(self, *args, **options):
        stats = reconcile_extraction_lines(wait_seconds=120.0)
        if stats.get('skipped_concurrent'):
            self.stdout.write(
                self.style.WARNING(f'Reconcile busy (lock not acquired): {stats}'),
            )
            raise CommandError('reconcile skipped: concurrent lock not acquired')
        if stats.get('ok'):
            self.stdout.write(self.style.SUCCESS(f'Reconcile OK: {stats}'))
            return
        self.stdout.write(self.style.WARNING(f'Reconcile failed: {stats}'))
        raise CommandError('reconcile failed')