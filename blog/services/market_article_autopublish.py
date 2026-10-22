"""اجرای انتشار خودکار مقالات سیستماتیک."""
from __future__ import annotations

import logging
import time
from dataclasses import asdict
from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from blog.models import (
    MarketArticleRun,
    Post,
    SystematicArticleAutoPublishConfig,
    SystematicArticleAutoPublishRun,
)
from blog.services.market_article_ai_polish import (
    AIPolishError,
    AIPolishJsonError,
    AIPolishRecoverableError,
    finalize_polish_resume_state,
    polish_failure_snapshot,
    polish_market_article_run,
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
from blog.services.market_article_data_readiness import MarketArticleDataInsufficient
from blog.services.market_article_pipeline import (
    build_preview_for_autopublish,
    create_draft,
    get_existing_link,
    update_existing_post,
)
from blog.services.market_article_post_publish import verify_published_post
from blog.services.market_article_publish_decision import PublishAction, decide_publish_action
from blog.services.market_article_numeric_truth import assess_data_consistency
from blog.services.market_article_qa_remediation import remediate_unverified_numeric_sentences
from blog.services.market_article_quality_gates import (
    QAReport,
    critical_pre_polish_data_failures,
    find_unverified_numeric_claims,
    qa_passes_for_publish,
    run_quality_gates,
)

User = get_user_model()
logger = logging.getLogger(__name__)

STUCK_RUN_MAX_HOURS = 6
MAX_POLISH_RETRIES = 2
MAX_QA_AUTO_FIX_ATTEMPTS = 2
POLISH_RETRY_BACKOFF_SECONDS = 2.0
_PRE_POLISH_SNAPSHOT_KEY = 'autopublish_pre_polish_snapshot'

_ACTIVE_STATUSES = (
    SystematicArticleAutoPublishRun.Status.QUEUED,
    SystematicArticleAutoPublishRun.Status.GENERATING,
    SystematicArticleAutoPublishRun.Status.AI_POLISHING,
    SystematicArticleAutoPublishRun.Status.QA_RUNNING,
    SystematicArticleAutoPublishRun.Status.READY_TO_PUBLISH,
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


def append_autopublish_step(
    run: SystematicArticleAutoPublishRun,
    step: str,
    *,
    detail: str = '',
    extra: dict[str, Any] | None = None,
    save: bool = True,
) -> None:
    history = list(run.step_history or [])
    entry: dict[str, Any] = {
        'step': step,
        'at': timezone.now().isoformat(),
        'detail': detail,
    }
    if extra:
        entry.update(extra)
    history.append(entry)
    run.step_history = history
    if save:
        run.save(update_fields=['step_history', 'updated_at'])


def recover_stuck_autopublish_runs(*, max_age_hours: int = STUCK_RUN_MAX_HOURS) -> int:
    """اجراهای فعال قدیمی را به needs_review منتقل می‌کند — جلوگیری از قفل دائمی."""
    cutoff = timezone.now() - timedelta(hours=max(1, max_age_hours))
    qs = SystematicArticleAutoPublishRun.objects.filter(
        status__in=_ACTIVE_STATUSES,
        updated_at__lt=cutoff,
    )
    recovered = 0
    for run in qs.iterator():
        append_autopublish_step(
            run,
            'recovered_stuck',
            detail=f'بازیابی پس از {max_age_hours} ساعت بی‌حرکتی',
            extra={'previous_status': run.status},
            save=False,
        )
        run.status = SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW
        reasons = list(run.failure_reasons or [])
        reasons.append(
            f'اجرای متوقف‌شده ({run.get_status_display()}) پس از {max_age_hours} ساعت بازیابی شد.',
        )
        run.failure_reasons = reasons
        run.save(update_fields=['status', 'failure_reasons', 'step_history', 'updated_at'])
        recovered += 1
        logger.warning('autopublish recovered stuck run=%s status was active', run.pk)
    return recovered


def _should_run_for_schedule(config: SystematicArticleAutoPublishConfig, *, force: bool) -> bool:
    if force:
        return True
    publish_time = config.publish_time
    if not publish_time:
        return True
    now_local = timezone.localtime()
    if now_local.time() < publish_time:
        return False
    return True


def compute_next_run_hint(config: SystematicArticleAutoPublishConfig) -> str:
    if not config.is_enabled and not config.shadow_mode:
        return '—'
    today = local_today()
    if _daily_publish_count(today) >= max(1, config.max_daily_publish):
        return 'فردا (سقف امروز پر شده)'
    now_local = timezone.localtime()
    pt = config.publish_time
    if pt and now_local.time() < pt:
        return f'امروز ساعت {pt.strftime("%H:%M")} (Asia/Tehran)'
    return 'امروز (systemd timer)'


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


def _qa_to_dict(qa: QAReport) -> dict[str, Any]:
    return {
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


def _snapshot_pre_polish_content(market_run: MarketArticleRun) -> None:
    assets = dict(market_run.chart_assets or {})
    if _PRE_POLISH_SNAPSHOT_KEY in assets:
        return
    assets[_PRE_POLISH_SNAPSHOT_KEY] = {
        'content_html': market_run.content_html,
        'seo_json': dict(market_run.seo_json or {}),
    }
    market_run.chart_assets = assets
    market_run.save(update_fields=['chart_assets', 'updated_at'])


def _stop_for_data_quality(
    autopublish_run: SystematicArticleAutoPublishRun,
    *,
    reasons: list[str],
    market_run: MarketArticleRun | None = None,
    qa: QAReport | None = None,
    step: str = 'data_quality_failed',
) -> SystematicArticleAutoPublishRun:
    autopublish_run.status = SystematicArticleAutoPublishRun.Status.DATA_QUALITY_FAILED
    autopublish_run.failure_reasons = reasons
    autopublish_run.critical_errors_count = len(reasons)
    autopublish_run.would_publish = False
    if market_run:
        autopublish_run.market_article_run = market_run
    _attach_final_summary(autopublish_run, qa=qa, publish_result='data_quality_failed')
    append_autopublish_step(autopublish_run, step, detail='; '.join(reasons)[:400])
    autopublish_run.save()
    touch_autopublish_last_run()
    return autopublish_run


def _restore_pre_polish_content(market_run: MarketArticleRun) -> bool:
    assets = dict(market_run.chart_assets or {})
    snap = assets.get(_PRE_POLISH_SNAPSHOT_KEY)
    if not isinstance(snap, dict):
        return False
    market_run.content_html = snap.get('content_html') or ''
    market_run.seo_json = snap.get('seo_json') or {}
    market_run.save(update_fields=['content_html', 'seo_json', 'updated_at'])
    return True


def _attach_final_summary(
    autopublish_run: SystematicArticleAutoPublishRun,
    *,
    qa: QAReport | None,
    publish_result: str,
) -> None:
    polish = autopublish_run.ai_polish_report if isinstance(autopublish_run.ai_polish_report, dict) else {}
    existing = autopublish_run.qa_report if isinstance(autopublish_run.qa_report, dict) else {}
    autopublish_run.qa_report = {
        **existing,
        'summary': {
            'qa_score': qa.total_score if qa else existing.get('total_score'),
            'qa_critical_errors': qa.critical_errors if qa else existing.get('critical_errors'),
            'polish_ok': polish.get('ok'),
            'fallback_ratio': polish.get('fallback_ratio'),
            'polish_provider': polish.get('provider'),
            'publish_result': publish_result,
            'would_publish': autopublish_run.would_publish,
        },
    }


def _run_post_polish_qa_with_remediation(
    autopublish_run: SystematicArticleAutoPublishRun,
    market_run: MarketArticleRun,
    settings,
) -> tuple[bool, QAReport | None]:
    qa: QAReport | None = None
    inconsistency = assess_data_consistency(market_run)
    if inconsistency:
        qa = run_quality_gates(market_run, settings)
        autopublish_run.failure_reasons = [f'داده ناسازگار: {inconsistency[0]}']
        append_autopublish_step(
            autopublish_run,
            'qa_data_inconsistent',
            detail=inconsistency[0],
        )
        return False, qa

    for attempt in range(MAX_QA_AUTO_FIX_ATTEMPTS + 1):
        qa = run_quality_gates(market_run, settings)
        if qa_passes_for_publish(qa, settings):
            if attempt:
                append_autopublish_step(
                    autopublish_run,
                    'qa_auto_remediate_ok',
                    detail=f'attempt={attempt}',
                )
            return True, qa

        unverified = find_unverified_numeric_claims(market_run)
        numeric_failed = any(
            c.key == 'data_numeric_claims' and not c.passed for c in qa.checks
        )
        if not numeric_failed or not unverified or attempt >= MAX_QA_AUTO_FIX_ATTEMPTS:
            break
        if not remediate_unverified_numeric_sentences(market_run, unverified):
            break
        append_autopublish_step(
            autopublish_run,
            'qa_auto_remediate',
            detail=f'attempt={attempt + 1} tokens={len(unverified)}',
        )

    return False, qa


def _store_pre_polish_qa(autopublish_run: SystematicArticleAutoPublishRun, qa: QAReport) -> None:
    existing = autopublish_run.qa_report if isinstance(autopublish_run.qa_report, dict) else {}
    autopublish_run.qa_report = {
        **existing,
        'pre_polish': _qa_to_dict(qa),
    }


def _apply_qa_to_run(autopublish_run: SystematicArticleAutoPublishRun, qa: QAReport, settings) -> bool:
    existing = autopublish_run.qa_report if isinstance(autopublish_run.qa_report, dict) else {}
    post = _qa_to_dict(qa)
    autopublish_run.qa_report = {**existing, **post, 'post_polish': post}
    autopublish_run.quality_score = qa.total_score
    autopublish_run.critical_errors_count = qa.critical_errors
    autopublish_run.failure_reasons = list(qa.failure_reasons)
    would_publish = qa_passes_for_publish(qa, settings)
    autopublish_run.would_publish = would_publish
    return would_publish


def _duplicate_publish_blocked(
    market_run: MarketArticleRun,
    decision_action: str,
    run_date,
    *,
    exclude_run_id=None,
) -> str | None:
    """جلوگیری از انتشار تکراری همان بازار در یک روز یا ساخت دوباره."""
    link = get_existing_link(market_run.market_key)
    seo = market_run.seo_json or {}
    slug = (seo.get('slug') or market_run.market_key or '').strip()

    if decision_action == PublishAction.CREATE_NEW:
        if link and link.post_id:
            return 'مقاله برای این کلید بازار از قبل وجود دارد.'
        if slug and Post.objects.filter(slug=slug).exists():
            return f'اسلاگ «{slug}» قبلاً استفاده شده است.'

    already_today = SystematicArticleAutoPublishRun.objects.filter(
        run_date=run_date,
        status__in=_PUBLISHED_STATUSES,
        market_article_run__market_key=market_run.market_key,
    ).exists()
    if already_today:
        return 'همین بازار امروز قبلاً منتشر شده است.'

    in_flight_qs = SystematicArticleAutoPublishRun.objects.filter(
        status__in=_ACTIVE_STATUSES,
        candidate_snapshot__market_key=market_run.market_key,
    )
    if exclude_run_id:
        in_flight_qs = in_flight_qs.exclude(pk=exclude_run_id)
    in_flight = in_flight_qs.exists()
    if in_flight:
        return 'اجرای دیگری برای همین بازار در حال انجام است.'

    return None


def publish_market_article_from_run(
    run: MarketArticleRun,
    *,
    user=None,
    is_update: bool = False,
) -> Post:
    """انتشار واقعی — reuse create_draft/update سپس is_published=True."""
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


def _run_ai_polish_with_retries(
    autopublish_run: SystematicArticleAutoPublishRun,
    market_run: MarketArticleRun,
) -> bool:
    autopublish_run.status = SystematicArticleAutoPublishRun.Status.AI_POLISHING
    autopublish_run.save(update_fields=['status', 'updated_at'])
    append_autopublish_step(autopublish_run, 'ai_polish_start', detail='شروع پولیش AI')

    attempts = 0
    last_error = ''
    last_recoverable = False
    while attempts < MAX_POLISH_RETRIES:
        attempts += 1
        try:
            result = polish_market_article_run(market_run, resume=True)
            autopublish_run.ai_polish_report = {
                **result.report,
                'attempts': attempts,
            }
            autopublish_run.retry_count = max(0, attempts - 1)
            append_autopublish_step(
                autopublish_run,
                'ai_polish_done',
                detail=f'{result.provider} / {result.model}',
                extra={'latency_ms': result.latency_ms},
            )
            autopublish_run.save(update_fields=['ai_polish_report', 'retry_count', 'updated_at'])
            return True
        except (AIPolishRecoverableError, AIPolishJsonError) as exc:
            last_error = str(exc)
            last_recoverable = True
            logger.warning('autopublish ai polish recoverable attempt=%s run=%s', attempts, autopublish_run.pk)
            autopublish_run.retry_count = attempts
            append_autopublish_step(
                autopublish_run,
                'ai_polish_retry',
                detail=last_error,
                extra={'attempt': attempts, 'kind': type(exc).__name__},
            )
            autopublish_run.save(update_fields=['retry_count', 'updated_at'])
            time.sleep(min(30.0, POLISH_RETRY_BACKOFF_SECONDS * (2 ** (attempts - 1))))
            continue
        except AIPolishError as exc:
            last_error = str(exc)
            last_recoverable = False
            break

    failed_report = autopublish_run.ai_polish_report if isinstance(autopublish_run.ai_polish_report, dict) else {}
    progress = polish_failure_snapshot(market_run)
    autopublish_run.status = SystematicArticleAutoPublishRun.Status.AI_POLISH_FAILED
    autopublish_run.ai_polish_report = {
        **failed_report,
        **progress,
        'ok': False,
        'error': last_error,
        'attempts': attempts,
        'recoverable': last_recoverable,
    }
    autopublish_run.failure_reasons = [f'پولیش AI ناموفق: {last_error}']
    append_autopublish_step(autopublish_run, 'ai_polish_failed', detail=last_error)
    autopublish_run.save()
    return False


def run_systematic_article_autopublish(
    *,
    shadow: bool = False,
    dry_run: bool = False,
    force: bool = False,
    recover_stuck: bool = True,
) -> SystematicArticleAutoPublishRun:
    """اجرای روزانه انتشار خودکار."""
    run_date = local_today()
    settings = get_autopublish_settings()
    publish_mode = _resolve_publish_mode(shadow=shadow, dry_run=dry_run)

    if recover_stuck and not dry_run:
        recover_stuck_autopublish_runs()

    config = get_autopublish_config()

    if not dry_run and not _should_run_for_schedule(config, force=force):
        raise AutoPublishBlocked(
            f'هنوز زمان ترجیحی اجرا ({config.publish_time}) نرسیده است.',
        )

    if not dry_run:
        _acquire_run_lock(run_date)

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
    append_autopublish_step(autopublish_run, 'candidate_selected', detail=candidate.market_key if candidate else 'none')

    if not candidate:
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.SKIPPED
        autopublish_run.failure_reasons = ['امروز هیچ Dataset مناسبی برای انتشار خودکار یافت نشد.']
        autopublish_run.save(update_fields=['status', 'failure_reasons', 'updated_at'])
        touch_autopublish_last_run()
        return autopublish_run

    from workspace.models import Dataset

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
    append_autopublish_step(autopublish_run, 'generating', detail=dataset.name)

    user = _system_user()
    try:
        market_run = build_preview_for_autopublish(dataset, user)
    except MarketArticleDataInsufficient as exc:
        logger.warning('autopublish data quality blocked dataset=%s: %s', dataset.pk, exc.reason)
        failed_run = (
            MarketArticleRun.objects.filter(dataset=dataset)
            .order_by('-created_at')
            .first()
        )
        return _stop_for_data_quality(
            autopublish_run,
            reasons=[f'✗ {exc.reason}'],
            market_run=failed_run,
            step='data_quality_failed_build',
        )
    except Exception as exc:
        logger.exception('autopublish build failed dataset=%s', dataset.pk)
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW
        autopublish_run.failure_reasons = [f'خطا در ساخت مقاله: {exc}']
        autopublish_run.market_article_run = None
        append_autopublish_step(autopublish_run, 'generate_failed', detail=str(exc)[:200])
        autopublish_run.save()
        touch_autopublish_last_run()
        return autopublish_run

    autopublish_run.market_article_run = market_run
    append_autopublish_step(autopublish_run, 'generated', detail=str(market_run.pk))

    return _pipeline_after_market_preview(
        autopublish_run,
        market_run,
        decision,
        settings=settings,
        publish_mode=publish_mode,
        shadow=shadow,
        run_date=run_date,
        user=user,
    )


def _pipeline_after_market_preview(
    autopublish_run: SystematicArticleAutoPublishRun,
    market_run: MarketArticleRun,
    decision,
    *,
    settings,
    publish_mode: str,
    shadow: bool,
    run_date,
    user,
) -> SystematicArticleAutoPublishRun:
    """ادامه pipeline پس از داشتن MarketArticleRun — بدون ساخت مجدد."""
    dup_reason = _duplicate_publish_blocked(
        market_run,
        decision.action,
        run_date,
        exclude_run_id=autopublish_run.pk,
    )
    if dup_reason:
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.SKIPPED
        autopublish_run.failure_reasons = [dup_reason]
        append_autopublish_step(autopublish_run, 'duplicate_blocked', detail=dup_reason)
        autopublish_run.save()
        touch_autopublish_last_run()
        return autopublish_run

    pre_qa = run_quality_gates(market_run, settings)
    _store_pre_polish_qa(autopublish_run, pre_qa)
    autopublish_run.save(update_fields=['qa_report', 'updated_at'])
    append_autopublish_step(
        autopublish_run,
        'qa_pre_polish',
        detail=f'score={pre_qa.total_score} critical={pre_qa.critical_errors}',
    )

    data_failures = critical_pre_polish_data_failures(pre_qa)
    if data_failures:
        return _stop_for_data_quality(
            autopublish_run,
            reasons=data_failures,
            market_run=market_run,
            qa=pre_qa,
            step='data_quality_failed',
        )

    _snapshot_pre_polish_content(market_run)
    if not _run_ai_polish_with_retries(autopublish_run, market_run):
        touch_autopublish_last_run()
        return autopublish_run

    autopublish_run.status = SystematicArticleAutoPublishRun.Status.QA_RUNNING
    autopublish_run.save(update_fields=['status', 'updated_at'])
    append_autopublish_step(autopublish_run, 'qa_start', detail='کنترل کیفیت نهایی پس از پولیش')

    would_publish, qa = _run_post_polish_qa_with_remediation(
        autopublish_run,
        market_run,
        settings,
    )
    if qa:
        _apply_qa_to_run(autopublish_run, qa, settings)

    if not would_publish:
        restored = _restore_pre_polish_content(market_run)
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.QA_FAILED
        append_autopublish_step(
            autopublish_run,
            'qa_failed',
            detail=f'score={qa.total_score if qa else 0} restored={restored}',
        )
        _attach_final_summary(autopublish_run, qa=qa, publish_result='qa_failed')
        autopublish_run.save()
        touch_autopublish_last_run()
        return autopublish_run

    finalize_polish_resume_state(market_run)
    assets = dict(market_run.chart_assets or {})
    assets.pop(_PRE_POLISH_SNAPSHOT_KEY, None)
    market_run.chart_assets = assets
    market_run.save(update_fields=['chart_assets', 'updated_at'])

    autopublish_run.status = SystematicArticleAutoPublishRun.Status.READY_TO_PUBLISH
    append_autopublish_step(autopublish_run, 'qa_passed', detail=f'score={qa.total_score}')
    _attach_final_summary(autopublish_run, qa=qa, publish_result='qa_passed')
    autopublish_run.save(
        update_fields=[
            'status', 'qa_report', 'quality_score', 'critical_errors_count',
            'failure_reasons', 'would_publish', 'updated_at',
        ],
    )

    if shadow or publish_mode == SystematicArticleAutoPublishRun.PublishMode.SHADOW:
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW
        autopublish_run.failure_reasons = []
        _attach_final_summary(autopublish_run, qa=qa, publish_result='shadow_ok')
        append_autopublish_step(autopublish_run, 'shadow_stop', detail='بدون انتشار واقعی')
        autopublish_run.save(update_fields=['status', 'failure_reasons', 'qa_report', 'updated_at'])
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
        append_autopublish_step(autopublish_run, 'publish_failed', detail=str(exc)[:200])
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
    append_autopublish_step(autopublish_run, 'published', detail=post.slug)
    autopublish_run.save()

    verify_report = verify_published_post(post)
    autopublish_run.post_publish_report = verify_report
    autopublish_run.post_publish_verified = verify_report.get('passed', False)
    autopublish_run.save(update_fields=['post_publish_report', 'post_publish_verified', 'updated_at'])

    touch_autopublish_last_run()
    return autopublish_run


def resume_systematic_article_autopublish(
    *,
    market_article_run_id,
    autopublish_run_id=None,
    shadow: bool = False,
    force: bool = False,
    recover_stuck: bool = True,
) -> SystematicArticleAutoPublishRun:
    """
    ادامه از MarketArticleRun موجود — بدون build_preview (نقشه/نمودار دوباره ساخته نمی‌شود).
    پیشرفت پولیش از chart_assets.autopublish_polish_state خوانده می‌شود.
    """
    run_date = local_today()
    settings = get_autopublish_settings()
    publish_mode = _resolve_publish_mode(shadow=shadow, dry_run=False)

    if recover_stuck:
        recover_stuck_autopublish_runs()

    config = get_autopublish_config()
    if not _should_run_for_schedule(config, force=force):
        raise AutoPublishBlocked(f'هنوز زمان ترجیحی اجرا ({config.publish_time}) نرسیده است.')

    market_run = MarketArticleRun.objects.select_related('dataset').filter(pk=market_article_run_id).first()
    if not market_run:
        raise AutoPublishBlocked('MarketArticleRun یافت نشد.')
    if market_run.status not in (
        MarketArticleRun.Status.PREVIEW,
        MarketArticleRun.Status.DRAFT_LINKED,
    ):
        raise AutoPublishBlocked(f'وضعیت MarketArticleRun برای Resume مناسب نیست: {market_run.status}')
    if not (market_run.content_html or '').strip():
        raise AutoPublishBlocked('محتوای HTML پیش‌نمایش خالی است.')

    dataset = market_run.dataset
    if not dataset or not dataset.is_active:
        raise AutoPublishBlocked('دیتاست منبع غیرفعال است.')

    if publish_mode == SystematicArticleAutoPublishRun.PublishMode.LIVE:
        if not config.is_enabled and not force:
            raise AutoPublishBlocked('انتشار خودکار غیرفعال است.')
        if config.shadow_mode and not force:
            publish_mode = SystematicArticleAutoPublishRun.PublishMode.SHADOW
            shadow = True

    user = _system_user()
    decision = decide_publish_action(dataset, None)

    if autopublish_run_id:
        autopublish_run = SystematicArticleAutoPublishRun.objects.filter(pk=autopublish_run_id).first()
        if not autopublish_run:
            raise AutoPublishBlocked('AutoPublishRun یافت نشد.')
        autopublish_run.market_article_run = market_run
        autopublish_run.dataset = dataset
        autopublish_run.failure_reasons = []
        autopublish_run.status = SystematicArticleAutoPublishRun.Status.GENERATING
        autopublish_run.publish_mode = publish_mode
        autopublish_run.save()
    else:
        if not force:
            _acquire_run_lock(run_date)
        autopublish_run = SystematicArticleAutoPublishRun.objects.create(
            run_date=run_date,
            status=SystematicArticleAutoPublishRun.Status.GENERATING,
            publish_mode=publish_mode,
            dataset=dataset,
            market_article_run=market_run,
            action=decision.action,
            candidate_snapshot={'market_key': market_run.market_key, 'resume': True},
        )

    append_autopublish_step(
        autopublish_run,
        'resume_market_run',
        detail=str(market_run.pk),
        extra={'autopublish_run_id': str(autopublish_run.pk)},
    )

    return _pipeline_after_market_preview(
        autopublish_run,
        market_run,
        decision,
        settings=settings,
        publish_mode=publish_mode,
        shadow=shadow,
        run_date=run_date,
        user=user,
    )


def get_autopublish_dashboard_context() -> dict[str, Any]:
    """Context برای UI انتشار خودکار."""
    config = get_autopublish_config()
    settings = get_autopublish_settings()
    today = local_today()
    candidate = pick_best_candidate(settings)

    last_run = SystematicArticleAutoPublishRun.objects.order_by('-created_at').first()
    last_success = (
        SystematicArticleAutoPublishRun.objects.filter(
            Q(status__in=_PUBLISHED_STATUSES)
            | Q(
                status=SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW,
                would_publish=True,
            ),
        )
        .order_by('-created_at')
        .select_related('post', 'dataset')
        .first()
    )
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
                SystematicArticleAutoPublishRun.Status.AI_POLISH_FAILED,
                SystematicArticleAutoPublishRun.Status.DATA_QUALITY_FAILED,
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
        if last_run.status in (
            SystematicArticleAutoPublishRun.Status.QA_FAILED,
            SystematicArticleAutoPublishRun.Status.AI_POLISH_FAILED,
            SystematicArticleAutoPublishRun.Status.DATA_QUALITY_FAILED,
            SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW,
        ):
            today_status = 'needs_review'
        elif last_run.status == SystematicArticleAutoPublishRun.Status.SKIPPED:
            today_status = 'skipped'
        elif last_run.status in _ACTIVE_STATUSES:
            today_status = 'running'

    next_run_hint = compute_next_run_hint(config)

    today_labels = {
        'published': 'منتشر شد',
        'skipped': 'چیزی مناسب نبود',
        'needs_review': 'نیازمند بررسی',
        'running': 'در حال اجرا',
        'none': 'هنوز اجرا نشده',
    }

    ai_polish_status = '—'
    if last_run and last_run.ai_polish_report:
        report = last_run.ai_polish_report
        if report.get('ok'):
            ai_polish_status = f'موفق ({report.get("provider") or "AI"})'
        else:
            ai_polish_status = f'ناموفق: {(report.get("error") or "")[:80]}'

    return {
        'config': config,
        'settings': settings,
        'candidate': candidate,
        'last_run': last_run,
        'last_success': last_success,
        'last_published': last_published,
        'last_failure': last_failure,
        'today_runs': today_runs,
        'history': history,
        'published_today': published_today,
        'today_status': today_status,
        'today_status_label': today_labels.get(today_status, '—'),
        'next_run_hint': next_run_hint,
        'ai_polish_status': ai_polish_status,
        'step_history': (last_run.step_history or []) if last_run else [],
    }
