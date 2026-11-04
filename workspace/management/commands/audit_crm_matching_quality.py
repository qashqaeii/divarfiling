"""ممیزی read-only کیفیت موتور تطبیق CRM."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from workspace.models import Customer
from workspace.services.crm_matching_audit import audit_customer_matches, audit_report_json

User = get_user_model()


class Command(BaseCommand):
    help = (
        'گزارش read-only مراحل تطبیق برای مخاطبین مشخص — '
        'بدون تغییر دیتابیس. برای مقایسه قبل/بعد دو snapshot JSON را با --compare مقایسه کنید.'
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
            help='کاربر مالک/مشاهده‌گر تطبیق',
        )
        parser.add_argument(
            '--no-divar',
            action='store_true',
            help='فقط CRM شخصی',
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
            help='مسیر snapshot قبلی برای diff شناسه‌های واجد شرایط',
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
        reports = []
        for cid in customer_ids:
            customer = Customer.objects.filter(pk=cid, user=user).first()
            if not customer:
                customer = Customer.objects.filter(pk=cid).first()
            if not customer:
                self.stderr.write(self.style.WARNING(f'مخاطب {cid} یافت نشد — رد شد'))
                continue
            report = audit_customer_matches(customer, user, divar_enabled=divar)
            reports.append(report)
            self.stdout.write(audit_report_json(report))

        compare_path = (options.get('compare') or '').strip()
        if compare_path and reports:
            with open(compare_path, encoding='utf-8') as fh:
                before = json.load(fh)
            if isinstance(before, list):
                before = before[0]
            from workspace.services.crm_matching_audit import compare_match_id_sets

            diff = compare_match_id_sets(before, reports[0])
            self.stdout.write(self.style.MIGRATE_HEADING('--- compare ---'))
            self.stdout.write(json.dumps(diff, ensure_ascii=False, indent=2))

        out_path = (options.get('output') or '').strip()
        if out_path and reports:
            with open(out_path, 'w', encoding='utf-8') as fh:
                json.dump(reports if len(reports) > 1 else reports[0], fh, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(self.style.SUCCESS(f'ذخیره شد: {out_path}'))
