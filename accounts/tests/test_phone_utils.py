from django.test import SimpleTestCase

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone, phone_username


class PhoneUtilsTests(SimpleTestCase):
    def test_normalize_persian_digits(self):
        self.assertEqual(normalize_phone('۰۹۱۲۳۴۵۶۷۸۹'), '09123456789')

    def test_normalize_plus98(self):
        self.assertEqual(normalize_phone('+989123456789'), '09123456789')

    def test_normalize_98_prefix(self):
        self.assertEqual(normalize_phone('989123456789'), '09123456789')

    def test_normalize_without_zero(self):
        self.assertEqual(normalize_phone('9123456789'), '09123456789')

    def test_valid_mobile(self):
        self.assertTrue(is_valid_iran_mobile('09123456789'))
        self.assertFalse(is_valid_iran_mobile('08123456789'))
        self.assertFalse(is_valid_iran_mobile('0912345678'))

    def test_phone_username(self):
        self.assertEqual(phone_username('09123456789'), 'u9123456789')
