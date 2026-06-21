"""تگ‌های قالب بلاگ."""
from django import template
from django.utils.html import strip_tags

register = template.Library()


def _reading_time_minutes(html_content: str) -> int:
    words = len(strip_tags(html_content or '').split())
    return max(1, round(words / 200))


@register.filter
def reading_time(content) -> int:
    return _reading_time_minutes(str(content or ''))


@register.filter
def category_icon(slug: str) -> str:
    icons = {
        'crm-consultants': 'fa-users',
        'market-analysis': 'fa-chart-line',
        'workflow-automation': 'fa-sitemap',
        'extraction': 'fa-robot',
        'divar-extraction': 'fa-download',
        'workflow': 'fa-sitemap',
        'real-estate': 'fa-building',
    }
    return icons.get(str(slug or ''), 'fa-newspaper')
