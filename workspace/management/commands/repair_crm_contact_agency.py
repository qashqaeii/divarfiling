"""اصلاح احتیاطی agency=NULL — فقط با شواهد Import فایل و تأیید صریح ریسک."""
from __future__ import annotations

import json
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.models import Customer, CustomerActivity
from workspace.services.crm_scope import get_membership

User = get_user_model()


class Command(BaseCommand):
    help = (
        'پیش‌نمایش یا اعمال agency روی مخاطبین user=عضو با agency=NULL '
        'که از Import فایل (فعالیت Import) شناسایی شده‌اند. '
        'مخاطبین شخصی قدیمی بدون این شواهد شامل نمی‌شوند.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, required=True)
        parser.add_argument('--apply', action='store_true', help='اعمال تغییر (پیش‌فرض: dry-run)')
        parser.add_argument(
            '--confirm-risk',
            action='store_true',
            help='الزامی همراه --apply — تأیید آگاهانه ریسک',
        )
        parser.add_argument(
            '--rollback-log',
            type=str,
            default='',
            help='مسیر فایل JSON برای ذخیره pkهای قبل از apply (بازگشت دستی)',
        )
        parser.add_argument('--limit', type=int, default=5000)

    def handle(self, *args, **options):
        user_id = options['user_id']
        apply = options['apply']
        limit = options['limit']

        user = User.objects.filter(pk=user_id).first()
        if not user:
            self.stderr.write('کاربر یافت نشد.')
            return

        m = get_membership(user)
        if not m:
            self.stderr.write('کاربر عضو آژانس فعال نیست — اصلاح خودکار مجاز نیست.')
            return

        import_customer_ids = CustomerActivity.objects.filter(
            title='Import',
            customer__user_id=user_id,
            customer__agency__isnull=True,
        ).values_list('customer_id', flat=True).distinct()

        qs = Customer.objects.filter(
            pk__in=import_customer_ids,
            user_id=user_id,
            agency__isnull=True,
        ).order_by('id')[:limit]
        pks = list(qs.values_list('pk', flat=True))
        count = len(pks)

        self.stdout.write(
            f'مخاطبین واجد شرایط (Import فایل + agency=NULL): {count} '
            f'(user={user_id} → agency {m.agency_id})'
        )
        ambiguous = Customer.objects.filter(
            user_id=user_id,
            agency__isnull=True,
        ).exclude(pk__in=import_customer_ids).count()
        self.stdout.write(
            self.style.WARNING(
                f'مخاطبین agency=NULL بدون شواهد Import (اصلاح نمی‌شوند): {ambiguous}'
            )
        )

        if not count:
            return

        if not apply:
            self.stdout.write(self.style.WARNING('Dry-run — بدون تغییر داده.'))
            return

        if not options['confirm_risk']:
            self.stderr.write(
                'برای اعمال باید --confirm-risk را هم ارسال کنید. '
                'مخاطبین شخصی قدیمی بدون شواهد Import شامل نمی‌شوند.'
            )
            return

        rollback_path = (options.get('rollback_log') or '').strip()
        if rollback_path:
            payload = {
                'user_id': user_id,
                'agency_id': m.agency_id,
                'at': datetime.utcnow().isoformat() + 'Z',
                'customer_ids': pks,
                'action': 'set_agency',
            }
            with open(rollback_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self.stdout.write(f'Rollback log: {rollback_path}')

        with transaction.atomic():
            updated = Customer.objects.filter(
                pk__in=pks,
                user_id=user_id,
                agency__isnull=True,
            ).update(agency=m.agency)

        self.stdout.write(self.style.SUCCESS(f'به‌روزرسانی شد: {updated}'))
