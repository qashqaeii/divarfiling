"""Runner Dry Run بازیابی سفارش pending — بدون SMS."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from accounts.services.pending_recovery import SIMULATION_BANNER, run_pending_recovery


class Command(BaseCommand):
    help = (
        'Resolver مخاطب Recovery + Dry Run would_send. '
        'بدون --dry-run اجرا نمی‌شود. هیچ SMS ارسال نمی‌کند.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط would_send در ActionLog (الزامی در این مرحله)',
        )
        parser.add_argument(
            '--simulate-enabled',
            action='store_true',
            help='شبیه‌سازی مخاطبان بدون فعال‌کردن Flow Live',
        )
        parser.add_argument(
            '--batch',
            type=int,
            default=None,
            help='حداکثر Event بررسی‌شده',
        )
        parser.add_argument(
            '--lookback-days',
            type=int,
            default=None,
            help='بازه جستجوی Event (روز)',
        )

    def handle(self, *args, **options):
        if not options.get('dry_run'):
            raise CommandError(
                'اجرای واقعی pending_recovery هنوز فعال نیست. '
                'فقط با --dry-run مجاز است.'
            )

        simulate_enabled = bool(options.get('simulate_enabled'))
        stats = run_pending_recovery(
            dry_run=True,
            simulate_enabled=simulate_enabled,
            batch_limit=options.get('batch'),
            lookback_days=options.get('lookback_days'),
        )
        rs = stats.get('recovery_stats') or {}
        self.stdout.write(self.style.NOTICE(
            f'[DRY-RUN] flow={stats["flow_key"]} run_id={stats["run_id"]}'
        ))
        self.stdout.write(self.style.WARNING(SIMULATION_BANNER))
        self.stdout.write(
            f'examined={stats["examined"]} unique_recipients={stats["eligible"]} '
            f'would_send={stats["would_send"]} suppressed={stats["suppressed"]} '
            f'actions_created={stats["actions_created"]} errors={stats["errors"]} '
            f'simulate_enabled={stats["simulate_enabled"]} flow_live={stats["flow_live_enabled"]}'
        )
        if rs:
            self.stdout.write(
                f'raw_events={rs.get("raw_abandon_events")} '
                f'step_1={rs.get("step_1_recipients")} step_1_late={rs.get("step_1_late_recipients")} '
                f'step_2={rs.get("step_2_recipients")} expired={rs.get("expired_recipients")} '
                f'dup_suppressed={rs.get("suppressed_duplicates")}'
            )
        if stats['errors']:
            self.stdout.write(self.style.WARNING(f'errors={stats["errors"]}'))
        else:
            self.stdout.write(self.style.SUCCESS('done'))
