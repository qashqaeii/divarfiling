"""زمان‌بندی اجرای خودکار phone-detector → مرکز جذب."""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.services.acquisition_automation import schedule_due_campaigns


class Command(BaseCommand):
    help = 'Queue due AcquisitionAutomationCampaign runs (phone-detector collector).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-jobs',
            type=int,
            default=1,
            help='Maximum queued runs to create per invocation (default: 1)',
        )

    def handle(self, *args, **options):
        max_jobs = max(1, int(options.get('max_jobs') or 1))
        created = schedule_due_campaigns(max_jobs=max_jobs)
        report = {
            'at': timezone.now().isoformat(),
            'queued': [r.pk for r in created],
            'count': len(created),
        }
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Queued {len(created)} acquisition run(s): {[r.pk for r in created]}',
                ),
            )
        else:
            self.stdout.write('No acquisition runs queued.')
        self.stdout.write(str(report))
