"""ممیزی: آیا عدد «خرید / لایسنس» داشبورد با واقعیت سرنخ‌ها یکی است؟"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from accounts.services.acquisition_funnel_audit import audit_acquisition_funnel


class Command(BaseCommand):
    help = (
        'Compare dashboard purchase count with real paid orders for MarketingLead phones/users. '
        'Run on server: python manage.py audit_acquisition_funnel'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output full report as JSON',
        )
        parser.add_argument(
            '--sample',
            type=int,
            default=10,
            help='Max sample rows per section (default: 10)',
        )

    def handle(self, *args, **options):
        report = audit_acquisition_funnel(sample_limit=max(1, int(options['sample'] or 10)))

        if options.get('json'):
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        d = report['dashboard']
        a = report['attribution']
        g = report['ground_truth']

        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('=== ممیزی قیف جذب / خرید ==='))
        self.stdout.write('')

        self.stdout.write(self.style.MIGRATE_LABEL('── داشبورد (همان UI) ──'))
        self.stdout.write(f"  کل سرنخ‌ها:           {d['leads_total']}")
        self.stdout.write(f"  ثبت‌نام‌شده:          {d['leads_registered']}")
        self.stdout.write(f"  مشتری (status):       {d['leads_customer']}")
        self.stdout.write(f"  کلیک لندینگ:         {d['total_clicks']}")
        self.stdout.write(f"  خرید UI (conversion): {d['total_purchases_ui']}")
        self.stdout.write(f"  درآمد UI:             {d['purchase_revenue_ui']} تومان")
        self.stdout.write('')

        self.stdout.write(self.style.MIGRATE_LABEL('── واقعیت (تطبیق شماره/کاربر → سفارش paid) ──'))
        self.stdout.write(
            f"  سرنخ‌هایی با سفارش paid:     {g['leads_with_paid_order_by_phone_or_user']} "
            f"(از {d['leads_total']} سرنخ)",
        )
        self.stdout.write(
            f"  └─ enroll کمپین جذب:         {g['enrolled_leads_with_paid_order']}",
        )
        self.stdout.write(
            f"  └─ وضعیت registered:         {g['registered_leads_with_paid_order']}",
        )
        self.stdout.write(f"  touchpoint paid/licensed:    {g['leads_with_paid_or_licensed_touchpoint']}")
        self.stdout.write(
            f"  LeadAttribution (همه سرنخ‌ها): {a['conversion_last_all_leads']}",
        )
        self.stdout.write(
            f"  └─ enroll کمپین جذب:         {a['conversion_last_enrolled_acquisition']}",
        )
        self.stdout.write(
            f"  خریدار enroll بدون conversion: {g['enrolled_buyers_missing_conversion_attr']}",
        )
        self.stdout.write('')
        self.stdout.write(f"  سفارش paid کل سایت:          {g['paid_orders_site_total']}")
        self.stdout.write(
            f"  کاربر paid بدون سرنخ:        {g['paid_users_without_marketing_lead']}",
        )
        self.stdout.write('')

        verdict = report['verdict']
        if verdict == 'ok' and g['leads_with_paid_order_by_phone_or_user'] == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    '✓ نتیجه: عدد ۰ خرید درست است — هیچ سرنخی (حتی پلن یک‌هفته‌ای) '
                    'سفارش paid ندارد.',
                ),
            )
        elif verdict == 'attribution_gap':
            self.stdout.write(
                self.style.WARNING(
                    '⚠ نتیجه: خرید واقعی هست ولی داشبورد ۰ نشان می‌دهد — '
                    'attribute_purchase conversion ثبت نشده.',
                ),
            )
        elif verdict == 'ok':
            self.stdout.write(self.style.SUCCESS('✓ نتیجه: attribution و خرید هم‌خوان است.'))
        else:
            self.stdout.write(self.style.WARNING('? نتیجه: نیاز به بررسی دستی'))

        for note in report.get('notes') or []:
            self.stdout.write(f'  → {note}')

        samples = report.get('samples') or {}
        if samples.get('buyers_among_all_leads'):
            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_LABEL('── نمونه خریداران بین سرنخ‌ها ──'))
            for row in samples['buyers_among_all_leads']:
                self.stdout.write(
                    f"  lead#{row['lead_id']} {row['phone']} "
                    f"status={row['lead_status']} orders={row['paid_orders']} "
                    f"plans={row['plans']} conv_attr={row['conversion_attribution']}",
                )

        if samples.get('buyers_enrolled_missing_attr'):
            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_LABEL('── enroll شده · conversion ندارند ──'))
            for row in samples['buyers_enrolled_missing_attr']:
                self.stdout.write(
                    f"  lead#{row['lead_id']} {row['phone']} revenue={row['paid_revenue_toman']}",
                )

        self.stdout.write('')
        self.stdout.write('JSON کامل: python manage.py audit_acquisition_funnel --json')
        self.stdout.write('')
