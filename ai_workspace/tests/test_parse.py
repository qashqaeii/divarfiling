"""تست پارس JSON از LLM."""
from django.test import TestCase

from ai_workspace.services.parse import parse_json_text


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

    def test_invalid_returns_none(self):
        self.assertIsNone(parse_json_text('not json at all'))
