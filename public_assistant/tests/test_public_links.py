"""لینک‌های مارک‌داون در پاسخ دستیار عمومی."""
from django.test import TestCase

from public_assistant.services.plan_advisor import compose_no_catalog_answer
from public_assistant.services.public_copy import finalize_public_answer, polish_public_answer
from public_assistant.services.public_links import (
    md_link,
    normalize_public_answer_links,
    plan_purchase_markdown,
)
from public_assistant.services.security import is_allowed_public_link


class PublicLinksTests(TestCase):
    def test_md_link_blocks_javascript(self):
        out = md_link('کلیک', 'javascript:alert(1)')
        self.assertEqual(out, 'کلیک')
        self.assertNotIn('javascript', out)

    def test_md_link_relative_path(self):
        out = md_link('ورود به میزکار', '/workspace/')
        self.assertEqual(out, '[ورود به میزکار](/workspace/)')

    def test_normalize_backtick_path(self):
        raw = 'راهنما: `/license-guide/`.'
        out = normalize_public_answer_links(raw)
        self.assertIn('[راهنمای فعال‌سازی لایسنس](/license-guide/)', out)
        self.assertNotIn('`/license-guide/`', out)

    def test_normalize_buy_line_legacy(self):
        raw = 'خرید رسمی: /products/divar-extraction-bot/buy/?plan=6'
        out = normalize_public_answer_links(raw)
        self.assertIn('[', out)
        self.assertIn('](/products/divar-extraction-bot/buy/?plan=6)', out)
        self.assertNotIn('خرید رسمی:', out)

    def test_finalize_strips_html(self):
        raw = '<a href="/workspace/">ورود</a> به سیستم'
        out = finalize_public_answer(raw)
        self.assertNotIn('<a', out)

    def test_polish_applies_link_normalization(self):
        out = polish_public_answer('صفحه خرید: /products/divar-extraction-bot/buy/')
        self.assertIn('](', out)
        self.assertNotIn('/products/divar-extraction-bot/buy/', out.replace('](/products', ''))

    def test_allowed_hosts(self):
        self.assertTrue(is_allowed_public_link('/workspace/support/'))
        self.assertFalse(is_allowed_public_link('https://evil.example/'))

    def test_compose_no_catalog_uses_markdown(self):
        ans = compose_no_catalog_answer()
        self.assertIn('[', ans)
        self.assertNotIn('`/products', ans)
