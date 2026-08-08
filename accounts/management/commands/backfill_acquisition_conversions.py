"""Backfill LeadAttribution conversion for leads with paid orders."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.services.lead_attribution import backfill_conversion_attributions


class Command(BaseCommand):
    help = 'Create missing conversion attributions for MarketingLeads with paid orders.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only count candidates; do not write',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Max paid orders to scan (0 = all)',
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get('dry_run'))
        limit = int(options.get('limit') or 0)
        stats = backfill_conversion_attributions(dry_run=dry_run, limit=limit)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN — {stats['candidates']} lead(s) would get conversion attribution",
                ),
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {stats['created']} conversion attribution(s)",
                ),
            )

        self.stdout.write(
            f"candidates={stats['candidates']} "
            f"skipped_has_conversion={stats['skipped_has_conversion']} "
            f"skipped_no_lead={stats['skipped_no_lead']} "
            f"errors={stats['errors']}",
        )

        if not dry_run and stats['created']:
            self.stdout.write(
                'Re-run: python manage.py audit_acquisition_funnel',
            )
