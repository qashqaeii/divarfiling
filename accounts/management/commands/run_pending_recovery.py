"""Runner بازیابی سفارش pending — Dry Run و Live SMS (فاز ۲.۲)."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from accounts.services.pending_recovery import SIMULATION_BANNER, run_pending_recovery


class Command(BaseCommand):
    help = (
        'Resolver مخاطب Recovery. '
        '--dry-run: would_send بدون SMS. '
        '--live --confirm-live: ارسال واقعی با Kill Switch و محدودیت تست.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط would_send در ActionLog (بدون SMS)',
        )
        parser.add_argument(
            '--live',
            action='store_true',
            help='ارسال Live — نیاز به --confirm-live و Kill Switch',
        )
        parser.add_argument(
            '--confirm-live',
            action='store_true',
            help='تأیید صریح ارسال SMS واقعی',
        )
        parser.add_argument(
            '--test-only',
            action='store_true',
            help='ارسال فقط به RECOVERY_LIVE_TEST_PHONE',
        )
        parser.add_argument(
            '--no-test-only',
            action='store_true',
            help='ارسال به شماره واقعی مخاطب (خطرناک — فقط پس از تست ادمین)',
        )
        parser.add_argument(
            '--max-sends',
            type=int,
            default=None,
            help='حداکثر SMS موفق در این Run (پیش‌فرض: RECOVERY_LIVE_MAX_SENDS_PER_RUN)',
        )
        parser.add_argument(
            '--allow-retry-failed',
            action='store_true',
            help='اجازه retry روی send_idempotency_key با وضعیت failed',
        )
        parser.add_argument(
            '--simulate-enabled',
            action='store_true',
            help='شبیه‌سازی مخاطبان بدون فعال‌کردن Flow Live (فقط dry-run)',
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
        live = bool(options.get('live'))
        dry_run = bool(options.get('dry_run'))

        if live and dry_run:
            raise CommandError('فقط یکی از --dry-run یا --live را انتخاب کنید.')

        if live:
            self._handle_live(options)
            return

        if not dry_run:
            raise CommandError(
                'اجرای بدون --dry-run مجاز نیست. '
                'برای Live: --live --confirm-live'
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

    def _handle_live(self, options):
        from accounts.services.pending_recovery_live import run_pending_recovery_live

        if not options.get('confirm_live'):
            raise CommandError('ارسال Live نیاز به --confirm-live دارد.')

        test_only = None
        if options.get('test_only'):
            test_only = True
        elif options.get('no_test_only'):
            test_only = False

        try:
            stats = run_pending_recovery_live(
                confirm_live=True,
                test_only=test_only,
                batch_limit=options.get('batch'),
                lookback_days=options.get('lookback_days'),
                allow_retry_failed=bool(options.get('allow_retry_failed')),
                max_sends_per_run=options.get('max_sends'),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.NOTICE(
            f'[LIVE] flow={stats["flow_key"]} run_id={stats["run_id"]}'
        ))
        self.stdout.write(self.style.WARNING(stats.get('simulation_banner', 'LIVE SEND')))
        self.stdout.write(
            f'examined={stats["examined"]} would_send={stats["would_send"]} '
            f'send_requested={stats["send_requested"]} provider_accepted={stats["provider_accepted"]} '
            f'failed={stats["failed"]} skipped={stats["skipped"]} '
            f'test_only={stats["test_only"]} live_enabled={stats["live_send_enabled"]}'
        )
        if stats.get('ambiguous_in_flight'):
            self.stdout.write(self.style.WARNING(
                f'ambiguous_in_flight={stats["ambiguous_in_flight"]} (send_requested — بدون retry خودکار)'
            ))
        if stats.get('skip_breakdown'):
            self.stdout.write(f'skip_breakdown={stats["skip_breakdown"]}')
        if stats['failed'] or stats['errors']:
            self.stdout.write(self.style.WARNING('completed with failures'))
        else:
            self.stdout.write(self.style.SUCCESS('done'))
