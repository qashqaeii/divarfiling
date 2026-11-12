"""Premium admin phase 02B: consistent decision hierarchy and shared KPI cards."""
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.services.admin_presentation import prioritize_management_actions

User = get_user_model()


class AdminPresentationContractTests(SimpleTestCase):
    def test_priority_sort_critical_before_high_then_medium(self):
        original = [
            {'key': 'pending', 'priority': 'high', 'count': 7},
            {'key': 'medium', 'priority': 'medium', 'count': 200},
            {'key': 'critical-small', 'priority': 'critical', 'count': 2},
            {'key': 'critical-big', 'priority': 'critical', 'count': 9},
            {'key': 'high-small', 'priority': 'high', 'count': 1},
        ]
        ordered = prioritize_management_actions(original)
        self.assertEqual(
            [x['key'] for x in ordered],
            ['critical-big', 'critical-small', 'pending', 'high-small', 'medium'],
        )
        self.assertEqual(original[0]['key'], 'pending')

    def test_priority_sort_is_stable_on_ties(self):
        items = [
            {'key': 'first', 'priority': 'high', 'count': 3},
            {'key': 'second', 'priority': 'high', 'count': 3},
            {'key': 'missing', 'count': None},
        ]
        self.assertEqual(
            [row['key'] for row in prioritize_management_actions(items)],
            ['first', 'second', 'missing'],
        )

    def test_shared_kpi_card_has_server_rendered_value_and_chart_id(self):
        markup = render_to_string(
            'accounts/partials/admin_prime_kpi_card.html',
            {'card': {
                'key': 'revenue_period', 'icon': 'fa-sack-dollar',
                'accent': 'emerald', 'status': 'ok', 'label': 'درآمد',
                'value': 12345, 'format': 'money',
                'delta': 7, 'delta_label': 'نسبت قبل',
                'sublabel': '۳۰ روز', 'sparkline_json': '[1,2,3]',
            }, 'kpi_kind': 'range'},
        )
        self.assertIn('data-count-up="12345"', markup)
        self.assertIn('spark-revenue_period', markup)
        self.assertIn('data-kpi-kind="range"', markup)
        self.assertIn('۱۲۳۴۵', markup)
        self.assertIn('is-up', markup)

    def test_pending_kpi_displays_unknown_not_fake_zero(self):
        markup = render_to_string(
            'accounts/partials/admin_prime_kpi_card.html',
            {'card': {
                'key': 'retention_d30', 'icon': 'fa-chart-line',
                'accent': 'amber', 'status': 'ok', 'label': 'بازگشت',
                'value': 0, 'pending': True, 'format': 'percent',
                'sublabel': 'داده ناکافی',
            }, 'kpi_kind': 'range'},
        )
        self.assertIn('aria-label="داده کافی نیست"', markup)
        self.assertNotIn('data-count-up=', markup)

    def test_css_action_first_on_narrow_screens_and_audit_fold(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / 'static/css/mizkar-admin-v2-foundations.css').read_text(encoding='utf-8')
        js = (root / 'static/js/mizkar-admin-panel-shell.js').read_text(encoding='utf-8')
        self.assertIn('.adm-prime-hero__rail { order: -1; }', css)
        self.assertIn('max-width: 1099px', css)
        self.assertIn('adm-v2-audit__summary', css)
        self.assertIn('initDetailsDeepLinks()', js)


class AdminFourCenterHierarchyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='premium_center_owner', phone='09129994999',
            password='pass1234', is_staff=True, is_superuser=True,
        )
        self.staff = User.objects.create_user(
            username='premium_center_staff', phone='09129994888',
            password='pass1234', is_staff=True,
        )

    def test_four_centers_use_shared_kpi_card_and_action_first_source(self):
        self.client.force_login(self.owner)
        for name in (
            'admin_panel', 'admin_panel_sales',
            'admin_panel_users', 'admin_panel_licenses',
        ):
            with self.subTest(name=name):
                response = self.client.get(reverse(name), {'days': '7'})
                self.assertEqual(response.status_code, 200)
                html = response.content.decode('utf-8')
                self.assertIn('adm-v2-kpi-card', html)
                self.assertIn('adm-prime-hero', html)
                self.assertIn('adm-prime-hero__rail', html)
                self.assertIn('adm-prime-hero__chart', html)
                self.assertIn('adm-prime-action-queue', html)

    def test_sales_integrity_moves_below_today_and_opens_on_query(self):
        self.client.force_login(self.owner)
        url = reverse('admin_panel_sales')
        response = self.client.get(
            url, {'days': '7', 'audit': 'complete_without_license'}
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertLess(
            html.index('adm-prime-today-block'),
            html.index('id="sales-integrity"'),
        )
        self.assertIn('id="sales-integrity" open', html)
        self.assertIn('id="sales-integrity-results"', html)
        self.assertIn('ممکن است هم‌پوشانی داشته باشند', html)

    def test_non_privileged_user_sees_no_dead_personal_actions(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin_panel_users'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertNotIn('جستجو، فیلتر و پرونده کاربر', html)
        self.assertIn('پرونده فردی کاربران', html)
        self.assertNotIn('class="adm-prime-today__item adm-prime-today__item--link" href="#ecc-users-mgmt"', html)
