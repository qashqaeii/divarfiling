"""ممیزی خطوط استخراج — پیش‌فرض read-only؛ --reactivate-healthy پس از Probe موفق."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from accounts.services.extraction_line_health import (
    VERDICT_LABELS_FA,
    audit_all_extraction_lines,
    reactivate_healthy_line,
)
from accounts.services.phone_detector_lines import PhoneDetectorLineError


class Command(BaseCommand):
    help = (
        'Audit Phone Detector extraction lines (read-only by default). '
        'Use --probe for live Divar checks; --reactivate-healthy only after successful probe.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reactivate-healthy',
            action='store_true',
            help='پس از Probe موفق و تأیید مالک نشست، خطوط مجاز را ACTIVE می‌کند',
        )
        parser.add_argument(
            '--probe',
            action='store_true',
            help='برای هر خط Probe زنده (auth + read-only) اجرا شود',
        )
        parser.add_argument('--phone', type=str, default='', help='فقط یک شماره')
        parser.add_argument('--json', action='store_true', help='خروجی JSON')

    def handle(self, *args, **options):
        reactivate = bool(options['reactivate_healthy'])
        probe = bool(options['probe']) or reactivate
        phone = (options.get('phone') or '').strip() or None
        rows = audit_all_extraction_lines(probe=probe, phone=phone)

        reactivated: list[str] = []
        failed_reactivate: list[tuple[str, str]] = []

        if reactivate:
            targets = [r for r in rows if r.get('verdict') == 'healthy']
            if phone and not targets:
                targets = [r for r in rows if r.get('phone') == phone]
            for row in targets:
                ph = row['phone']
                try:
                    reactivate_healthy_line(ph)
                    reactivated.append(ph)
                except PhoneDetectorLineError as exc:
                    failed_reactivate.append((ph, exc.message))
                except Exception as exc:
                    failed_reactivate.append((ph, str(exc)))

        if options['json']:
            payload = {
                'results': rows,
                'reactivated': reactivated,
                'reactivate_failed': [
                    {'phone': p, 'error': e} for p, e in failed_reactivate
                ],
            }
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        self.stdout.write(f'تعداد خطوط: {len(rows)}')
        for row in rows:
            probed = ' [probe]' if row.get('probed') else ''
            self.stdout.write(
                f"{row['phone']}\t{row.get('line_source', '')}\t"
                f"{row.get('operational_status', '')}\t"
                f"{row.get('verdict_label', '')}{probed}\t"
                f"{(row.get('detail') or '')[:120]}",
            )

        if reactivate:
            if reactivated:
                self.stdout.write(self.style.SUCCESS(f'فعال شد: {", ".join(reactivated)}'))
            for ph, err in failed_reactivate:
                self.stdout.write(self.style.WARNING(f'فعال‌سازی نشد {ph}: {err}'))

        unhealthy = [r for r in rows if r.get('verdict') != 'healthy']
        if unhealthy and not probe:
            self.stdout.write(
                self.style.NOTICE(
                    f'نتیجه آفلاین — برای {len(unhealthy)} خط Probe با --probe توصیه می‌شود.',
                ),
            )
        labels = ', '.join(sorted(set(VERDICT_LABELS_FA.values())))
        self.stdout.write(f'برچسب‌های ممکن: {labels}')

        if failed_reactivate and not reactivated:
            raise CommandError('هیچ خطی فعال نشد')