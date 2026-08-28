"""تأیید پس از انتشار مقاله سیستماتیک."""
from __future__ import annotations

import logging
import re
from typing import Any

from django.test.client import Client
from django.urls import reverse

from blog.models import Post

logger = logging.getLogger(__name__)


def _management_alert(message: str, *, context: dict[str, Any] | None = None) -> None:
    logger.error('AUTOPUBLISH_ALERT: %s | %s', message, context or {})
    try:
        from accounts.models import ManagementAutomationRule, ManagementAutomationExecution

        rule = ManagementAutomationRule.objects.filter(key='systematic_article_post_publish').first()
        if rule:
            ManagementAutomationExecution.objects.create(
                rule=rule,
                status=ManagementAutomationExecution.Status.FAILED,
                error_summary=message[:2000],
                matched_count=1,
                failed_count=1,
            )
    except Exception:
        logger.exception('failed to persist management alert')


def verify_published_post(post: Post, *, request_host: str = 'testserver') -> dict[str, Any]:
    """بررسی HTTP و محتوای منتشرشده."""
    report: dict[str, Any] = {
        'checks': [],
        'critical_errors': [],
        'passed': False,
    }

    def add_check(key: str, ok: bool, msg: str, *, critical: bool = False) -> None:
        report['checks'].append({'key': key, 'ok': ok, 'message': msg})
        if not ok and critical:
            report['critical_errors'].append(msg)

    add_check('post_exists', bool(post.pk), 'Post exists', critical=True)
    add_check('published_flag', post.is_published, 'is_published=True', critical=True)
    add_check('title', bool((post.title or '').strip()), 'Title present', critical=True)
    add_check('excerpt', bool((post.excerpt or '').strip()), 'Meta/excerpt present', critical=False)
    add_check('content', bool((post.content or '').strip()), 'Content non-empty', critical=True)
    add_check('featured', bool(post.featured_image and post.featured_image.name), 'Featured image', critical=True)

    client = Client()
    try:
        url = post.get_absolute_url()
        resp = client.get(url, HTTP_HOST=request_host)
        add_check('http_200', resp.status_code == 200, f'HTTP {resp.status_code}', critical=True)
        body = resp.content.decode('utf-8', errors='ignore')
        add_check('title_in_page', post.title[:40] in body, 'Title in rendered page', critical=True)
        if post.featured_image:
            img_fragment = post.featured_image.url.split('/')[-1][:20]
            add_check('featured_loads', img_fragment in body or post.featured_image.url in body, 'Featured in page', critical=True)
        add_check('schema_article', 'Article' in body or 'article' in body.lower(), 'Schema/article markup', critical=False)
        broken = len(re.findall(r'src=["\'][^"\']*placeholder', body, re.I))
        add_check('no_broken_img', broken == 0, f'{broken} broken images', critical=True)
    except Exception as exc:
        add_check('http_fetch', False, f'Fetch failed: {exc}', critical=True)

    report['passed'] = len(report['critical_errors']) == 0
    if not report['passed']:
        _management_alert(
            f'Post-publish verification failed for post {post.pk}',
            context={'post_id': post.pk, 'errors': report['critical_errors']},
        )
    return report
