"""ادامه پولیش AI پس از ai_polish_failed — بدون ساخت مجدد مقاله/نقشه."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from blog.models import MarketArticleRun, SystematicArticleAutoPublishRun
from blog.services.market_article_autopublish import resume_systematic_article_autopublish
from blog.services.market_article_ai_polish import (
    AIPolishError,
    AIPolishRecoverableError,
    AIPolishResumeError,
    polish_market_article_run,
    reopen_and_persist_polish_resume_state,
    validate_autopublish_polish_resume,
    validate_market_run_for_polish_resume,
)


class Command(BaseCommand):
    help = (
        'بازگشایی segmentهای identity_fallback و ادامه پولیش یا pipeline انتشار خودکار. '
        'با --autopublish-run فقط pipeline استاندارد Resume اجرا می‌شود (یک بار پولیش در pipeline).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--market-run', metavar='UUID', required=True)
        parser.add_argument(
            '--autopublish-run',
            metavar='UUID',
            help='ادامه pipeline — پولیش فقط داخل resume_systematic_article_autopublish',
        )
        parser.add_argument('--shadow', action='store_true', default=True)
        parser.add_argument('--force', action='store_true')
        parser.add_argument(
            '--polish-only',
            action='store_true',
            help='فقط یک بار polish_market_article_run — بدون autopublish/QA',
        )

    def handle(self, *args, **options):
        polish_only = bool(options['polish_only'])
        ap_pk = options.get('autopublish_run')

        if polish_only and ap_pk:
            raise CommandError('همزمان --polish-only و --autopublish-run مجاز نیست.')
        if not polish_only and not ap_pk:
            raise CommandError('یکی از --polish-only یا --autopublish-run الزامی است.')

        market_pk = options['market_run']
        try:
            market_run = MarketArticleRun.objects.get(pk=market_pk)
        except MarketArticleRun.DoesNotExist:
            raise CommandError(f'MarketArticleRun {market_pk} یافت نشد.')

        try:
            validate_market_run_for_polish_resume(market_run)
        except AIPolishResumeError as exc:
            raise CommandError(str(exc)) from exc

        reopened = reopen_and_persist_polish_resume_state(market_run)
        if reopened:
            self.stdout.write(
                self.style.WARNING(
                    f'{reopened} segment با identity_fallback برای Retry باز شد.',
                ),
            )

        if polish_only:
            try:
                result = polish_market_article_run(market_run, resume=True, persist=True)
            except (AIPolishRecoverableError, AIPolishError) as exc:
                raise CommandError(str(exc)) from exc
            eq = result.report.get('editorial_quality') or {}
            self.stdout.write(self.style.SUCCESS('پولیش (polish-only) با موفقیت تمام شد.'))
            self.stdout.write(f'  fallback_ratio: {result.report.get("fallback_ratio")}')
            self.stdout.write(f'  tokens: {eq.get("total_recorded_tokens")}')
            return

        ap = SystematicArticleAutoPublishRun.objects.filter(pk=ap_pk).first()
        if not ap:
            raise CommandError('Autopublish run یافت نشد.')

        try:
            validate_autopublish_polish_resume(market_run, ap)
        except AIPolishResumeError as exc:
            raise CommandError(str(exc)) from exc

        resume_systematic_article_autopublish(
            market_article_run_id=market_run.pk,
            autopublish_run_id=ap.pk,
            shadow=bool(options['shadow']),
            force=bool(options['force']),
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'pipeline autopublish {ap_pk} از سر گرفته شد (پولیش داخل pipeline، یک بار).',
            ),
        )
