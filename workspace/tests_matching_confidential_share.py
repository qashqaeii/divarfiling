"""تطبیق و پیشنهاد — عدم افشای فایل اشتراک محرمانه."""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from workspace.models import CRMAgency, CRMAgencyMember, CRMProperty, CRMResourceShare, Customer
from workspace.services.crm import apply_property_suggestions
from workspace.services.crm_matching import get_customer_matches
from workspace.services.crm_sharing import share_property
from workspace.services.property_suggestion_share import enrich_match_with_links

User = get_user_model()


class ConfidentialShareMatchingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='09120001111', phone='09120001111', password='x')
        self.advisor = User.objects.create_user(username='09120002222', phone='09120002222', password='x')
        self.agency = CRMAgency.objects.create(name='آژانس تطبیق', owner=self.owner)
        CRMAgencyMember.objects.create(agency=self.agency, user=self.owner, role='owner', is_active=True)
        self.advisor_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
        )
        self.buyer = Customer.objects.create(
            user=self.advisor,
            agency=self.agency,
            name='خریدار',
            phone='09123334444',
            customer_type='خریدار',
            budget_min=8_000_000_000,
            budget_max=20_000_000_000,
            areas='ونک',
            status='در حال پیگیری',
        )
        self.prop = CRMProperty.objects.create(
            user=self.owner,
            agency=self.agency,
            title='آپارتمان مخفی ونک',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=12_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=100,
            link='https://divar.ir/v/secret123',
            phone='09125556677',
            owner_name='مالک مخفی',
        )
        share_property(
            self.owner,
            self.prop,
            self.advisor_member.pk,
            share_mode=CRMResourceShare.SHARE_MODE_CONFIDENTIAL,
        )
        self.factory = RequestFactory()

    def test_get_customer_matches_masks_confidential_shared_property(self):
        data = get_customer_matches(self.buyer, self.advisor, divar_enabled=False)
        crm = data.get('crm_matches') or []
        self.assertTrue(crm, 'باید حداقل یک پیشنهاد CRM باشد')
        match = next(m for m in crm if m.get('property_id') == self.prop.pk)
        self.assertTrue(match.get('mask_sensitive'))
        self.assertNotIn('آپارتمان مخفی', match.get('title') or '')
        self.assertNotIn('divar.ir', (match.get('link') or '').lower())
        self.assertNotIn('۱۲', match.get('price_label') or '')
        self.assertNotIn('ونک', match.get('neighborhood') or '')

    def test_enrich_match_does_not_create_public_link_for_confidential(self):
        match = {
            'source': 'crm',
            'property_id': self.prop.pk,
            'title': 'عنوان جعلی',
            'link': 'https://divar.ir/v/fake',
            'price_label': '۹۹ میلیارد',
        }
        request = self.factory.get('/')
        enriched = enrich_match_with_links(self.advisor, request, match)
        self.assertTrue(enriched.get('mask_sensitive'))
        self.assertEqual(enriched.get('public_share_url'), '')
        self.assertEqual(enriched.get('link'), '')

    def test_apply_suggestions_ignores_tampered_title(self):
        matches = [{
            'source': 'crm',
            'property_id': self.prop.pk,
            'title': 'عنوان دستکاری‌شده',
            'price_label': '۱ میلیون',
            'score': 99,
        }]
        text, linked = apply_property_suggestions(self.buyer, self.advisor, matches)
        self.assertEqual(linked, 1)
        self.assertNotIn('عنوان دستکاری‌شده', text)
        self.assertNotIn('divar.ir', text.lower())
