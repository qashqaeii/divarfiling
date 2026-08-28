"""تصمیم CREATE / UPDATE / SKIP برای انتشار خودکار."""
from __future__ import annotations

from dataclasses import dataclass

from blog.models import MarketArticleLink
from blog.services.market_article_candidate_selection import AutoPublishCandidate
from blog.services.market_article_eligibility import (
    ARTICLE_STATUS_DRAFT,
    ARTICLE_STATUS_NONE,
    ARTICLE_STATUS_PUBLISHED,
    ARTICLE_STATUS_READY,
    ARTICLE_STATUS_STALE,
)
from blog.services.market_article_pipeline import get_existing_link
from workspace.models import Dataset


class PublishAction:
    CREATE_NEW = 'create_new'
    UPDATE_EXISTING = 'update_existing'
    SKIP = 'skip'


@dataclass
class PublishDecision:
    action: str
    reason: str
    existing_link: MarketArticleLink | None = None
    preserve_slug: bool = False


def decide_publish_action(
    dataset: Dataset,
    candidate: AutoPublishCandidate | None = None,
) -> PublishDecision:
    from blog.services.market_article_eligibility import market_key_for_dataset

    market_key = market_key_for_dataset(dataset)
    link = get_existing_link(market_key)

    if link and link.post_id:
        post = link.post
        stale = False
        if link.last_generated_at and dataset.updated_at and dataset.updated_at > link.last_generated_at:
            stale = True

        if post.is_published and not stale:
            return PublishDecision(
                action=PublishAction.SKIP,
                reason='مقاله منتشرشده و دیتاست جدیدتر نیست.',
                existing_link=link,
                preserve_slug=True,
            )

        return PublishDecision(
            action=PublishAction.UPDATE_EXISTING,
            reason='Intent مشابه قبلاً مقاله دارد؛ به‌روزرسانی مناسب است.',
            existing_link=link,
            preserve_slug=True,
        )

    if candidate and candidate.article_status in (
        ARTICLE_STATUS_DRAFT,
        ARTICLE_STATUS_READY,
    ):
        return PublishDecision(
            action=PublishAction.SKIP,
            reason='پیش‌نویس/پیش‌نمایش موجود نیازمند بررسی دستی است.',
            existing_link=link,
        )

    if candidate and candidate.has_direct_duplicate:
        return PublishDecision(
            action=PublishAction.SKIP,
            reason='مقاله مشابه مستقیم وجود دارد.',
            existing_link=link,
        )

    if candidate and candidate.article_status == ARTICLE_STATUS_NONE:
        return PublishDecision(
            action=PublishAction.CREATE_NEW,
            reason='موضوع جدید بدون مقاله موجود.',
            existing_link=None,
        )

    if candidate and candidate.article_status in (ARTICLE_STATUS_STALE, ARTICLE_STATUS_PUBLISHED):
        if link:
            return PublishDecision(
                action=PublishAction.UPDATE_EXISTING,
                reason='داده جدید برای به‌روزرسانی مقاله موجود.',
                existing_link=link,
                preserve_slug=True,
            )

    return PublishDecision(
        action=PublishAction.CREATE_NEW,
        reason='ساخت مقاله جدید.',
        existing_link=None,
    )
