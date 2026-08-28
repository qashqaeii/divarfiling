"""اجرای انتشار خودکار مقالات سیستماتیک."""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from blog.models import (
    MarketArticleRun,
    SystematicArticleAutoPublishConfig,
    SystematicArticleAutoPublishRun,
)
from blog.services.market_article_autopublish_config import (
    get_autopublish_config,
    get_autopublish_settings,
    local_today,
    touch_autopublish_last_run,
)
from blog.services.market_article_candidate_selection import (
    AutoPublishCandidate,
    pick_best_candidate,
)
from blog.services.market_article_pipeline import (
    build_preview,
    create_draft,
    update_existing_post,
)
from blog.services.market_article_post_publish import verify_published_post
from blog.services.market_article_publish_decision import PublishAction, decide_publish_action
from blog.services.market_article_quality_gates import qa_passes_for_publish, run_quality_gates
from workspace.models import Dataset

User = get_user_model()
logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = (
    SystematicArticleAutoPublishRun.Status.QUEUED,
    SystematicArticleAutoPublishRun.Status.GENERATING,
    SystematicArticleAutoPublishRun.Status.QA_RUNNING,
)
_PUBLISHED_STATUSES = (
    SystematicArticleAutoPublishRun.Status.PUBLISHED,
    SystematicArticleAutoPublishRun.Status.UPDATED,
)


class AutoPublishBlocked(Exception):
    def __init__(self, reason: str, *, run: SystematicArticleAutoPublishRun | None = None):
        super().__init__(reason)
        self.reason = reason
        self.run = run


def _resolve_publish_mode(*, shadow: bool, dry_run: bool) -> str:
    if dry_run:
        return SystematicArticleAutoPublishRun.PublishMode.DRY_RUN
    if shadow:
        return SystematicArticleAutoPublishRun.PublishMode.SHADOW
    return SystematicArticleAutoPublishRun.PublishMode.LIVE


def _daily_publish_count(run_date) -> int:
    return SystematicArticleAutoPublishRun.objects.filter(
        run_date=run_date,
        status__in=_PUBLISHED_STATUSES,
    ).count()


def _has_active_run(run_date) -> bool:
    return SystematicArticleAutoPublishRun.objects.filter(
        run_date=run_date,
        status__in=_ACTIVE_STATUSES,
    ).exists()


@transaction.atomic
def _acquire_run_lock(run_date) -> SystematicArticleAutoPublishConfig:
    config = SystematicArticleAutoPublishConfig.objects.select_for_update().get(pk=1)
    if _has_active_run(run_date):
        raise AutoPublishBlocked('اجرای هم‌زمان دیگری در حال انجام است.')
    if _daily_publish_count(run_date) >= max(1, config.max_daily_publish):
        raise AutoPublishBlocked('سقف انتشار روزانه تکمیل شده است.')
    return config


def _system_user():
    return User.objects.filter(is_superuser=True).order_by('pk').first()


def publish_market_article_from_run(
    run: MarketArticleRun,
    *,
    user=None,
    is_update: bool = False,
) -> Any:
    """انتشار واقعی — reuse create_draft/update سپس is_published=True."""
    from blog.models import Post

    if is_update:
        post = update_existing_post(run)
    else:
        post = create_draft(run, user or _system_user())

    if not post.is_published:
        post.is_published = True
        if not post.published_at:
            post.published_at = timezone.now()
        post.save(update_fields=['is_published', 'published_at', 'updated_at'])
    return post


def run_systematic_article_autopublish(
    *,
    shadow: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> SystematicArticleAutoPublishRun:
    """اجرای روزانه انتشار خودکار."""
    run_date = local_today()
    settings = get_autopublish_settings()
    publish_mode = _resolve_publish_mode(shadow=shadow, dry_run=dry_run)

    if not dry_run:
        _acquire_run_lock(run_date)

    config = get_autopublish_config()
    if publish_mode == SystematicArticleAutoPublishRun.PublishMode.LIVE:
        if not config.is_enabled and not force:
            raise AutoPublishBlocked('انتشار خودکار غیرفعال است.')
        if config.shadow_mode and not force:
            publish_mode = SystematicArticleAutoPublishRun.PublishMode.SHADOW
            shadow = True

    candidate = pick_best_candidate(settings)
    autopublish_run = SystematicArticleAutoPublishRun.objects.create(
        run_date=run_date,
        status=SystematicArticleAutoPublishRun.Status.CANDIDATE,
        publish_mode=publish_mode,
        candidate_snapshot=asdict(candidate) if candidate else {},
        opportunity_score=candidate.opportunity_score if candidate else None,
    )

    if not candidate:
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.SKIPPED
        autopublish_run.failure_reasons = ['امروز هیچ Dataset مناسبی برای انتشار خودکار یافت نشد.']
        autopublish_run.save(update_fields=['status', 'failure_reasons', 'updated_at'])
        touch_autopublish_last_run()
        return autopublish_run

    dataset = Dataset.objects.filter(pk=candidate.dataset_id, is_active=True).first()
    if not dataset:
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.SKIPPED
        autopublish_run.failure_reasons = ['دیتاست کاندید یافت نشد.']
        autopublish_run.save(update_fields=['status', 'failure_reasons', 'updated_at'])
        touch_autopublish_last_run()
        return autopublish_run

    autopublish_run.dataset = dataset
    decision = decide_publish_action(dataset, candidate)
    autopublish_run.action = decision.action

    if decision.action == PublishAction.SKIP:
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.SKIPPED
        autopublish_run.failure_reasons = [decision.reason]
        autopublish_run.save()
        touch_autopublish_last_run()
        return autopublish_run

    if dry_run:
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.SKIPPED
        autopublish_run.failure_reasons = []
        autopublish_run.qa_report = {
            'dry_run': True,
            'candidate': autopublish_run.candidate_snapshot,
            'decision': decision.reason,
            'action': decision.action,
        }
        autopublish_run.would_publish = (
            decision.action in (PublishAction.CREATE_NEW, PublishAction.UPDATE_EXISTING)
        )
        autopublish_run.save()
        touch_autopublish_last_run()
        return autopublish_run

    autopublish_run.status = SystematicArticleAutoPublishRun.Status.GENERATING
    autopublish_run.save(update_fields=['dataset', 'action', 'status', 'updated_at'])

    user = _system_user()
    try:
        market_run = build_preview(dataset, user)
    except Exception as exc:
        logger.exception('autopublish build failed dataset=%s', dataset.pk)
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW
        autopublish_run.failure_reasons = [f'خطا در ساخت مقاله: {exc}']
        autopublish_run.market_article_run = None
        autopublish_run.save()
        touch_autopublish_last_run()
        return autopublish_run

    autopublish_run.market_article_run = market_run
    autopublish_run.status = SystematicArticleAutoPublishRun.Status.QA_RUNNING
    autopublish_run.save(update_fields=['market_article_run', 'status', 'updated_at'])

    qa = run_quality_gates(market_run, settings)
    autopublish_run.qa_report = {
        'total_score': qa.total_score,
        'critical_errors': qa.critical_errors,
        'data_score': qa.data_score,
        'content_score': qa.content_score,
        'seo_score': qa.seo_score,
        'media_score': qa.media_score,
        'technical_score': qa.technical_score,
        'checks': [
            {'key': c.key, 'category': c.category, 'passed': c.passed, 'critical': c.critical, 'message': c.message}
            for c in qa.checks
        ],
    }
    autopublish_run.quality_score = qa.total_score
    autopublish_run.critical_errors_count = qa.critical_errors
    autopublish_run.failure_reasons = list(qa.failure_reasons)

    would_publish = qa_passes_for_publish(qa, settings)
    autopublish_run.would_publish = would_publish

    if not would_publish:
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.QA_FAILED
        autopublish_run.save()
        touch_autopublish_last_run()
        return autopublish_run

    autopublish_run.status = SystematicArticleAutoPublishRun.Status.READY_TO_PUBLISH
    autopublish_run.save(update_fields=['status', 'qa_report', 'quality_score', 'critical_errors_count', 'failure_reasons', 'would_publish', 'updated_at'])

    if shadow or publish_mode == SystematicArticleAutoPublishRun.PublishMode.SHADOW:
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW
        autopublish_run.failure_reasons = []
        autopublish_run.save(update_fields=['status', 'failure_reasons', 'updated_at'])
        touch_autopublish_last_run()
        return autopublish_run

    if _daily_publish_count(run_date) >= settings.max_daily_publish:
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW
        autopublish_run.failure_reasons = ['سقف انتشار روزانه پر شده است.']
        autopublish_run.save()
        touch_autopublish_last_run()
        return autopublish_run

    is_update = decision.action == PublishAction.UPDATE_EXISTING
    try:
        post = publish_market_article_from_run(market_run, user=user, is_update=is_update)
    except Exception as exc:
        logger.exception('autopublish publish failed run=%s', market_run.pk)
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW
        autopublish_run.failure_reasons = [f'خطا در انتشار: {exc}']
        autopublish_run.save()
        touch_autopublish_last_run()
        return autopublish_run

    autopublish_run.post = post
    autopublish_run.published_at = timezone.now()
    autopublish_run.status = (
        SystematicArticleAutoPublishRun.Status.UPDATED
        if is_update
        else SystematicArticleAutoPublishRun.Status.PUBLISHED
    )
    autopublish_run.save()

    verify_report = verify_published_post(post)
    autopublish_run.post_publish_report = verify_report
    autopublish_run.post_publish_verified = verify_report.get('passed', False)
    autopublish_run.save(update_fields=['post_publish_report', 'post_publish_verified', 'updated_at'])

    touch_autopublish_last_run()
    return autopublish_run


def get_autopublish_dashboard_context() -> dict[str, Any]:
    """Context برای UI انتشار خودکار."""
    config = get_autopublish_config()
    settings = get_autopublish_settings()
    today = local_today()
    candidate = pick_best_candidate(settings)

    last_run = SystematicArticleAutoPublishRun.objects.order_by('-created_at').first()
    last_published = (
        SystematicArticleAutoPublishRun.objects.filter(status__in=_PUBLISHED_STATUSES)
        .order_by('-published_at')
        .select_related('post', 'dataset')
        .first()
    )
    last_failure = (
        SystematicArticleAutoPublishRun.objects.filter(
            status__in=(
                SystematicArticleAutoPublishRun.Status.QA_FAILED,
                SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW,
                SystematicArticleAutoPublishRun.Status.SKIPPED,
            ),
        )
        .exclude(failure_reasons=[])
        .order_by('-created_at')
        .first()
    )
    today_runs = SystematicArticleAutoPublishRun.objects.filter(run_date=today).order_by('-created_at')[:10]
    history = SystematicArticleAutoPublishRun.objects.select_related('dataset', 'post').order_by('-run_date', '-created_at')[:30]

    published_today = _daily_publish_count(today)
    today_status = 'none'
    if published_today:
        today_status = 'published'
    elif last_run and last_run.run_date == today:
        if last_run.status in (SystematicArticleAutoPublishRun.Status.QA_FAILED, SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW):
            today_status = 'needs_review'
        elif last_run.status == SystematicArticleAutoPublishRun.Status.SKIPPED:
            today_status = 'skipped'
        elif last_run.status in (
            SystematicArticleAutoPublishRun.Status.GENERATING,
            SystematicArticleAutoPublishRun.Status.QA_RUNNING,
            SystematicArticleAutoPublishRun.Status.QUEUED,
        ):
            today_status = 'running'

    if published_today >= config.max_daily_publish:
        next_run_hint = 'فردا'
    elif config.is_enabled or config.shadow_mode:
        next_run_hint = 'امروز (via cron)'
    else:
        next_run_hint = '—'

    today_labels = {
        'published': 'منتشر شد',
        'skipped': 'چیزی مناسب نبود',
        'needs_review': 'نیازمند بررسی',
        'running': 'در حال اجرا',
        'none': 'هنوز اجرا نشده',
    }

    return {
        'config': config,
        'settings': settings,
        'candidate': candidate,
        'last_run': last_run,
        'last_published': last_published,
        'last_failure': last_failure,
        'today_runs': today_runs,
        'history': history,
        'published_today': published_today,
        'today_status': today_status,
        'today_status_label': today_labels.get(today_status, '—'),
        'next_run_hint': next_run_hint,
    }
