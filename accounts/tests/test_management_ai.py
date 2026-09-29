"""Management AI — manual-only, snapshots, security."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import AdminManagementAIAnalysis
from accounts.services.management_ai.fingerprint import compute_fingerprint
from accounts.services.management_ai.registry import build_section_snapshot
from accounts.services.management_ai.sanitize import assert_no_pii, sanitize_snapshot_dict
from accounts.services.management_ai.service import generate_analysis, get_latest_analysis
from accounts.services.management_ai.validator import validate_analysis_response
from ai_workspace.constants import FEATURE_MANAGEMENT_ANALYSIS, PROMPT_VERSIONS

User = get_user_model()

SAMPLE_AI = {
    'summary': 'خلاصه تست.',
    'status': 'watch',
    'insights': [{
        'title': 'رشد',
        'description': 'ثبت‌نام افزایش یافته.',
        'type': 'interpretation',
        'metric_refs': ['metrics.users_new_period'],
        'confidence': 0.8,
    }],
    'actions': [],
    'risks': [],
    'opportunities': [],
}


@override_settings(AI_ENABLED=True, ADMIN_MANAGEMENT_AI_ENABLED=True)
class ManagementAISnapshotTests(TestCase):
    def test_users_snapshot_has_metrics(self):
        snap = build_section_snapshot('users', 30, False)
        self.assertEqual(snap['section'], 'users')
        self.assertIn('metrics', snap)
        self.assertIsInstance(snap['facts'], list)

    def test_sales_snapshot(self):
        snap = build_section_snapshot('sales', 30, False)
        self.assertEqual(snap['section'], 'sales')

    def test_licenses_snapshot(self):
        snap = build_section_snapshot('licenses', 30, False)
        self.assertEqual(snap['section'], 'licenses')

    def test_crm_snapshot(self):
        snap = build_section_snapshot('crm', 30, False)
        self.assertEqual(snap['section'], 'crm')

    def test_executive_snapshot(self):
        snap = build_section_snapshot('executive', 30, False)
        self.assertIn('users', snap['metrics'])

    def test_pii_stripped(self):
        dirty = {'metrics': {'x': 1}, 'phone': '09121234567', 'email': 'a@b.com'}
        clean = sanitize_snapshot_dict(dirty)
        self.assertNotIn('phone', clean)
        self.assertNotIn('email', clean)
        assert_no_pii(clean)

    def test_fingerprint_changes(self):
        a = build_section_snapshot('users', 30, False)
        b = dict(a)
        b['metrics'] = dict(a['metrics'])
        fp1 = compute_fingerprint(a)
        b['metrics']['users_total'] = {'current': 999999}
        fp2 = compute_fingerprint(b)
        self.assertNotEqual(fp1, fp2)


@override_settings(AI_ENABLED=True, ADMIN_MANAGEMENT_AI_ENABLED=True)
class ManagementAIAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user(username='staff_ai', password='x', is_staff=True)
        self.client = Client()
        self.client.force_login(self.staff)

    def test_get_never_calls_provider(self):
        with patch('accounts.services.management_ai.analyzer.gateway_run') as mock_run:
            url = reverse('admin_panel_ai_analysis', args=['users']) + '?days=30'
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()['status'], 'not_generated')
            mock_run.assert_not_called()

    def test_page_load_no_provider_in_html(self):
        with patch('accounts.services.management_ai.analyzer.gateway_run') as mock_run:
            resp = self.client.get(reverse('admin_panel_users') + '?days=30')
            self.assertEqual(resp.status_code, 200)
            mock_run.assert_not_called()

    @patch('accounts.services.management_ai.analyzer.gateway_run')
    def test_only_post_generate_calls_provider(self, mock_run):
        mock_run.return_value = MagicMock(
            text=json.dumps(SAMPLE_AI, ensure_ascii=False),
            data=SAMPLE_AI,
            provider='arvan',
            model='test-model',
        )
        snap = build_section_snapshot('users', 30, False)
        SAMPLE_AI['insights'][0]['metric_refs'] = list(snap['metrics'].keys())[:1]
        SAMPLE_AI['insights'][0]['metric_refs'] = [
            f'metrics.{k}' for k in list(snap['metrics'].keys())[:1]
        ]
        mock_run.return_value.text = json.dumps(SAMPLE_AI, ensure_ascii=False)

        gen_url = reverse('admin_panel_ai_analysis_generate', args=['users']) + '?days=30'
        resp = self.client.post(gen_url, {'force': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get('ok'))
        mock_run.assert_called_once()

    @patch('accounts.services.management_ai.analyzer.gateway_run')
    def test_stale_detection(self, mock_run):
        mock_run.return_value = MagicMock(
            text=json.dumps({
                **SAMPLE_AI,
                'insights': [{
                    'title': 't',
                    'description': 'd',
                    'type': 'interpretation',
                    'metric_refs': ['metrics.users_new_period'],
                    'confidence': 0.5,
                }],
            }, ensure_ascii=False),
            data={},
            provider='arvan',
            model='m',
        )
        generate_analysis('users', 30, False, self.staff, force=True)

        stored = AdminManagementAIAnalysis.objects.get(section='users', days_key='30', compare=False)
        stored.snapshot_fingerprint = 'stale_fp'
        stored.save(update_fields=['snapshot_fingerprint'])

        payload = get_latest_analysis('users', 30, False)
        self.assertEqual(payload['status'], 'available')
        self.assertTrue(payload['is_stale'])

    def test_feature_flag_disabled(self):
        with override_settings(ADMIN_MANAGEMENT_AI_ENABLED=False):
            url = reverse('admin_panel_ai_analysis', args=['users'])
            resp = self.client.get(url)
            self.assertEqual(resp.json()['status'], 'disabled')

    def test_staff_required(self):
        guest = Client()
        url = reverse('admin_panel_ai_analysis', args=['users'])
        resp = guest.get(url)
        self.assertIn(resp.status_code, (302, 403))

    @patch('accounts.services.management_ai.analyzer.gateway_run')
    def test_rate_limit(self, mock_run):
        mock_run.return_value = MagicMock(
            text=json.dumps({**SAMPLE_AI, 'insights': []}, ensure_ascii=False),
            data={},
            provider='arvan',
            model='m',
        )
        gen_url = reverse('admin_panel_ai_analysis_generate', args=['users']) + '?days=30'
        self.client.post(gen_url, {'force': '1'})
        resp2 = self.client.post(gen_url, {'force': '1'})
        self.assertEqual(resp2.status_code, 429)


    @patch('accounts.services.management_ai.analyzer.gateway_run')
    def test_provider_failure_isolated(self, mock_run):
        mock_run.side_effect = RuntimeError('timeout')
        gen_url = reverse('admin_panel_ai_analysis_generate', args=['users']) + '?days=30'
        resp = self.client.post(gen_url, {'force': '1'})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json().get('ok'))

    @patch('accounts.services.management_ai.analyzer.gateway_run')
    def test_invalid_json_from_provider(self, mock_run):
        mock_run.return_value = MagicMock(text='not json', data={}, provider='arvan', model='m')
        gen_url = reverse('admin_panel_ai_analysis_generate', args=['users']) + '?days=30'
        resp = self.client.post(gen_url, {'force': '1'})
        self.assertFalse(resp.json().get('ok'))


@override_settings(AI_ENABLED=True, ADMIN_MANAGEMENT_AI_ENABLED=True)
class ManagementAIExecutiveEfficiencyTests(TestCase):
    def test_executive_builds_insights_once(self):
        with patch(
            'accounts.services.management_ai.facts.build_management_insights',
            wraps=__import__(
                'accounts.services.admin_management_assistant',
                fromlist=['build_management_insights'],
            ).build_management_insights,
        ) as mock_insights:
            build_section_snapshot('executive', 30, False)
            self.assertEqual(mock_insights.call_count, 1)


class ManagementAIPromptVersionTests(TestCase):
    def test_prompt_versions_fit_ai_usage_log(self):
        for feature, version in PROMPT_VERSIONS.items():
            self.assertLessEqual(
                len(version),
                20,
                msg=f'{feature} prompt_version too long for AIUsageLog: {version!r}',
            )


class ManagementAIValidatorTests(TestCase):
    def test_bare_metric_refs_normalized(self):
        snap = {
            'metrics': {
                'retention_d30': {'current': 12},
                'users_without_license': {'current': 3},
            },
        }
        data = {
            **SAMPLE_AI,
            'insights': [{
                'title': 'x',
                'description': 'y',
                'type': 'interpretation',
                'metric_refs': ['retention_d30', 'users_without_license'],
                'confidence': 0.5,
            }],
        }
        cleaned, errs = validate_analysis_response(data, snap)
        self.assertEqual(errs, [])
        self.assertEqual(
            cleaned['insights'][0]['metric_refs'],
            ['metrics.retention_d30', 'metrics.users_without_license'],
        )

    def test_invalid_metric_refs_rejected(self):
        snap = {'metrics': {'users_new_period': {'current': 5}}}
        bad = {**SAMPLE_AI, 'insights': [{
            'title': 'x',
            'description': 'y',
            'type': 'interpretation',
            'metric_refs': ['metrics.fake_metric'],
            'confidence': 0.5,
        }]}
        with self.assertRaises(ValueError):
            validate_analysis_response(bad, snap)
