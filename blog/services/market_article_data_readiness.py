"""بررسی کفایت داده قبل از پولیش/دارایی‌های سنگین."""
from __future__ import annotations

from django.utils import timezone

from blog.models import MarketArticleRun
from blog.services.market_article_autopublish_config import AutoPublishSettings, local_today
from blog.services.market_article_numeric_truth import assess_data_consistency
from workspace.models import Dataset


class MarketArticleDataInsufficient(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _freshness_days(dataset: Dataset) -> int | None:
    updated_at = getattr(dataset, 'updated_at', None)
    if not updated_at:
        return None
    return (local_today() - timezone.localtime(updated_at).date()).days


def data_readiness_issues(
    *,
    dataset: Dataset,
    settings: AutoPublishSettings,
    metrics: dict | None = None,
    market_run: MarketArticleRun | None = None,
) -> list[str]:
    """خطاهای غیرقابل‌اصلاح داده — بدون وابستگی به محتوای پولیش‌شده."""
    issues: list[str] = []
    row_count = int(dataset.row_count or 0)
    valid = None
    raw = None
    quality_pct = None

    if market_run is not None:
        valid = int(market_run.valid_count or 0)
        raw = int(market_run.raw_count or 0) or valid
        quality_pct = market_run.quality_pct
    if metrics:
        if metrics.get('valid_count') is not None:
            valid = int(metrics['valid_count'])
        if metrics.get('raw_count') is not None:
            raw = int(metrics['raw_count'])
        if metrics.get('quality_pct') is not None:
            quality_pct = float(metrics['quality_pct'])

    if valid is None:
        valid = 0
    if not raw:
        raw = row_count or valid

    if valid < settings.min_records:
        issues.append(
            f'{valid} رکورد معتبر (حداقل {settings.min_records})',
        )

    ratio = (valid / raw) if raw else 0.0
    pct = quality_pct if quality_pct is not None else (ratio * 100)
    if ratio < settings.min_valid_ratio:
        issues.append(f'کیفیت داده {pct:.1f}٪ (حداقل {settings.min_valid_ratio * 100:.0f}٪)')

    freshness = _freshness_days(dataset)
    if freshness is None:
        issues.append('تاریخ به‌روزرسانی دیتاست نامشخص است.')
    elif freshness > settings.max_dataset_age_days:
        issues.append(
            f'دیتاست {freshness} روز پیش به‌روز شده (حداکثر {settings.max_dataset_age_days} روز).',
        )

    if market_run is not None:
        issues.extend(assess_data_consistency(market_run))

    return issues


def assert_autopublish_data_readiness(
    *,
    dataset: Dataset,
    metrics: dict,
    settings: AutoPublishSettings,
    market_run: MarketArticleRun | None = None,
) -> None:
    issues = data_readiness_issues(
        dataset=dataset,
        settings=settings,
        metrics=metrics,
        market_run=market_run,
    )
    if issues:
        raise MarketArticleDataInsufficient(issues[0])
