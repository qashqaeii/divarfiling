from django.core.management.base import BaseCommand, CommandError

from product_hub.services.changelog_from_codebase import build_changelog_from_codebase


class Command(BaseCommand):
    help = 'ساخت changelog حرفه‌ای از تاریخ migrationهای کدبیس برای کاربر مالک'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            default='09357930033',
            help='شماره موبایل مالک changelog (پیش‌فرض: قشقایی)',
        )
        parser.add_argument(
            '--no-replace',
            action='store_true',
            help='نسخه‌های هم‌شماره قبلی را حذف نکن؛ فقط update_or_create',
        )

    def handle(self, *args, **options):
        try:
            result = build_changelog_from_codebase(
                phone=options['phone'],
                replace_existing=not options['no_replace'],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f"Changelog built for {result['username']} ({result['phone']}): "
            f"+{result['created']} ~{result['updated']} "
            f"(total tracked versions={result['total']})"
        ))
