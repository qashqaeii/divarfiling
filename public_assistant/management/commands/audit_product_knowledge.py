"""ممیزی جامع دانش محصول — read-only (Phase 1.1)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand

from public_assistant.audit.catalog import build_feature_catalog
from public_assistant.audit.collectors.knowledge import collect_knowledge_articles
from public_assistant.audit.coverage import coverage_rows
from public_assistant.audit.gap_backlog import build_gap_backlog, gap_backlog_markdown
from public_assistant.audit.paths import audit_output_dir
from public_assistant.audit.report import build_audit_report
from public_assistant.audit.retrieval_baseline import run_full_baseline
from public_assistant.audit.retrieval_offline import make_offline_retrieve_fn
from public_assistant.audit.source_index import build_source_index
from public_assistant.audit.staleness import build_staleness_plan, write_staleness_registry


class Command(BaseCommand):
    help = 'Read-only product knowledge audit — writes only to knowledge/audit/.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-retrieval',
            action='store_true',
            help='Skip retrieval baseline (still read-only)',
        )

    def handle(self, *args, **options):
        out = audit_output_dir()
        out.mkdir(parents=True, exist_ok=True)

        articles = collect_knowledge_articles()
        catalog = build_feature_catalog()
        catalog['platforms_audit']['knowledge_articles_markdown'] = len(articles)

        features = catalog['features']
        logical = [f for f in features if f.get('entity_type') == 'feature']
        cov_rows = coverage_rows(features, articles)
        source_index = build_source_index(catalog, articles)
        gaps = build_gap_backlog(features, cov_rows)

        retrieval: dict = {}
        if not options['skip_retrieval']:
            retrieval = run_full_baseline(make_offline_retrieve_fn())
        else:
            retrieval = {'skipped': True, 'reason': '--skip-retrieval', 'mode': 'offline_markdown'}

        verified_full = sum(1 for r in cov_rows if r.get('verified_coverage') == 'full')
        needs_review = sum(1 for r in cov_rows if r.get('verified_coverage') == 'needs_review')

        stats = {
            'generated_at': catalog.get('generated_at'),
            'feature_count': len(features),
            'logical_feature_count': len(logical),
            'verified_full_count': verified_full,
            'needs_review_count': needs_review,
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
            build_audit_report(catalog, cov_rows, retrieval, gaps, source_index, stats),
            encoding='utf-8',
        )
        staleness = build_staleness_plan(source_index, catalog_features=features)
        write_staleness_registry(staleness)

        self.stdout.write(self.style.SUCCESS(f'Audit written to {out} (read-only, no DB sync)'))

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
