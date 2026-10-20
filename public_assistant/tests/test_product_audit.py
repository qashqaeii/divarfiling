"""تست ابزار ممیزی دانش محصول — فاز ۱."""
from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import yaml
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from public_assistant.audit.catalog import build_feature_catalog
from public_assistant.audit.collectors.django_urls import collect_workspace_routes
from public_assistant.audit.collectors.knowledge import collect_knowledge_articles
from public_assistant.audit.coverage import aggregate_depth, score_article_coverage
from public_assistant.audit.gap_backlog import build_gap_backlog
from public_assistant.audit.paths import audit_output_dir, catalog_seed_path, workspace_urls_path
from public_assistant.audit.retrieval_baseline import evaluate_retrieval
from public_assistant.tests.eval_dataset import EVAL_QUESTIONS


class CatalogSeedTest(SimpleTestCase):
    def test_seed_file_loads(self):
        data = yaml.safe_load(catalog_seed_path().read_text(encoding='utf-8'))
        features = data.get('features') or []
        self.assertGreaterEqual(len(features), 25)
        ids = [f['id'] for f in features]
        self.assertEqual(len(ids), len(set(ids)))

    def test_build_catalog_merges_help_sections(self):
        catalog = build_feature_catalog()
        self.assertGreaterEqual(catalog['feature_count'], 25)
        fids = {f['id'] for f in catalog['features']}
        self.assertTrue(any(x.startswith('help-workspace-') for x in fids))


class UrlCollectorTest(SimpleTestCase):
    def test_workspace_routes_non_empty(self):
        routes = collect_workspace_routes(workspace_urls_path())
        self.assertGreater(len(routes), 50)
        names = [r.name for r in routes if r.name]
        self.assertIn('crm_dashboard', names)


class CoverageHeuristicTest(SimpleTestCase):
    def test_aggregate_depth_howto(self):
        dims = {
            'intro_purpose': True,
            'ui_location': True,
            'howto_steps': True,
            'prerequisites_limits': False,
            'specialist_scenarios': False,
            'troubleshooting': False,
            'compare_similar': False,
            'faq_synonyms': False,
        }
        self.assertEqual(aggregate_depth(dims), 'howto')

    def test_personal_properties_article_scores(self):
        articles = collect_knowledge_articles()
        art = next(a for a in articles if a['article_id'] == 'crm-personal-properties')
        from public_assistant.audit.paths import knowledge_articles_dir
        from public_assistant.services.knowledge_loader import parse_markdown_file

        body = parse_markdown_file(knowledge_articles_dir() / 'crm-personal-properties.md').body
        dims = score_article_coverage(art['article_id'], art, body)
        self.assertTrue(dims['ui_location'])
        self.assertTrue(dims['howto_steps'])


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class AuditCommandTest(TestCase):
    def test_audit_command_writes_outputs(self):
        out = audit_output_dir()
        for name in (
            'feature_catalog.yaml',
            'coverage_matrix.csv',
            'source_index.json',
            'retrieval_baseline.json',
            'knowledge_gap_backlog.md',
            'audit_report.md',
        ):
            p = out / name
            if p.exists():
                p.unlink()

        call_command('audit_product_knowledge', stdout=StringIO())
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
        self.assertIn('eval_dataset', baseline)
        self.assertIn('hit_at_5', baseline['eval_dataset'])


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class RetrievalBaselineMetricsTest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge', verbosity=0)
        from public_assistant.services.retrieval import retrieve

        self.retrieve = retrieve

    def test_eval_dataset_hit_rates_bounded(self):
        report = evaluate_retrieval(self.retrieve, EVAL_QUESTIONS[:15])
        self.assertEqual(report['query_count'], 15)
        for key in ('hit_at_1', 'hit_at_3', 'hit_at_5'):
            self.assertGreaterEqual(report[key], 0.0)
            self.assertLessEqual(report[key], 1.0)
