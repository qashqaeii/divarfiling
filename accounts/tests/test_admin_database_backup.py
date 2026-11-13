"""تست بک‌آپ دیتابیس در پنل مدیریت."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.services.admin_database_backup import (
    create_database_backup,
    get_database_backup_info,
)

User = get_user_model()


class DatabaseBackupServiceTests(TestCase):
    def test_backup_info_sqlite_dev(self):
        info = get_database_backup_info()
        self.assertIn('engine_label', info)
        self.assertIn(info['engine_label'], ('SQLite', 'PostgreSQL'))

    def test_dumpdata_backup_produces_gzip(self):
        result = create_database_backup(fmt='dumpdata')
        self.assertTrue(result.filename.endswith('.json.gz'))
        self.assertEqual(result.method, 'dumpdata')
        self.assertGreater(result.size_bytes, 10)
        self.assertTrue(result.content[:2] == b'\x1f\x8b')  # gzip magic

    def test_auto_backup_works(self):
        result = create_database_backup(fmt='auto')
        self.assertGreater(result.size_bytes, 10)
        self.assertTrue(result.filename.startswith('divarfiling-'))


class AdminDatabaseBackupViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='admin_backup',
            password='secret123',
            phone='09120000001',
            is_staff=True,
        )
        self.superuser = User.objects.create_user(
            username='owner_backup',
            password='secret123',
            phone='09120000003',
            is_staff=True,
            is_superuser=True,
        )
        self.user = User.objects.create_user(
            username='regular_backup',
            password='secret123',
            phone='09120000002',
            is_staff=False,
        )

    def test_superuser_can_download_dumpdata(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(
            reverse('admin_panel_database_backup'),
            {'format': 'dumpdata'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp.get('Content-Disposition', ''))
        self.assertIn('divarfiling-dumpdata', resp.get('Content-Disposition', ''))
        self.assertEqual(resp['X-Backup-Method'], 'dumpdata')

    def test_staff_cannot_download_full_database(self):
        from unittest.mock import patch

        self.client.force_login(self.staff)
        with patch('accounts.admin_views.create_database_backup') as backup:
            resp = self.client.get(reverse('admin_panel_database_backup'), {'format': 'dumpdata'})
        self.assertEqual(resp.status_code, 403)
        backup.assert_not_called()

    def test_non_staff_forbidden(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('admin_panel_database_backup'))
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(reverse('admin_panel_database_backup'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)

    def test_backup_actions_visible_only_to_superuser(self):
        url = reverse('admin_panel_operations')
        backup_url = reverse('admin_panel_database_backup')

        self.client.force_login(self.staff)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ops-backup')
        self.assertContains(response, 'دریافت بک‌آپ کامل فقط برای مدیر ارشد')
        self.assertNotContains(response, backup_url)

        self.client.force_login(self.superuser)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, backup_url)
