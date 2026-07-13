"""تست فیلترهای crm_tags."""
from django.test import SimpleTestCase

from workspace.templatetags.crm_tags import crm_avatar_hue, crm_initials, nav_badge_count


class CrmTagsInitialsTests(SimpleTestCase):
    def test_initials_whitespace_only(self):
        self.assertEqual(crm_initials('   '), '؟')
        self.assertEqual(crm_initials('\t\n'), '؟')

    def test_initials_empty(self):
        self.assertEqual(crm_initials(''), '؟')
        self.assertEqual(crm_initials(None), '؟')

    def test_initials_single_and_double_names(self):
        self.assertEqual(crm_initials('علی'), 'ع')
        self.assertEqual(crm_initials('علی رضایی'), 'عر')

    def test_avatar_hue_whitespace_only(self):
        self.assertEqual(crm_avatar_hue('   '), 0)
        self.assertEqual(crm_avatar_hue(None), 0)

    def test_nav_badge_count_caps_at_99_plus(self):
        self.assertEqual(nav_badge_count(0), '')
        self.assertEqual(nav_badge_count(5), '5')
        self.assertEqual(nav_badge_count(99), '99')
        self.assertEqual(nav_badge_count(100), '99+')
        self.assertEqual(nav_badge_count(250), '99+')
