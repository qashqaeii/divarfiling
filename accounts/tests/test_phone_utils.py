from django.test import SimpleTestCase

from accounts.phone_utils import (
    extract_iran_mobiles_from_text,
    is_valid_iran_mobile,
    normalize_iran_mobile_from_text,
    normalize_phone,
    normalize_phone_field,
    phone_username,
    resolve_contact_phones,
)
from ai_workspace.services.nl_command.contact_validators import validate_contact_parse


class PhoneUtilsTests(SimpleTestCase):
    def test_normalize_persian_digits(self):
        self.assertEqual(normalize_phone('۰۹۱۲۳۴۵۶۷۸۹'), '09123456789')

    def test_normalize_spaced_ascii(self):
        self.assertEqual(normalize_phone('0912 123 4567'), '09121234567')

    def test_normalize_plus98(self):
        self.assertEqual(normalize_phone('+989123456789'), '09123456789')

    def test_normalize_0098(self):
        self.assertEqual(normalize_phone('0098 912 123 4567'), '09121234567')

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

    def test_normalize_iran_mobile_from_text_literal(self):
        self.assertEqual(normalize_iran_mobile_from_text('09121234567'), '09121234567')

    def test_spoken_digit_sequence(self):
        spoken = 'صفر نه یک دو یک دو سه چهار پنج شش هفت'
        self.assertEqual(normalize_iran_mobile_from_text(spoken), '09121234567')

    def test_spoken_operator_prefix(self):
        spoken = 'صفر نهصد و دوازده یک دو سه چهار پنج شش هفت'
        self.assertEqual(normalize_iran_mobile_from_text(spoken), '09121234567')

    def test_invalid_short(self):
        self.assertIsNone(normalize_iran_mobile_from_text('12345'))

    def test_two_numbers_ambiguous_single_helper(self):
        text = '09121111111 و 09222222222'
        self.assertIsNone(normalize_iran_mobile_from_text(text))
        self.assertEqual(len(extract_iran_mobiles_from_text(text)), 2)

    def test_resolve_contact_phones_two_numbers_from_user_text(self):
        phone, phone_alt, inv, amb = resolve_contact_phones(
            None,
            None,
            user_text='شماره 09121111111 و دوم 09222222222',
        )
        self.assertFalse(inv)
        self.assertFalse(amb)
        self.assertEqual(phone, '09121111111')
        self.assertEqual(phone_alt, '09222222222')

    def test_resolve_contact_phones_ambiguous_multiple(self):
        _phone, _alt, _inv, amb = resolve_contact_phones(
            None,
            None,
            user_text='09121111111 و 09222222222 و 09333333333',
        )
        self.assertTrue(amb)

    def test_validate_contact_parse_voice_phone(self):
        validated, missing, ambiguous, _err = validate_contact_parse(
            {'contact': {'phone': 'صفر نه یک دو یک دو سه چهار پنج شش هفت'}, 'name': 'احمدی'},
            llm_missing=[],
            llm_ambiguous=[],
        )
        self.assertEqual(validated['phone'], '09121234567')
        self.assertNotIn('phone', ambiguous)
        self.assertNotIn('phone', missing)

    def test_validate_contact_parse_typed_spaced(self):
        validated, _missing, ambiguous, _err = validate_contact_parse(
            {'contact': {'phone': '۰۹۱۲ ۱۲۳ ۴۵ ۶۷'}, 'name': 'احمدی'},
            llm_missing=[],
            llm_ambiguous=[],
        )
        self.assertEqual(validated['phone'], '09121234567')
        self.assertNotIn('phone', ambiguous)

    def test_normalize_phone_field_property_owner(self):
        phone, inv, amb = normalize_phone_field('+98 912 123 4567')
        self.assertEqual(phone, '09121234567')
        self.assertFalse(inv)
        self.assertFalse(amb)
