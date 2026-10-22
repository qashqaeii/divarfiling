"""ادامه پولیش AI پس از ai_polish_failed — بدون ساخت مجدد مقاله/نقشه."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from blog.models import MarketArticleRun, SystematicArticleAutoPublishRun
from blog.services.market_article_autopublish import resume_systematic_article_autopublish
from blog.services.market_article_ai_polish import (
    AIPolishError,
    AIPolishRecoverableError,
    polish_market_article_run,
    reopen_identity_fallback_segments,
    _load_polish_state,
    _save_polish_state,
)


class Command(BaseCommand):
    help = (
        'بازگشایی segmentهای identity_fallback و ادامه پولیش/پipeline '
        'روی MarketArticleRun موجود.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--market-run', metavar='UUID', required=True)
        parser.add_argument(
            '--autopublish-run',
            metavar='UUID',
            help='ادامه pipeline انتشار خودکار پس از پولیش موفق',
        )
        parser.add_argument('--shadow', action='store_true', default=True)
        parser.add_argument('--force', action='store_true')
        parser.add_argument(
            '--polish-only',
            action='store_true',
            help='فقط پولیش — بدون ادامه autopublish',
        )

    def handle(self, *args, **options):
        market_pk = options['market_run']
        try:
            market_run = MarketArticleRun.objects.get(pk=market_pk)
        except MarketArticleRun.DoesNotExist:
            raise CommandError(f'MarketArticleRun {market_pk} یافت نشد.')

        state = reopen_identity_fallback_segments(_load_polish_state(market_run))
        if state:
            _save_polish_state(market_run, state)
            self.stdout.write(self.style.WARNING('segmentهای identity_fallback برای Retry باز شدند.'))

        try:
            result = polish_market_article_run(market_run, resume=True, persist=True)
        except (AIPolishRecoverableError, AIPolishError) as exc:
            raise CommandError(str(exc)) from exc

        eq = (result.report.get('editorial_quality') or {})
        self.stdout.write(self.style.SUCCESS('پولیش با موفقیت تمام شد.'))
        self.stdout.write(f'  fallback_ratio: {result.report.get("fallback_ratio")}')
        self.stdout.write(f'  tokens: {eq.get("total_recorded_tokens")}')

        if options['polish_only']:
            return

        ap_pk = options.get('autopublish_run')
        if not ap_pk:
            raise CommandError('برای ادامه انتشار، --autopublish-run الزامی است (یا --polish-only).')

        ap = SystematicArticleAutoPublishRun.objects.filter(pk=ap_pk).first()
        if not ap:
            raise CommandError('Autopublish run یافت نشد.')

        resume_systematic_article_autopublish(
            market_article_run_id=market_run.pk,
            autopublish_run_id=ap.pk,
            shadow=bool(options['shadow']),
            force=bool(options['force']),
        )
        self.stdout.write(self.style.SUCCESS(f'pipeline autopublish {ap_pk} از سر گرفته شد.'))
