"""Gateway provider chain scenarios — Arvan primary production."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_workspace.providers.base import ProviderError, ProviderResult
from ai_workspace.services.gateway import run
from ai_workspace.services.quota import QuotaExceededError, get_or_create_quota

User = get_user_model()

_CTX = {
    'title': 'آپارتمان',
    'price_label': '۱۲ میلیارد تومان',
    'content_version': 'chain-test',
}

_OK_JSON = (
    '{"summary":"خلاصه تست زنجیره provider برای آگهی نمونه","highlights":[],'
    '"negotiation_tip":"","advertiser_note":""}'
)


def _result(provider: str, model: str = 'm', is_fallback: bool = False) -> ProviderResult:
    return ProviderResult(
        text=_OK_JSON,
        provider=provider,
        model=model,
        input_tokens=5,
        output_tokens=3,
        latency_ms=50,
        is_fallback=is_fallback,
    )


def _fail():
    return ProviderError('429', retryable=True, code='429')


def _chain(arvan=None, openrouter=None, gemini_p=None, gemini_l=None):
    """Order: Arvan, OpenRouter, Gemini Primary, Gemini Lite."""
    a, o, gp, gl = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    for mock, behavior in ((a, arvan), (o, openrouter), (gp, gemini_p), (gl, gemini_l)):
        if behavior == 'ok':
            prov = 'arvan' if mock is a else 'openrouter' if mock is o else 'gemini'
            mock.complete.return_value = _result(prov, is_fallback=(mock is not a))
        elif behavior == 'fail':
            mock.complete.side_effect = _fail()
        else:
            mock.complete.side_effect = _fail()
    return [a, o, gp, gl]


@override_settings(AI_ENABLED=True, GEMINI_API_KEY='test')
class GatewayChainScenarioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='chain_staff', password='x', is_staff=True, phone='09120000004',
        )

    def _run(self, chain, content_version='cv1'):
        with patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=chain):
            return run(
                'listing_summary',
                self.user,
                context={**_CTX, 'content_version': content_version},
                entity_type='listing',
                entity_id='1',
            )

    def test_scenario_a_arvan_success_only(self):
        chain = _chain(arvan='ok', openrouter='fail', gemini_p='fail', gemini_l='fail')
        result = self._run(chain, 'a')
        self.assertEqual(result.provider, 'arvan')
        chain[0].complete.assert_called_once()
        chain[1].complete.assert_not_called()
        chain[2].complete.assert_not_called()
        chain[3].complete.assert_not_called()

    def test_scenario_a_provider_attempt_one(self):
        chain = _chain(arvan='ok')
        with patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=chain):
            with patch('ai_workspace.services.gateway._log_usage') as log_mock:
                self._run(chain, 'a-attempt')
        log_mock.assert_called()
        self.assertEqual(log_mock.call_args.kwargs.get('provider_attempt'), 1)

    def test_scenario_b_arvan_fail_openrouter_ok(self):
        chain = _chain(arvan='fail', openrouter='ok', gemini_p='fail', gemini_l='fail')
        result = self._run(chain, 'b')
        self.assertEqual(result.provider, 'openrouter')
        chain[0].complete.assert_called_once()
        chain[1].complete.assert_called_once()
        chain[2].complete.assert_not_called()
        chain[3].complete.assert_not_called()

    def test_scenario_c_gemini_primary_after_or_fail(self):
        chain = _chain(arvan='fail', openrouter='fail', gemini_p='ok', gemini_l='fail')
        result = self._run(chain, 'c')
        self.assertEqual(result.provider, 'gemini')
        chain[3].complete.assert_not_called()

    def test_scenario_d_all_http_fail_rule_based(self):
        chain = _chain(arvan='fail', openrouter='fail', gemini_p='fail', gemini_l='fail')
        result = self._run(chain, 'd')
        self.assertEqual(result.provider, 'rule_based')

    def test_scenario_e_cache_hit_no_http(self):
        chain = _chain(arvan='ok')
        ctx = {**_CTX, 'content_version': 'cache-e-fixed'}
        with patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=chain):
            run('listing_summary', self.user, context=ctx, entity_type='listing', entity_id='ce')
            result = run('listing_summary', self.user, context=ctx, entity_type='listing', entity_id='ce')
        self.assertTrue(result.from_cache)
        self.assertEqual(chain[0].complete.call_count, 1)

    def test_scenario_f_quota_exceeded_no_http(self):
        chain = _chain(arvan='ok')
        with patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=chain):
            with patch('ai_workspace.services.gateway.check_quota', side_effect=QuotaExceededError('daily')):
                with self.assertRaises(QuotaExceededError):
                    run(
                        'listing_summary',
                        self.user,
                        context={**_CTX, 'content_version': 'quota-f'},
                        entity_type='listing',
                        entity_id='qf',
                    )
        chain[0].complete.assert_not_called()

    @override_settings(AI_ENABLED=True, AI_LICENSED_UNLIMITED=True, GEMINI_API_KEY='test')
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    @patch('ai_workspace.services.gateway._global_cap_reached', return_value=True)
    def test_global_cap_does_not_bypass_free_quota(self, _cap, _lic):
        free_user = User.objects.create_user(
            username='free_cap_user', password='x', phone='09120000099',
        )
        quota = get_or_create_quota(free_user)
        quota.used_today = 30
        quota.save(update_fields=['used_today'])
        chain = _chain(arvan='ok')
        with patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=chain):
            with self.assertRaises(QuotaExceededError):
                run(
                    'listing_summary',
                    free_user,
                    context={**_CTX, 'content_version': 'global-cap-quota'},
                    entity_type='listing',
                    entity_id='gcq',
                )
        chain[0].complete.assert_not_called()

    @override_settings(AI_ENABLED=True, AI_LICENSED_UNLIMITED=True, GEMINI_API_KEY='test')
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    @patch('ai_workspace.services.gateway._global_cap_reached', return_value=True)
    def test_global_cap_rule_based_when_quota_remaining(self, _cap, _lic):
        free_user = User.objects.create_user(
            username='free_cap_ok', password='x', phone='09120000098',
        )
        chain = _chain(arvan='ok')
        with patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=chain):
            result = run(
                'listing_summary',
                free_user,
                context={**_CTX, 'content_version': 'global-cap-ok'},
                entity_type='listing',
                entity_id='gco',
            )
        self.assertEqual(result.provider, 'rule_based')
        chain[0].complete.assert_not_called()

    @override_settings(AI_ENABLED=True, AI_LICENSED_UNLIMITED=True, GEMINI_API_KEY='test')
    @patch('ai_workspace.services.gateway.has_active_bot_license', return_value=False, create=True)
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    @patch('ai_workspace.services.gateway._global_cap_reached', return_value=True)
    def test_global_cap_does_not_bypass_free_quota(self, _cap, _lic_quota, _lic_gw):
        free_user = User.objects.create_user(
            username='free_cap_user', password='x', phone='09120000099',
        )
        quota = get_or_create_quota(free_user)
        quota.used_today = 30
        quota.save(update_fields=['used_today'])
        chain = _chain(arvan='ok')
        with patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=chain):
            with self.assertRaises(QuotaExceededError):
                run(
                    'listing_summary',
                    free_user,
                    context={**_CTX, 'content_version': 'global-cap-quota'},
                    entity_type='listing',
                    entity_id='gcq',
                )
        chain[0].complete.assert_not_called()

    @override_settings(AI_ENABLED=True, AI_LICENSED_UNLIMITED=True, GEMINI_API_KEY='test')
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    @patch('ai_workspace.services.gateway._global_cap_reached', return_value=True)
    def test_global_cap_rule_based_when_quota_remaining(self, _cap, _lic):
        free_user = User.objects.create_user(
            username='free_cap_ok', password='x', phone='09120000098',
        )
        chain = _chain(arvan='ok')
        with patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=chain):
            result = run(
                'listing_summary',
                free_user,
                context={**_CTX, 'content_version': 'global-cap-ok'},
                entity_type='listing',
                entity_id='gco',
            )
        self.assertEqual(result.provider, 'rule_based')
        chain[0].complete.assert_not_called()
