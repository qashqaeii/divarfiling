"""ساخت Feature Catalog از seed + جمع‌آوری خودکار."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

import yaml

from public_assistant.audit.collectors.android_routes import collect_android_routes
from public_assistant.audit.collectors.django_urls import collect_workspace_routes
from public_assistant.audit.collectors.help_content import collect_help_sections, collect_help_toc
from public_assistant.audit.collectors.windows_features import collect_windows_surface
from public_assistant.audit.paths import (
    android_nav_host_path,
    catalog_seed_path,
    django_root,
    monorepo_root,
    windows_src_dir,
    workspace_urls_path,
)

_HELP_DOMAIN = {
    'start': 'onboarding',
    'bot-extraction': 'extractor',
    'workspace-filing': 'filing',
    'market-analysis': 'analysis',
    'smart-tools': 'analysis',
    'smart-assistant': 'ai',
    'crm-overview': 'crm',
    'crm-contacts': 'crm_contacts',
    'crm-properties': 'crm_personal_properties',
    'crm-deals': 'crm_deals',
    'crm-scheduling': 'crm_scheduling',
    'crm-communication': 'crm_automation',
    'crm-team': 'agency',
    'agency-hub': 'agency',
    'crm-finance-contracts': 'contracts',
    'workspace-settings': 'account',
    'faq': 'support',
}


def _load_seed() -> list[dict[str, Any]]:
    path = catalog_seed_path()
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    return list(data.get('features') or [])


def _ref_exists(ref: str) -> bool:
    ref = ref.split('#')[0].strip()
    candidates = [
        django_root() / ref,
        monorepo_root() / ref,
        django_root() / 'workspace' / ref,
    ]
    return any(p.is_file() or p.is_dir() for p in candidates)


def _slug_part(text: str) -> str:
    t = re.sub(r'\s+', '-', (text or '').strip())
    if len(t) > 36:
        t = hashlib.sha1(t.encode('utf-8')).hexdigest()[:10]
    return t or 'topic'


def _merge_help_topic_features(features: list[dict[str, Any]], sections: list[dict]) -> None:
    """هر topic در help_content به‌عنوان قابلیت ریز (وضعیت help_content_only)."""
    existing = {f['id'] for f in features}
    for sec in sections:
        sid = sec['section_id']
        parent = next(
            (f for f in features if sid in (f.get('help_section_ids') or [])),
            None,
        )
        parent_id = parent['id'] if parent else f'help-workspace-{sid}'
        for topic in sec.get('topics') or []:
            title = topic.get('title') or 'topic'
            fid = f"help-topic-{sid}-{_slug_part(title)}"
            if fid in existing:
                continue
            features.append(
                {
                    'id': fid,
                    'title': title,
                    'domain': _HELP_DOMAIN.get(sid, 'workspace'),
                    'parent_id': parent_id,
                    'user_description': title,
                    'platforms': ['web'],
                    'web_paths': [],
                    'operations': [],
                    'roles': [],
                    'license_notes': '',
                    'release_status': 'shipped',
                    'verification_status': 'help_content_only',
                    'knowledge_articles': [],
                    'help_section_ids': [sid],
                    'help_topic_title': title,
                    'source_refs': [sec['source_ref']],
                    'last_verified_at': None,
                    'notes': 'topic از help_content؛ لینک url_name=%s' % topic.get('url_name'),
                }
            )
            existing.add(fid)


def _merge_help_features(features: list[dict[str, Any]], sections: list[dict]) -> None:
    existing_help = {h for f in features for h in (f.get('help_section_ids') or [])}
    for sec in sections:
        sid = sec['section_id']
        if sid in existing_help:
            continue
        fid = f"help-workspace-{sid}"
        if any(f['id'] == fid for f in features):
            continue
        features.append(
            {
                'id': fid,
                'title': sec['title'],
                'domain': _HELP_DOMAIN.get(sid, 'workspace'),
                'parent_id': None,
                'user_description': sec.get('subtitle') or sec['title'],
                'platforms': ['web'],
                'web_paths': [],
                'operations': [],
                'roles': [],
                'license_notes': sec.get('badge') or '',
                'release_status': 'shipped',
                'verification_status': 'help_content_only',
                'knowledge_articles': [],
                'help_section_ids': [sid],
                'source_refs': [sec['source_ref']],
                'last_verified_at': None,
                'notes': 'استخراج خودکار از help_content؛ مسیر UI جداگانه تأیید نشده',
            }
        )


def _attach_audit_meta(features: list[dict[str, Any]], routes: list) -> dict[str, Any]:
    route_patterns = {r.pattern for r in routes}
    verified_paths = 0
    missing_paths = 0
    for f in features:
        valid_paths = []
        for p in f.get('web_paths') or []:
            # مسیر کامل workspace
            suffix = p.replace('/workspace/', '').strip('/')
            found = any(
                r.pattern == suffix or r.pattern.startswith(suffix.split('/')[0])
                for r in routes
            ) or suffix == ''
            if found or not suffix:
                valid_paths.append(p)
                verified_paths += 1
            else:
                missing_paths += 1
                f.setdefault('verification_notes', []).append(f'web_path_unmatched_in_urls:{p}')
        f['web_paths_verified'] = valid_paths
    return {'verified_path_refs': verified_paths, 'unmatched_path_refs': missing_paths}


def build_feature_catalog() -> dict[str, Any]:
    features = _load_seed()
    sections = collect_help_sections()
    _merge_help_features(features, sections)
    _merge_help_topic_features(features, sections)

    routes = collect_workspace_routes(workspace_urls_path())
    android_routes, android_note = collect_android_routes(android_nav_host_path())
    windows = collect_windows_surface(windows_src_dir())
    toc = collect_help_toc()

    for f in features:
        refs = f.get('source_refs') or []
        f['source_refs_resolved'] = [
            {'ref': r, 'exists': _ref_exists(r)} for r in refs
        ]

    path_audit = _attach_audit_meta(features, routes)

    status_counts: dict[str, int] = {}
    for f in features:
        st = f.get('release_status', 'unverified')
        status_counts[st] = status_counts.get(st, 0) + 1

    return {
        'catalog_version': 1,
        'generated_at': date.today().isoformat(),
        'feature_count': len(features),
        'release_status_counts': status_counts,
        'platforms_audit': {
            'django_workspace_routes': len(routes),
            'help_sections': len(sections),
            'help_toc_entries': len(toc),
            'knowledge_articles_markdown': None,  # filled in command
            'android': {
                'available': android_note == 'ok',
                'note': android_note,
                'route_count': len(android_routes),
                'source': str(android_nav_host_path().relative_to(monorepo_root()))
                if android_nav_host_path().is_file()
                else None,
            },
            'windows': windows,
        },
        'android_routes_sample': [
            {'const': r.const_name, 'route': r.route} for r in android_routes[:25]
        ],
        'path_audit': path_audit,
        'features': features,
    }
