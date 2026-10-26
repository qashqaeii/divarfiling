"""اعتبارسنجی تلفن در Import."""
from django.test import SimpleTestCase

from workspace.services.crm_import_phone import coerce_phone_cell, parse_import_phone_fields


class CRMImportPhoneTests(SimpleTestCase):
    def test_excel_float_mobile(self):
        phone, alt, err = parse_import_phone_fields(9121234567.0, None)
        self.assertIsNone(err)
        self.assertEqual(phone, '09121234567')

    def test_rejects_garbage(self):
        phone, alt, err = parse_import_phone_fields('abc-def', None)
        self.assertTrue(err)
        self.assertEqual(phone, '')

    def test_landline(self):
        phone, alt, err = parse_import_phone_fields('02188776655', None)
        self.assertIsNone(err)
        self.assertTrue(phone.startswith('021'))

    def test_scientific_notation_cell(self):
        raw = coerce_phone_cell(9.121234567e10)
        self.assertNotIn('e', raw.lower())
