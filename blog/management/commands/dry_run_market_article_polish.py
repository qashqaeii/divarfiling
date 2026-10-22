"""پولیش AI بدون ذخیره — گزارش توکن و Before/After برای آزمون دستی."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from blog.models import MarketArticleRun
from blog.services.market_article_ai_polish import AIPolishError, AIPolishRecoverableError, polish_market_article_run


class Command(BaseCommand):
    help = (
        'اجرای پولیش AI روی MarketArticleRun بدون ذخیره content_html/seo و بدون Resume state. '
        'برای آزمون واقعی مدل — نه Production publish.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-id',
            metavar='UUID',
            required=True,
            help='شناسه MarketArticleRun (مثلاً اجرای جیحون)',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='خروجی گزارش به‌صورت JSON',
        )

    def handle(self, *args, **options):
        run_id = options['run_id']
        try:
            run = MarketArticleRun.objects.get(pk=run_id)
        except MarketArticleRun.DoesNotExist:
            raise CommandError(f'MarketArticleRun {run_id} پیدا نشد.')

        if run.post_id and options.get('verbosity', 1) >= 1:
            self.stdout.write(
                self.style.WARNING(
                    f'این run به Post {run.post_id} متصل است؛ '
                    'با persist=False هیچ تغییری روی مقاله ذخیره نمی‌شود.',
                ),
            )

        try:
            result = polish_market_article_run(
                run,
                resume=False,
                persist=False,
                persist_resume_state=False,
                clear_resume_state_on_apply=False,
            )
        except (AIPolishRecoverableError, AIPolishError) as exc:
            raise CommandError(str(exc)) from exc

        eq = result.report.get('editorial_quality') or {}
        summary = {
            'run_id': str(run.pk),
            'market_key': run.market_key,
            'provider': result.provider,
            'model': result.model,
            'batch_count': result.report.get('batch_count'),
            'batch_plan_version': result.report.get('batch_plan_version'),
            'text_segments': result.report.get('text_segments'),
            'polish_change_ratio': result.report.get('polish_change_ratio'),
            'input_tokens': eq.get('input_tokens'),
            'output_tokens': eq.get('output_tokens'),
            'total_recorded_tokens': eq.get('total_recorded_tokens'),
            'ai_call_count': eq.get('ai_call_count'),
            'retry_count': eq.get('retry_count'),
            'fallback_count': eq.get('fallback_count'),
            'editorial_quality_score': eq.get('editorial_quality_score'),
            'snapshots': eq.get('snapshots'),
        }

        if options['json']:
            self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
            return

        self.stdout.write(self.style.SUCCESS('پولیش dry-run موفق (بدون ذخیره در DB).'))
        for key, val in summary.items():
            if key == 'snapshots':
                continue
            self.stdout.write(f'  {key}: {val}')
        snaps = summary.get('snapshots') or {}
        if snaps:
            self.stdout.write('\n--- intro_before ---\n' + (snaps.get('intro_before') or ''))
            self.stdout.write('\n--- intro_after ---\n' + (snaps.get('intro_after') or ''))
