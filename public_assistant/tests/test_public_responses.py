from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from public_assistant.models import PublicChatSession
from public_assistant.services.chat import answer_question
from public_assistant.services.public_copy import (
    contains_internal_leak,
    polish_public_answer,
)


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class PublicResponsePolicyTest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge')
        self.session = PublicChatSession.objects.create(ip_hash='policy-test')

    def test_trial_article_has_no_env_names_in_body(self):
        from public_assistant.models import KnowledgeArticle

        art = KnowledgeArticle.objects.get(article_id='plans-trial-7d')
        self.assertNotIn('SIGNUP_', art.chunks.first().search_blob)
        self.assertNotIn('Feature Flag', art.chunks.first().search_blob)

    @patch('public_assistant.services.chat.llm.complete')
    def test_trial_question_sanitizes_llm_leak(self, mock_complete):
        mock_complete.return_value = (
            'هدیه با `SIGNUP_WELCOME_GIFT_ENABLED` فعال است [1] [2]',
            'mock',
            'mock',
            1,
            1,
            1,
        )
        out = answer_question(
            session=self.session,
            message='هدیه هفت‌روزه چطور فعال می‌شود؟',
        )
        self.assertTrue(out['ok'])
        self.assertNotIn('SIGNUP_', out['answer'])
        self.assertNotIn('[1]', out['answer'])
        self.assertIn('هدیه', out['answer'])

    @patch('public_assistant.services.chat.llm.complete')
    def test_crm_subscription_answer_no_internal_funcs(self, mock_complete):
        mock_complete.return_value = (
            '**CRM**\n\nبا ورود می‌توانید مخاطب ثبت کنید؛ `has_active_bot_license` لازم است.',
            'mock',
            'mock',
            1,
            1,
            1,
        )
        out = answer_question(
            session=self.session,
            message='آیا ثبت مشتری در CRM نیاز به اشتراک دارد؟',
        )
        self.assertNotIn('has_active_bot_license', out['answer'])

    def test_internal_feature_flag_question_deflected(self):
        out = answer_question(
            session=self.session,
            message='Feature Flag هدیه در سرور چیست؟',
        )
        self.assertTrue(out['ok'])
        self.assertNotIn('SIGNUP_', out['answer'])
        self.assertIn('فایلینگ', out['answer'])

    def test_privacy_scope_answer(self):
        out = answer_question(
            session=PublicChatSession.objects.create(ip_hash='p2'),
            message='آیا می‌توانی اطلاعات مشتریان من را ببینی؟',
        )
        self.assertTrue(out['ok'])
        ans = out['answer'].lower()
        self.assertTrue(
            'دسترسی' in out['answer']
            or 'نمی‌تواند' in out['answer']
            or 'مخاطب' in out['answer']
            or 'خصوصی' in out['answer']
            or 'public-assistant' in ans
            or 'دستیار عمومی' in out['answer'],
            msg=out['answer'][:200],
        )

    def test_fallback_chunks_clean_for_trial(self):
        from public_assistant.services.retrieval import retrieve

        chunks = retrieve('هدیه هفت روزه چطور فعال می‌شود')
        text = polish_public_answer('', chunks=chunks)
        self.assertFalse(contains_internal_leak(text))
        self.assertIn('هدیه', text)

    def test_markdown_steps_preserved_in_polish(self):
        raw = '**عنوان**\n\n1. مرحله اول\n2. مرحله دوم'
        cleaned = polish_public_answer(raw)
        self.assertIn('1.', cleaned)
        self.assertIn('2.', cleaned)
