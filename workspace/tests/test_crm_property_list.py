"""تست اسکرول بی‌نهایت لیست فایل‌های شخصی CRM."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMProperty

User = get_user_model()


class CRMPropertyListInfiniteScrollTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09125550001',
            phone='09125550001',
            password='testpass123',
        )
        self.client = Client()
        self.client.force_login(self.user)
        for i in range(25):
            CRMProperty.objects.create(
                user=self.user,
                title=f'ملک تست {i:02d}',
                city='تهران',
                deal_mode='فروش',
            )
        self.url = reverse('workspace:crm_properties')

    def test_list_uses_infinite_scroll_instead_of_page_links(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'crm-files-load-sentinel')
        self.assertContains(response, 'crm-properties-list.js')
        self.assertContains(response, 'data-has-next="1"')
        self.assertNotContains(response, 'aria-label="صفحه‌بندی"')

    def test_partial_load_returns_json_with_html(self):
        response = self.client.get(self.url, {'partial': '1', 'page': '2'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('html', data)
        self.assertTrue(data['html'].strip())
        self.assertIn('crm-files-card', data['html'])
        self.assertIn('has_next', data)
        self.assertFalse(data['has_next'])
        self.assertIsNone(data['next_page'])

    def test_partial_table_view_returns_rows(self):
        response = self.client.get(self.url, {'partial': '1', 'page': '2', 'view': 'table'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('crm-ft-row', data['html'])
        self.assertNotIn('crm-files-card', data['html'])
