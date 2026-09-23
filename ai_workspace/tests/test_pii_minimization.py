"""حداقل‌سازی PII در context ارسالی به LLM."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from ai_workspace.context_builders import contact_context, listing_context, property_context
from ai_workspace.context_builders.base import redact_pii_text
from ai_workspace.services.prompts import public_context_for_llm
from workspace.models import CRMProperty, Customer, CustomerActivity, Dataset, Listing


class RedactPiiTextTests(TestCase):
    def test_masks_mobile_and_email(self):
        raw = 'تماس 09123456789 یا test@example.com'
        out = redact_pii_text(raw)
        self.assertIn('[شماره]', out)
        self.assertIn('[ایمیل]', out)
        self.assertNotIn('09123456789', out)
        self.assertNotIn('test@example.com', out)


class ContactContextPiiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='pii_crm', password='x', phone='09120000099',
        )
        self.customer = Customer.objects.create(
            user=self.user,
            name='احمدی',
            phone='09121112233',
            email='secret@mail.com',
            national_id='1234567890',
            notes='یادداشت مخفی',
        )
        CustomerActivity.objects.create(
            customer=self.customer,
            activity_type='تماس',
            title='تماس',
            content='با 09129998877 صحبت شد',
            created_at=timezone.now(),
        )

    @patch('ai_workspace.context_builders.contact_context.get_customer_matches')
    def test_llm_context_excludes_phone_and_raw_activity(self, mocked_matches):
        mocked_matches.return_value = {
            'crm_matches': [{
                'title': 'ملک',
                'price_label': '۱۲ میلیارد',
                'score': 80,
                'link': 'https://divar.ir/v/abc',
                'token': 'tok',
            }],
            'divar_matches': [],
        }
        ctx = contact_context.build(self.customer, self.user, include_matches=True)
        public = public_context_for_llm(ctx)
        payload = str(public)
        self.assertNotIn('09121112233', payload)
        self.assertNotIn('secret@mail.com', payload)
        self.assertNotIn('1234567890', payload)
        self.assertNotIn('09129998877', payload)
        self.assertNotIn('top_matches', public)
        self.assertNotIn('divar.ir', payload)
        self.assertIn('تماس:', public.get('recent_activities', ''))


class PropertyContextPiiTests(TestCase):
    def test_address_omitted_from_location_tab(self):
        user = get_user_model().objects.create_user(username='pii_prop', password='x', phone='09120000088')
        prop = CRMProperty.objects.create(
            user=user,
            title='ویلا',
            city='تهران',
            neighborhood='سعادت‌آباد',
            address='کوچه مخفی پلاک ۷',
            notes='تماس 09123334455',
            sale_price=10_000_000_000,
            area=100,
            deal_mode='فروش',
        )
        ctx = property_context.build(prop, {})
        public = public_context_for_llm(ctx)
        blob = str(public)
        self.assertNotIn('کوچه مخفی', blob)
        self.assertNotIn('09123334455', blob)
        self.assertIn('سعادت‌آباد', public.get('neighborhood', ''))


class ListingContextPiiTests(TestCase):
    def test_description_redacted(self):
        user = get_user_model().objects.create_user(username='pii_lst', password='x', phone='09120000077')
        dataset = Dataset.objects.create(user=user, name='ds', city='تهران', transaction_type='فروش')
        listing = Listing.objects.create(
            dataset=dataset,
            token='t1',
            title='آپارتمان',
            price=5_000_000_000,
            description='مالک: 09125556677',
        )
        ctx = listing_context.build(listing, dataset, {})
        public = public_context_for_llm(ctx)
        self.assertNotIn('09125556677', str(public))
        self.assertIn('[شماره]', public.get('description_excerpt', ''))
