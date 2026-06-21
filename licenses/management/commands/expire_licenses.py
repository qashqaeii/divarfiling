"""همگام‌سازی وضعیت انقضای لایسنس‌ها — برای cron روزانه.

Usage:
  python manage.py expire_licenses
  python manage.py expire_licenses --dry-run
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from licenses.models import License


class Command(BaseCommand):
    help = 'Mark expired licenses (expires_at in the past) as status=expired'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report licenses that would be expired',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        qs = License.objects.filter(
            expires_at__lt=now,
        ).exclude(status__in=['expired', 'suspended'])

        count = qs.count()
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'Would expire {count} license(s).'))
            for lic in qs[:20]:
                self.stdout.write(f'  {lic.license_key} user={lic.order.user_id}')
            return

        updated = 0
        for lic in qs.iterator():
            lic.status = 'expired'
            lic.save(update_fields=['status'])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f'Expired {updated} license(s).'))
