"""Management command — ارسال اعلان‌های زمان‌بندی‌شده موبایل."""
from django.core.management.base import BaseCommand

from mobile_api.services.notification_scheduler import run_all_scheduled


class Command(BaseCommand):
    help = 'ارسال اعلان‌های زمان‌بندی‌شده موبایل (CRM، digest، لایسنس، استخراج)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-digest',
            action='store_true',
            help='ارسال digest و overdue بدون توجه به ساعت',
        )

    def handle(self, *args, **options):
        result = run_all_scheduled(force_digest=options['force_digest'])
        self.stdout.write(
            self.style.SUCCESS(
                ' '.join(f'{k}={v}' for k, v in result.items()),
            ),
        )
