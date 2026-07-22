"""بازسازی آمار بازدید آکادمی از پیشرفت و رویدادهای قبلی."""
from django.core.management.base import BaseCommand

from workspace.academy.services.backfill_views import backfill_academy_views


class Command(BaseCommand):
    help = 'بازسازی views_count و بازدید روزانه آکادمی از UserVideoProgress و AcademyEvent'

    def add_arguments(self, parser):
        parser.add_argument(
            '--merge-daily',
            action='store_true',
            help='به‌جای جایگزینی کامل روزانه، فقط افزایش بده',
        )

    def handle(self, *args, **options):
        result = backfill_academy_views(replace_daily=not options['merge_daily'])
        self.stdout.write(self.style.SUCCESS(
            'Academy views backfill done: '
            f"videos_touched={result['videos_touched']} "
            f"daily_rows={result['daily_rows']} "
            f"historical_hits={result['historical_hits']} "
            f"views_total={result['views_total']} "
            f"progress_videos={result['videos_with_progress']} "
            f"started_events={result['event_started']}"
        ))
