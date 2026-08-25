"""تست fallback خلاصه فایل شخصی."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_workspace.services.property_summary import build_fallback_for_property
from workspace.models import CRMProperty

User = get_user_model()


class PropertyFallbackSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='propfb', password='pass', phone='09128887766',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ۱۲۰ متری نوساز',
            deal_mode='فروش',
            city='تهران',
            neighborhood='سعادت‌آباد',
            area=120,
            rooms='۳',
            sale_price=18_000_000_000,
            has_parking=True,
            has_elevator=True,
            amenities='نمای باز\nنورگیر عالی',
        )

    def test_structured_fallback_payload(self):
        data = build_fallback_for_property(self.user, self.prop)
        self.assertIn('summary', data)
        self.assertIn('highlights', data)
        self.assertIn('negotiation_tip', data)
        self.assertIn('آپارتمان ۱۲۰ متری', data['summary'])
        self.assertIn('سعادت‌آباد', data['summary'])
        self.assertTrue(data['highlights'])
        self.assertTrue(data['negotiation_tip'])
