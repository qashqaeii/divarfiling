"""Phase 02A: shared admin shell behavior and presentation contracts."""
from pathlib import Path
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.services.admin_panel_shell import build_admin_panel_shell_context

User = get_user_model()


class AdminPremiumV2FoundationTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='v2_shell_staff',
            password='shell-test-pass',
            phone='09129994021',
            is_staff=True,
        )

    def test_global_period_preserves_local_filters_without_stale_compare(self):
        request = RequestFactory().get(
            '/accounts/admin-panel/sales/',
            {
                'days': '30', 'audit': 'complete_without_license',
                'focus': 'paid', 'compare': '1',
            },
        )
        request.user = self.staff
        links = build_admin_panel_shell_context(request)['admin_panel_range_links']
        self.assertEqual(set(links), {'all', '1', '7', '30', '90'})
        today = parse_qs(links['1'].removeprefix('?'))
        self.assertEqual(today['days'], ['1'])
        self.assertEqual(today['audit'], ['complete_without_license'])
        self.assertEqual(today['focus'], ['paid'])
        self.assertEqual(today['compare'], ['1'])
        all_time = parse_qs(links['all'].removeprefix('?'))
        self.assertEqual(all_time['days'], ['all'])
        self.assertEqual(all_time['audit'], ['complete_without_license'])
        self.assertEqual(all_time['focus'], ['paid'])
        self.assertNotIn('compare', all_time)

    def test_global_period_preserves_repeated_query_values(self):
        request = RequestFactory().get(
            '/accounts/admin-panel/users/?tag=first&tag=second&days=7'
        )
        request.user = self.staff
        links = build_admin_panel_shell_context(request)['admin_panel_range_links']
        query = parse_qs(links['90'][1:])
        self.assertEqual(query['tag'], ['first', 'second'])
        self.assertEqual(query['days'], ['90'])

    def test_sidebar_current_page_and_group_controls_are_structured(self):
        for current, group in (
            ('sales', 'business'),
            ('users', 'customers'),
            ('forum', 'operations'),
            ('android', 'product'),
            ('blog_systematic', 'content'),
            ('exports', 'system'),
        ):
            with self.subTest(current=current):
                markup = render_to_string(
                    'accounts/partials/admin_panel_sidebar.html',
                    {'admin_panel_nav_active': current,
                     'admin_panel_query_suffix': '?days=7'},
                )
                self.assertEqual(markup.count('aria-current="page"'), 1)
                self.assertIn('data-nav-id="%s" aria-current="page"' % current, markup)
                self.assertIn('aria-controls="ecc-nav-group-items-%s"' % group, markup)
                self.assertIn('id="ecc-nav-group-items-%s"' % group, markup)

    def test_shared_foundations_present_on_command_sales_and_support(self):
        self.client.force_login(self.staff)
        for name in ('admin_panel', 'admin_panel_sales', 'admin_panel_support'):
            with self.subTest(name=name):
                response = self.client.get(reverse(name), {'days': '7', 'focus': 'pending'})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'mizkar-admin-v2-foundations.css')
                self.assertContains(response, 'id="admin-main" tabindex="-1"')
                self.assertContains(response, 'href="#admin-main"')
                self.assertContains(response, 'mizkar-admin-panel-shell.js')
                self.assertContains(response, 'aria-current="page"')
                self.assertContains(response, 'focus=pending')

    def test_css_foundations_include_dark_mobile_focus_and_reduced_motion(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / 'static/css/mizkar-admin-v2-foundations.css').read_text(
            encoding='utf-8'
        )
        js = (root / 'static/js/mizkar-admin-panel-shell.js').read_text(
            encoding='utf-8'
        )
        for token in (
            'html[data-theme="dark"]',
            'prefers-reduced-motion: reduce',
            'max-width: 1024px',
            ':focus-visible',
            '--adm-v2-accent',
            'ecc-nav-item[aria-current="page"]',
        ):
            with self.subTest(token=token):
                self.assertIn(token, css)
        self.assertIn("event.key === 'Tab'", js)
        self.assertIn("event.key === 'Escape'", js)
        self.assertNotIn('initDashboardNavigation()', js)
