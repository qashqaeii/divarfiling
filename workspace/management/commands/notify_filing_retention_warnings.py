"""هشدار retention فایلینگ — اجرای روزانه؛ فقط در بازه ۳ روزه قبل از پاک‌سازی ماهانه."""
from django.core.management.base import BaseCommand

from workspace.services.filing_retention_notifications import notify_filing_retention_warnings


class Command(BaseCommand):
    help = 'اعلان تجمیعی برای فایل‌های در آستانه پاک‌سازی فایلینگ (حداکثر یکی به ازای هر کاربر در هر cycle)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط شمارش — بدون ایجاد notification',
        )

    def handle(self, *args, **options):
        stats = notify_filing_retention_warnings(dry_run=options['dry_run'])
        lines = [
            f"warning_window_active={stats['warning_window_active']}",
            f"cycle_key={stats['cycle_key']}",
            f"cleanup_at={stats['cleanup_at']}",
            f"users_with_warnings={stats['users_with_warnings']:,}",
            f"users_notified={stats['users_notified']:,}",
            f"notifications_created={stats['notifications_created']:,}",
        ]
        if stats.get('skipped_reason'):
            lines.append(f"skipped_reason={stats['skipped_reason']}")
        prefix = '[dry-run] ' if stats['dry_run'] else ''
        self.stdout.write(self.style.WARNING(prefix + '\n'.join(lines)))
