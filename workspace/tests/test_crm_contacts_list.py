"""تست اسکرول بی‌نهایت لیست مخاطبین CRM."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import Customer

User = get_user_model()


class CRMContactsListInfiniteScrollTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09125550002',
            phone='09125550002',
            password='testpass123',
        )
        self.client = Client()
        self.client.force_login(self.user)
        for i in range(26):
            Customer.objects.create(
                user=self.user,
                name=f'مخاطب تست {i:02d}',
                phone=f'0912555{i:04d}',
            )
        self.url = reverse('workspace:crm_contacts')

    def test_list_uses_infinite_scroll_instead_of_page_links(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'crm-contacts-load-sentinel')
        self.assertContains(response, 'crm-contacts-list.js')
        self.assertContains(response, 'data-has-next="1"')
        self.assertNotContains(response, 'crm-contacts-pagination')

    def test_partial_load_returns_json_with_html(self):
        response = self.client.get(self.url, {'partial': '1', 'page': '2'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('html', data)
        self.assertTrue(data['html'].strip())
        self.assertIn('crm-row-selectable', data['html'])
        self.assertIn('has_next', data)
        self.assertFalse(data['has_next'])
        self.assertIsNone(data['next_page'])
