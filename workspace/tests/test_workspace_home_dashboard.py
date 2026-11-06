"""تست‌های داشبورد میزکار V2 — بدون DB سنگین، با mock سرویس‌های وابسته."""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


class WorkspaceHomeDashboardBuildersTests(SimpleTestCase):
    def test_day_status_ok_when_empty(self):
        from workspace.services.workspace_home_dashboard import _build_day_status

        status = _build_day_status(overdue=0, today_due=0, contracts_action=0)
        self.assertEqual(status['tone'], 'ok')
        self.assertIn('فوری', status['label'])

    def test_day_status_warn_with_overdue(self):
        from workspace.services.workspace_home_dashboard import _build_day_status

        status = _build_day_status(overdue=2, today_due=1, contracts_action=0)
        self.assertEqual(status['tone'], 'warn')
        self.assertIn('معوق', status['label'])

    def test_kpi_definitions(self):
        from workspace.services.workspace_home_dashboard import _build_kpi

        with patch('workspace.services.workspace_home_dashboard.reverse', side_effect=lambda name, **kw: f'/{name}'):
            kpi = _build_kpi(
                crm_stats={
                    'overdue_followups': 2,
                    'due_today': 3,
                    'new_contacts': 4,
                    'in_progress': 5,
                    'total_contacts': 20,
                    'total_properties': 8,
                },
                deal_stats={'active': 6, 'stale': 1},
                queue_stats={'total': 7, 'overdue': 2, 'today': 5},
                active_properties=8,
            )
        self.assertEqual(kpi['today_work'], 7)
        self.assertEqual(kpi['active_contacts'], 9)
        self.assertEqual(kpi['active_properties'], 8)
        self.assertEqual(kpi['active_deals'], 6)
        self.assertEqual(kpi['stale_deals'], 1)

    def test_quick_actions_include_agency_only_when_allowed(self):
        from workspace.services.workspace_home_dashboard import _build_quick_actions

        with patch('workspace.services.workspace_home_dashboard.reverse', side_effect=lambda name, **kw: f'/{name}'):
            with_agency = _build_quick_actions(has_bot_license=True, show_agency=True)
            without = _build_quick_actions(has_bot_license=True, show_agency=False)
        self.assertTrue(any(a['key'] == 'agency' for a in with_agency))
        self.assertFalse(any(a['key'] == 'agency' for a in without))
        self.assertLessEqual(len(with_agency), 8)
        self.assertTrue(any(a['key'] == 'filing' for a in with_agency))

    def test_opportunities_skip_today_nba_cards(self):
        from workspace.services.workspace_home_dashboard import _build_opportunities

        nba = [
            {'key': 'overdue', 'title': 'معوق', 'desc': 'x', 'url': '/t', 'cta': 'a', 'tone': 'warn', 'count': 1},
            {'key': 'matches', 'title': 'تطبیق', 'desc': 'y', 'url': '/m', 'cta': 'b', 'tone': 'info', 'count': 2},
        ]
        with patch('workspace.services.workspace_home_dashboard._match_opportunities', return_value=[]):
            with patch('workspace.services.workspace_home_dashboard._stale_deal_opportunities', return_value=[]):
                result = _build_opportunities(MagicMock(), home_nba=nba)
        keys = [i['key'] for i in result['items']]
        self.assertNotIn('overdue', keys)
        self.assertIn('matches', keys)

    def test_build_dashboard_empty_user(self):
        from workspace.services.workspace_home_dashboard import build_workspace_home_dashboard

        user = MagicMock()
        ds = MagicMock()
        ds.filter.return_value = ds
        ds.count.return_value = 0
        ds.order_by.return_value.first.return_value = None
        reminders_qs = MagicMock()
        reminders_qs.filter.return_value.count.return_value = 0

        with ExitStack() as stack:
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.active_stages_for_user', return_value=[]))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard._serialize_recent_activities', return_value=[]))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard._safe_contract_needs_action', return_value=0))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard._active_properties_count', return_value=0))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.has_active_bot_license', return_value=False))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.build_dashboard_charts', return_value=[]))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.get_dashboard_stats', return_value={
                'total_contacts': 0, 'total_properties': 0, 'overdue_followups': 0, 'due_today': 0,
                'new_contacts': 0, 'in_progress': 0, 'active_reminders': 0,
            }))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.get_deal_stats', return_value={'total': 0, 'active': 0, 'stale': 0, 'by_stage': {}}))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.get_today_queue', return_value=([], {'total': 0, 'overdue': 0, 'today': 0, 'followups': 0, 'reminders': 0})))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.build_home_nba', return_value=[]))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.build_workspace_agency_panel', return_value=None))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard._match_opportunities', return_value=[]))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard._stale_deal_opportunities', return_value=[]))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.reminders_qs', return_value=reminders_qs))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.Dataset.objects.filter', return_value=ds))
            listing_filter = stack.enter_context(patch('workspace.services.workspace_home_dashboard.Listing.objects.filter'))
            stack.enter_context(patch('workspace.services.workspace_home_dashboard.reverse', side_effect=lambda name, **kw: f'/{name}'))
            visits = stack.enter_context(patch('workspace.services.workspace_home_dashboard.PropertyVisit.objects.filter'))
            listing_filter.return_value.count.return_value = 0
            visits.return_value.select_related.return_value.order_by.return_value = []
            ctx = build_workspace_home_dashboard(user)

        self.assertTrue(ctx['home_is_empty'])
        self.assertIn('home_kpi', ctx)
        self.assertIn('home_today_center', ctx)
        self.assertIn('home_opportunities', ctx)
        self.assertIn('home_deal_funnel', ctx)
        self.assertIn('home_quick_actions', ctx)
