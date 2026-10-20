"""تست ابزار ممیزی — Phase 1.1 (ایزوله، بدون sync DB)."""
from __future__ import annotations

import json
import os
import tempfile
from io import StringIO
from pathlib import Path

import yaml
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from public_assistant.audit.catalog import build_feature_catalog
from public_assistant.audit.collectors.django_urls import collect_url_inventory
from public_assistant.audit.collectors.knowledge import collect_knowledge_articles
from public_assistant.audit.coverage import aggregate_heuristic_depth, score_article_heuristic_dims
from public_assistant.audit.gap_backlog import build_gap_backlog
from public_assistant.audit.paths import audit_output_dir, catalog_seed_path, workspace_urls_path
from public_assistant.audit.retrieval_baseline import evaluate_retrieval
from public_assistant.audit.retrieval_offline import make_offline_retrieve_fn
from public_assistant.tests.eval_dataset import EVAL_QUESTIONS


class CatalogSeedTest(SimpleTestCase):
    def test_seed_file_loads(self):
        data = yaml.safe_load(catalog_seed_path().read_text(encoding='utf-8'))
        features = data.get('features') or []
        self.assertGreaterEqual(len(features), 25)
        ids = [f['id'] for f in features]
        self.assertEqual(len(ids), len(set(ids)))

    def test_build_catalog_entity_types(self):
        catalog = build_feature_catalog()
        self.assertGreaterEqual(catalog['logical_feature_count'], 25)
        counts = catalog.get('entity_type_counts') or {}
        self.assertGreater(counts.get('feature', 0), 20)
        self.assertGreater(counts.get('help_topic', 0), 5)


class UrlCollectorTest(SimpleTestCase):
    def test_url_inventory_parses_includes(self):
        inv = collect_url_inventory(workspace_urls_path())
        self.assertGreater(inv['summary']['total_parsed'], 80)
        self.assertGreater(inv['summary']['api'], 5)


class CoverageHeuristicTest(SimpleTestCase):
    def test_heuristic_never_auto_full(self):
        dims = {k: True for k in (
            'intro_purpose', 'ui_location', 'howto_steps', 'prerequisites_limits',
            'specialist_scenarios', 'troubleshooting', 'compare_similar', 'faq_synonyms',
        )}
        self.assertEqual(aggregate_heuristic_depth(dims), 'howto')

    def test_personal_properties_heuristic(self):
        articles = collect_knowledge_articles()
        art = next(a for a in articles if a['article_id'] == 'crm-personal-properties')
        from public_assistant.audit.paths import knowledge_articles_dir
        from public_assistant.services.knowledge_loader import parse_markdown_file

        body = parse_markdown_file(knowledge_articles_dir() / 'crm-personal-properties.md').body
        dims = score_article_heuristic_dims(art['article_id'], art, body)
        self.assertTrue(dims['ui_location'])
        self.assertTrue(dims['howto_steps'])


class AuditCommandTest(SimpleTestCase):
    def test_audit_command_read_only_isolated_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ['PUBLIC_ASSISTANT_AUDIT_OUTPUT_DIR'] = tmp
            try:
                call_command('audit_product_knowledge', stdout=StringIO())
                out = Path(tmp)
                for name in (
                    'feature_catalog.yaml',
                    'coverage_matrix.csv',
                    'source_index.json',
                    'retrieval_baseline.json',
                    'knowledge_gap_backlog.md',
                    'audit_report.md',
                ):
                    self.assertTrue((out / name).is_file(), msg=name)
                baseline = json.loads((out / 'retrieval_baseline.json').read_text(encoding='utf-8'))
                self.assertEqual(baseline.get('mode'), 'offline_markdown')
                self.assertIn('article_hit_at_5', baseline['eval_dataset'])
            finally:
                os.environ.pop('PUBLIC_ASSISTANT_AUDIT_OUTPUT_DIR', None)


class OfflineRetrievalBaselineTest(SimpleTestCase):
    def test_eval_dataset_metrics_bounded(self):
        report = evaluate_retrieval(make_offline_retrieve_fn(), EVAL_QUESTIONS[:20])
        self.assertEqual(report['query_count'], 20)
        for key in (
            'article_hit_at_5',
            'chunk_hit_at_5',
            'hit_at_5',
        ):
            self.assertGreaterEqual(report[key], 0.0)
            self.assertLessEqual(report[key], 1.0)


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class GapBacklogScopeTest(TestCase):
    def test_gap_only_features(self):
        catalog = build_feature_catalog()
        articles = collect_knowledge_articles()
        from public_assistant.audit.coverage import coverage_rows

        rows = coverage_rows(catalog['features'], articles)
        gaps = build_gap_backlog(catalog['features'], rows)
        for g in gaps:
            feat = next(f for f in catalog['features'] if f['id'] == g['feature_id'])
            self.assertEqual(feat.get('entity_type'), 'feature')
