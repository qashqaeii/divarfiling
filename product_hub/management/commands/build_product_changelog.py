from django.core.management.base import BaseCommand, CommandError

from product_hub.services.changelog_from_codebase import build_changelog_from_codebase, git_available


class Command(BaseCommand):
    help = 'ساخت changelog حرفه‌ای از تاریخچه Git برای کاربر مالک محصول'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            default='09357930033',
            help='شماره موبایل مالک (پیش‌فرض: قشقایی)',
        )
        parser.add_argument(
            '--no-replace',
            action='store_true',
            help='نسخه‌های هم‌شماره را از نو نساز',
        )

    def handle(self, *args, **options):
        if git_available():
            self.stdout.write(self.style.NOTICE('Git repo detected — enriching from commit history.'))
        else:
            self.stdout.write(self.style.WARNING('Git not detected — using curated milestones only.'))

        try:
            result = build_changelog_from_codebase(
                phone=options['phone'],
                replace_existing=not options['no_replace'],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f"Changelog for {result['username']} ({result['phone']}): "
            f"+{result['created']} ~{result['updated']} total={result['total']}"
        ))
        for item in result.get('enriched') or []:
            self.stdout.write(
                f"  v{item['version']}: {item['commits']} commits"
            )
