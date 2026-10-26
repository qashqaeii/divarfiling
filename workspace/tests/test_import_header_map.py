"""نگاشت ستون‌های Import مخاطب."""
from django.test import SimpleTestCase

from workspace.services.import_header_map import build_contact_header_map, map_row_by_headers


class ImportHeaderMapTests(SimpleTestCase):
    def test_tags_column_variants(self):
        for header in ('برچسب‌ها', 'برچسبها', 'برچسب\u200cها', '  برچسب ها  '):
            m = build_contact_header_map([header, 'نام'])
            self.assertIn('name', m.values())
            self.assertIn('tags', m.values())
            row = map_row_by_headers({header: 'VIP', 'نام': 'علی'}, m)
            self.assertEqual(row.get('tags'), 'VIP')
            self.assertEqual(row.get('name'), 'علی')

    def test_mobile_alias(self):
        m = build_contact_header_map(['نام مخاطب', 'موبایل'])
        self.assertEqual(m.get('موبایل'), 'phone')
