"""ارزیابی سناریوهای Product Expert — بازیابی offline بدون LLM."""
from __future__ import annotations

from django.test import SimpleTestCase

from public_assistant.audit.retrieval_baseline import evaluate_retrieval
from public_assistant.audit.retrieval_offline import make_offline_retrieve_fn

# سناریوهای ترکیبی، محاوره‌ای، خطا و محدودیت دسترسی
PRODUCT_EXPERT_SCENARIOS: list[tuple[str, str]] = [
    ('استخراج کردم زونکن فروش تطبیق لینک مشتری', 'workflow-extract-to-share'),
    ('مچینگ کار نمیکنه برای خریدار', 'crm-matching'),
    ('فایلام تو پیشنهادها نمیاد', 'crm-matching'),
    ('دستیار بعد تماس گوشی سامسونگ', 'android-post-call-assistant'),
    ('مجوز پنجره روی سایر اپ‌ها', 'android-post-call-assistant'),
    ('تالار گفتگو فعال نیست', 'community-forum'),
    ('اطلاعات مشتریان من رو میبینی', 'public-assistant-scope'),
    ('قیمت پلن شخصی', 'plans-overview'),
    ('فایل شخصی با dataset فرق', 'intro-crm-filing-extractor'),
    ('ربات وصل نمیشه میزکار', 'extractor-to-filing'),
]


class ProductExpertRetrievalTest(SimpleTestCase):
    def test_expert_scenarios_hit_at_5(self):
        report = evaluate_retrieval(make_offline_retrieve_fn(), PRODUCT_EXPERT_SCENARIOS)
        self.assertGreaterEqual(
            report['article_hit_at_5'],
            0.85,
            msg=report.get('misses'),
        )
