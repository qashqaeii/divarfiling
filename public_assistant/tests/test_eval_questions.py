"""مجموعه ارزیابی بازیابی — بدون فراخوانی LLM."""
from django.core.management import call_command
from django.test import TestCase

from public_assistant.services.retrieval import retrieve

EVAL = [
    ('فایلینگ دیوار چیست', 'intro-what-is-divar-filing'),
    ('تفاوت crm و فایلینگ', 'intro-crm-filing-extractor'),
    ('هدیه هفت روزه', 'plans-trial-7d'),
    ('دانلود اندروید', 'platforms-web-android-windows'),
    ('فرمان هوشمند', 'ai-nl-command'),
    ('مشتری اضافه', 'crm-contacts'),
    ('استخراج آگهی', 'extractor-overview'),
    ('لایسنس فعال', 'license-activation'),
    ('مدیریت آژانس', 'agency-create-roles'),
    ('قیمت پلن', 'plans-overview'),
]


class RetrievalEvalTest(TestCase):
    def setUp(self):
        call_command('sync_public_knowledge')

    def test_eval_hits(self):
        misses = []
        for query, expected_id in EVAL:
            hits = retrieve(query)
            ids = [h.article_id for h in hits]
            if expected_id not in ids[:3]:
                misses.append((query, expected_id, ids[:5]))
        self.assertLessEqual(len(misses), 2, msg=f'misses: {misses}')
