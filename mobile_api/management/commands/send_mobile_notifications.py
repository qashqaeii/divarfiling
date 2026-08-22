"""Management command — ارسال اعلان‌های زمان‌بندی‌شده موبایل."""
import logging
import time

from django.core.management.base import BaseCommand

from mobile_api.services.notification_scheduler import run_all_scheduled

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'ارسال اعلان‌های زمان‌بندی‌شده موبایل (CRM، digest، لایسنس، استخراج، broadcast)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-digest',
            action='store_true',
            help='ارسال digest و overdue بدون توجه به ساعت',
        )

    def handle(self, *args, **options):
        started = time.monotonic()
        result = run_all_scheduled(force_digest=options['force_digest'])
        elapsed_ms = int((time.monotonic() - started) * 1000)
        summary = ' '.join(f'{k}={v}' for k, v in result.items())
        logger.info('send_mobile_notifications %s elapsed_ms=%s', summary, elapsed_ms)
        self.stdout.write(self.style.SUCCESS(f'{summary} elapsed_ms={elapsed_ms}'))
