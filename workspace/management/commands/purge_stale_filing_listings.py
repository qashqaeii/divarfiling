"""حذف آگهی‌های قدیمی فایلینگ — اجرای روزانه با --dry-run پیشنهاد می‌شود."""
from django.core.management.base import BaseCommand

from workspace.services.filing_retention import purge_stale_filing_listings


class Command(BaseCommand):
    help = (
        'حذف آگهی‌های فایلینگ قدیمی‌تر از FILING_LISTING_RETENTION_DAYS '
        '(پیش‌فرض ۳۱ روز). CRM و سرکوب کاربر دست نخورده می‌مانند.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط شمارش — بدون هیچ write روی DB',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='اندازه batch حذف (پیش‌فرض: 500)',
        )

    def handle(self, *args, **options):
        stats = purge_stale_filing_listings(
            dry_run=options['dry_run'],
            batch_size=max(1, options['batch_size']),
        )
        if stats['dry_run']:
            self.stdout.write(self.style.WARNING(
                '[dry-run] هیچ تغییری در DB اعمال نشد. '
                f"eligible={stats['eligible']:,} "
                f"retention_days={stats['retention_days']} "
                f"batch_size={stats['batch_size']}",
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            'پاکسازی انجام شد: '
            f"eligible={stats['eligible']:,} "
            f"deleted={stats['deleted']:,} "
            f"affected_datasets={stats['affected_datasets']:,} "
            f"retention_days={stats['retention_days']}",
        ))
