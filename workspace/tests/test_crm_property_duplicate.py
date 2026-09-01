"""تست کپی فایل شخصی CRM."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from workspace.models import (
    CRMProperty,
    CRMPropertyCabinet,
    CRMPropertyFolder,
    CRMPropertyFolderItem,
    Customer,
    CustomerActivity,
    PropertyContact,
)
from workspace.services.crm_property_duplicate import COPY_SUFFIX, duplicate_property

User = get_user_model()


class CRMPropertyDuplicateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='propowner', password='test', phone='09121110091')
        self.other = User.objects.create_user(username='otheruser', password='test', phone='09121110092')
        self.cabinet = CRMPropertyCabinet.objects.create(user=self.user, name='فروش')
        self.folder = CRMPropertyFolder.objects.create(
            user=self.user, name='برج سپهر', cabinet=self.cabinet,
        )
        self.source = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ۱۲۰ متری برج سپهر',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            publish_status='پیش‌نویس',
            city='تهران',
            neighborhood='ونک',
            area=120,
            floor=5,
            sale_price=12_000_000_000,
            token='divar-token-abc',
            pipeline_order=42,
            phone='09121234567',
            owner_name='مالک',
            images=['/media/workspace/crm/properties/1/1/a.jpg'],
            feature_data={'جهت': 'شمال'},
            notes='یادداشت داخلی',
        )
        CRMPropertyFolderItem.objects.create(folder=self.folder, property=self.source)

    def test_duplicate_own_property_successfully(self):
        new_prop = duplicate_property(self.user, self.source.pk)
        self.assertNotEqual(new_prop.pk, self.source.pk)

    def test_copied_scalar_data_matches_original(self):
        new_prop = duplicate_property(self.user, self.source.pk)
        self.assertEqual(new_prop.deal_mode, self.source.deal_mode)
        self.assertEqual(new_prop.area, self.source.area)
        self.assertEqual(new_prop.sale_price, self.source.sale_price)
        self.assertEqual(new_prop.phone, self.source.phone)
        self.assertEqual(new_prop.feature_data, self.source.feature_data)
        self.assertEqual(new_prop.images, self.source.images)

    def test_copied_title_gets_copy_suffix(self):
        new_prop = duplicate_property(self.user, self.source.pk)
        self.assertTrue(new_prop.title.endswith(COPY_SUFFIX))
        self.assertIn('برج سپهر', new_prop.title)

    def test_editing_copy_does_not_modify_original(self):
        new_prop = duplicate_property(self.user, self.source.pk)
        new_prop.area = 99
        new_prop.save(update_fields=['area'])
        self.source.refresh_from_db()
        self.assertEqual(self.source.area, 120)

    def test_folder_memberships_copied(self):
        new_prop = duplicate_property(self.user, self.source.pk)
        folder_ids = set(
            CRMPropertyFolderItem.objects.filter(property=new_prop).values_list('folder_id', flat=True)
        )
        self.assertEqual(folder_ids, {self.folder.pk})

    def test_folder_membership_rows_independent(self):
        new_prop = duplicate_property(self.user, self.source.pk)
        new_item = CRMPropertyFolderItem.objects.get(property=new_prop, folder=self.folder)
        source_item = CRMPropertyFolderItem.objects.get(property=self.source, folder=self.folder)
        self.assertNotEqual(new_item.pk, source_item.pk)

    def test_cabinet_indirect_through_folder(self):
        new_prop = duplicate_property(self.user, self.source.pk)
        folder = CRMPropertyFolderItem.objects.select_related('folder__cabinet').get(
            property=new_prop,
        ).folder
        self.assertEqual(folder.cabinet_id, self.cabinet.pk)

    def test_timestamps_are_new(self):
        new_prop = duplicate_property(self.user, self.source.pk)
        self.assertGreaterEqual(new_prop.created_at, self.source.created_at)
        self.assertGreaterEqual(new_prop.updated_at, self.source.created_at)

    def test_unique_system_fields_not_reused(self):
        new_prop = duplicate_property(self.user, self.source.pk)
        self.assertEqual(new_prop.token, '')
        self.assertEqual(new_prop.source_platform, '')
        self.assertEqual(new_prop.source_external_id, '')
        self.assertIsNone(new_prop.deleted_at)
        self.assertEqual(new_prop.pipeline_order, 0)
        self.assertIsNone(new_prop.next_follow_up)

    def test_cross_user_duplicate_denied(self):
        with self.assertRaises(ValueError):
            duplicate_property(self.other, self.source.pk)

    def test_missing_property_error(self):
        with self.assertRaises(ValueError):
            duplicate_property(self.user, 999_999)

    def test_web_endpoint_returns_edit_redirect(self):
        self.client.force_login(self.user)
        url = reverse('workspace:crm_property_duplicate', kwargs={'property_id': self.source.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        new_id = data['property']['id']
        self.assertIn(f'/crm/properties/{new_id}/edit/', data['redirect_url'])

    def test_contacts_not_copied(self):
        customer = Customer.objects.create(user=self.user, name='خریدار', phone='09121111111')
        PropertyContact.objects.create(customer=customer, property=self.source, role='مالک')
        new_prop = duplicate_property(self.user, self.source.pk)
        self.assertEqual(new_prop.contact_links.count(), 0)
        self.assertEqual(self.source.contact_links.count(), 1)

    def test_activities_not_copied(self):
        customer = Customer.objects.create(user=self.user, name='خریدار', phone='09121111111')
        CustomerActivity.objects.create(
            customer=customer,
            property=self.source,
            activity_type='تماس',
            title='پیگیری',
        )
        new_prop = duplicate_property(self.user, self.source.pk)
        self.assertEqual(new_prop.activities.count(), 0)
        self.assertEqual(self.source.activities.count(), 1)

    def test_mobile_api_duplicate(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        url = f'/api/mobile/v1/crm/properties/{self.source.pk}/duplicate'
        resp = client.post(url)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertTrue(data['ok'])
        new_id = data['data']['id']
        self.assertNotEqual(new_id, self.source.pk)
        self.assertTrue(data['data']['title'].endswith(COPY_SUFFIX))
