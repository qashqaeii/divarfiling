"""تست پارس JSON از LLM."""
from django.test import TestCase

from ai_workspace.services.parse import parse_json_text, salvage_listing_json


class ParseJsonTests(TestCase):
    def test_plain_json(self):
        data = parse_json_text('{"summary":"ok","highlights":[]}')
        self.assertEqual(data['summary'], 'ok')

    def test_markdown_fence(self):
        text = '```json\n{"summary":"x","highlights":[]}\n```'
        data = parse_json_text(text)
        self.assertEqual(data['summary'], 'x')

    def test_preamble_and_fence(self):
        text = 'این خلاصه است:\n```json\n{"summary":"y","highlights":[]}\n```\nپایان'
        data = parse_json_text(text)
        self.assertEqual(data['summary'], 'y')

    def test_braced_object_in_text(self):
        text = 'نتیجه: {"summary":"z","highlights":["a"]} — تمام'
        data = parse_json_text(text)
        self.assertEqual(data['summary'], 'z')

    def test_truncated_json_salvage(self):
        text = (
            '{\n  "summary": "واحد ۱۵۰ متری در ولنجک با قیمت ۹۷ میلیارد.",\n'
            '  "highlights": [\n'
            '    "قیمت: ۹۷ میلیارد",\n'
            '    "دو پارکینگ",\n'
            '    "سند بدون ریشه",\n'
            '    "امکان دریافت واحد'
        )
        data = salvage_listing_json(text)
        self.assertIsNotNone(data)
        self.assertIn('ولنجک', data['summary'])
        self.assertGreaterEqual(len(data['highlights']), 3)
