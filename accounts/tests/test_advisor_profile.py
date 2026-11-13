"""تست تکمیل پروفایل حرفه‌ای مشاور."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from accounts.services.advisor_profile import is_advisor_profile_complete

User = get_user_model()


class AdvisorProfileCompletionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='adv_test', password='x')

    def _base_profile(self, **extra):
        defaults = {
            'activity_province': 'tehran',
            'activity_city': 'تهران',
            'activity_districts': ['منطقه ۳'],
            'activity_neighborhoods': [],
            'years_experience': 4,
            'expertise_areas': ['sale'],
            'property_specialties': ['apartment'],
            'job_role': 'independent',
        }
        defaults.update(extra)
        UserProfile.objects.update_or_create(user=self.user, defaults=defaults)
        return self.user.profile

    def test_independent_without_agency_fields_is_complete(self):
        profile = self._base_profile(job_role='independent')
        self.assertTrue(is_advisor_profile_complete(profile))

    def test_agency_role_requires_office_fields(self):
        profile = self._base_profile(
            job_role='agency_advisor',
            office_agency_name='',
        )
        self.assertFalse(is_advisor_profile_complete(profile))
        profile.office_agency_name = 'آسمان'
        profile.office_agency_city = 'تهران'
        profile.office_agency_address = 'خیابان نمونه'
        profile.office_agency_phone = '02112345678'
        profile.save()
        self.assertTrue(is_advisor_profile_complete(profile))

    def test_activity_requires_district_or_neighborhood(self):
        profile = self._base_profile(activity_districts=[], activity_neighborhoods=[])
        self.assertFalse(is_advisor_profile_complete(profile))
