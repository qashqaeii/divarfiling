"""مسیرهای ریپو برای ممیزی read-only."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings


def django_root() -> Path:
    return Path(settings.BASE_DIR).resolve()


def monorepo_root() -> Path:
    return django_root().parent


def workspace_urls_path() -> Path:
    return django_root() / 'workspace' / 'urls.py'


def help_content_path() -> Path:
    return django_root() / 'workspace' / 'help_content.py'


def knowledge_articles_dir() -> Path:
    return django_root() / 'public_assistant' / 'knowledge' / 'articles'


def audit_output_dir() -> Path:
    import os

    override = os.environ.get('PUBLIC_ASSISTANT_AUDIT_OUTPUT_DIR')
    if override:
        return Path(override).resolve()
    return django_root() / 'public_assistant' / 'knowledge' / 'audit'


def catalog_seed_path() -> Path:
    return django_root() / 'public_assistant' / 'audit' / 'data' / 'catalog_seed.yaml'


def android_nav_host_path() -> Path:
    return (
        monorepo_root()
        / 'divar-mobile-app'
        / 'android'
        / 'app'
        / 'src'
        / 'main'
        / 'java'
        / 'ir'
        / 'divarfiling'
        / 'mobile'
        / 'navigation'
        / 'DivarFilingNavHost.kt'
    )


def windows_src_dir() -> Path:
    return monorepo_root() / 'src'
