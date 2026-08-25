"""تست سال کبیسه شمسی."""
from django.test import TestCase

from workspace.services.jalali_input import jalali_esfand_days, jalali_is_leap_year


class JalaliLeapTests(TestCase):
    def test_leap_years(self):
        self.assertTrue(jalali_is_leap_year(1403))
        self.assertFalse(jalali_is_leap_year(1402))

    def test_esfand_days(self):
        self.assertEqual(jalali_esfand_days(1403), 30)
        self.assertEqual(jalali_esfand_days(1402), 29)
