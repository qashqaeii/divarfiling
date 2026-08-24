"""Tests for FCM push resilience helpers."""
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from mobile_api.services import push_service


class PushServiceResilienceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        push_service._oauth_token_cache['token'] = None
        push_service._oauth_token_cache['expires_at'] = 0.0

    def test_circuit_open_skips_send_without_network(self):
        cache.set(push_service.FCM_CIRCUIT_OPEN_KEY, True, 60)
        stats = push_service.send_push_to_tokens(
            ['token-a', 'token-b'],
            title='t',
            body='b',
        )
        self.assertEqual(stats['attempted'], 2)
        self.assertEqual(stats['success'], 0)
        self.assertEqual(stats['failure'], 2)

    @patch('mobile_api.services.push_service._get_v1_access_token', return_value=None)
    def test_no_access_token_does_not_crash(self, _mock_token):
        stats = push_service.send_push_to_tokens(['token-a'], title='t', body='b')
        self.assertEqual(stats['failure'], 1)

    def test_record_failures_opens_circuit(self):
        for _ in range(push_service.FCM_CIRCUIT_FAIL_THRESHOLD):
            push_service._record_fcm_failure('test')
        self.assertTrue(push_service._circuit_is_open())
