"""تست مرکز خروجی — کاتالوگ و فیلتر دسته."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.services.admin_exports import EXPORT_REGISTRY
from accounts.services.admin_exports_center import get_exports_center_context
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active

User = get_user_model()


class ExportsCenterServiceTests(TestCase):
    def test_catalog_matches_registry(self):
        ctx = get_exports_center_context(days=30)
        self.assertEqual(ctx['export_total_count'], len(EXPORT_REGISTRY))

    def test_category_filter_orders(self):
        ctx = get_exports_center_context(days=7, category='orders')
        self.assertEqual(ctx['category'], 'orders')
        self.assertTrue(all(g['key'] == 'orders' for g in ctx['export_groups']))
        for item in ctx['export_items']:
            self.assertEqual(item['category'], 'orders')

    def test_download_url_includes_days_when_supported(self):
        ctx = get_exports_center_context(days=14)
        paid = next(i for i in ctx['export_items'] if i['key'] == 'paid_orders')
        self.assertIn('days=14', paid['download_url'])
        self.assertIn('format=xlsx', paid['download_url'])


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminExportsCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='expstaff', password='pass1234', phone='09120000401', is_staff=True,
        )
        self.user = User.objects.create_user(username='expnorm', password='x', phone='09120000402')
        self.owner = User.objects.create_user(
            username='expowner', password='pass1234', phone='09120000403',
            is_staff=True, is_superuser=True,
        )

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse('admin_panel_exports')).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin_panel_exports')).status_code, 403)

    def test_render_catalog_and_filters(self):
        self.client.force_login(self.owner)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_exports'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('ecc-exports', content)
            self.assertIn('ecc-module-dock', content)
            self.assertIn(f'data-range="{days}"', content)

        resp = self.client.get(reverse('admin_panel_exports'), {'days': '30', 'category': 'users'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('category=users', resp.content.decode())

        resp = self.client.get(reverse('admin_panel_exports'), {'days': '30', 'compare': '1'})
        self.assertIn('compare=1', resp.content.decode())
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/exports/'), 'exports')

    def test_staff_without_export_permissions_sees_no_downloads(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin_panel_exports'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'برای دریافت خروجی باید مجوز')
        self.assertNotContains(response, 'class="ecc-module"')

    def test_anchor_fallback_in_dashboard(self):
        self.client.force_login(self.staff)
        dash = self.client.get(reverse('admin_panel'), {'days': '7'})
        content = dash.content.decode()
        self.assertIn('/accounts/admin-panel/exports/', content)
        self.assertIn('#ecc-exports', content)
