from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from public_assistant.models import PublicChatSession
from public_assistant.services.chat import answer_question
from public_assistant.services.public_copy import (
    contains_internal_leak,
    insufficient_info_message,
    polish_public_answer,
)

GOLDEN_HOWTO_QUESTIONS = [
    'چطوری مخاطب ثبت کنم؟',
    'چطوری فایل شخصی داشته باشم؟',
    'لینک برای مشتری چطوری بفرستم؟',
    'شماره تماس کجا وارد کنم در فایل شخصی؟',
    'چطوری لینک برای مشتری بسازیم؟',
]


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

    def test_extractor_overview_kb_no_browser_rate_limit_disclaimer(self):
        from public_assistant.models import KnowledgeArticle

        art = KnowledgeArticle.objects.get(article_id='extractor-overview')
        blob = ' '.join(c.search_blob for c in art.chunks.all())
        self.assertNotIn('استخراج مستقیم از مرورگر', blob)
        self.assertNotIn('محدودیت نرخ و قوانین دیوار', blob)

    def test_public_product_paths_in_backticks_not_leaks(self):
        self.assertFalse(contains_internal_leak('از `/workspace/` وارد شوید'))
        self.assertFalse(contains_internal_leak('از `/contact/` کمک بگیرید'))
        self.assertFalse(contains_internal_leak('مسیر `/p/` را باز کنید'))
        self.assertFalse(contains_internal_leak('مخاطبین: `/workspace/crm/contacts/`'))

    def test_internal_snake_case_in_backticks_still_blocked(self):
        self.assertTrue(contains_internal_leak('نیاز به `has_active_bot_license` دارد'))

    def test_sanitize_strips_unique_together_jargon(self):
        from public_assistant.services.public_copy import sanitize_public_knowledge_text

        raw = 'یکتا است (`unique_together dataset+token`).'
        cleaned = sanitize_public_knowledge_text(raw)
        self.assertNotIn('unique_together', cleaned.lower())
        self.assertFalse(contains_internal_leak(cleaned))

    def test_polish_keeps_answer_with_workspace_paths(self):
        raw = (
            '**ثبت مخاطب**\n\n'
            '1. به `/workspace/crm/contacts/` بروید\n'
            '2. مخاطب جدید را بزنید'
        )
        cleaned = polish_public_answer(raw)
        self.assertIn('/workspace/crm/contacts/', cleaned)
        self.assertNotEqual(cleaned, insufficient_info_message())

    @patch('public_assistant.services.chat.llm.complete')
    def test_howto_contact_not_replaced_by_insufficient(self, mock_complete):
        mock_complete.return_value = (
            '**ثبت مخاطب**\n\n'
            'از `/workspace/crm/contacts/` وارد شوید و مخاطب جدید بسازید.',
            'mock',
            'mock',
            1,
            1,
            1,
        )
        out = answer_question(session=self.session, message='چطوری مخاطب ثبت کنم؟')
        self.assertTrue(out['ok'])
        self.assertNotIn('اطلاعات تأییدشدهٔ کافی', out['answer'])
        self.assertIn('مخاطب', out['answer'])

    def test_golden_howto_retrieval_and_fallback(self):
        from public_assistant.services.retrieval import retrieve

        for q in GOLDEN_HOWTO_QUESTIONS:
            chunks = retrieve(q)
            self.assertTrue(chunks, msg=q)
            fallback = polish_public_answer('', chunks=chunks)
            self.assertNotEqual(
                fallback,
                insufficient_info_message(),
                msg=f'fallback empty for: {q}',
            )
            self.assertNotIn('اطلاعات تأییدشدهٔ کافی', fallback, msg=q)

    def test_polish_strips_extractor_auto_disclaimer(self):
        raw = (
            '**راهنما**\n\nمتن.\n\n'
            'نکته: استخراج مستقیم از مرورگر معمولاً جایگزین اپ نیست. همچنین، '
            'محدودیت نرخ و قوانین دیوار ممکن است استخراج را کند یا موقتاً متوقف کند '
            'و بدون اینترنت نیز همگام‌سازی با میزکار انجام نمی‌شود.'
        )
        cleaned = polish_public_answer(raw)
        self.assertNotIn('استخراج مستقیم از مرورگر', cleaned)
        self.assertIn('راهنما', cleaned)
