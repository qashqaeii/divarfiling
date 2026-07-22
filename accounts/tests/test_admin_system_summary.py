"""تست خروجی JSON خلاصه آماری یکپارچه."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.services.admin_system_summary import build_system_summary

User = get_user_model()


class SystemSummaryServiceTests(TestCase):
    def test_statistical_payload_shape(self):
        payload = build_system_summary(days=7)
        self.assertEqual(payload['meta']['version'], '2.0')
        self.assertEqual(payload['meta']['mode'], 'statistical_summary')
        self.assertNotIn('lists', payload)
        for key in (
            'overview', 'trends', 'action_items', 'workspace',
            'content', 'marketing', 'recovery', 'sales', 'affiliates',
        ):
            self.assertIn(key, payload)
        self.assertIn('blog', payload['content'])
        self.assertIn('academy', payload['content'])
        self.assertIn('posts_total', payload['content']['blog'])
        self.assertIn('videos_total', payload['content']['academy'])
        self.assertNotIn('top_posts', payload['content']['blog'])
        self.assertNotIn('top_videos', payload['content']['academy'])
        self.assertIn('recovered', payload['recovery'])
        self.assertIn('campaigns_total', payload['marketing'])
        self.assertIn('datasets_total', payload['workspace'])
        self.assertNotIn('datasets_by_user_top', payload['workspace'])
        self.assertNotIn('top_affiliates', payload['affiliates'])


class SystemSummaryViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='sumstaff', password='pass1234', phone='09128888888', is_staff=True,
        )

    def test_json_endpoint_stats_only(self):
        self.client.login(username='sumstaff', password='pass1234')
        resp = self.client.get(
            reverse('admin_panel_system_summary'),
            {'days': 7, 'download': '0'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['meta']['mode'], 'statistical_summary')
        self.assertNotIn('lists', data)
        self.assertIn('content', data)
        self.assertIn('recovery', data)
        self.assertIn('marketing', data)

    def test_dashboard_shows_unified_stats_mosaic(self):
        self.client.login(username='sumstaff', password='pass1234')
        resp = self.client.get(reverse('admin_panel'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'خروجی JSON یکپارچه')
        self.assertContains(resp, 'adm-json-modules')
        self.assertContains(resp, 'خلاصه آماری کل سیستم')
