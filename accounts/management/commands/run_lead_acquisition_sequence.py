"""اجرای توالی خودکار کمپین‌های جذب سرنخ."""
from django.core.management.base import BaseCommand

from accounts.services.lead_sequence import run_acquisition_sequence


class Command(BaseCommand):
    help = 'Run due Lead Acquisition sequence steps (UTC scheduling; display Tehran in UI).'

    def add_arguments(self, parser):
        parser.add_argument('--campaign-id', type=int, default=None)
        parser.add_argument('--limit', type=int, default=200)

    def handle(self, *args, **options):
        report = run_acquisition_sequence(
            campaign_id=options.get('campaign_id'),
            limit_per_step=options.get('limit') or 200,
        )
        self.stdout.write(self.style.SUCCESS(str(report)))
