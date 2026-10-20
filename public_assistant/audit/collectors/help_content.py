"""استخراج بخش‌های راهنمای میزکار."""
from __future__ import annotations

from typing import Any


def collect_help_sections() -> list[dict[str, Any]]:
    from workspace.help_content import workspace_help_content

    data = workspace_help_content()
    out: list[dict[str, Any]] = []
    for guide in data.get('guides') or []:
        topics = []
        for topic in guide.get('topics') or []:
            topics.append(
                {
                    'title': topic.get('title'),
                    'url_name': topic.get('url_name'),
                    'step_count': len(topic.get('steps') or []),
                }
            )
        out.append(
            {
                'section_id': guide.get('id'),
                'title': guide.get('title'),
                'subtitle': guide.get('subtitle'),
                'badge': guide.get('badge'),
                'topic_count': len(topics),
                'topics': topics,
                'source_ref': 'workspace/help_content.py',
            }
        )
    return out


def collect_help_toc() -> list[dict[str, str]]:
    from workspace.help_content import workspace_help_content

    data = workspace_help_content()
    return list(data.get('toc') or [])
