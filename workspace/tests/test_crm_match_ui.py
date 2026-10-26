"""رگرسیون UI تطبیق — شمارنده‌ها، قالب صفحه‌بندی، CSS فیلتر مخاطب."""
from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase

from workspace.templatetags.crm_tags import crm_match_tab_count

User = get_user_model()
REPO_ROOT = Path(__file__).resolve().parents[2]
CONTACT_DETAIL_CSS = REPO_ROOT / 'static' / 'workspace' / 'css' / 'workspace-contact-detail.css'
CRM_JS = REPO_ROOT / 'static' / 'workspace' / 'js' / 'crm.js'


class CrmMatchTabCountTests(SimpleTestCase):
    def test_uses_total_count_not_loaded_cards(self):
        data = {
            'eligible': True,
            'total_count': 278,
            'crm_matches': [{'id': 1}] * 24,
            'divar_matches': [{'id': 2}] * 24,
        }
        self.assertEqual(crm_match_tab_count(data), 278)

    def test_builder_groups_use_group_totals(self):
        data = {
            'eligible': True,
            'match_groups': [
                {
                    'crm_matches': [{}] * 10,
                    'divar_matches': [{}] * 5,
                    'crm_total_count': 120,
                    'divar_total_count': 30,
                },
                {
                    'crm_matches': [{}] * 8,
                    'divar_matches': [{}] * 3,
                    'crm_total_count': 90,
                    'divar_total_count': 8,
                },
            ],
        }
        self.assertEqual(crm_match_tab_count(data), 120 + 30 + 90 + 8)


class CrmMatchPanelTemplateTests(TestCase):
    def test_panel_exposes_real_totals_in_data_attributes(self):
        user = User.objects.create_user(username='09123334455', phone='09123334455', password='x')
        tpl = Template(
            '{% include "workspace/crm/includes/matches_panel.html" %}',
        )
        html = tpl.render(Context({
            'match_data': {
                'eligible': True,
                'total_count': 278,
                'crm_total_count': 254,
                'divar_total_count': 24,
                'crm_matches': [{}] * 24,
                'divar_matches': [{}] * 24,
                'crm_has_more': True,
                'divar_has_more': False,
                'crm_page': 1,
                'divar_page': 1,
                'matching_tolerance_percent': 20,
            },
            'customer': type('C', (), {'pk': 1})(),
            'has_bot_license': True,
            'suggested': False,
        }))
        self.assertIn('data-crm-total="254"', html)
        self.assertIn('data-divar-total="24"', html)
        self.assertIn('data-match-tab-count="crm">254', html)
        self.assertIn('data-match-pager="crm"', html)
        self.assertIn('data-match-load-more', html)
        self.assertIn('data-match-total="254"', html)


class CrmMatchUiAssetTests(SimpleTestCase):
    def test_pcm_card_hidden_css_rule_exists(self):
        css = CONTACT_DETAIL_CSS.read_text(encoding='utf-8')
        self.assertIn('.crm-pcm-card-v3[hidden]', css)
        self.assertIn('display: none !important', css)

    def test_crm_js_syncs_tab_counts_from_dataset(self):
        js = CRM_JS.read_text(encoding='utf-8')
        self.assertIn('function crmSyncMatchPanelTabCounts', js)
        self.assertIn('function crmUpdateMatchColumnPager', js)
        self.assertNotIn('totalCrm || panel.querySelectorAll', js)
