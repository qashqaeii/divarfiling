"""Unit tests for ArvanCloud AIaaS provider (HTTP mocked — no live calls)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from ai_workspace.providers.arvan import ArvanAIProvider, is_arvan_configured
from ai_workspace.providers.arvan_http import (
    build_authorization_header,
    build_chat_completions_url,
    extract_chat_message_content,
)
from ai_workspace.providers.base import ProviderError


def _ok_response(text: str, *, status=200, usage=None, model='Gemini-2.5-Flash-lite'):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {}
    resp.ok = status < 400
    body = {
        'model': model,
        'choices': [{'message': {'role': 'assistant', 'content': text}}],
        'usage': usage or {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18},
    }
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp


@override_settings(
    ARVAN_AI_ENABLED=True,
    ARVAN_AI_BASE_URL='https://arvancloudai.ir/gateway/models/test-endpoint/v1',
    ARVAN_AI_API_KEY='secret-key-12345',
    ARVAN_AI_MODEL='Gemini-2.5-Flash-lite',
    ARVAN_AI_FALLBACK_MODEL='',
    ARVAN_AI_TIMEOUT_SECONDS=10,
    ARVAN_AI_MAX_RETRIES=0,
)
class ArvanProviderTests(SimpleTestCase):
    def test_is_configured(self):
        self.assertTrue(is_arvan_configured())

    def test_successful_completion(self):
        provider = ArvanAIProvider()
        with patch('ai_workspace.providers.arvan.requests.post', return_value=_ok_response('سلام')) as post:
            result = provider.complete(system='sys', user='user')
        self.assertEqual(result.text, 'سلام')
        self.assertEqual(result.provider, 'arvan')
        self.assertEqual(result.input_tokens, 11)
        self.assertEqual(result.output_tokens, 7)
        self.assertFalse(result.is_fallback)

    def test_correct_endpoint_url(self):
        provider = ArvanAIProvider()
        with patch('ai_workspace.providers.arvan.requests.post', return_value=_ok_response('x')) as post:
            provider.complete(system='', user='u')
        url = post.call_args[0][0]
        self.assertEqual(
            url,
            'https://arvancloudai.ir/gateway/models/test-endpoint/v1/chat/completions',
        )

    def test_authorization_header(self):
        provider = ArvanAIProvider()
        with patch('ai_workspace.providers.arvan.requests.post', return_value=_ok_response('x')) as post:
            provider.complete(system='', user='u')
        headers = post.call_args[1]['headers']
        self.assertEqual(headers['Authorization'], 'apikey secret-key-12345')

    @override_settings(ARVAN_AI_API_KEY='apikey already-prefixed')
    def test_api_key_prefix_handling(self):
        self.assertEqual(build_authorization_header('apikey already-prefixed'), 'apikey already-prefixed')
        provider = ArvanAIProvider()
        with patch('ai_workspace.providers.arvan.requests.post', return_value=_ok_response('x')) as post:
            provider.complete(system='', user='u')
        self.assertEqual(post.call_args[1]['headers']['Authorization'], 'apikey already-prefixed')

    def test_correct_model_in_payload(self):
        provider = ArvanAIProvider()
        with patch('ai_workspace.providers.arvan.requests.post', return_value=_ok_response('x')) as post:
            provider.complete(system='s', user='u')
        body = post.call_args[1]['json']
        self.assertEqual(body['model'], 'Gemini-2.5-Flash-lite')
        self.assertEqual(body['messages'][0], {'role': 'system', 'content': 's'})
        self.assertEqual(body['messages'][1], {'role': 'user', 'content': 'u'})

    def test_empty_choices(self):
        provider = ArvanAIProvider()
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {}
        resp.ok = True
        resp.json.return_value = {'choices': []}
        with patch('ai_workspace.providers.arvan.requests.post', return_value=resp):
            with self.assertRaises(ProviderError) as ctx:
                provider.complete(system='', user='u')
        self.assertEqual(ctx.exception.code, 'empty_response')

    def test_empty_content(self):
        provider = ArvanAIProvider()
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {}
        resp.ok = True
        resp.json.return_value = {'choices': [{'message': {'content': ''}}]}
        with patch('ai_workspace.providers.arvan.requests.post', return_value=resp):
            with self.assertRaises(ProviderError) as ctx:
                provider.complete(system='', user='u')
        self.assertEqual(ctx.exception.code, 'empty_response')

    def test_malformed_json_response(self):
        provider = ArvanAIProvider()
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {}
        resp.ok = True
        resp.json.side_effect = ValueError('bad json')
        with patch('ai_workspace.providers.arvan.requests.post', return_value=resp):
            with self.assertRaises(ProviderError) as ctx:
                provider.complete(system='', user='u')
        self.assertEqual(ctx.exception.code, 'invalid_response')

    def test_401_auth_error(self):
        provider = ArvanAIProvider()
        resp = MagicMock()
        resp.status_code = 401
        resp.headers = {}
        resp.ok = False
        with patch('ai_workspace.providers.arvan.requests.post', return_value=resp):
            with self.assertRaises(ProviderError) as ctx:
                provider.complete(system='', user='u')
        self.assertEqual(ctx.exception.code, 'auth_error')
        self.assertFalse(ctx.exception.retryable)

    def test_429_rate_limited(self):
        provider = ArvanAIProvider()
        resp = MagicMock()
        resp.status_code = 429
        resp.headers = {}
        resp.ok = False
        with patch('ai_workspace.providers.arvan.requests.post', return_value=resp):
            with self.assertRaises(ProviderError) as ctx:
                provider.complete(system='', user='u')
        self.assertEqual(ctx.exception.code, 'rate_limited')
        self.assertTrue(ctx.exception.retryable)

    def test_502_upstream(self):
        provider = ArvanAIProvider()
        resp = MagicMock()
        resp.status_code = 502
        resp.headers = {}
        resp.ok = False
        with patch('ai_workspace.providers.arvan.requests.post', return_value=resp):
            with self.assertRaises(ProviderError) as ctx:
                provider.complete(system='', user='u')
        self.assertEqual(ctx.exception.code, 'upstream_5xx')

    def test_timeout(self):
        import requests

        provider = ArvanAIProvider()
        with patch(
            'ai_workspace.providers.arvan.requests.post',
            side_effect=requests.Timeout('timed out'),
        ):
            with self.assertRaises(ProviderError) as ctx:
                provider.complete(system='', user='u')
        self.assertEqual(ctx.exception.code, 'timeout')

    def test_connection_failure(self):
        import requests

        provider = ArvanAIProvider()
        with patch(
            'ai_workspace.providers.arvan.requests.post',
            side_effect=requests.ConnectionError('failed'),
        ):
            with self.assertRaises(ProviderError) as ctx:
                provider.complete(system='', user='u')
        self.assertEqual(ctx.exception.code, 'connection_error')

    def test_secret_not_in_exception_message(self):
        provider = ArvanAIProvider()
        resp = MagicMock()
        resp.status_code = 401
        resp.headers = {}
        resp.ok = False
        with patch('ai_workspace.providers.arvan.requests.post', return_value=resp):
            with self.assertRaises(ProviderError) as ctx:
                provider.complete(system='', user='u')
        self.assertNotIn('secret-key', str(ctx.exception))


class ArvanHttpHelperTests(SimpleTestCase):
    def test_url_normalize_no_double_slash(self):
        url = build_chat_completions_url('https://example.com/gateway/v1/')
        self.assertEqual(url, 'https://example.com/gateway/v1/chat/completions')

    def test_extract_message_content(self):
        data = {'choices': [{'message': {'content': 'ok'}}]}
        self.assertEqual(extract_chat_message_content(data), 'ok')
