"""Affiliate end-to-end tests."""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from affiliates.models import Affiliate, AffiliateSale, Wallet
from affiliates.services.commission import record_affiliate_commission
from affiliates.services.pricing import apply_affiliate_discount
from affiliates.services.referral import (
    assign_referred_user,
    capture_referral_from_request,
    is_valid_attribution,
    resolve_order_affiliate,
)
from shop.models import LicensePlan, Order, Product

User = get_user_model()


class AffiliateReferralFlowTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            username='refuser', phone='09121111111', password='pass12345'
        )
        self.buyer = User.objects.create_user(
            username='buyer', phone='09122222222', password='pass12345'
        )
        self.affiliate = Affiliate.objects.create(user=self.referrer, code='TESTREF123', is_active=True)
        self.product = Product.objects.create(
            title='ربات تست',
            slug='test-bot',
            description='توضیح تست',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=Decimal('1000000'),
            duration_days=30,
            is_active=True,
        )

    def test_self_referral_blocked(self):
        self.assertFalse(is_valid_attribution(self.referrer, self.affiliate))

    def test_assign_referred_user_first_touch(self):
        self.assertTrue(assign_referred_user(self.buyer, self.affiliate))
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.referred_by_id, self.affiliate.pk)

    def test_assign_referred_user_does_not_override(self):
        other = Affiliate.objects.create(user=User.objects.create_user(
            username='other', phone='09123333333', password='pass12345'
        ), code='OTHERCODE1', is_active=True)
        assign_referred_user(self.buyer, self.affiliate)
        assign_referred_user(self.buyer, other)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.referred_by_id, self.affiliate.pk)

    def test_middleware_stores_cookie_and_redirects_guest(self):
        client = Client()
        response = client.get('/', {'ref': self.affiliate.code})
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.AFFILIATE_COOKIE_NAME, response.cookies)
        self.assertIn('/accounts/register/', response.url)

    def test_checkout_links_order_to_affiliate(self):
        assign_referred_user(self.buyer, self.affiliate)
        order = Order.objects.create(
            user=self.buyer,
            product=self.product,
            plan=self.plan,
            amount=Decimal('950000'),
            original_price=Decimal('1000000'),
            affiliate=self.affiliate,
        )
        order.status = 'paid'
        order.save()
        record_affiliate_commission(order)
        self.assertEqual(AffiliateSale.objects.filter(affiliate=self.affiliate).count(), 1)
        wallet = Wallet.objects.get(user=self.referrer)
        self.assertGreater(wallet.balance, 0)

    def test_commission_idempotent(self):
        assign_referred_user(self.buyer, self.affiliate)
        order = Order.objects.create(
            user=self.buyer,
            product=self.product,
            plan=self.plan,
            amount=Decimal('950000'),
            original_price=Decimal('1000000'),
            affiliate=self.affiliate,
            status='paid',
        )
        record_affiliate_commission(order)
        record_affiliate_commission(order)
        self.assertEqual(AffiliateSale.objects.filter(order=order).count(), 1)

    def test_affiliate_discount_first_order_only(self):
        assign_referred_user(self.buyer, self.affiliate)
        request = self.client.request().wsgi_request
        request.user = self.buyer
        disc, price, label = apply_affiliate_discount(
            self.buyer, request, self.product, Decimal('1000000')
        )
        self.assertGreater(disc, 0)
        self.assertIsNotNone(label)
        Order.objects.create(
            user=self.buyer,
            product=self.product,
            plan=self.plan,
            amount=Decimal('1000000'),
            original_price=Decimal('1000000'),
            status='paid',
        )
        disc2, _, _ = apply_affiliate_discount(
            self.buyer, request, self.product, Decimal('1000000')
        )
        self.assertEqual(disc2, 0)

    def test_capture_from_cookie(self):
        client = Client()
        client.cookies[settings.AFFILIATE_COOKIE_NAME] = self.affiliate.code
        request = client.get('/').wsgi_request
        captured = capture_referral_from_request(request)
        self.assertEqual(captured.pk, self.affiliate.pk)

    def test_referred_users_list_includes_no_purchase(self):
        assign_referred_user(self.buyer, self.affiliate)
        from affiliates.services.referral import get_referred_users_data
        data = get_referred_users_data(self.affiliate)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['without_orders'], 1)
        self.assertEqual(data['items'][0]['phone'], '09122222222')
        self.assertFalse(data['items'][0]['has_paid_order'])

    def test_register_sets_referred_by(self):
        from accounts.services.otp import request_otp, verify_otp

        client = Client()
        client.cookies[settings.AFFILIATE_COOKIE_NAME] = self.affiliate.code
        phone = '09124444444'

        with self.settings(SMS_PROVIDER='console', FARAZSMS_PATTERN_OTP='TESTOTP'):
            challenge = request_otp(phone, 'register')
            self.assertTrue(challenge.debug_code)
            verify_otp(phone, 'register', challenge.debug_code)

            session = client.session
            session['otp_phone'] = phone
            session['otp_purpose'] = 'register'
            session['otp_register_verified'] = True
            session.save()

            response = client.post(reverse('otp_register_password'), {
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
            })
        self.assertIn(response.status_code, (302, 200))
        new_user = User.objects.get(phone=phone)
        self.assertEqual(new_user.referred_by_id, self.affiliate.pk)
        self.assertTrue(new_user.phone_verified)
