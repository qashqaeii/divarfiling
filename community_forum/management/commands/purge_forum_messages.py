"""حذف پیام‌های منقضی تالار."""
from django.core.management.base import BaseCommand

from community_forum.constants import RETENTION_DAYS
from community_forum.services.retention import purge_expired_messages


class Command(BaseCommand):
    help = 'حذف پیام‌های تالار قدیمی‌تر از ۳۰ روز'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=RETENTION_DAYS)

    def handle(self, *args, **options):
        stats = purge_expired_messages(retention_days=options['days'])
        self.stdout.write(self.style.SUCCESS(
            f"پاکسازی تالار: {stats['messages']} پیام، "
            f"{stats['reactions']} واکنش، {stats['reports']} گزارش"
        ))
