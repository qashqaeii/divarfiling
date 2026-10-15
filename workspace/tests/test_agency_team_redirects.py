"""Legacy CRM Team → Agency Hub redirect tests."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.services.crm_agency import create_agency
from workspace.tests.agency_test_utils import ensure_agency_subscription

User = get_user_model()


class AgencyTeamLegacyRedirectTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner_redirect', password='pass12345')
        self.agency = create_agency(self.owner, 'آژانس ریدایرکت')
        ensure_agency_subscription(self.owner, self.agency)
        self.client = Client()
        self.client.force_login(self.owner)

    def _assert_redirects_to(self, legacy_url, expected_name):
        resp = self.client.get(legacy_url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse(expected_name))

    def test_team_members_redirects_to_advisors(self):
        self._assert_redirects_to(
            reverse('workspace:crm_team') + '?tab=members',
            'workspace:agency_hub_advisors',
        )

    def test_team_command_redirects_to_dashboard(self):
        self._assert_redirects_to(
            reverse('workspace:crm_team') + '?tab=command',
            'workspace:agency_hub_dashboard',
        )

    def test_team_settings_redirects_to_profile(self):
        self._assert_redirects_to(
            reverse('workspace:crm_team') + '?tab=settings',
            'workspace:agency_hub_settings_profile',
        )

    def test_team_inbox_redirects(self):
        self._assert_redirects_to(
            reverse('workspace:crm_team') + '?tab=inbox',
            'workspace:agency_hub_inbox',
        )

    def test_team_messages_redirects(self):
        self._assert_redirects_to(
            reverse('workspace:crm_team') + '?tab=messages',
            'workspace:agency_hub_messages',
        )

    def test_team_sync_redirects(self):
        self._assert_redirects_to(
            reverse('workspace:crm_team') + '?tab=sync',
            'workspace:agency_hub_settings_sync',
        )

    def test_team_tv_legacy_redirects(self):
        self._assert_redirects_to(
            reverse('workspace:crm_team_tv'),
            'workspace:agency_hub_tv',
        )

    def test_bad_path_redirects_to_sync_settings(self):
        resp = self.client.get('/workspace/crm/team/undefined/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('workspace:agency_hub_settings_sync'))

    def test_agency_hub_advisors_renders_members_ui(self):
        resp = self.client.get(reverse('workspace:agency_hub_advisors'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'اعضای آژانس')
        self.assertContains(resp, 'agency-fold--export')
        self.assertNotContains(resp, '/crm/team/')
        self.assertNotContains(resp, 'workspace:crm_team')

    def test_agency_hub_templates_have_no_legacy_team_hrefs(self):
        import os
        from pathlib import Path

        root = Path(__file__).resolve().parents[2] / 'templates' / 'workspace' / 'crm' / 'agency'
        banned = ('/crm/team/', "url 'workspace:crm_team'", '?tab=members', '?tab=command')
        hits = []
        for path in root.rglob('*.html'):
            text = path.read_text(encoding='utf-8')
            for needle in banned:
                if needle in text:
                    hits.append(f'{path.relative_to(root)}: {needle}')
        self.assertEqual(hits, [], msg='Legacy team links in agency templates: ' + '; '.join(hits))
