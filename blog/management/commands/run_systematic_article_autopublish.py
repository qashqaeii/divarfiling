"""Management command: انتشار خودکار مقالات سیستماتیک."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from blog.services.market_article_autopublish import (
    AutoPublishBlocked,
    recover_stuck_autopublish_runs,
    run_systematic_article_autopublish,
)


class Command(BaseCommand):
    help = 'انتشار خودکار روزانه مقالات سیستماتیک (حداکثر ۱ در روز)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط انتخاب کاندید و تصمیم CREATE/UPDATE — بدون ساخت مقاله',
        )
        parser.add_argument(
            '--shadow',
            action='store_true',
            help='ساخت کامل + QA بدون Publish واقعی',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='نادیده گرفتن is_enabled و زمان ترجیحی (نه shadow_mode)',
        )
        parser.add_argument(
            '--recover-stuck',
            action='store_true',
            help='فقط بازیابی اجراهای متوقف‌شده — بدون pipeline انتشار',
        )
        parser.add_argument(
            '--no-recover',
            action='store_true',
            help='اجرای pipeline بدون بازیابی ابتدایی stuck runs',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        shadow = options['shadow']
        force = options['force']

        if options['recover_stuck']:
            n = recover_stuck_autopublish_runs()
            self.stdout.write(self.style.SUCCESS(f'Recovered {n} stuck run(s).'))
            return

        if dry_run and shadow:
            self.stderr.write(self.style.WARNING('هر دو --dry-run و --shadow: dry-run اولویت دارد.'))

        try:
            run = run_systematic_article_autopublish(
                shadow=shadow,
                dry_run=dry_run,
                force=force,
                recover_stuck=not options['no_recover'],
            )
        except AutoPublishBlocked as exc:
            self.stdout.write(self.style.WARNING(str(exc)))
            return

        self.stdout.write(f'Run ID: {run.pk}')
        self.stdout.write(f'Status: {run.status}')
        self.stdout.write(f'Action: {run.action}')
        self.stdout.write(f'Mode: {run.publish_mode}')
        if run.opportunity_score is not None:
            self.stdout.write(f'Opportunity score: {run.opportunity_score}')
        if run.quality_score is not None:
            self.stdout.write(f'QA score: {run.quality_score}')
        if run.ai_polish_report:
            polish_ok = run.ai_polish_report.get('ok')
            self.stdout.write(f'AI polish: {"OK" if polish_ok else "FAILED"}')
        if run.would_publish:
            self.stdout.write(self.style.SUCCESS('Would publish: YES'))
        elif run.status not in ('skipped',):
            self.stdout.write(self.style.WARNING('Would publish: NO'))
        if run.failure_reasons:
            for reason in run.failure_reasons:
                self.stdout.write(self.style.ERROR(f'  ✗ {reason}'))
        if run.post_id:
            self.stdout.write(self.style.SUCCESS(f'Post: {run.post_id} ({run.post.slug})'))
