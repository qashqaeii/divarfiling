"""تست مدیریت کاربران در پنل ادمین."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.services.admin_users_management import (
    get_user_management_detail,
    list_users_management,
)

User = get_user_model()


class AdminUsersManagementServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='um_user',
            phone='09121112233',
            password='test-pass-123',
        )
        self.staff = User.objects.create_user(
            username='um_staff',
            phone='09121112244',
            password='test-pass-123',
            is_staff=True,
        )

    def test_list_includes_user(self):
        data = list_users_management(q='09121112233')
        self.assertTrue(data['ok'])
        self.assertGreaterEqual(data['total'], 1)
        phones = [r['phone'] for r in data['results']]
        self.assertIn('09121112233', phones)

    def test_detail_payload(self):
        detail = get_user_management_detail(self.user.id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail['id'], self.user.id)
        self.assertIn('windows', detail)
        self.assertIn('android', detail)
        self.assertIn('usage', detail)
        self.assertIn('licenses', detail)
        self.assertIn('orders', detail)


class AdminUsersManagementViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='um_staff2',
            phone='09123334455',
            password='test-pass-123',
            is_staff=True,
        )
        self.user = User.objects.create_user(
            username='um_target',
            phone='09123334466',
            password='test-pass-123',
        )

    def test_list_requires_staff(self):
        url = reverse('admin_panel_users_json')
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (302, 403))

    def test_list_and_detail_ok_for_staff(self):
        self.client.force_login(self.staff)
        list_url = reverse('admin_panel_users_json')
        resp = self.client.get(list_url, {'q': '09123334466'})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload['ok'])
        self.assertGreaterEqual(payload['total'], 1)

        detail_url = reverse('admin_panel_user_detail_json', args=[self.user.id])
        resp2 = self.client.get(detail_url)
        self.assertEqual(resp2.status_code, 200)
        data = resp2.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['user']['id'], self.user.id)
