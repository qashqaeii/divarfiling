"""تنظیمات singleton انتشار خودکار."""
from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from blog.models import SystematicArticleAutoPublishConfig


@dataclass(frozen=True)
class AutoPublishSettings:
    is_enabled: bool
    shadow_mode: bool
    max_daily_publish: int
    quality_threshold: int
    min_records: int
    min_valid_ratio: float
    max_dataset_age_days: int
    min_insights: int
    publish_time: object | None = None


def get_autopublish_config() -> SystematicArticleAutoPublishConfig:
    config, _ = SystematicArticleAutoPublishConfig.objects.get_or_create(pk=1)
    return config


def get_autopublish_settings() -> AutoPublishSettings:
    cfg = get_autopublish_config()
    return AutoPublishSettings(
        is_enabled=cfg.is_enabled,
        shadow_mode=cfg.shadow_mode,
        max_daily_publish=max(1, int(cfg.max_daily_publish or 1)),
        quality_threshold=int(cfg.quality_threshold or 90),
        min_records=max(100, int(cfg.min_records or 150)),
        min_valid_ratio=float(cfg.min_valid_ratio or 0.85),
        max_dataset_age_days=max(1, int(cfg.max_dataset_age_days or 90)),
        min_insights=max(1, int(cfg.min_insights or 2)),
        publish_time=cfg.publish_time,
    )


def touch_autopublish_last_run() -> None:
    SystematicArticleAutoPublishConfig.objects.filter(pk=1).update(last_run_at=timezone.now())


def local_today():
    return timezone.localdate()
