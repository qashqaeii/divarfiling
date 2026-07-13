"""حذف پیام‌ها و ضمیمه‌های قدیمی آژانس."""
from django.core.management.base import BaseCommand

from workspace.constants import MESSAGE_RETENTION_DAYS
from workspace.services.crm_agency_messages import purge_old_messages


class Command(BaseCommand):
    help = 'حذف پیام‌های داخلی آژانس قدیمی‌تر از ۳۰ روز (همراه فایل‌های ضمیمه)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=MESSAGE_RETENTION_DAYS,
            help='تعداد روز نگهداری (پیش‌فرض: ۳۰)',
        )

    def handle(self, *args, **options):
        stats = purge_old_messages(retention_days=options['days'])
        self.stdout.write(self.style.SUCCESS(
            f"پاکسازی انجام شد: {stats['threads']} رشته، "
            f"{stats['messages']} پیام، {stats['files']} فایل"
        ))
