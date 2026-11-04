"""ممیزی read-only کیفیت موتور تطبیق CRM."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from workspace.services.crm_matching_audit import (
    audit_customer_matches,
    audit_report_json,
    compare_match_snapshots,
)
from workspace.services.crm_scope import customer_for_user

User = get_user_model()


class Command(BaseCommand):
    help = (
        'گزارش read-only نمونه‌ای از مراحل تطبیق — بدون rebuild کش یا ایندex. '
        'برای diff دو snapshot JSON از --compare استفاده کنید.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--customer-id',
            type=int,
            action='append',
            dest='customer_ids',
            help='شناسه مخاطب (قابل تکرار)',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            required=True,
            help='کاربر مشاهده‌گر (باید به مخاطب دسترسی داشته باشد)',
        )
        parser.add_argument(
            '--no-divar',
            action='store_true',
            help='فقط CRM',
        )
        parser.add_argument(
            '--crm-sample-cap',
            type=int,
            default=500,
            help='حداکثر ردیف CRM برای بررسی (پیش‌فرض ۵۰۰)',
        )
        parser.add_argument(
            '--divar-sample-cap',
            type=int,
            default=500,
            help='حداکثر ردیف Divar برای بررسی (پیش‌فرض ۵۰۰)',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='',
            help='مسیر فایل JSON خروجی (اختیاری)',
        )
        parser.add_argument(
            '--compare',
            type=str,
            default='',
            help='مسیر snapshot قبلی برای مقایسه نمونه',
        )

    def handle(self, *args, **options):
        user = User.objects.filter(pk=options['user_id']).first()
        if not user:
            self.stderr.write(self.style.ERROR('user-id نامعتبر'))
            return

        customer_ids = options.get('customer_ids') or []
        if not customer_ids:
            self.stderr.write(self.style.ERROR('حداقل یک --customer-id لازم است'))
            return

        divar = not options['no_divar']
        crm_cap = max(1, int(options['crm_sample_cap']))
        divar_cap = max(1, int(options['divar_sample_cap']))
        reports = []

        for cid in customer_ids:
            customer = customer_for_user(user, cid)
            if not customer:
                self.stderr.write(
                    self.style.ERROR(
                        f'مخاطب {cid} برای user_id={user.pk} یافت نشد یا دسترسی ندارید.'
                    )
                )
                continue
            report = audit_customer_matches(
                customer,
                user,
                divar_enabled=divar,
                crm_sample_cap=crm_cap,
                divar_sample_cap=divar_cap,
            )
            reports.append(report)
            self.stdout.write(audit_report_json(report))

        if not reports:
            return

        compare_path = (options.get('compare') or '').strip()
        if compare_path:
            with open(compare_path, encoding='utf-8') as fh:
                before = json.load(fh)
            if isinstance(before, list):
                before = before[0]
            diff = compare_match_snapshots(before, reports[0])
            self.stdout.write(self.style.MIGRATE_HEADING('--- compare ---'))
            self.stdout.write(json.dumps(diff, ensure_ascii=False, indent=2))

        out_path = (options.get('output') or '').strip()
        if out_path:
            with open(out_path, 'w', encoding='utf-8') as fh:
                json.dump(reports if len(reports) > 1 else reports[0], fh, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(self.style.SUCCESS(f'ذخیره شد: {out_path}'))
