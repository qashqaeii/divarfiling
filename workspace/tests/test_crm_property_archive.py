"""تست بایگانی فایل‌های شخصی CRM."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from workspace.models import (
    CRMAgency,
    CRMAgencyMember,
    CRMProperty,
    CRMPropertyCabinet,
    CRMPropertyFolder,
    CRMPropertyFolderItem,
    Reminder,
)
from workspace.services.crm_sharing import share_property
from workspace.services.crm import filter_properties
from workspace.services.crm_property_archive import (
    archive_property,
    bulk_archive_properties,
    bulk_restore_properties,
    is_property_archived,
    restore_property,
)
from workspace.services.crm_property_folders import add_property_to_folder
from workspace.services.crm_property_suggestions import resolve_property_suggestion_items
from workspace.models import Customer

User = get_user_model()


class CRMPropertyArchiveServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='arch', password='x', phone='09120001001')
        self.other = User.objects.create_user(username='arch2', password='x', phone='09120001002')
        self.viewer = User.objects.create_user(username='view', password='x', phone='09120001003')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک فعال',
            deal_mode='فروش',
            transaction_status='در مذاکره',
        )
        self.folder = CRMPropertyFolder.objects.create(user=self.user, name='زونکن تست')

    def test_archive_preserves_transaction_status(self):
        archive_property(self.user, self.prop)
        self.prop.refresh_from_db()
        self.assertTrue(is_property_archived(self.prop))
        self.assertEqual(self.prop.transaction_status, 'در مذاکره')
        self.assertIsNotNone(self.prop.archived_at)

    def test_restore_keeps_transaction_status(self):
        archive_property(self.user, self.prop)
        restore_property(self.user, self.prop)
        self.prop.refresh_from_db()
        self.assertFalse(is_property_archived(self.prop))
        self.assertEqual(self.prop.transaction_status, 'در مذاکره')

    def test_legacy_transaction_status_archive_compat(self):
        legacy = CRMProperty.objects.create(
            user=self.user,
            title='قدیمی',
            deal_mode='فروش',
            transaction_status='بایگانی',
        )
        self.assertTrue(is_property_archived(legacy))

    def test_bulk_archive_and_restore(self):
        p2 = CRMProperty.objects.create(user=self.user, title='دوم', deal_mode='فروش')
        bulk_archive_properties(self.user, [self.prop.pk, p2.pk])
        self.prop.refresh_from_db()
        p2.refresh_from_db()
        self.assertTrue(is_property_archived(self.prop))
        result = bulk_restore_properties(self.user, [self.prop.pk, p2.pk])
        self.assertEqual(result['restored'], 2)

    def test_viewer_cannot_archive(self):
        agency = CRMAgency.objects.create(name='آ', owner=self.user)
        CRMAgencyMember.objects.create(agency=agency, user=self.user, role='owner', is_active=True)
        member = CRMAgencyMember.objects.create(
            agency=agency, user=self.viewer, role='advisor', is_active=True,
        )
        self.prop.agency = agency
        self.prop.save(update_fields=['agency'])
        share_property(self.user, self.prop, member.pk)
        with self.assertRaises(PermissionError):
            archive_property(self.viewer, self.prop)

    def test_folder_membership_preserved_on_archive(self):
        add_property_to_folder(self.user, self.folder.pk, self.prop.pk)
        archive_property(self.user, self.prop)
        self.assertEqual(CRMPropertyFolderItem.objects.filter(property=self.prop).count(), 1)


class CRMPropertyArchiveFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='filt', password='x', phone='09120002001')
        self.active = CRMProperty.objects.create(user=self.user, title='جاری', deal_mode='فروش')
        self.archived = CRMProperty.objects.create(
            user=self.user,
            title='بایگانی',
            deal_mode='فروش',
            archived_at=timezone.now(),
        )

    def test_default_list_excludes_archived(self):
        ids = list(filter_properties(self.user, {}).values_list('pk', flat=True))
        self.assertEqual(ids, [self.active.pk])

    def test_archived_scope(self):
        ids = list(filter_properties(self.user, {'archive_scope': 'archived'}).values_list('pk', flat=True))
        self.assertEqual(ids, [self.archived.pk])

    def test_archived_not_in_matching_suggestions(self):
        buyer = Customer.objects.create(
            user=self.user, name='خریدار', phone='09120002002', customer_type='خریدار',
            budget_min=1, budget_max=9_999_999_999,
        )
        archive_property(self.user, self.archived)
        ok, fails = resolve_property_suggestion_items(
            self.user, buyer, [{'source': 'crm', 'property_id': self.archived.pk}],
        )
        self.assertEqual(ok, [])
        self.assertTrue(fails)

    def test_cabinet_filter_distinct_for_multi_folder_property(self):
        cabinet = CRMPropertyCabinet.objects.create(user=self.user, name='کمد')
        folder_a = CRMPropertyFolder.objects.create(user=self.user, name='الف', cabinet=cabinet)
        folder_b = CRMPropertyFolder.objects.create(user=self.user, name='ب', cabinet=cabinet)
        CRMPropertyFolderItem.objects.create(folder=folder_a, property=self.active)
        CRMPropertyFolderItem.objects.create(folder=folder_b, property=self.active)
        qs = filter_properties(self.user, {'cabinet_id': str(cabinet.pk)})
        self.assertEqual(qs.count(), 1)


class CRMPropertyArchiveWebApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='web', password='x', phone='09120003001')
        self.client = Client()
        self.client.force_login(self.user)
        self.prop = CRMProperty.objects.create(user=self.user, title='وب', deal_mode='رهن و اجاره')

    def test_list_has_archive_tabs(self):
        res = self.client.get(reverse('workspace:crm_properties'))
        self.assertContains(res, 'بایگانی‌شده')
        self.assertContains(res, 'crmPropBulkArchive')

    def test_export_preserves_folder_id_in_filter_qs(self):
        folder = CRMPropertyFolder.objects.create(user=self.user, name='خروجی')
        res = self.client.get(reverse('workspace:crm_properties'), {'folder_id': folder.pk})
        self.assertContains(res, f'folder_id={folder.pk}')

    def test_rental_reminder_not_duplicated(self):
        archive_property(self.user, self.prop)
        url = reverse('workspace:crm_property_rental_reminder', kwargs={'property_id': self.prop.pk})
        body = json.dumps({'contract_end_jalali': '1406/08/03', 'create_reminder': True})
        first = self.client.post(url, body, content_type='application/json')
        self.assertEqual(first.status_code, 200)
        second = self.client.post(url, body, content_type='application/json')
        self.assertEqual(second.status_code, 200)
        from workspace.services.crm_property_rental_renewal import RENEWAL_REMINDER_KIND
        self.assertEqual(
            Reminder.objects.filter(
                user=self.user, property=self.prop, reminder_kind=RENEWAL_REMINDER_KIND, is_done=False,
            ).count(),
            1,
        )


class CRMPropertyArchiveMobileApiTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        self.owner = User.objects.create_user(username='09120004001', phone='09120004001', password='x')
        self.viewer = User.objects.create_user(username='09120004002', phone='09120004002', password='x')
        agency = CRMAgency.objects.create(name='موبایل', owner=self.owner)
        CRMAgencyMember.objects.create(agency=agency, user=self.owner, role='owner', is_active=True)
        viewer_member = CRMAgencyMember.objects.create(
            agency=agency, user=self.viewer, role='advisor', is_active=True,
        )
        self.prop = CRMProperty.objects.create(
            user=self.owner, agency=agency, title='موبایل', deal_mode='فروش',
        )
        share_property(self.owner, self.prop, viewer_member.pk)
        self.client = APIClient()
        token = RefreshToken.for_user(self.viewer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_readonly_cannot_change_status(self):
        resp = self.client.post(
            f'/api/mobile/v1/crm/properties/{self.prop.pk}/status',
            {'transaction_status': 'در مذاکره'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_readonly_cannot_patch_or_delete(self):
        patch = self.client.patch(
            f'/api/mobile/v1/crm/properties/{self.prop.pk}',
            {'title': 'هک'},
            format='json',
        )
        self.assertEqual(patch.status_code, 403)
        delete = self.client.delete(f'/api/mobile/v1/crm/properties/{self.prop.pk}')
        self.assertEqual(delete.status_code, 403)
