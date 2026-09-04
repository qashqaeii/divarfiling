"""تست ثبت معامله از صفحه فایل شخصی."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from workspace.models import CRMDeal, CRMAgency, CRMAgencyMember, CRMProperty, Customer, PropertyContact
from workspace.services.crm_deals import (
    create_deal,
    default_deal_value_for_property,
    find_duplicate_active_deal,
    get_property_deal_parties_context,
    infer_deal_kind_from_property,
)

User = get_user_model()


class PropertyDealCreateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121111111', password='test', phone='09121111111')
        self.other = User.objects.create_user(username='deal-other', password='test', phone='09129998888')
        self.property = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان سعادت‌آباد',
            property_type='آپارتمان',
            deal_mode='فروش',
            sale_price=12_000_000_000,
            city='تهران',
            district='سعادت‌آباد',
        )
        self.rent_property = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان بریانک',
            property_type='آپارتمان',
            deal_mode='رهن و اجاره',
            deposit=500_000_000,
            monthly_rent=25_000_000,
        )
        self.buyer = Customer.objects.create(
            user=self.user, name='دکتر رحیمی', phone='09123334444', customer_type='خریدار',
        )
        self.tenant = Customer.objects.create(
            user=self.user, name='علی احمدی', phone='09124445555', customer_type='مستاجر',
        )
        self.foreign_customer = Customer.objects.create(
            user=self.other, name='مشتری دیگر', phone='09125556666',
        )
        self.create_url = reverse(
            'workspace:crm_property_deal_create',
            kwargs={'property_id': self.property.pk},
        )
        self.detail_url = reverse(
            'workspace:crm_property_detail',
            kwargs={'property_id': self.property.pk},
        )

    def _post_deal(self, user, prop, customer, **extra):
        self.client.force_login(user)
        data = {
            'customer': customer.pk,
            'deal_kind': extra.pop('deal_kind', infer_deal_kind_from_property(prop)),
            'title': extra.pop('title', ''),
            'stage': extra.pop('stage', 'سرنخ'),
            'value': extra.pop('value', prop.sale_price or prop.monthly_rent or ''),
            'force_duplicate': extra.pop('force_duplicate', ''),
        }
        data.update(extra)
        return self.client.post(
            reverse('workspace:crm_property_deal_create', kwargs={'property_id': prop.pk}),
            data,
        )

    def test_authorized_user_can_create_deal_from_property(self):
        resp = self._post_deal(self.user, self.property, self.buyer, title='فروش تست')
        self.assertEqual(resp.status_code, 302)
        deal = CRMDeal.objects.get(property=self.property, customer=self.buyer)
        self.assertEqual(deal.user_id, self.user.pk)
        self.assertEqual(deal.title, 'فروش تست')

    def test_property_linked_correctly(self):
        self._post_deal(self.user, self.property, self.buyer)
        deal = CRMDeal.objects.get(property=self.property)
        self.assertEqual(deal.property_id, self.property.pk)
        self.assertEqual(deal.listing_token, self.property.token or '')

    def test_customer_linked_correctly(self):
        self._post_deal(self.user, self.property, self.buyer)
        deal = CRMDeal.objects.get(property=self.property)
        self.assertEqual(deal.customer_id, self.buyer.pk)

    def test_sale_default_deal_kind_and_value(self):
        self._post_deal(self.user, self.property, self.buyer, value='')
        deal = CRMDeal.objects.get(property=self.property)
        self.assertEqual(deal.deal_kind, 'sale')
        self.assertEqual(deal.value, 12_000_000_000)

    def test_rent_default_deal_kind_and_monthly_rent_value(self):
        self._post_deal(
            self.user, self.rent_property, self.tenant,
            deal_kind='rent', value='',
        )
        deal = CRMDeal.objects.get(property=self.rent_property)
        self.assertEqual(deal.deal_kind, 'rent')
        self.assertEqual(deal.value, 25_000_000)

    def test_rent_deposit_only_does_not_prefill_deposit(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک فقط رهن',
            property_type='آپارتمان',
            deal_mode='رهن و اجاره',
            deposit=800_000_000,
            monthly_rent=None,
        )
        self.assertIsNone(default_deal_value_for_property(prop, 'rent'))
        self._post_deal(self.user, prop, self.tenant, deal_kind='rent', value='')
        deal = CRMDeal.objects.get(property=prop)
        self.assertIsNone(deal.value)

    def test_sale_price_default_value_helper(self):
        self.assertEqual(
            default_deal_value_for_property(self.property, 'sale'),
            12_000_000_000,
        )

    def test_unauthorized_property_denied(self):
        resp = self._post_deal(self.other, self.property, self.foreign_customer)
        self.assertIn(resp.status_code, (302, 403, 404))
        self.assertFalse(CRMDeal.objects.filter(property=self.property).exists())

    def test_unauthorized_customer_denied(self):
        resp = self._post_deal(self.user, self.property, self.foreign_customer)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(CRMDeal.objects.filter(property=self.property).exists())

    def test_duplicate_active_deal_warning_blocks_by_default(self):
        create_deal(self.user, self.buyer, property_obj=self.property, title='معامله اول')
        resp = self._post_deal(self.user, self.property, self.buyer, title='معامله دوم')
        self.assertEqual(CRMDeal.objects.filter(property=self.property, customer=self.buyer).count(), 1)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('drawer=property-deal', resp.url)

    def test_duplicate_can_be_overridden(self):
        create_deal(self.user, self.buyer, property_obj=self.property, title='معامله اول')
        resp = self._post_deal(
            self.user, self.property, self.buyer,
            title='معامله دوم', force_duplicate='on',
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            CRMDeal.objects.filter(property=self.property, customer=self.buyer).count(), 2,
        )

    def test_find_duplicate_active_deal_helper(self):
        existing = create_deal(self.user, self.buyer, property_obj=self.property)
        dup = find_duplicate_active_deal(self.user, self.property, self.buyer)
        self.assertEqual(dup.pk, existing.pk)

    def test_property_detail_shows_create_button(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.detail_url)
        self.assertContains(resp, 'ثبت معامله')
        self.assertContains(resp, 'drawer-property-deal')

    def test_creates_property_contact_link(self):
        self._post_deal(self.user, self.property, self.buyer)
        link = PropertyContact.objects.filter(
            property=self.property, customer=self.buyer,
        ).first()
        self.assertIsNotNone(link)
        self.assertEqual(link.role, 'خریدار')

    def test_agency_member_can_open_deal_detail_after_create(self):
        agency = CRMAgency.objects.create(name='آژانس تست', owner=self.user)
        CRMAgencyMember.objects.create(agency=agency, user=self.user, role='advisor')
        self.property.agency = agency
        self.property.save(update_fields=['agency'])
        self.buyer.agency = agency
        self.buyer.save(update_fields=['agency'])
        resp = self._post_deal(self.user, self.property, self.buyer, title='فروش آژانس')
        self.assertEqual(resp.status_code, 302)
        deal = CRMDeal.objects.get(property=self.property, title='فروش آژانس')
        self.assertEqual(deal.agency_id, agency.pk)
        detail = self.client.get(reverse('workspace:crm_deal_detail', kwargs={'deal_id': deal.pk}))
        self.assertEqual(detail.status_code, 200)

    def test_property_deal_parties_context_sale(self):
        owner = Customer.objects.create(
            user=self.user, name='مالکی', phone='09181112222', customer_type='مالک',
        )
        PropertyContact.objects.create(
            property=self.property, customer=owner, role='مالک', is_primary=True,
        )
        ctx = get_property_deal_parties_context(self.property, 'sale')
        self.assertEqual(ctx['property_side']['label'], 'فروشنده')
        self.assertEqual(ctx['customer_side']['label'], 'خریدار')
        self.assertEqual(ctx['property_side']['name'], 'مالکی')
        self.assertEqual(ctx['property_side']['phone'], '09181112222')

    def test_property_deal_parties_context_rent(self):
        owner = Customer.objects.create(
            user=self.user, name='موجر', phone='09183334444', customer_type='مالک',
        )
        PropertyContact.objects.create(
            property=self.rent_property, customer=owner, role='مالک', is_primary=True,
        )
        PropertyContact.objects.create(
            property=self.rent_property, customer=self.tenant, role='مستاجر',
        )
        ctx = get_property_deal_parties_context(self.rent_property, 'rent')
        self.assertEqual(ctx['property_side']['label'], 'موجر')
        self.assertEqual(ctx['customer_side']['label'], 'مستأجر')
        self.assertEqual(ctx['customer_side']['suggested']['id'], self.tenant.pk)
