"""ابطال کش هنگام create/revoke اشتراک CRMResourceShare."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from workspace.models import CRMAgency, CRMAgencyMember, CRMProperty, CRMResourceShare, Customer
from workspace.services.crm_matching_index import user_crm_properties_catalog_extra
from workspace.services.crm_sharing import revoke_share, share_property

User = get_user_model()


@override_settings(CACHES={
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
})
class ShareCatalogInvalidationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username='09128880011', phone='09128880011', password='x')
        self.advisor = User.objects.create_user(username='09128880012', phone='09128880012', password='x')
        self.agency = CRMAgency.objects.create(name='آژانس اشتراک', owner=self.owner)
        CRMAgencyMember.objects.create(agency=self.agency, user=self.owner, role='owner', is_active=True)
        self.advisor_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
        )
        self.prop = CRMProperty.objects.create(
            user=self.owner,
            agency=self.agency,
            title='ملک',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=12_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
        )
        before = user_crm_properties_catalog_extra(self.advisor)
        self.share = share_property(
            self.owner,
            self.prop,
            self.advisor_member.pk,
            share_mode=CRMResourceShare.SHARE_MODE_COLLABORATIVE,
        )
        self.catalog_after_share = user_crm_properties_catalog_extra(self.advisor)
        self.assertNotEqual(before, self.catalog_after_share)

    def test_revoke_share_bumps_advisor_catalog(self):
        after_share = self.catalog_after_share
        revoke_share(self.owner, self.share.pk)
        after_revoke = user_crm_properties_catalog_extra(self.advisor)
        self.assertNotEqual(after_share, after_revoke)
