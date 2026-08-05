from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class DashboardTabUrlTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='dashuser',
            phone='09124444444',
            password='ComplexPass123!',
        )
        self.client.login(username='09124444444', password='ComplexPass123!')

    def test_dashboard_downloads_tab_path(self):
        resp = self.client.get(reverse('dashboard_tab', kwargs={'tab': 'downloads'}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'downloads')
        self.assertContains(resp, 'id="tab-downloads"')
        self.assertContains(resp, 'href="/accounts/dashboard/downloads/"')

    def test_dashboard_default_is_overview(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['active_tab'], 'overview')

    def test_legacy_query_tab_redirects_to_path(self):
        resp = self.client.get(reverse('dashboard'), {'tab': 'downloads'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard_tab', kwargs={'tab': 'downloads'}))

    def test_invalid_tab_redirects_to_dashboard(self):
        resp = self.client.get(reverse('dashboard_tab', kwargs={'tab': 'invalid-tab'}))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('dashboard'))

    def test_query_with_filter_redirect_preserves_params(self):
        resp = self.client.get(reverse('dashboard'), {'tab': 'orders', 'order_status': 'pending'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('order_status=pending', resp.url)
        self.assertIn('/accounts/dashboard/orders/', resp.url)
