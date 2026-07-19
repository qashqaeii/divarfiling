"""ثبت Eventهای checkout_abandon — دستی / Dry Run؛ بدون ارسال SMS."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from shop.services.checkout_abandon import process_checkout_abandons


class Command(BaseCommand):
    help = (
        'ثبت idempotent رویداد checkout_abandon برای سفارش‌های pending قدیمی. '
        'هیچ پیامکی ارسال نمی‌کند. از --dry-run برای پیش‌نمایش استفاده کنید.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=None,
            help='حداقل سن سفارش به ساعت (پیش‌فرض: تنظیمات / ۲)',
        )
        parser.add_argument(
            '--batch',
            type=int,
            default=None,
            help='حداکثر تعداد سفارش در هر اجرا',
        )
        parser.add_argument(
            '--lookback-days',
            type=int,
            default=90,
            help='بازه جستجوی سفارش‌های pending (روز)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط آمار؛ Event نساز',
        )

    def handle(self, *args, **options):
        stats = process_checkout_abandons(
            hours=options.get('hours'),
            batch_limit=options.get('batch'),
            dry_run=bool(options.get('dry_run')),
            lookback_days=int(options.get('lookback_days') or 90),
        )
        mode = 'DRY-RUN' if stats['dry_run'] else 'APPLY'
        self.stdout.write(self.style.NOTICE(
            f'[{mode}] hours={stats["hours"]} batch={stats["batch_limit"]}'
        ))
        self.stdout.write(
            f'examined={stats["examined"]} eligible={stats["eligible"]} '
            f'created={stats["created"]} already={stats["already_recorded"]} '
            f'excluded={stats["excluded"]} errors={stats["errors"]}'
        )
        if stats.get('exclude_breakdown'):
            self.stdout.write(f'exclude_breakdown={stats["exclude_breakdown"]}')
        if stats['errors']:
            self.stdout.write(self.style.WARNING(f'errors={stats["errors"]}'))
        else:
            self.stdout.write(self.style.SUCCESS('done'))
