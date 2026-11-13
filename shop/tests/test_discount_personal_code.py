"""تست کدهای تخفیف شخصی — فقط صاحب issuance."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import UserDiscountIssuance
from accounts.services.discount_engine import POLICY_PROFILE_COMPLETE
from shop.models import DiscountCode, LicensePlan, Order, Product
from shop.services.order_discount import OrderDiscountError, apply_discount_code_to_pending_order

User = get_user_model()


class DiscountPersonalCodeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner1', password='x', phone='09120002001')
        self.other = User.objects.create_user(username='other1', password='x', phone='09120002002')
        self.code = DiscountCode.objects.create(
            code='DF-PERSONAL',
            discount_type='percentage',
            discount_value=Decimal('10'),
            max_uses=1,
            valid_from=timezone.now(),
            is_active=True,
        )
        UserDiscountIssuance.objects.create(
            user=self.owner,
            discount_code=self.code,
            policy_key=POLICY_PROFILE_COMPLETE,
            source_rule='profile_complete',
        )
        self.product = Product.objects.create(title='P', slug='p-personal-disc', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=100_000,
            duration_days=30,
            is_active=True,
        )

    def test_owner_can_validate_code(self):
        ok, msg = self.code.is_valid(self.owner)
        self.assertTrue(ok, msg)

    def test_other_user_cannot_use_personal_code(self):
        ok, msg = self.code.is_valid(self.other)
        self.assertFalse(ok)
        self.assertIn('صاحب', msg)

    def test_other_user_cannot_apply_to_order(self):
        order = Order.objects.create(
            user=self.other,
            product=self.product,
            plan=self.plan,
            amount=100_000,
            status='pending',
        )
        with self.assertRaises(OrderDiscountError) as ctx:
            apply_discount_code_to_pending_order(order, self.other, self.code.code)
        self.assertEqual(ctx.exception.code, 'invalid')

    def test_public_code_without_issuance_still_works(self):
        public = DiscountCode.objects.create(
            code='DF-PUBLIC01',
            discount_type='percentage',
            discount_value=Decimal('5'),
            max_uses=10,
            valid_from=timezone.now(),
            is_active=True,
        )
        self.assertTrue(public.is_valid(self.other)[0])
