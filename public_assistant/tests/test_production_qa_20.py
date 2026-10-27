"""رگرسیون ۲۰ مکالمه واقعی production — intent، بازیابی و پاسخ نهایی (Mock LLM)."""
from __future__ import annotations

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from public_assistant.audit.retrieval_baseline import evaluate_retrieval
from public_assistant.audit.retrieval_offline import make_offline_retrieve_fn
from public_assistant.models import PublicChatSession
from public_assistant.services.chat import answer_question
from public_assistant.services.plan_intent import analyze_subscription_query

_SUBSCRIPTION_LEAK = (
    'divar-extraction-bot/buy',
    'پلن **یک‌ماهه شخصی**',
    'برای کار **تک‌نفره**',
    '۳× ماهانه',
)

# (سؤال کوتاه‌شده, مقاله هدف, is_subscription باید False باشد)
PRODUCTION_RETRIEVAL: list[tuple[str, str, bool]] = [
    (
        'بودجه ۱۰ میلیارد فایل ۱۰ میلیارد و ۵۰۰ میلیون پیشنهاد تطبیق',
        'crm-matching',
        False,
    ),
    (
        'آگهی دیوار قیمت مشخصات تغییر کند به‌روزرسانی فایلینگ',
        'filing-listing-sync-update',
        False,
    ),
    (
        'محدوده هویتی مخاطب محله خرید تطبیق کدام اطلاعات',
        'crm-matching',
        False,
    ),
    (
        'بودجه ۱۳ تا ۱۸ میلیارد محله صیاد عدالت آپادانا پیشنهاد صفر',
        'crm-matching',
        False,
    ),
    (
        'ملک زونکن فروش نمی‌بینم',
        'crm-property-folders-cabinets',
        False,
    ),
    (
        'بایگانی گروهی مخاطب یادداشت فعالیت حذف',
        'crm-contact-archive',
        False,
    ),
    (
        'قرارداد اجاره یادآوری یک ماه قبل پایان',
        'crm-rental-renewal-reminder',
        False,
    ),
    (
        'ملک شخصی بایگانی وضعیت معامله',
        'crm-property-archive',
        False,
    ),
    (
        'انتقال گروهی آگهی فایل شخصی زونکن',
        'filing-bulk-to-personal',
        False,
    ),
    (
        'محله خیابان عنوان آگهی اولویت',
        'filing-location-fields',
        False,
    ),
    (
        'آگهی تکراری دو dataset',
        'filing-listing-duplicates',
        False,
    ),
    (
        'استخراج اندروید چه اطلاعات ذخیره تصویر ویدئو',
        'filing-listing-fields',
        False,
    ),
    (
        '۲۰ هزار آگهی ۳ هزار ملک شخصی تطبیق همه بررسی صفحه',
        'crm-matching',
        False,
    ),
    (
        'متراژ فقط توضیحات آگهی تطبیق',
        'crm-matching',
        False,
    ),
    (
        'چند نیاز مختلف مشتری خرید و اجاره crm',
        'crm-contacts',
        False,
    ),
    (
        'مخاطب خریدار بایگانی بازیابی یادداشت',
        'crm-contact-archive',
        False,
    ),
    (
        'افزودن آگهی فایل شخصی زونکن همان لحظه',
        'filing-listing-manage',
        False,
    ),
]


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class ProductionIntentRegressionTest(TestCase):
    def test_production_questions_not_subscription(self):
        for query, _article, expect_sub in PRODUCTION_RETRIEVAL:
            ctx = analyze_subscription_query(query)
            if expect_sub:
                self.assertTrue(ctx.is_subscription, msg=query)
            else:
                self.assertFalse(
                    ctx.is_subscription,
                    msg=f'subscription misfire: {query[:60]}',
                )


class ProductionRetrievalRegressionTest(TestCase):
    def setUp(self):
        from public_assistant.audit.retrieval_offline import _load_offline_chunks

        _load_offline_chunks.cache_clear()

    def test_production_hit_at_5(self):
        pairs = [(q, a) for q, a, _ in PRODUCTION_RETRIEVAL]
        report = evaluate_retrieval(make_offline_retrieve_fn(), pairs)
        self.assertGreaterEqual(
            report['article_hit_at_5'],
            0.85,
            msg=report.get('misses'),
        )


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class ProductionAnswerRegressionTest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge')

    @patch('public_assistant.services.chat.llm.complete')
    def test_no_subscription_pitch_on_product_questions(self, mock_llm):
        """LLM شبیه‌سازی پاسخ حاوی پلن — باید strip شود اگر intent محصول باشد."""
        mock_llm.return_value = (
            'پاسخ تست.\n\nبرای کار **تک‌نفره**، پلن **یک‌ماهه شخصی**: **۹۹۰٬۰۰۰ تومان**\n'
            '[خرید](/products/divar-extraction-bot/buy/?plan=1)',
            'mock',
            'mock',
            1,
            10,
            20,
        )
        samples = [
            'اگر مشتری بودجه ۱۰ میلیارد داشته باشد آیا فایل ۱۰ میلیارد و ۵۰۰ میلیون پیشنهاد می‌شود؟',
            'وقتی آگهی دیوار قیمتش عوض شود آیا فایلینگ به‌روز می‌شود؟',
        ]
        for msg in samples:
            session = PublicChatSession.objects.create(ip_hash='prod-qa')
            out = answer_question(session=session, message=msg)
            self.assertTrue(out['ok'], msg=msg)
            ans = out.get('answer') or ''
            for leak in _SUBSCRIPTION_LEAK:
                self.assertNotIn(leak, ans, msg=f'{leak} in {msg[:40]}')

    @patch('public_assistant.services.chat.llm.complete', return_value=('', 'mock', 'mock', 1, 0, 0))
    def test_fallback_budget_question_uses_matching_not_plan(self, _mock):
        session = PublicChatSession.objects.create(ip_hash='prod-fb')
        q = (
            'اگر مشتری بودجه ۱۰ میلیارد داشته باشد و فایل ۱۰ میلیارد و ۵۰۰ میلیون باشد '
            'آیا تطبیق پیشنهاد می‌دهد؟'
        )
        out = answer_question(session=session, message=q)
        self.assertTrue(out['ok'])
        ans = out['answer']
        self.assertTrue(
            'تطبیق' in ans or 'بودجه' in ans or 'انعطاف' in ans,
            msg=ans[:200],
        )
        self.assertNotIn('divar-extraction-bot/buy', ans)
