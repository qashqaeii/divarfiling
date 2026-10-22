"""انتخاب و رتبه‌بندی کاندیدهای انتشار خودکار."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import timedelta
from typing import Any

from django.utils import timezone

from blog.models import MarketArticleLink, MarketArticleRun, SystematicArticleAutoPublishRun
from blog.services.market_article_autopublish_config import AutoPublishSettings, get_autopublish_settings, local_today
from blog.services.market_article_eligibility import (
    ARTICLE_STATUS_NONE,
    ARTICLE_STATUS_PUBLISHED,
    ARTICLE_STATUS_STALE,
    _article_status_for_dataset,
    _dominant_neighborhood,
    eligible_datasets_qs,
    market_key_for_dataset,
)
from workspace.models import Dataset


@dataclass
class AutoPublishCandidate:
    dataset_id: str
    dataset_name: str
    city: str
    district: str
    transaction_type: str
    subcategory: str
    row_count: int
    valid_count: int | None
    quality_pct: float | None
    article_status: str
    market_key: str
    opportunity_score: float
    action_hint: str
    score_breakdown: dict[str, float]
    has_direct_duplicate: bool
    freshness_days: int | None

    def to_snapshot(self) -> dict[str, Any]:
        return asdict(self)


def _latest_runs_by_dataset(dataset_ids: list) -> dict[Any, MarketArticleRun]:
    if not dataset_ids:
        return {}
    seen: set = set()
    result: dict[Any, MarketArticleRun] = {}
    for run in (
        MarketArticleRun.objects.filter(dataset_id__in=dataset_ids)
        .exclude(status=MarketArticleRun.Status.DISCARDED)
        .order_by('-created_at')
    ):
        if run.dataset_id in seen:
            continue
        seen.add(run.dataset_id)
        result[run.dataset_id] = run
    return result


def _score_candidate(
    dataset: Dataset,
    *,
    settings: AutoPublishSettings,
    article_status: str,
    link: MarketArticleLink | None,
    run: MarketArticleRun | None,
    today,
) -> AutoPublishCandidate | None:
    row_count = int(dataset.row_count or 0)
    if row_count < settings.min_records:
        return None

    valid_count = run.valid_count if run else None
    quality_pct = run.quality_pct if run else None
    valid_ratio = 1.0
    if run and valid_count is not None and row_count:
        valid_ratio = valid_count / row_count
        if valid_ratio < settings.min_valid_ratio:
            return None
    elif quality_pct is not None:
        valid_ratio = quality_pct / 100.0
        if valid_ratio < settings.min_valid_ratio:
            return None
    effective_valid = valid_count if valid_count is not None else row_count

    updated_at = dataset.updated_at
    freshness_days = None
    if updated_at:
        freshness_days = (today - timezone.localtime(updated_at).date()).days
        if freshness_days > settings.max_dataset_age_days:
            return None

    market_key = market_key_for_dataset(dataset)
    has_direct_duplicate = bool(link and link.post_id and link.post.is_published)

    if article_status == ARTICLE_STATUS_PUBLISHED and not (
        link and link.last_generated_at and dataset.updated_at and dataset.updated_at > link.last_generated_at
    ):
        return None

    if run and run.status == MarketArticleRun.Status.BUILDING:
        return None

    breakdown: dict[str, float] = {}
    breakdown['records'] = min(30.0, (effective_valid / max(settings.min_records, 1)) * 15.0)
    breakdown['quality'] = min(25.0, (quality_pct or (valid_ratio * 100)) * 0.25)
    breakdown['freshness'] = max(0.0, 15.0 - (freshness_days or 0) * 0.15) if freshness_days is not None else 10.0

    if article_status == ARTICLE_STATUS_NONE:
        breakdown['coverage'] = 20.0
        action_hint = 'create_new'
    elif article_status == ARTICLE_STATUS_STALE:
        breakdown['coverage'] = 15.0
        action_hint = 'update_existing'
    elif article_status == ARTICLE_STATUS_PUBLISHED:
        breakdown['coverage'] = 8.0
        action_hint = 'update_existing'
    else:
        breakdown['coverage'] = 5.0
        action_hint = 'skip'

    if has_direct_duplicate and article_status == ARTICLE_STATUS_NONE:
        return None

    breakdown['richness'] = min(10.0, (run.confidence_score or 50) / 10.0) if run else 5.0
    opportunity_score = round(sum(breakdown.values()), 1)

    district = (dataset.district or '').strip() or _dominant_neighborhood(dataset) or 'کل شهر'

    return AutoPublishCandidate(
        dataset_id=str(dataset.pk),
        dataset_name=dataset.name,
        city=dataset.city or '—',
        district=district,
        transaction_type=dataset.transaction_type or '—',
        subcategory=dataset.subcategory or '—',
        row_count=row_count,
        valid_count=valid_count,
        quality_pct=quality_pct,
        article_status=article_status,
        market_key=market_key,
        opportunity_score=opportunity_score,
        action_hint=action_hint,
        score_breakdown=breakdown,
        has_direct_duplicate=has_direct_duplicate,
        freshness_days=freshness_days,
    )


def _dataset_ids_in_active_autopublish() -> set:
    active = (
        SystematicArticleAutoPublishRun.Status.QUEUED,
        SystematicArticleAutoPublishRun.Status.GENERATING,
        SystematicArticleAutoPublishRun.Status.AI_POLISHING,
        SystematicArticleAutoPublishRun.Status.QA_RUNNING,
        SystematicArticleAutoPublishRun.Status.READY_TO_PUBLISH,
    )
    return set(
        SystematicArticleAutoPublishRun.objects.filter(status__in=active)
        .exclude(dataset_id__isnull=True)
        .values_list('dataset_id', flat=True),
    )


def rank_autopublish_candidates(
    settings: AutoPublishSettings | None = None,
    *,
    limit: int = 20,
) -> list[AutoPublishCandidate]:
    settings = settings or get_autopublish_settings()

    today = local_today()
    in_flight_ids = _dataset_ids_in_active_autopublish()
    qs = eligible_datasets_qs().filter(row_count__gte=settings.min_records).order_by('-updated_at')[:500]
    datasets = [d for d in qs if d.pk not in in_flight_ids]

    keys = [market_key_for_dataset(d) for d in datasets]
    links = {
        link.market_key: link
        for link in MarketArticleLink.objects.filter(market_key__in=keys).select_related('post')
    }
    runs = _latest_runs_by_dataset([d.pk for d in datasets])

    candidates: list[AutoPublishCandidate] = []
    for dataset in datasets:
        market_key = market_key_for_dataset(dataset)
        link = links.get(market_key)
        run = runs.get(dataset.pk)
        status, _, _ = _article_status_for_dataset(
            dataset,
            links_by_key=links,
            runs_by_dataset=runs,
        )
        scored = _score_candidate(
            dataset,
            settings=settings,
            article_status=status,
            link=link,
            run=run,
            today=today,
        )
        if scored and scored.action_hint != 'skip':
            candidates.append(scored)

    candidates.sort(key=lambda c: c.opportunity_score, reverse=True)
    return candidates[:limit]


def pick_best_candidate(settings: AutoPublishSettings | None = None) -> AutoPublishCandidate | None:
    ranked = rank_autopublish_candidates(settings, limit=1)
    return ranked[0] if ranked else None
