"""تست پاداش تکمیل پروفایل."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserDiscountIssuance, UserProfile
from accounts.services.discount_engine import POLICY_PROFILE_COMPLETE
from accounts.phone_utils import phone_username
from accounts.services.profile_completion_reward import (
    build_profile_completion_reward_context,
    is_default_phone_username,
    is_profile_reward_consumed,
    is_profile_reward_eligible,
    is_supplementary_profile_complete,
    issue_profile_completion_discount,
    user_has_custom_username,
    user_phone_is_verified,
)
from shop.models import DiscountCode

User = get_user_model()


class ProfileCompletionRewardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='prof_reward', password='x', phone='09120000999')
        self.user.phone_verified = True
        self.user.save(update_fields=['phone_verified'])

    def _complete_profile(self, **extra):
        defaults = {
            'activity_province': 'tehran',
            'activity_city': 'تهران',
            'activity_districts': ['منطقه ۳'],
            'activity_neighborhoods': [],
            'years_experience': 5,
            'expertise_areas': ['sale', 'rent'],
            'property_specialties': ['apartment'],
            'job_role': 'independent',
            'city': 'تهران',
            'bio': 'مشاور املاک',
            'address': 'خیابان نمونه ۱۲',
        }
        defaults.update(extra)
        UserProfile.objects.update_or_create(user=self.user, defaults=defaults)

    def test_incomplete_profile_blocks_issue(self):
        UserProfile.objects.create(user=self.user, activity_city='تهران')
        result = issue_profile_completion_discount(self.user)
        self.assertFalse(result.ok)
        self.assertFalse(is_supplementary_profile_complete(self.user.profile))

    def test_issue_once_and_reuse(self):
        self._complete_profile()
        first = issue_profile_completion_discount(self.user)
        self.assertTrue(first.ok)
        self.assertTrue(first.code.startswith('DF-'))
        self.assertEqual(
            UserDiscountIssuance.objects.filter(
                user=self.user, policy_key=POLICY_PROFILE_COMPLETE
            ).count(),
            1,
        )
        second = issue_profile_completion_discount(self.user)
        self.assertTrue(second.ok)
        self.assertTrue(second.reused)
        self.assertEqual(first.code, second.code)
        self.assertEqual(
            DiscountCode.objects.filter(description__contains=f'user:{self.user.pk}').count(),
            1,
        )

    def test_context_hides_after_paid_use(self):
        self._complete_profile()
        result = issue_profile_completion_discount(self.user)
        dc = DiscountCode.objects.get(pk=result.discount_code_id)
        dc.used_count = 1
        dc.save(update_fields=['used_count', 'updated_at'])
        self.assertTrue(is_profile_reward_consumed(dc, self.user))
        ctx = build_profile_completion_reward_context(self.user)
        self.assertFalse(ctx['show'])
        self.assertEqual(ctx['state'], 'consumed')

    def test_context_ready_when_issued(self):
        self._complete_profile()
        issue_profile_completion_discount(self.user)
        ctx = build_profile_completion_reward_context(self.user)
        self.assertTrue(ctx['show'])
        self.assertEqual(ctx['state'], 'ready')
        self.assertTrue(ctx['code'])

    def test_auto_phone_username_blocks_reward(self):
        phone = '09353556010'
        auto_user = User.objects.create_user(
            username=phone_username(phone),
            password='x',
            phone=phone,
        )
        self.assertTrue(is_default_phone_username(auto_user))
        self.assertFalse(user_has_custom_username(auto_user))
        auto_user.phone_verified = True
        auto_user.save(update_fields=['phone_verified'])
        UserProfile.objects.update_or_create(
            user=auto_user,
            defaults={
                'activity_province': 'tehran',
                'activity_city': 'تهران',
                'activity_districts': ['منطقه ۱'],
                'years_experience': 2,
                'expertise_areas': ['sale'],
                'property_specialties': ['apartment'],
                'job_role': 'independent',
            },
        )
        self.assertFalse(is_profile_reward_eligible(auto_user))
        result = issue_profile_completion_discount(auto_user)
        self.assertFalse(result.ok)

    def test_custom_username_allows_reward_with_full_profile(self):
        phone = '09127777001'
        custom = User.objects.create_user(username='ali.moshaver', password='x', phone=phone)
        custom.phone_verified = True
        custom.save(update_fields=['phone_verified'])
        UserProfile.objects.update_or_create(
            user=custom,
            defaults={
                'activity_province': 'tehran',
                'activity_city': 'تهران',
                'activity_districts': ['منطقه ۳'],
                'years_experience': 5,
                'expertise_areas': ['sale'],
                'property_specialties': ['apartment'],
                'job_role': 'independent',
            },
        )
        self.assertTrue(is_profile_reward_eligible(custom))
        result = issue_profile_completion_discount(custom)
        self.assertTrue(result.ok)

    def test_unverified_phone_blocks_reward(self):
        phone = '09126666002'
        user = User.objects.create_user(username='reza.agent', password='x', phone=phone)
        self.assertFalse(user_phone_is_verified(user))
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'activity_province': 'tehran',
                'activity_city': 'تهران',
                'activity_districts': ['منطقه ۲'],
                'years_experience': 3,
                'expertise_areas': ['rent'],
                'property_specialties': ['villa'],
                'job_role': 'independent',
            },
        )
        self.assertFalse(is_profile_reward_eligible(user))
        self.assertFalse(issue_profile_completion_discount(user).ok)
