"""Phase 03B: verify Command chart parity and honest summary export windows."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.services.admin_dashboard import (
    build_charts_payload,
    get_command_center_context,
    get_command_revenue_chart,
)

User = get_user_model()


class CommandChartPerformanceRegressionTests(TestCase):
    def test_command_chart_matches_full_analytics_contract(self):
        for days in (1, 7, 30):
            with self.subTest(days=days):
                compact = get_command_revenue_chart(days)
                complete = build_charts_payload(days)
                self.assertEqual(
                    compact['revenue_analytics'],
                    complete['revenue_analytics'],
                )
                self.assertEqual(set(compact), {'revenue_analytics'})
                self.assertEqual(len(compact['revenue_analytics']['datasets']), 3)

    def test_compact_chart_skips_unrelated_full_dashboard_subsystems(self):
        unrelated = (
            'get_user_registration_series',
            'get_order_status_breakdown',
            'get_license_status_breakdown',
            'get_payment_method_breakdown',
            'get_plan_sales_breakdown',
            'get_product_revenue',
        )
        # The test uses one ExitStack rather than mocking the chart itself.
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name in unrelated:
                stack.enter_context(patch(
                    'accounts.services.admin_dashboard.' + name,
                    side_effect=AssertionError('unrelated chart loaded: ' + name),
                ))
            result = get_command_revenue_chart(7)
        self.assertEqual(set(result), {'revenue_analytics'})

    def test_command_context_does_not_call_full_chart_builder(self):
        with patch(
            'accounts.services.admin_dashboard.build_charts_payload',
            side_effect=AssertionError('full chart builder should not run'),
        ):
            context = get_command_center_context(days=7)
        self.assertEqual(set(context['charts']), {'revenue_analytics'})


class CommandSummaryExportWindowTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='phase03b_staff', phone='09129996344',
            password='test-pass', is_staff=True,
        )
        self.client.force_login(self.staff)

    def test_json_export_link_shows_actual_supported_window(self):
        for selected, expected in (
            ('all', 30),
            ('1', 7),
            ('7', 7),
            ('30', 30),
            ('90', 90),
        ):
            with self.subTest(selected=selected):
                response = self.client.get(
                    reverse('admin_panel'), {'days': selected},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.context['system_summary_trend_days'], expected,
                )
                self.assertContains(
                    response, '?days=%d&amp;download=1' % expected,
                )
                self.assertContains(response, 'خلاصه آماری سیستم؛ روندهای')
