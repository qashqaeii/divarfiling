"""تست حذف گروهی فایل‌های شخصی CRM."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from workspace.models import CRMProperty

User = get_user_model()


class CRMPropertyBulkDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='bulkdel', password='test', phone='09121110911',
        )
        self.other = User.objects.create_user(
            username='bulkdelother', password='test', phone='09121110912',
        )
        self.client.force_login(self.user)
        self.p1 = CRMProperty.objects.create(user=self.user, title='فایل یک', deal_mode='فروش')
        self.p2 = CRMProperty.objects.create(user=self.user, title='فایل دو', deal_mode='فروش')
        self.p3 = CRMProperty.objects.create(user=self.user, title='فایل سه', deal_mode='اجاره')
        self.foreign = CRMProperty.objects.create(
            user=self.other, title='فایل دیگری', deal_mode='فروش',
        )
        self.url = reverse('workspace:crm_properties_bulk_delete')

    def test_list_shows_bulk_delete_even_without_folders(self):
        res = self.client.get(reverse('workspace:crm_properties'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'crmPropBulkDelete')
        self.assertContains(res, 'حذف فایل‌ها')
        self.assertContains(res, 'حذف قطعی')
        self.assertContains(res, 'crmPropSelectMode')

    def test_soft_deletes_selected_own_properties(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'property_ids': [self.p1.pk, self.p2.pk]}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['deleted'], 2)
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.p3.refresh_from_db()
        self.assertIsNotNone(self.p1.deleted_at)
        self.assertIsNotNone(self.p2.deleted_at)
        self.assertIsNone(self.p3.deleted_at)

    def test_does_not_delete_other_users_properties(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'property_ids': [self.p1.pk, self.foreign.pk]}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['deleted'], 1)
        self.foreign.refresh_from_db()
        self.assertIsNone(self.foreign.deleted_at)
        self.p1.refresh_from_db()
        self.assertIsNotNone(self.p1.deleted_at)

    def test_empty_selection_returns_error(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'property_ids': []}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['ok'])
