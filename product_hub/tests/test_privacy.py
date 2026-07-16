"""تست نمایش محرمانه هویت در مرکز توسعه."""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from product_hub.services.privacy import mask_identifier, public_submitter_label

User = get_user_model()


class MaskIdentifierTests(SimpleTestCase):
    def test_masks_last_four_chars(self):
        self.assertEqual(mask_identifier('09124567890'), '0912456****')
        self.assertEqual(mask_identifier('u09128012345'), 'u0912801****')
        self.assertEqual(mask_identifier('کشاورز'), 'کش****')

    def test_short_values_fully_hidden(self):
        self.assertEqual(mask_identifier('abcd'), '****')
        self.assertEqual(mask_identifier('ab'), '****')
        self.assertEqual(mask_identifier(''), '****')


class PublicSubmitterLabelTests(SimpleTestCase):
    def test_prefers_username_over_phone(self):
        user = User(username='کشاورز', phone='09124567890')
        self.assertEqual(public_submitter_label(user), 'کش****')

    def test_falls_back_to_phone_without_username(self):
        user = User(username='', phone='09124567890')
        self.assertEqual(public_submitter_label(user), '0912456****')

    def test_auto_username_is_masked(self):
        user = User(username='u9123456789', phone='09123456789')
        self.assertEqual(public_submitter_label(user), 'u912345****')

    def test_none_user(self):
        self.assertEqual(public_submitter_label(None), '****')
