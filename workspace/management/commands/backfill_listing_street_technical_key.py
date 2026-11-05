"""تکمیل محدود مکان_خیابان از ستون معتبر خیابان — بدون overwrite."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from workspace.models import Dataset, Listing
from workspace.services.listing_street_data import (
    listing_street_backfill_plan,
    sync_street_keys_in_listing_data,
)


class Command(BaseCommand):
    help = (
        'تکمیل مکان_خیابان از خیابان در Listing.data برای رکوردهایی که کلید فنی خالی است. '
        'پیش‌فرض dry-run است؛ با --apply برای نوشتن در DB.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='اعمال تغییر در DB (بدون این پرچم فقط dry-run)',
        )
        parser.add_argument(
            '--dataset-id',
            type=str,
            default='',
            help='محدود به یک Dataset (UUID)',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            default=None,
            help='محدود به Datasetهای یک کاربر',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='حداکثر تعداد Listing بررسی‌شده (پیش‌فرض 500)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='اندازه bulk_update',
        )

    def handle(self, *args, **options):
        dry_run = not options['apply']
        limit = max(1, int(options['limit']))
        batch_size = max(1, int(options['batch_size']))
        dataset_id = str(options['dataset_id'] or '').strip()
        user_id = options['user_id']

        qs = Listing.objects.all().only('pk', 'token', 'data', 'dataset_id')
        if dataset_id:
            if not Dataset.objects.filter(pk=dataset_id).exists():
                raise CommandError(f'Dataset {dataset_id} یافت نشد.')
            qs = qs.filter(dataset_id=dataset_id)
        if user_id is not None:
            qs = qs.filter(dataset__user_id=user_id)

        scanned = 0
        eligible = 0
        updated = 0
        to_update: list[Listing] = []

        for listing in qs.iterator(chunk_size=batch_size):
            if scanned >= limit:
                break
            scanned += 1
            data = dict(listing.data or {})
            should, _value = listing_street_backfill_plan(data)
            if not should:
                continue
            eligible += 1
            new_data = sync_street_keys_in_listing_data(data)
            if new_data == (listing.data or {}):
                continue
            listing.data = new_data
            to_update.append(listing)
            if len(to_update) >= batch_size:
                if not dry_run:
                    Listing.objects.bulk_update(to_update, ['data'], batch_size=batch_size)
                updated += len(to_update)
                to_update = []

        if to_update:
            if not dry_run:
                Listing.objects.bulk_update(to_update, ['data'], batch_size=batch_size)
            updated += len(to_update)

        mode = 'dry-run' if dry_run else 'apply'
        self.stdout.write(
            f'[{mode}] scanned={scanned} eligible={eligible} '
            f'would_update={updated if dry_run else updated} '
            f'dataset_id={dataset_id or "all"} user_id={user_id or "all"}',
        )
        if dry_run and eligible:
            self.stdout.write(self.style.WARNING(
                'برای اعمال در DB از --apply استفاده کنید (ترجیحاً با --dataset-id).',
            ))
