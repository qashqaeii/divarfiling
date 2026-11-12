"""تحویل ۱: لینک‌های معتبر + راهنمای تیکت و استودیوی استوری."""
from __future__ import annotations

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from public_assistant.models import PublicChatSession
from public_assistant.services.chat import answer_question
from public_assistant.services.public_copy import polish_public_answer
from public_assistant.services.public_links import normalize_public_answer_links
from public_assistant.services.public_paths import canonical_public_path, scrub_commerce_links_from_answer
from public_assistant.services.retrieval import retrieve


TICKET_QUESTION = 'از کجا تیکت بزنم؟'
STORY_ANDROID_QUESTION = 'توی اندروید چطور از فایل ملک استوری بسازم؟'


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class PublicPathNormalizationTest(TestCase):
    def test_contact_us_aliases_to_contact(self):
        self.assertEqual(canonical_public_path('/contact-us/'), '/contact/')
        out = normalize_public_answer_links('تماس: [پشتیبانی](/contact-us/)')
        self.assertIn('](/contact/)', out)
        self.assertNotIn('contact-us', out)

    def test_scrub_commerce_keeps_label(self):
        raw = 'برای خرید [پلن ماهانه](/products/divar-extraction-bot/buy/) بروید.'
        out = scrub_commerce_links_from_answer(raw)
        self.assertNotIn('/products/', out)
        self.assertIn('پلن ماهانه', out)


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class Delivery1RetrievalTest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge')

    def test_ticket_question_top_article(self):
        chunks = retrieve(TICKET_QUESTION)
        self.assertTrue(chunks)
        top_ids = [c.article_id for c in chunks[:3]]
        self.assertIn(
            'support-common-errors',
            top_ids,
            msg=f'got {top_ids}',
        )

    def test_android_story_question_finds_content_studio(self):
        chunks = retrieve(STORY_ANDROID_QUESTION)
        self.assertTrue(chunks)
        self.assertEqual(chunks[0].article_id, 'content-studio-story')

    def test_story_fallback_has_steps_without_commerce(self):
        chunks = retrieve(STORY_ANDROID_QUESTION)
        text = polish_public_answer('', chunks=chunks, query=STORY_ANDROID_QUESTION)
        self.assertIn('املاک شخصی', text)
        self.assertIn('استوری', text)
        self.assertNotIn('/products/', text)


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class Delivery1ChatTest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge')
        self.session = PublicChatSession.objects.create(ip_hash='delivery1')

    @patch('public_assistant.services.chat.llm.complete')
    def test_ticket_answer_prefers_workspace_support(self, mock_complete):
        mock_complete.return_value = (
            'برای تیکت از `/contact-us/` استفاده کنید.',
            'mock',
            'mock',
            1,
            1,
            1,
        )
        out = answer_question(session=self.session, message=TICKET_QUESTION)
        self.assertTrue(out['ok'])
        self.assertIn('/workspace/support/', out['answer'])
        self.assertNotIn('contact-us', out['answer'])
        commerce_sources = [
            s for s in out.get('sources') or [] if '/products/' in s.get('url', '')
        ]
        self.assertEqual(commerce_sources, [])

    @patch('public_assistant.services.chat.llm.complete')
    def test_story_llm_fallback_uses_knowledge_not_buy_link(self, mock_complete):
        mock_complete.return_value = ('', 'mock', 'mock', 1, 0, 0)
        out = answer_question(session=self.session, message=STORY_ANDROID_QUESTION)
        self.assertTrue(out['ok'])
        self.assertIn('استودیو', out['answer'])
        self.assertNotIn('divar-extraction-bot/buy', out['answer'])
