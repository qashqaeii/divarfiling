"""تست اشتراک پیشنهاد ملک — فقط لینک عمومی."""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from workspace.models import CRMProperty, Customer, Dataset, Listing, ListingPublicShare, PropertyContact
from workspace.models import CRMAgency, CRMAgencyMember
from workspace.services.crm import (
    apply_property_suggestions,
    build_portfolio_whatsapp_text,
    build_suggestions_whatsapp_text,
)
from workspace.services.property_suggestion_share import sharing_link_for_match

User = get_user_model()


@override_settings(SITE_URL='https://divarfiling.ir')
class PropertySuggestionShareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124445555', phone='09124445555', password='x')
        self.customer = Customer.objects.create(
            user=self.user,
            name='مستاجر اشتراک',
            phone='09124445555',
            customer_type='مستاجر',
            status='در حال پیگیری',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان تست اشتراک',
            property_type='آپارتمان',
            deal_mode='رهن و اجاره',
            transaction_status='فعال',
            deposit=200_000_000,
            monthly_rent=18_000_000,
            neighborhood='ونک',
            city='تهران',
            area=80,
            link='https://divar.ir/v/abc123',
        )
        self.factory = RequestFactory()

    def test_sharing_link_ignores_divar_url(self):
        match = {
            'link': 'https://divar.ir/v/abc123',
            'public_share_url': '',
        }
        self.assertEqual(sharing_link_for_match(match), '')

    def test_build_text_uses_public_share_url_not_divar(self):
        matches = [{
            'source': 'crm',
            'property_id': self.prop.pk,
            'title': self.prop.title,
            'price_label': 'رهن ۲۰۰ میلیون',
            'link': 'https://divar.ir/v/abc123',
            'public_share_url': 'https://divarfiling.ir/p/abc-share/',
        }]
        text = build_suggestions_whatsapp_text(self.customer, matches)
        self.assertIn('https://divarfiling.ir/p/abc-share/', text)
        self.assertNotIn('divar.ir', text)

    def test_apply_property_suggestions_enriches_public_url(self):
        request = self.factory.get('/')
        matches = [{
            'source': 'crm',
            'property_id': self.prop.pk,
            'title': self.prop.title,
            'link': 'https://divar.ir/v/abc123',
        }]
        text, linked = apply_property_suggestions(
            self.customer, self.user, matches, request=request,
        )
        self.assertEqual(linked, 1)
        self.assertIn('/p/', text)
        self.assertNotIn('divar.ir', text)

    def test_divar_listing_gets_public_share_in_text(self):
        request = self.factory.get('/')
        ds = Dataset.objects.create(
            user=self.user,
            name='ds',
            original_filename='test.xlsx',
            file_format='xlsx',
            transaction_type='rent',
        )
        listing = Listing.objects.create(
            dataset=ds,
            token='tok-share-1',
            title='آگهی دیوار تست',
            link='https://divar.ir/v/tok-share-1',
            neighborhood='ونک',
            rent=15_000_000,
            deposit=200_000_000,
        )
        matches = [{
            'source': 'divar',
            'token': listing.token,
            'title': listing.title,
            'link': listing.link,
        }]
        text, linked = apply_property_suggestions(
            self.customer, self.user, matches, request=request,
        )
        self.assertEqual(linked, 1)
        share = ListingPublicShare.objects.get(listing=listing, created_by=self.user)
        expected_path = reverse('listing_public:view', kwargs={'share_token': share.share_token})
        self.assertIn(expected_path, text)
        self.assertNotIn('divar.ir', text)

    def test_apply_property_suggestions_links_shared_agency_property(self):
        from workspace.services.crm_sharing import share_property

        owner = User.objects.create_user(username='09123334444', phone='09123334444', password='x')
        advisor = User.objects.create_user(username='09125556666', phone='09125556666', password='x')
        agency = CRMAgency.objects.create(name='آژانس پیشنهاد', owner=owner)
        owner_member = CRMAgencyMember.objects.create(
            agency=agency, user=owner, role='owner', is_active=True,
        )
        advisor_member = CRMAgencyMember.objects.create(
            agency=agency, user=advisor, role='advisor', is_active=True,
        )
        shared_prop = CRMProperty.objects.create(
            user=owner,
            agency=agency,
            title='ملک هم‌تیمی',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=5_000_000_000,
            neighborhood='نیاوران',
            city='تهران',
            area=100,
        )
        share_property(owner, shared_prop, advisor_member.pk)
        customer = Customer.objects.create(
            user=advisor,
            agency=agency,
            name='خریدار تست',
            phone='09127778888',
            customer_type='خریدار',
            status='در حال پیگیری',
        )
        matches = [{
            'source': 'crm',
            'property_id': shared_prop.pk,
            'title': shared_prop.title,
        }]
        text, linked = apply_property_suggestions(customer, advisor, matches)
        self.assertEqual(linked, 1)
        self.assertTrue(
            PropertyContact.objects.filter(
                customer=customer,
                property=shared_prop,
                role='پیشنهادی',
            ).exists()
        )
        self.assertIn(shared_prop.title, text)

    def test_portfolio_owner_whatsapp_text_not_buyer_copy(self):
        matches = [{
            'title': '۲۳۵متر زعفرانیه',
            'price_label': '199 میلیارد تومان',
            'area': 235,
            'neighborhood': 'ولنجک',
            'role': 'مالک',
            'share_url': 'https://divarfiling.ir/p/abc/',
        }]
        text = build_portfolio_whatsapp_text(self.customer, matches)
        self.assertIn('لینک فایل ملک شما:', text)
        self.assertNotIn('چند ملک مناسب برای شما', text)
        self.assertIn('https://divarfiling.ir/p/abc/', text)

    def test_portfolio_buyer_whatsapp_text_keeps_suggestion_copy(self):
        matches = [{
            'title': 'آپارتمان نیاوران',
            'role': 'خریدار',
            'share_url': 'https://divarfiling.ir/p/xyz/',
        }]
        text = build_portfolio_whatsapp_text(self.customer, matches)
        self.assertIn('چند ملک مناسب برای شما:', text)
        self.assertNotIn('لینک فایل ملک شما', text)
