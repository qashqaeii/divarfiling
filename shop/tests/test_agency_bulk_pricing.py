"""تست‌های قیمت‌گذاری آژانس — bulk tiers، quantity rules، fulfillment."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from licenses.models import License
from licenses.services.claim import issue_licenses_for_paid_order
from shop.models import LicensePlan, Order, Product
from shop.services.plan_pricing import (
    AGENCY_MAX_QUANTITY,
    AGENCY_MIN_QUANTITY,
    calculate_plan_pricing,
    clamp_quantity,
    get_agency_bulk_discount_percent,
)

User = get_user_model()


class AgencyBulkPricingEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='test-pass-123')
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-agency-pricing',
            description='test',
            is_active=True,
            repeat_purchase_discount=10,
        )
        self.monthly = LicensePlan.objects.create(
            product=self.product,
            name='پلن آژانس — ماهانه',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            allow_bulk_purchase=True,
            min_quantity=2,
            max_quantity=25,
            is_active=True,
        )
        self.quarterly = LicensePlan.objects.create(
            product=self.product,
            name='پلن آژانس — سه‌ماهه',
            plan_type='quarterly',
            price=2_500_000,
            duration_days=90,
            max_activations=2,
            allow_bulk_purchase=True,
            min_quantity=2,
            max_quantity=25,
            is_active=True,
        )
        self.yearly = LicensePlan.objects.create(
            product=self.product,
            name='پلن آژانس — سالانه',
            plan_type='yearly',
            price=8_000_000,
            compare_at_price=10_000_000,
            duration_days=365,
            max_activations=2,
            allow_bulk_purchase=True,
            min_quantity=2,
            max_quantity=25,
            is_active=True,
        )
        self.personal = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس یک‌ماهه',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            allow_bulk_purchase=False,
            is_active=True,
        )

    def test_personal_quantity_always_one(self):
        self.assertEqual(clamp_quantity(self.personal, 5), 1)
        pricing = calculate_plan_pricing(self.personal, self.product, self.user, quantity=5)
        self.assertEqual(pricing['quantity'], 1)

    def test_agency_quantity_clamp_min(self):
        self.assertEqual(clamp_quantity(self.monthly, 1), 2)
        self.assertEqual(clamp_quantity(self.monthly, 0), 2)

    def test_agency_quantity_clamp_max(self):
        self.assertEqual(clamp_quantity(self.monthly, 26), 25)
        self.assertEqual(clamp_quantity(self.monthly, 100), 25)

    def test_bulk_tier_percents(self):
        self.assertEqual(get_agency_bulk_discount_percent(2), Decimal('10'))
        self.assertEqual(get_agency_bulk_discount_percent(3), Decimal('15'))
        self.assertEqual(get_agency_bulk_discount_percent(5), Decimal('15'))
        self.assertEqual(get_agency_bulk_discount_percent(6), Decimal('20'))
        self.assertEqual(get_agency_bulk_discount_percent(10), Decimal('20'))
        self.assertEqual(get_agency_bulk_discount_percent(11), Decimal('25'))
        self.assertEqual(get_agency_bulk_discount_percent(25), Decimal('25'))

    def test_monthly_expected_unit_prices(self):
        cases = (
            (2, Decimal('891000')),
            (3, Decimal('841500')),
            (5, Decimal('841500')),
            (6, Decimal('792000')),
            (10, Decimal('792000')),
            (11, Decimal('742500')),
            (25, Decimal('742500')),
        )
        for qty, expected_unit in cases:
            pricing = calculate_plan_pricing(self.monthly, self.product, self.user, quantity=qty)
            self.assertEqual(pricing['effective_unit_price'], expected_unit, msg=f'qty={qty}')

    def test_monthly_totals(self):
        p2 = calculate_plan_pricing(self.monthly, self.product, self.user, quantity=2)
        self.assertEqual(p2['final_price'], Decimal('1782000'))
        p5 = calculate_plan_pricing(self.monthly, self.product, self.user, quantity=5)
        self.assertEqual(p5['final_price'], Decimal('4207500'))
        p10 = calculate_plan_pricing(self.monthly, self.product, self.user, quantity=10)
        self.assertEqual(p10['final_price'], Decimal('7920000'))
        p25 = calculate_plan_pricing(self.monthly, self.product, self.user, quantity=25)
        self.assertEqual(p25['final_price'], Decimal('18562500'))

    def test_quarterly_tier_behavior(self):
        p2 = calculate_plan_pricing(self.quarterly, self.product, self.user, quantity=2)
        self.assertEqual(p2['effective_unit_price'], Decimal('2250000'))
        p5 = calculate_plan_pricing(self.quarterly, self.product, self.user, quantity=5)
        self.assertEqual(p5['effective_unit_price'], Decimal('2125000'))
        p10 = calculate_plan_pricing(self.quarterly, self.product, self.user, quantity=10)
        self.assertEqual(p10['effective_unit_price'], Decimal('2000000'))
        p25 = calculate_plan_pricing(self.quarterly, self.product, self.user, quantity=25)
        self.assertEqual(p25['effective_unit_price'], Decimal('1875000'))

    def test_yearly_bulk_uses_price_not_compare_at(self):
        p25 = calculate_plan_pricing(self.yearly, self.product, self.user, quantity=25)
        self.assertEqual(p25['effective_unit_price'], Decimal('6000000'))
        self.assertEqual(p25['final_price'], Decimal('150000000'))
        self.assertEqual(p25['base_unit_price'], Decimal('8000000'))

    def test_yearly_agency_duration_365(self):
        self.assertEqual(self.yearly.duration_days, 365)

    def test_repeat_and_bulk_max_not_sum(self):
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.monthly,
            quantity=1,
            amount=990_000,
            original_price=990_000,
            status='paid',
        )
        pricing = calculate_plan_pricing(self.monthly, self.product, self.user, quantity=5)
        self.assertEqual(pricing['applied_discount_percent'], 15)
        self.assertIn('آژانس', pricing['applied_discount_reason'])
        self.assertEqual(pricing['final_price'], Decimal('4207500'))

    def test_repeat_wins_when_higher(self):
        self.product.repeat_purchase_discount = 20
        self.product.save(update_fields=['repeat_purchase_discount'])
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.monthly,
            quantity=1,
            amount=990_000,
            original_price=990_000,
            status='paid',
        )
        pricing = calculate_plan_pricing(self.monthly, self.product, self.user, quantity=3)
        self.assertEqual(pricing['applied_discount_percent'], 20)
        self.assertIn('خرید مجدد', pricing['applied_discount_reason'])

    def test_fulfillment_qty5_creates_five_licenses(self):
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.monthly,
            quantity=5,
            amount=4_207_500,
            original_price=4_950_000,
            status='paid',
        )
        licenses = issue_licenses_for_paid_order(order)
        self.assertEqual(len(licenses), 5)
        self.assertTrue(all(lic.max_activations == 2 for lic in licenses))
        keys = list(License.objects.filter(order=order).values_list('license_key', flat=True))
        self.assertEqual(len(set(keys)), 5)

    def test_device_capacity_metadata(self):
        pricing = calculate_plan_pricing(self.monthly, self.product, self.user, quantity=5)
        self.assertEqual(pricing['licenses_count'], 5)
        self.assertEqual(pricing['total_activation_slots'], 10)

    def test_agency_constants(self):
        self.assertEqual(AGENCY_MIN_QUANTITY, 2)
        self.assertEqual(AGENCY_MAX_QUANTITY, 25)
