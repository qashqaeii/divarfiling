"""تست دقت تطبیق جغرافیایی — جلوگیری از false positive."""
from django.test import TestCase

from workspace.services.crm_matching_geo import location_tokens_equivalent


class MatchingGeoPrecisionTests(TestCase):
    def test_edalat_not_edalat_abad(self):
        self.assertFalse(location_tokens_equivalent('عدالت', 'عدالت آباد'))

    def test_sayyad_not_sayyad_shirazi(self):
        self.assertFalse(location_tokens_equivalent('صیاد', 'صیاد شیرازی'))

    def test_poonak_not_poonak_jonubi(self):
        self.assertFalse(location_tokens_equivalent('پونک', 'پونک جنوبی'))

    def test_compound_shiraz_sayyad(self):
        self.assertTrue(location_tokens_equivalent('صیاد', 'شیراز - محله صیاد'))

    def test_exact_match(self):
        self.assertTrue(location_tokens_equivalent('آپادانا', 'آپادانا'))
