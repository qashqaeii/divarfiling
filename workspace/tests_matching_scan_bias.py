"""فایل بهتر با امتیاز بالاتر نباید فقط به‌خاطر جدیدتر بودن دیگری حذف شود."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import CRMProperty, Customer
from workspace.services.crm_matching import match_crm_properties

User = get_user_model()


class MatchingScanBiasTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09126667777', phone='09126667777', password='x')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار اسکن',
            phone='09126667777',
            customer_type='خریدار',
            budget_min=9_000_000_000,
            budget_max=11_000_000_000,
            min_area=90,
            max_area=110,
            areas='ونک',
            matching_tolerance_percent=5,
        )
        now = timezone.now()
        # پر کردن اسکن با فایل‌های ضعیف جدید
        for i in range(850):
            CRMProperty.objects.create(
                user=self.user,
                title=f'ضعیف {i}',
                property_type='آپارتمان',
                deal_mode='فروش',
                transaction_status='فعال',
                sale_price=25_000_000_000,
                neighborhood='نیاوران',
                city='تهران',
                area=200,
                updated_at=now - timedelta(minutes=i),
            )
        self.best_old = CRMProperty.objects.create(
            user=self.user,
            title='بهترین تطبیق',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=100,
            updated_at=now - timedelta(days=400),
        )

    def test_old_high_score_property_in_results(self):
        matches = match_crm_properties(self.buyer, self.user)
        ids = [m['property_id'] for m in matches]
        self.assertIn(self.best_old.pk, ids)
