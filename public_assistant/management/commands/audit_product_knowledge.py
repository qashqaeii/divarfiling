"""ممیزی جامع دانش محصول — read-only، خروجی در knowledge/audit/."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand
from django.core.management import call_command

from public_assistant.audit.catalog import build_feature_catalog
from public_assistant.audit.collectors.knowledge import collect_knowledge_articles
from public_assistant.audit.coverage import coverage_rows
from public_assistant.audit.gap_backlog import build_gap_backlog, gap_backlog_markdown
from public_assistant.audit.paths import audit_output_dir
from public_assistant.audit.report import build_audit_report
from public_assistant.audit.retrieval_baseline import run_full_baseline
from public_assistant.audit.source_index import build_source_index
from public_assistant.audit.staleness import build_staleness_plan


class Command(BaseCommand):
    help = 'Comprehensive product knowledge audit (Phase 1) — generates catalog, coverage, RAG baseline.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-retrieval',
            action='store_true',
            help='Skip DB sync and retrieval eval (faster, no RAG metrics)',
        )

    def handle(self, *args, **options):
        out = audit_output_dir()
        out.mkdir(parents=True, exist_ok=True)

        articles = collect_knowledge_articles()
        catalog = build_feature_catalog()
        catalog['platforms_audit']['knowledge_articles_markdown'] = len(articles)

        features = catalog['features']
        cov_rows = coverage_rows(features, articles)
        source_index = build_source_index(catalog, articles)
        gaps = build_gap_backlog(features, cov_rows)

        retrieval: dict = {}
        if not options['skip_retrieval']:
            call_command('sync_public_knowledge', verbosity=0)
            from public_assistant.services.retrieval import retrieve

            retrieval = run_full_baseline(retrieve)
        else:
            retrieval = {'skipped': True, 'reason': '--skip-retrieval'}

        stats = {
            'generated_at': catalog.get('generated_at'),
            'feature_count': len(features),
            'p0_count': sum(1 for g in gaps if g['priority'] == 'P0'),
            'p1_count': sum(1 for g in gaps if g['priority'] == 'P1'),
            'p2_count': sum(1 for g in gaps if g['priority'] == 'P2'),
        }

        self._write_yaml(out / 'feature_catalog.yaml', catalog)
        self._write_coverage_csv(out / 'coverage_matrix.csv', cov_rows)
        self._write_json(out / 'source_index.json', source_index)
        self._write_json(out / 'retrieval_baseline.json', retrieval)
        (out / 'knowledge_gap_backlog.md').write_text(
            gap_backlog_markdown(gaps, stats), encoding='utf-8'
        )
        (out / 'audit_report.md').write_text(
            build_audit_report(catalog, cov_rows, retrieval, gaps, source_index),
            encoding='utf-8',
        )
        staleness = build_staleness_plan(source_index)
        (out.parent / 'audit' / 'staleness_registry.yaml').write_text(
            yaml.safe_dump(staleness, allow_unicode=True, sort_keys=False),
            encoding='utf-8',
        )

        self.stdout.write(self.style.SUCCESS(f'Audit written to {out}'))

    def _write_yaml(self, path: Path, data: dict) -> None:
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120),
            encoding='utf-8',
        )

    def _write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def _write_coverage_csv(self, path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text('', encoding='utf-8')
            return
        fieldnames = list(rows[0].keys())
        with path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
