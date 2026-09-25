"""تست مرکز AI — KPI، امنیت، JSON و export."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_ai_center import (
    format_latency_seconds,
    get_ai_recent_logs,
    CACHE_HIT_Q,
    PROVIDER_SUCCESS_Q,
    build_ai_center_context,
    build_ai_stats_json,
    get_ai_feature_breakdown,
    get_ai_kpis,
    get_ai_top_users,
)
from accounts.services.admin_dashboard import _date_range
from accounts.services.admin_exports import build_export
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from ai_workspace.models import AIQuota, AIUsageLog

User = get_user_model()


def _log(user, **kwargs):
    defaults = {
        'user': user,
        'feature_code': 'nl_command',
        'provider': 'arvan',
        'model': 'test-model',
        'status': AIUsageLog.STATUS_OK,
        'cache_hit': False,
        'input_tokens': 10,
        'output_tokens': 5,
        'total_tokens': 15,
        'latency_ms': 120,
    }
    defaults.update(kwargs)
    return AIUsageLog.objects.create(**defaults)


@override_settings(TIME_ZONE='Asia/Tehran')
class AiCenterServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='aiu1', password='x', phone='09120001001')
        self.other = User.objects.create_user(username='aiu2', password='x', phone='09120001002')

    def test_recent_log_latency_and_cost(self):
        _log(
            self.user,
            model='Gemini-2.5-Flash-lite',
            input_tokens=1000,
            output_tokens=500,
            latency_ms=2340,
            cache_hit=False,
        )
        rows = get_ai_recent_logs(7)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['latency_label'], '2.3s')
        self.assertGreater(rows[0]['cost_toman'], 0)

    def test_recent_log_cached_no_cost(self):
        _log(
            self.user,
            model='Gemini-2.5-Flash-lite',
            input_tokens=1000,
            output_tokens=0,
            cache_hit=True,
            status=AIUsageLog.STATUS_CACHED,
        )
        rows = get_ai_recent_logs(7)
        self.assertIsNone(rows[0]['cost_formatted'])

    def test_format_latency_seconds(self):
        self.assertEqual(format_latency_seconds(2000)['display'], '2s')
        self.assertEqual(format_latency_seconds(3500)['display'], '3.5s')

    def test_estimated_cost_in_kpis(self):
        _log(
            self.user,
            model='Gemini-2.5-Flash-lite',
            input_tokens=1_000_000,
            output_tokens=0,
            cache_hit=False,
        )
        kpis = get_ai_kpis(7)
        self.assertGreaterEqual(kpis['cost_estimate']['total_toman'], 21000)

    def test_cached_rows_excluded_from_cost(self):
        _log(
            self.user,
            model='Gemini-2.5-Flash-lite',
            input_tokens=1_000_000,
            output_tokens=0,
            cache_hit=True,
            status=AIUsageLog.STATUS_CACHED,
        )
        kpis = get_ai_kpis(7)
        self.assertEqual(kpis['cost_estimate']['total_toman'], 0)

    def test_kpi_totals_and_cache(self):
        _log(self.user, status=AIUsageLog.STATUS_OK, cache_hit=False)
        _log(self.user, status=AIUsageLog.STATUS_CACHED, cache_hit=True, total_tokens=0)
        _log(self.user, status=AIUsageLog.STATUS_ERROR, cache_hit=False)
        _log(self.user, status=AIUsageLog.STATUS_QUOTA, cache_hit=False)
        _log(self.other, status=AIUsageLog.STATUS_FALLBACK, cache_hit=False, total_tokens=20)

        kpis = get_ai_kpis(7)
        self.assertEqual(kpis['total_requests'], 5)
        self.assertEqual(kpis['cache_hits'], 1)
        self.assertEqual(kpis['errors'], 1)
        self.assertEqual(kpis['quota_exceeded'], 1)
        self.assertEqual(kpis['provider_success'], 2)
        self.assertEqual(kpis['active_users'], 2)
        self.assertGreaterEqual(kpis['total_tokens'], 35)

    def test_top_users_modes_deterministic(self):
        _log(self.user, total_tokens=100, feature_code='nl_command')
        _log(self.user, total_tokens=50, feature_code='crm_message')
        _log(self.other, total_tokens=10)
        by_token = get_ai_top_users(7, mode='tokens')
        self.assertEqual(by_token[0]['user_id'], self.user.pk)
        by_req = get_ai_top_users(7, mode='requests')
        self.assertEqual(by_req[0]['requests'], 2)
        by_nl = get_ai_top_users(7, mode='nl_command')
        self.assertEqual(by_nl[0]['requests'], 1)

    def test_feature_breakdown_percentages(self):
        _log(self.user, feature_code='nl_command', total_tokens=30)
        _log(self.other, feature_code='crm_message', total_tokens=70)
        rows = get_ai_feature_breakdown(7)
        self.assertEqual(sum(r['request_share_pct'] for r in rows), 100.0)
        self.assertEqual(sum(r['token_share_pct'] for r in rows), 100.0)

    def test_range_excludes_old_rows(self):
        old = timezone.now() - timezone.timedelta(days=40)
        log = _log(self.user)
        AIUsageLog.objects.filter(pk=log.pk).update(created_at=old)
        _log(self.other)
        kpis = get_ai_kpis(7)
        self.assertEqual(kpis['total_requests'], 1)

    def test_no_prompt_text_in_context(self):
        _log(self.user, prompt_hash='abc123secret')
        ctx = build_ai_center_context(days=7)
        for row in ctx['recent_logs']:
            self.assertNotIn('prompt', row)
            self.assertNotIn('result_text', row)
        payload = str(ctx)
        self.assertNotIn('nl_command_v', payload)
        self.assertNotIn('فرمان خیلی', payload)

    def test_compare_deltas(self):
        _log(self.user)
        kpis = get_ai_kpis(7, compare=True)
        self.assertIn('deltas', kpis)


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminAiCenterViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.staff = User.objects.create_user(
            username='aistaff', password='pass1234', phone='09120001003', is_staff=True,
        )
        self.user = User.objects.create_user(username='aiu3', password='x', phone='09120001004')

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse('admin_panel_ai')).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin_panel_ai')).status_code, 403)

    def test_render_and_nav(self):
        _log(self.user)
        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90', 'all'):
            resp = self.client.get(reverse('admin_panel_ai'), {'days': days})
            self.assertEqual(resp.status_code, 200)
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/ai/'), 'ai')
        resp = self.client.get(reverse('admin_panel_ai'), {'days': '30', 'compare': '1'})
        self.assertIn('compare=1', resp.content.decode())

    def test_stats_json(self):
        _log(self.user)
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_ai_stats_json'), {'days': '7'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['kpis']['total_requests'], 1)

    def test_export_xlsx(self):
        _log(self.user)
        self.client.force_login(self.staff)
        resp = build_export('ai_usage', fmt='xlsx', days=7)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'PK', resp.content[:4])


@override_settings(TIME_ZONE='Asia/Tehran')
class AiCenterQueryConstantsTests(TestCase):
    def test_status_q_objects(self):
        self.assertTrue(str(PROVIDER_SUCCESS_Q))
        self.assertTrue(str(CACHE_HIT_Q))
