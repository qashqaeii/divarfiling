"""اجرای یکپارچه پایپلاین رشد: جذب → Activation → Recovery → تمدید لایسنس."""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils import timezone


class Command(BaseCommand):
    help = (
        'Run unified growth pipeline: acquisition drip, activation drip, '
        'pending recovery (optional), license renewal.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200, help='Limit per sequence step')
        parser.add_argument('--skip-acquisition', action='store_true')
        parser.add_argument('--skip-activation', action='store_true')
        parser.add_argument('--skip-recovery', action='store_true')
        parser.add_argument('--skip-renewal', action='store_true')
        parser.add_argument(
            '--recovery-live',
            action='store_true',
            help='Also run pending recovery in live mode (requires env kill switches)',
        )
        parser.add_argument(
            '--renewal-live',
            action='store_true',
            help='Send license renewal SMS (default is dry-run)',
        )
        parser.add_argument('--backfill', action='store_true', help='Backfill GrowthJourney first')

    def handle(self, *args, **options):
        report = {'started_at': timezone.now().isoformat(), 'parts': {}}

        if options.get('backfill'):
            from accounts.services.growth_journey import backfill_journeys
            report['parts']['backfill'] = backfill_journeys()

        limit = int(options.get('limit') or 200)

        if not options.get('skip_acquisition'):
            from accounts.services.lead_sequence import run_acquisition_sequence
            report['parts']['acquisition'] = run_acquisition_sequence(limit_per_step=limit)

        if not options.get('skip_activation'):
            from accounts.services.lead_sequence import run_activation_sequence
            report['parts']['activation'] = run_activation_sequence(limit_per_step=limit)

        if not options.get('skip_recovery'):
            try:
                from accounts.services.pending_recovery import run_pending_recovery
                if options.get('recovery_live'):
                    from accounts.services.pending_recovery_live import run_pending_recovery_live
                    report['parts']['recovery'] = run_pending_recovery_live(
                        confirm_live=True,
                        max_sends_per_run=1,
                    )
                else:
                    report['parts']['recovery'] = run_pending_recovery(
                        dry_run=True,
                        simulate_enabled=True,
                    )
            except Exception as exc:
                report['parts']['recovery'] = {'error': str(exc)}

        if not options.get('skip_renewal'):
            from accounts.services.license_renewal import run_license_renewal
            live = bool(options.get('renewal_live'))
            report['parts']['license_renewal'] = run_license_renewal(
                dry_run=not live,
                live=live,
                limit=limit,
            )

        report['finished_at'] = timezone.now().isoformat()
        cache.set('growth_pipeline_last_run', report, timeout=60 * 60 * 48)
        self.stdout.write(self.style.SUCCESS(str(report)))
