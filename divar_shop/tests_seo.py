"""Tests for robots.txt and FAQ schema extraction."""
from django.test import SimpleTestCase, override_settings
from django.test import Client

from blog.seo_schema import extract_faq_pairs


FAQ_HTML = """
<h2>سوالات متداول</h2>
<h3>ربات دیوار املاک چیست؟</h3>
<p>ابزار استخراج خودکار آگهی از دیوار.</p>
<h3>CRM رایگان است؟</h3>
<p>بله، میزکار CRM رایگان دارد.</p>
"""


class FaqSchemaTests(SimpleTestCase):
    def test_extract_faq_pairs(self):
        pairs = extract_faq_pairs(FAQ_HTML)
        self.assertEqual(len(pairs), 2)
        self.assertIn('ربات دیوار', pairs[0][0])

    def test_no_faq_section_returns_empty(self):
        self.assertEqual(extract_faq_pairs('<h2>مقدمه</h2><p>متن</p>'), [])


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class RobotsTxtTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_openai_bots_allowed_with_private_disallow(self):
        resp = self.client.get('/robots.txt')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('User-agent: OAI-SearchBot', body)
        self.assertIn('User-agent: GPTBot', body)
        self.assertIn('User-agent: ChatGPT-User', body)
        self.assertIn('Disallow: /workspace/', body)
        self.assertIn('Sitemap: https://divarfiling.ir/sitemap.xml', body)

    def test_oai_searchbot_block_before_wildcard(self):
        resp = self.client.get('/robots.txt')
        body = resp.content.decode('utf-8')
        oai_pos = body.index('OAI-SearchBot')
        star_pos = body.index('User-agent: *')
        self.assertLess(oai_pos, star_pos)
