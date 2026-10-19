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
        self.assertTrue(any(h.article_id == 'crm-contacts' for h in hits))

    def test_config_sets_csrf(self):
        r = self.client.get('/api/public-assistant/config/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(self.client.cookies.get('csrftoken'))
        data = r.json()
        self.assertTrue(data['ok'])

    def test_chat_requires_csrf(self):
        r = self.client.post(
            '/api/public-assistant/chat/',
            data='{"message":"فایلینگ دیوار چیست"}',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 403)


@override_settings(PUBLIC_ASSISTANT_ENABLED=False)
class DisabledAssistantTest(TestCase):
    def test_config_disabled(self):
        r = Client().get('/api/public-assistant/config/')
        self.assertEqual(r.status_code, 503)


class PersianTokenTest(TestCase):
    def test_tokenize_synonym(self):
        tokens = tokenize_query('ثبت مشتری')
        self.assertTrue('مخاطب' in tokens or 'مشتری' in tokens)
