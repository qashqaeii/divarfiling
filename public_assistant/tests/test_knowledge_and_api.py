from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from public_assistant.models import KnowledgeArticle, KnowledgeChunk
from public_assistant.services.persian_text import normalize_persian, tokenize_query
from public_assistant.services.retrieval import retrieve


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class PublicAssistantAPITest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge')
        self.client = Client(enforce_csrf_checks=True)

    def test_sync_creates_articles(self):
        self.assertGreaterEqual(KnowledgeArticle.objects.filter(is_active=True).count(), 30)
        self.assertGreater(KnowledgeChunk.objects.count(), 30)

    def test_persian_normalize(self):
        self.assertEqual(normalize_persian('كتاب'), normalize_persian('کتاب'))

    def test_retrieve_crm(self):
        hits = retrieve('چطور مشتری اضافه کنم')
        self.assertTrue(any('crm' in h.article_id or 'مخاطب' in h.title for h in hits))

    def test_config_endpoint(self):
        r = self.client.get('/api/public-assistant/config/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertTrue(len(data['suggested_questions']) >= 3)

    def test_chat_requires_csrf(self):
        r = self.client.post(
            '/api/public-assistant/chat/',
            data='{"message":"فایلینگ دیوار چیست"}',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 403)

    def test_chat_with_csrf(self):
        home = self.client.get('/contact/')
        csrf = home.cookies.get('csrftoken')
        self.assertIsNotNone(csrf)
        r = self.client.post(
            '/api/public-assistant/chat/',
            data='{"message":"فایلینگ دیوار چیست"}',
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf.value,
        )
        self.assertIn(r.status_code, (200, 429))
        if r.status_code == 200:
            data = r.json()
            self.assertTrue(data.get('ok'))
            self.assertTrue(data.get('answer'))


@override_settings(PUBLIC_ASSISTANT_ENABLED=False)
class DisabledAssistantTest(TestCase):
    def test_config_disabled(self):
        r = Client().get('/api/public-assistant/config/')
        self.assertEqual(r.status_code, 503)


class PersianTokenTest(TestCase):
    def test_tokenize(self):
        tokens = tokenize_query('ثبت مشتری در CRM')
        self.assertIn('مشتری', tokens)
