"""رگرسیون کش تطبیق برای فایل‌های اشتراکی آژانس."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from workspace.models import CRMAgency, CRMAgencyMember, CRMProperty, CRMResourceShare, Customer
from workspace.services.crm_matching import get_customer_matches
from workspace.services.crm_matching_index import user_crm_properties_catalog_extra
from workspace.services.crm_sharing import share_property

User = get_user_model()


@override_settings(CACHES={
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
})
class AgencyCrmMatchCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username='09129990001', phone='09129990001', password='x')
        self.advisor = User.objects.create_user(username='09129990002', phone='09129990002', password='x')
        self.agency = CRMAgency.objects.create(name='آژانس کش', owner=self.owner)
        CRMAgencyMember.objects.create(agency=self.agency, user=self.owner, role='owner', is_active=True)
        self.advisor_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
        )
        self.buyer = Customer.objects.create(
            user=self.advisor,
            agency=self.agency,
            name='خریدار',
            phone='09129990003',
            customer_type='خریدار',
            budget_min=10_000_000_000,
            budget_max=20_000_000_000,
            areas='ونک',
        )
        self.prop = CRMProperty.objects.create(
            user=self.owner,
            agency=self.agency,
            title='آپارتمان ونک',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=25_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=100,
        )
        share_property(
            self.owner,
            self.prop,
            self.advisor_member.pk,
            share_mode=CRMResourceShare.SHARE_MODE_COLLABORATIVE,
        )

    def test_advisor_catalog_extra_changes_when_owner_updates_shared_property(self):
        before = user_crm_properties_catalog_extra(self.advisor)
        self.prop.sale_price = 12_000_000_000
        self.prop.save(update_fields=['sale_price'])
        after = user_crm_properties_catalog_extra(self.advisor)
        self.assertNotEqual(before, after)

    def test_advisor_sees_updated_match_after_owner_price_drop(self):
        get_customer_matches(
            self.buyer, self.advisor, divar_enabled=False, rebuild_index=True,
        )
        self.prop.sale_price = 12_000_000_000
        self.prop.save(update_fields=['sale_price'])
        data = get_customer_matches(
            self.buyer, self.advisor, divar_enabled=False, rebuild_index=False,
        )
        ids = {m['property_id'] for m in data['crm_matches']}
        self.assertIn(self.prop.pk, ids)
