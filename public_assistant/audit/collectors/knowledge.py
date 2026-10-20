"""ممیزی مقالات دانشنامه از فایل Markdown."""
from __future__ import annotations

from typing import Any

from public_assistant.audit.paths import knowledge_articles_dir
from public_assistant.services.knowledge_loader import parse_markdown_file


def collect_knowledge_articles() -> list[dict[str, Any]]:
    root = knowledge_articles_dir()
    items: list[dict[str, Any]] = []
    if not root.is_dir():
        return items
    for path in sorted(root.glob('*.md')):
        parsed = parse_markdown_file(path)
        meta = parsed.meta
        body = parsed.body
        headings = [line[3:].strip() for line in body.splitlines() if line.startswith('## ')]
        items.append(
            {
                'article_id': str(meta['id']),
                'title': meta['title'],
                'category': meta['category'],
                'platforms': meta.get('platforms') or [],
                'synonyms': meta.get('synonyms') or [],
                'technical_refs': list(meta.get('technical_refs') or meta.get('sources') or []),
                'prerequisites': meta.get('prerequisites') or '',
                'limitations': meta.get('limitations') or '',
                'reviewed_at': meta.get('reviewed_at'),
                'headings': headings,
                'body_length': len(body),
                'source_path': parsed.source_path,
            }
        )
    return items
