from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
import json

from licenses.models import License
from licenses.services.claim import issue_licenses_for_paid_order
from shop.models import LicensePlan, Order, Product
from shop.services.plan_pricing import calculate_plan_purchase_prices, clamp_quantity

User = get_user_model()


class PlanPricingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='test-pass-123')
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-pricing-test',
            description='test',
            is_active=True,
        )
        self.yearly = LicensePlan.objects.create(
            product=self.product,
            name='یک‌ساله',
            plan_type='yearly',
            price=7_000_000,
            compare_at_price=8_000_000,
            duration_days=365,
            max_activations=2,
            offer_badge='آفر ویژه',
            is_active=True,
        )

    def test_promo_offer_detected(self):
        self.assertTrue(self.yearly.has_promo_offer())
        self.assertEqual(self.yearly.promo_discount_percent(), 12)

    def test_normalized_features_custom_and_default(self):
        custom = LicensePlan.objects.create(
            product=self.product,
            name='سفارشی',
            plan_type='monthly',
            price=500_000,
            duration_days=30,
            features=[
                'پشتیبانی VIP',
                {'text': 'CRM کامل', 'icon': 'fa-users'},
            ],
            is_active=True,
        )
        feats = custom.normalized_features()
        self.assertEqual(len(feats), 2)
        self.assertEqual(feats[0]['text'], 'پشتیبانی VIP')
        self.assertEqual(feats[1]['icon'], 'fa-users')

        defaults = self.yearly.normalized_features()
        self.assertTrue(any('روز دسترسی' in f['text'] for f in defaults))
        self.assertTrue(any('دستگاه' in f['text'] for f in defaults))

    def test_pricing_uses_compare_at_as_original(self):
        pricing = calculate_plan_purchase_prices(
            self.yearly, self.product, self.user, quantity=1,
        )
        self.assertEqual(pricing['original_price'], Decimal('8000000'))
        self.assertEqual(pricing['final_price'], Decimal('7000000'))

    def test_bulk_quantity_clamped(self):
        self.yearly.allow_bulk_purchase = True
        self.yearly.min_quantity = 2
        self.yearly.max_quantity = 5
        self.yearly.save()
        self.assertEqual(clamp_quantity(self.yearly, 10), 5)
        self.assertEqual(clamp_quantity(self.yearly, 1), 2)

    def test_bulk_pricing_multiplies_unit_price(self):
        self.yearly.allow_bulk_purchase = True
        self.yearly.save()
        pricing = calculate_plan_purchase_prices(
            self.yearly, self.product, self.user, quantity=3,
        )
        self.assertEqual(pricing['quantity'], 3)
        self.assertEqual(pricing['final_price'], Decimal('21000000'))

    def test_agency_bulk_pricing_per_license(self):
        """هر لایسنس آژانس = قیمت واحد پلن × تعداد."""
        agency = LicensePlan.objects.create(
            product=self.product,
            name='یک ماهه آژانس',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            allow_bulk_purchase=True,
            min_quantity=2,
            max_quantity=5,
            is_active=True,
        )
        pricing = calculate_plan_purchase_prices(
            agency, self.product, self.user, quantity=2,
        )
        self.assertEqual(pricing['quantity'], 2)
        self.assertEqual(pricing['unit_sale_price'], Decimal('990000'))
        self.assertEqual(pricing['original_price'], Decimal('1980000'))
        self.assertEqual(pricing['final_price'], Decimal('1980000'))


class ApplyDiscountQuantityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='agency2', password='test-pass-123')
        self.client.login(username='agency2', password='test-pass-123')
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-apply-discount-qty',
            description='test',
            is_active=True,
            repeat_purchase_discount=10,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='آژانس حرفه‌ای',
            plan_type='quarterly',
            price=2_500_000,
            compare_at_price=2_500_000,
            duration_days=90,
            max_activations=2,
            allow_bulk_purchase=True,
            min_quantity=2,
            max_quantity=10,
            is_active=True,
        )
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            quantity=1,
            amount=2_250_000,
            original_price=2_500_000,
            status='paid',
        )

    def test_apply_discount_scales_with_quantity(self):
        url = reverse('apply_discount', kwargs={'slug': self.product.slug})
        cases = (
            (1, 2, 4_500_000),
            (2, 2, 4_500_000),
            (3, 3, 6_750_000),
        )
        for requested_qty, expected_qty, expected_final in cases:
            response = self.client.post(
                url,
                data=json.dumps({'plan_id': self.plan.id, 'quantity': requested_qty, 'discount_code': ''}),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200, response.content)
            payload = response.json()
            self.assertTrue(payload['success'], payload)
            self.assertEqual(payload['quantity'], expected_qty)
            self.assertEqual(payload['final_price'], expected_final)


class BulkLicenseIssueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='agency', password='test-pass-123')
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-bulk-test',
            description='test',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='سه‌ماهه آژانس',
            plan_type='quarterly',
            price=2_500_000,
            duration_days=90,
            max_activations=2,
            allow_bulk_purchase=True,
            min_quantity=1,
            max_quantity=10,
            is_active=True,
        )
        self.order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            quantity=3,
            amount=7_500_000,
            original_price=7_500_000,
            status='paid',
        )

    def test_issue_multiple_licenses_for_one_order(self):
        licenses = issue_licenses_for_paid_order(self.order)
        self.assertEqual(len(licenses), 3)
        self.assertEqual(License.objects.filter(order=self.order).count(), 3)
        keys = list(License.objects.filter(order=self.order).values_list('license_key', flat=True))
        self.assertEqual(len(set(keys)), 3)

    def test_issue_is_idempotent(self):
        issue_licenses_for_paid_order(self.order)
        issue_licenses_for_paid_order(self.order)
        self.assertEqual(License.objects.filter(order=self.order).count(), 3)
