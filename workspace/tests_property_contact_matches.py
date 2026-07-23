"""تست حرفه‌ای تطبیق معکوس: پیشنهاد مخاطب برای فایل شخصی."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMProperty, Customer, CustomerActivity, PropertyContact
from workspace.services.crm import apply_contact_suggestions
from workspace.services.crm_matching import (
    get_property_contact_matches,
    match_customers_for_property,
)

User = get_user_model()


class PropertyContactMatchEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121112233', phone='09121112233', password='x',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ونک',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=2_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
            rooms='2',
        )
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار مناسب',
            phone='09121110001',
            customer_type='خریدار',
            status='در حال پیگیری',
            budget_min=1_000_000_000,
            budget_max=3_000_000_000,
            areas='ونک',
            property_type='آپارتمان',
            min_area=70,
            max_area=120,
        )
        self.tenant = Customer.objects.create(
            user=self.user,
            name='مستاجر',
            phone='09121110002',
            customer_type='مستاجر',
            status='در حال پیگیری',
            deposit_min=100_000_000,
            deposit_max=500_000_000,
            rent_min=5_000_000,
            rent_max=30_000_000,
            areas='ونک',
        )
        self.seller = Customer.objects.create(
            user=self.user,
            name='فروشنده',
            phone='09121110003',
            customer_type='فروشنده',
            status='در حال پیگیری',
        )

    def test_buyer_matches_sale_property(self):
        data = get_property_contact_matches(self.prop, self.user)
        self.assertTrue(data['eligible'])
        self.assertTrue(data['is_sale'])
        ids = {m['customer_id'] for m in data['matches']}
        self.assertIn(self.buyer.pk, ids)
        self.assertNotIn(self.tenant.pk, ids)
        self.assertNotIn(self.seller.pk, ids)
        buyer_card = next(m for m in data['matches'] if m['customer_id'] == self.buyer.pk)
        self.assertGreaterEqual(buyer_card['score'], 25)
        self.assertIn('matching_tolerance_percent', buyer_card)

    def test_tenant_excluded_from_sale(self):
        matches = match_customers_for_property(self.prop, self.user)
        types = {m['customer_type'] for m in matches}
        self.assertNotIn('مستاجر', types)

    def test_rent_applicant_excluded_from_sale(self):
        rent_applicant = Customer.objects.create(
            user=self.user,
            name='متقاضی اجاره',
            phone='09121110004',
            customer_type='متقاضی اجاره',
            status='در حال پیگیری',
            deposit_min=100_000_000,
            deposit_max=800_000_000,
            rent_min=5_000_000,
            rent_max=40_000_000,
            areas='ونک',
            property_type='آپارتمان',
            min_area=70,
            max_area=120,
        )
        data = get_property_contact_matches(self.prop, self.user)
        ids = {m['customer_id'] for m in data['matches']}
        types = {m['customer_type'] for m in data['matches']}
        self.assertNotIn(rent_applicant.pk, ids)
        self.assertNotIn('متقاضی اجاره', types)
        self.assertIn(self.buyer.pk, ids)

    def test_rent_property_matches_tenant_not_buyer(self):
        rent_prop = CRMProperty.objects.create(
            user=self.user,
            title='اجاره ونک',
            property_type='آپارتمان',
            deal_mode='رهن و اجاره',
            transaction_status='فعال',
            deposit=300_000_000,
            monthly_rent=15_000_000,
            neighborhood='ونک',
            city='تهران',
            area=85,
            rooms='2',
        )
        data = get_property_contact_matches(rent_prop, self.user)
        self.assertTrue(data['eligible'])
        self.assertTrue(data['is_rent'])
        ids = {m['customer_id'] for m in data['matches']}
        types = {m['customer_type'] for m in data['matches']}
        self.assertIn(self.tenant.pk, ids)
        self.assertNotIn(self.buyer.pk, ids)
        self.assertNotIn('خریدار', types)

    def test_already_linked_excluded(self):
        PropertyContact.objects.create(
            customer=self.buyer,
            property=self.prop,
            role='پیشنهادی',
            deal_type='خرید',
        )
        data = get_property_contact_matches(self.prop, self.user)
        ids = {m['customer_id'] for m in data['matches']}
        self.assertNotIn(self.buyer.pk, ids)

    def test_archived_property_ineligible(self):
        self.prop.transaction_status = 'فروخته شده'
        self.prop.save(update_fields=['transaction_status'])
        data = get_property_contact_matches(self.prop, self.user)
        self.assertFalse(data['eligible'])
        self.assertEqual(data['total_count'], 0)

    def test_apply_contact_suggestions_links_once_activity(self):
        result = apply_contact_suggestions(self.prop, self.user, [self.buyer.pk])
        self.assertEqual(result['linked_count'], 1)
        self.assertIn(self.buyer.name, result['whatsapp_text'])
        self.assertEqual(len(result['suggestions']), 1)
        self.assertTrue(
            PropertyContact.objects.filter(
                customer=self.buyer,
                property=self.prop,
                role='پیشنهادی',
            ).exists()
        )
        activities = CustomerActivity.objects.filter(
            customer=self.buyer,
            property=self.prop,
            title='پیشنهاد ملک از فایل شخصی',
        )
        self.assertEqual(activities.count(), 1)

    def test_builder_not_filtered_out_by_apartment_area(self):
        """سازنده نباید به‌خاطر max_area آپارتمان از اسکن حذف شود."""
        land = CRMProperty.objects.create(
            user=self.user,
            title='زمین ونک',
            property_type='زمین',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=5_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=250,
        )
        builder = Customer.objects.create(
            user=self.user,
            name='سازنده',
            phone='09121110005',
            customer_type='سازنده',
            status='در حال پیگیری',
            max_area=120,  # ترجیح فروش آپارتمان — نباید acquisition را بکشد
            builder_buy_budget_min=3_000_000_000,
            builder_buy_budget_max=8_000_000_000,
            builder_buy_min_area=200,
            builder_buy_max_area=400,
            builder_buy_areas='ونک',
            builder_buy_property_types='زمین,کلنگی',
            areas='ونک',
        )
        data = get_property_contact_matches(land, self.user)
        ids = {m['customer_id'] for m in data['matches']}
        self.assertIn(builder.pk, ids)


class PropertyContactSuggestViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09127778899', phone='09127778899', password='x',
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک تست ویو',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=2_500_000_000,
            neighborhood='ونک',
            city='تهران',
            area=95,
            rooms='2',
        )
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار ویو',
            phone='09127770001',
            customer_type='خریدار',
            status='در حال پیگیری',
            budget_min=1_500_000_000,
            budget_max=4_000_000_000,
            areas='ونک',
            property_type='آپارتمان',
        )

    def test_detail_includes_contact_match_data(self):
        url = reverse('workspace:crm_property_detail', kwargs={'property_id': self.prop.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['can_suggest_contacts'])
        self.assertIn('contact_match_data', resp.context)
        self.assertTrue(resp.context['contact_match_data']['eligible'])
        self.assertContains(resp, 'پیشنهاد مخاطب')

    def test_post_suggest_contacts(self):
        url = reverse('workspace:crm_property_detail', kwargs={'property_id': self.prop.pk})
        resp = self.client.post(url, {
            'action': 'suggest_contacts',
            'matches_json': json.dumps([{'customer_id': self.buyer.pk}]),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            PropertyContact.objects.filter(
                customer=self.buyer,
                property=self.prop,
                role='پیشنهادی',
            ).exists()
        )
        # پس از ریدایرکت، اکشن‌های واتساپ در تب مخاطبین باشد
        follow = self.client.get(resp.url)
        self.assertEqual(follow.status_code, 200)
        self.assertTrue(follow.context['contact_suggested'])
        self.assertTrue(follow.context['contact_suggestion_items'])
