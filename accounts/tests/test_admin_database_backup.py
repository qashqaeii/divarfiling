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
        self.user = User.objects.create_user(
            username='regular_backup',
            password='secret123',
            phone='09120000002',
            is_staff=False,
        )

    def test_staff_can_download_dumpdata(self):
        self.client.force_login(self.staff)
        resp = self.client.get(
            reverse('admin_panel_database_backup'),
            {'format': 'dumpdata'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp.get('Content-Disposition', ''))
        self.assertIn('divarfiling-dumpdata', resp.get('Content-Disposition', ''))
        self.assertEqual(resp['X-Backup-Method'], 'dumpdata')

    def test_non_staff_forbidden(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('admin_panel_database_backup'))
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(reverse('admin_panel_database_backup'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)

    def test_dashboard_includes_backup_info(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'بک‌آپ دیتابیس')
        self.assertContains(resp, reverse('admin_panel_database_backup'))
