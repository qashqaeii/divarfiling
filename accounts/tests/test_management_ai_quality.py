"""Quality tuning tests — terminology, snapshot semantics, validator limits."""
from __future__ import annotations

from django.test import TestCase

from accounts.services.management_ai.metric_semantics import enrich_data_quality
from accounts.services.management_ai.schemas import MAX_ACTIONS, MAX_INSIGHTS, MAX_OPPORTUNITIES, MAX_RISKS
from accounts.services.management_ai.text_quality import (
    contains_forbidden_license_terms,
    polish_analysis_dict,
    polish_management_text,
)
from accounts.services.management_ai.validator import validate_analysis_response

SAMPLE = {
    'summary': 'خلاصه.',
    'status': 'watch',
    'insights': [],
    'actions': [],
    'risks': [],
    'opportunities': [],
}


class ManagementAITerminologyTests(TestCase):
    def test_porane_replaced_with_license(self):
        raw = '۶۳۰ کاربر بدون پروانه فعالیت هستند.'
        polished = polish_management_text(raw)
        self.assertIn('لایسنس', polished)
        self.assertFalse(contains_forbidden_license_terms(polished))

    def test_polish_analysis_dict(self):
        data = {
            **SAMPLE,
            'insights': [{
                'title': 'بدون پروانه',
                'description': 'x',
                'type': 'fact',
                'metric_refs': [],
                'confidence': 0.5,
            }],
        }
        out = polish_analysis_dict(data)
        self.assertIn('لایسنس', out['insights'][0]['title'])


class ManagementAISemanticsTests(TestCase):
    def test_crm_stock_vs_flow_warning(self):
        metrics = {
            'overdue_reminders': {'current': 680},
            'reminders_created_period': {'current': 345},
        }
        dq = enrich_data_quality('crm', metrics, {'days': '30'})
        self.assertTrue(dq['metric_semantics'])
        self.assertGreaterEqual(len(dq['warnings']), 1)
        self.assertIn('metrics.overdue_reminders', dq['metric_semantics'])


class ManagementAIStatusLabelTests(TestCase):
    """Keep in sync with mizkar-admin-management-ai.js STATUS_UI labels."""

    EXPECTED = {
        'good': 'مطلوب',
        'watch': 'رصد',
        'warning': 'هشدار',
        'critical': 'بحرانی',
    }

    def test_status_fa_labels(self):
        self.assertEqual(self.EXPECTED['critical'], 'بحرانی')
        self.assertEqual(len(self.EXPECTED), 4)


class ManagementAIValidatorLimitTests(TestCase):
    def test_truncates_to_max_blocks(self):
        snap = {'metrics': {'users_new_period': {'current': 1}}}
        data = {
            **SAMPLE,
            'insights': [
                {'title': f'i{n}', 'description': 'd', 'type': 'fact', 'metric_refs': ['users_new_period'], 'confidence': 0.5}
                for n in range(6)
            ],
            'actions': [
                {'title': f'a{n}', 'description': 'd', 'priority': 'low', 'impact': 'low', 'effort': 'low', 'metric_refs': []}
                for n in range(5)
            ],
            'risks': [
                {'title': f'r{n}', 'description': 'd', 'severity': 'low', 'metric_refs': []}
                for n in range(4)
            ],
            'opportunities': [
                {'title': f'o{n}', 'description': 'd', 'potential': 'low', 'metric_refs': []}
                for n in range(4)
            ],
        }
        cleaned, _ = validate_analysis_response(data, snap)
        self.assertEqual(len(cleaned['insights']), MAX_INSIGHTS)
        self.assertEqual(len(cleaned['actions']), MAX_ACTIONS)
        self.assertEqual(len(cleaned['risks']), MAX_RISKS)
        self.assertEqual(len(cleaned['opportunities']), MAX_OPPORTUNITIES)
