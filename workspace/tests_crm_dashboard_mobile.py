"""CRM dashboard — mobile IA and markup smoke tests."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class CRMDashboardMobileMarkupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='crmdash',
            password='pass1234',
            phone='09128887766',
        )
        self.client.login(username='crmdash', password='pass1234')

    def test_dashboard_work_first_structure(self):
        resp = self.client.get(reverse('workspace:crm_dashboard'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        hero_idx = html.find('crm-dash-hero')
        alerts_idx = html.find('crm-dash-alerts')
        quick_idx = html.find('crm-dash-quick')
        kpi_idx = html.find('crm-dash-kpis')
        learn_idx = html.find('crm-dash-learn')
        self.assertGreater(hero_idx, -1)
        self.assertGreater(quick_idx, -1)
        self.assertGreater(kpi_idx, -1)
        self.assertGreater(learn_idx, -1)
        if alerts_idx > -1:
            self.assertLess(hero_idx, alerts_idx)
            self.assertLess(alerts_idx, quick_idx)
        else:
            self.assertLess(hero_idx, quick_idx)
        self.assertLess(quick_idx, kpi_idx)
        self.assertLess(kpi_idx, learn_idx)

    def test_dashboard_no_legacy_academy_count_copy(self):
        resp = self.client.get(reverse('workspace:crm_dashboard'))
        self.assertNotContains(resp, '۱۲ آموزش ویدیویی')

    def test_dashboard_quick_actions_and_drawer(self):
        resp = self.client.get(reverse('workspace:crm_dashboard'))
        self.assertContains(resp, 'data-drawer-open="drawer-quick-lead"')
        self.assertContains(resp, 'open=drawer-contact')
        self.assertContains(resp, 'id="crmDashInsightsToggle"')
