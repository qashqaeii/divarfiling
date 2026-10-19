import json
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings

from public_assistant.models import KnowledgeArticle, PublicChatSession
from public_assistant.services.chat import answer_question
from public_assistant.services.rate_limit import client_ip
from public_assistant.services.security import is_allowed_public_link
from django.test import RequestFactory
from public_assistant.tests.eval_dataset import EVAL_QUESTIONS


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class FirstVisitHomeChatTest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge')
        self.client = Client(enforce_csrf_checks=True)

    def test_first_visit_home_then_chat(self):
        home = self.client.get('/')
        self.assertEqual(home.status_code, 200)
        self.assertIn('pa-head__badge', home.content.decode('utf-8'))
        csrf = self.client.cookies.get('csrftoken')
        self.assertIsNotNone(csrf, 'صفحه اصلی باید CSRF cookie بدهد')
        r = self.client.post(
            '/api/public-assistant/chat/',
            data=json.dumps({'message': 'فایلینگ دیوار چیست'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf.value,
        )
        self.assertIn(r.status_code, (200, 429))
        if r.status_code == 200:
            self.assertTrue(r.json().get('ok'))


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class SessionSecurityTest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge')
        self.client = Client(enforce_csrf_checks=True)

    def test_json_session_id_cannot_hijack_other_cookie(self):
        other = PublicChatSession.objects.create(ip_hash='other')
        self.client.get('/api/public-assistant/config/')
        csrf = self.client.cookies.get('csrftoken').value
        own = PublicChatSession.objects.create(ip_hash='mine')
        self.client.cookies['pa_session'] = str(own.id)
        r = self.client.post(
            '/api/public-assistant/chat/',
            data=json.dumps({'message': 'تست', 'session_id': str(other.id)}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get('session_id'), str(own.id))


@override_settings(
    PUBLIC_ASSISTANT_ENABLED=True,
    PUBLIC_ASSISTANT_SESSION_CREATE_LIMIT_PER_HOUR=1,
)
class SessionCreateRateLimitTest(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        call_command('sync_public_knowledge')
        self.client = Client(enforce_csrf_checks=True)

    def _post_chat_no_session_cookie(self):
        self.client.cookies.pop('pa_session', None)
        self.client.get('/api/public-assistant/config/')
        csrf = self.client.cookies.get('csrftoken').value
        return self.client.post(
            '/api/public-assistant/chat/',
            data=json.dumps({'message': 'سلام'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf,
        )

    def test_chat_without_cookie_429_after_session_create_quota(self):
        first = self._post_chat_no_session_cookie()
        self.assertEqual(first.status_code, 200)
        second = self._post_chat_no_session_cookie()
        self.assertEqual(second.status_code, 429)
        self.assertFalse(second.json().get('ok'))


@override_settings(PUBLIC_ASSISTANT_TRUSTED_PROXY_IPS=['127.0.0.1'])
class ClientIpTrustTest(TestCase):
    def test_uses_last_x_forwarded_for_behind_trusted_proxy(self):
        req = RequestFactory().get(
            '/',
            REMOTE_ADDR='127.0.0.1',
            HTTP_X_FORWARDED_FOR='203.0.113.50, 198.51.100.99',
        )
        self.assertEqual(client_ip(req), '198.51.100.99')

    def test_ignores_x_forwarded_for_without_trusted_proxy(self):
        req = RequestFactory().get(
            '/',
            REMOTE_ADDR='203.0.113.50',
            HTTP_X_FORWARDED_FOR='1.2.3.4',
        )
        self.assertEqual(client_ip(req), '203.0.113.50')


class LinkSecurityTest(TestCase):
    def test_blocks_evil_hosts(self):
        self.assertFalse(is_allowed_public_link('https://evil.com/phish'))
        self.assertFalse(is_allowed_public_link('//evil.com'))
        self.assertFalse(is_allowed_public_link('javascript:alert(1)'))
        self.assertTrue(is_allowed_public_link('/products/'))
        self.assertTrue(is_allowed_public_link('https://divarfiling.ir/about/'))


class SyncAbortTest(TestCase):
    def test_invalid_article_aborts_sync(self):
        from pathlib import Path
        from django.conf import settings

        call_command('sync_public_knowledge')
        articles = Path(settings.BASE_DIR) / 'public_assistant' / 'knowledge' / 'articles'
        bad = articles / '__test_bad_sync__.md'
        bad.write_text('no frontmatter\n', encoding='utf-8')
        count_before = KnowledgeArticle.objects.filter(is_active=True).count()
        try:
            with self.assertRaises(CommandError):
                call_command('sync_public_knowledge')
            count_after = KnowledgeArticle.objects.filter(is_active=True).count()
            self.assertEqual(count_before, count_after)
        finally:
            if bad.exists():
                bad.unlink()
            call_command('sync_public_knowledge')


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class EvalRetrievalTest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge')
        from public_assistant.services.retrieval import retrieve

        self.retrieve = retrieve

    def test_eval_question_retrieval(self):
        from public_assistant.services.retrieval import retrieve

        misses = []
        for query, expected in EVAL_QUESTIONS:
            hits = retrieve(query)
            ids = [h.article_id for h in hits[:3]]
            if expected not in ids:
                misses.append((query, expected, ids))
        hit_rate = (len(EVAL_QUESTIONS) - len(misses)) / len(EVAL_QUESTIONS)
        self.assertGreaterEqual(hit_rate, 0.8, msg=f'retrieval misses ({len(misses)}): {misses[:10]}')


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class MockLLMChatTest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge')

    @patch('public_assistant.services.chat.llm.complete')
    def test_llm_path_uses_mock(self, mock_complete):
        mock_complete.return_value = ('پاسخ تست از mock', 'mock', 'mock', 5, 10, 20)
        session = PublicChatSession.objects.create(ip_hash='t')
        out = answer_question(session=session, message='چطور مشتری اضافه کنم')
        self.assertTrue(out['ok'])
        self.assertIn('mock', out['answer'])
        mock_complete.assert_called_once()

    @patch('public_assistant.services.chat.llm.complete')
    def test_low_confidence_skips_llm(self, mock_complete):
        session = PublicChatSession.objects.create(ip_hash='t')
        out = answer_question(session=session, message='qwertyuiop zzxxcc')
        self.assertNotIn('mock', out.get('answer', ''))
        mock_complete.assert_not_called()
