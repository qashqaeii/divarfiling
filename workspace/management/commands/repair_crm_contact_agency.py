"""اصلاح احتیاطی agency=NULL برای مخاطبین اعضای آژانس — فقط با تأیید صریح."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.models import Customer
from workspace.services.crm_scope import get_membership

User = get_user_model()


class Command(BaseCommand):
    help = (
        'پیش‌نمایش یا اعمال agency روی مخاطبین user=عضو که agency=NULL دارند '
        '(همان منطق backfill عضویت، بدون تغییر مالکیت).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, required=True)
        parser.add_argument('--apply', action='store_true', help='اعمال تغییر (پیش‌فرض: dry-run)')
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

        qs = Customer.objects.filter(user_id=user_id, agency__isnull=True).order_by('id')[:limit]
        count = qs.count()
        self.stdout.write(f'رکورد واجد شرایط (user={user_id}, agency→{m.agency_id}): {count}')

        if not count:
            return

        if not apply:
            self.stdout.write(self.style.WARNING('Dry-run — برای اعمال از --apply استفاده کنید.'))
            return

        with transaction.atomic():
            updated = Customer.objects.filter(
                pk__in=list(qs.values_list('pk', flat=True)),
                user_id=user_id,
                agency__isnull=True,
            ).update(agency=m.agency)

        self.stdout.write(self.style.SUCCESS(f'به‌روزرسانی شد: {updated}'))
