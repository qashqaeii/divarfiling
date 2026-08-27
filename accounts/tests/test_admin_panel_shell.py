"""تست Shell مشترک پنل ادمین."""
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from accounts.context_processors import admin_panel_shell
from accounts.services.admin_panel_shell import (
    build_admin_panel_shell_context,
    resolve_admin_panel_nav_active,
)

User = get_user_model()


class AdminPanelShellServiceTests(TestCase):
    def test_resolve_nav_active_paths(self):
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/'), 'command')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/marketing/'), 'marketing')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/marketing/growth/'), 'growth')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/marketing/leads/'), 'leads')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/plan-conversion/'), 'plan_conversion')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/sales/'), 'sales')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/users/'), 'users')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/licenses/'), 'licenses')

    def test_context_processor_staff_only(self):
        factory = RequestFactory()
        request = factory.get('/accounts/admin-panel/')
        request.user = User.objects.create_user(
            username='normal', password='pass1234', phone='09121111111',
        )
        self.assertEqual(admin_panel_shell(request), {})

        request.user.is_staff = True
        ctx = admin_panel_shell(request)
        self.assertTrue(ctx.get('admin_panel_shell'))
        self.assertIn('chart_days', ctx)
        self.assertIn('admin_panel_nav_badges', ctx)


class AdminPanelShellViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='admstaff', password='pass1234', phone='09126666666', is_staff=True,
        )

    def test_dashboard_renders_grouped_sidebar(self):
        self.client.login(username='admstaff', password='pass1234')
        resp = self.client.get(reverse('admin_panel'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ecc-sidebar--grouped')
        self.assertContains(resp, 'ecc-nav-group')
        self.assertContains(resp, 'ecc-header--shell')
        self.assertContains(resp, 'ecc-kpi-grid--cmd')

    def test_marketing_page_uses_shell(self):
        self.client.login(username='admstaff', password='pass1234')
        resp = self.client.get(reverse('admin_panel_marketing'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ecc-sidebar--grouped')
        self.assertContains(resp, 'اتوماسیون بازاریابی')

    def test_range_key_preserved(self):
        factory = RequestFactory()
        request = factory.get('/accounts/admin-panel/', {'days': '1'})
        request.user = self.staff
        ctx = build_admin_panel_shell_context(request)
        self.assertEqual(ctx['admin_panel_range_key'], '1')
        self.assertEqual(ctx['chart_days'], 1)
