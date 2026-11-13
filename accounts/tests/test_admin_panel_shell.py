"""تست Shell مشترک پنل ادمین."""
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.template.loader import render_to_string
import re
from django.urls import reverse

from accounts.context_processors import admin_panel_shell
from accounts.services.admin_panel_shell import (
    ADMIN_PANEL_SIDEBAR_LABELS,
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
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/operations/'), 'operations')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/support/'), 'support')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/activity/'), 'activity')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/windows/'), 'windows')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/android/'), 'android')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/ai/'), 'ai')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/crm/'), 'crm')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/affiliates/'), 'affiliates')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/exports/'), 'exports')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/forum/'), 'forum')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/blog/'), 'blog')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/blog/systematic/'), 'blog_systematic')
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/blog/systematic/autopublish/'), 'blog_systematic')

    def test_sidebar_has_exactly_one_active_blog_item(self):
        html = render_to_string('accounts/partials/admin_panel_sidebar.html', {
            'admin_panel_nav_active': 'blog_systematic',
            'admin_panel_query_suffix': '?days=7',
        })
        active_ids = re.findall(r'class="ecc-nav-item[^"]*is-active[^"]*"[^>]*data-nav-id="([^"]+)"', html)
        self.assertEqual(active_ids, ['blog_systematic'])

    def test_forum_expands_operations_group(self):
        html = render_to_string('accounts/partials/admin_panel_sidebar.html', {
            'admin_panel_nav_active': 'forum',
            'admin_panel_query_suffix': '?days=7',
        })
        self.assertIn('ecc-nav-group is-open" data-nav-group="operations"', html)

    def test_shell_exposes_short_sidebar_labels(self):
        factory = RequestFactory()
        request = factory.get('/accounts/admin-panel/')
        request.user = User.objects.create_user(
            username='adm', password='pass1234', phone='09123333333', is_staff=True,
        )
        ctx = build_admin_panel_shell_context(request)
        self.assertEqual(ctx['admin_panel_sidebar_labels'], ADMIN_PANEL_SIDEBAR_LABELS)
        self.assertEqual(ctx['admin_panel_sidebar_labels']['sales'], 'سفارش‌ها')
        self.assertEqual(ctx['admin_panel_sidebar_labels']['assistant'], 'دستیار')

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

@override_settings(COMMUNITY_FORUM_ENABLED=True, COMMUNITY_FORUM_ROLLOUT_MODE='all')
class AdminForumShellRegressionTests(TestCase):
    def test_forum_renders_in_admin_panel_content_block(self):
        moderator = User.objects.create_user(
            username='forum_owner',
            password='pass1234',
            phone='09120000991',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(moderator)
        response = self.client.get(reverse('admin_panel_forum'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="forum-moderation"')
        self.assertContains(response, 'گزارش‌های در انتظار')
        self.assertContains(response, reverse('admin:community_forum_forumreport_changelist'))
