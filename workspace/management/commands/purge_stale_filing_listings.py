"""حذف آگهی‌های قدیمی فایلینگ — اجرای روزانه با --dry-run پیشنهاد می‌شود."""
from django.core.management.base import BaseCommand, CommandError

from workspace.services.filing_retention import purge_stale_filing_listings


class Command(BaseCommand):
    help = (
        'حذف آگهی‌های فایلینگ قدیمی‌تر از FILING_LISTING_RETENTION_DAYS '
        '(پیش‌فرض از تنظیم مرکزی). CRM، سرکوب کاربر، share فعال، '
        'تعامل کاربر، و CustomerListing دست نخورده می‌مانند.'
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
        parser.add_argument(
            '--max-delete',
            type=int,
            default=None,
            help='حداکثر تعداد Listing برای حذف در این اجرا (canary؛ پیش‌فرض: نامحدود)',
        )

    def handle(self, *args, **options):
        max_delete = options['max_delete']
        if max_delete is not None and max_delete < 0:
            raise CommandError('--max-delete must be non-negative')

        try:
            stats = purge_stale_filing_listings(
                dry_run=options['dry_run'],
                batch_size=max(1, options['batch_size']),
                max_delete=max_delete,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        breakdown_lines = [
            f"retention_days={stats['retention_days']}",
            f"base_age_eligible={stats['base_age_eligible']:,}",
            f"protected_public_share={stats['protected_public_share']:,}",
            f"protected_favorite={stats['protected_favorite']:,}",
            f"protected_note={stats['protected_note']:,}",
            f"protected_workflow_tag={stats['protected_workflow_tag']:,}",
            f"protected_customer_relation={stats['protected_customer_relation']:,}",
            f"unique_protected={stats['unique_protected']:,}",
            f"final_eligible={stats['final_eligible']:,}",
            f"batch_size={stats['batch_size']}",
            f"max_delete={stats['max_delete'] if stats['max_delete'] is not None else 'unlimited'}",
        ]
        if stats['dry_run']:
            self.stdout.write(self.style.WARNING(
                '[dry-run] هیچ تغییری در DB اعمال نشد.\n'
                + '\n'.join(breakdown_lines),
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            'پاکسازی انجام شد:\n'
            + '\n'.join(breakdown_lines)
            + f"\ndeleted={stats['deleted']:,} "
            f"affected_datasets={stats['affected_datasets']:,} "
            f"batches={stats['batches']:,} "
            f"remaining_eligible={stats['remaining_eligible']:,}",
        ))
