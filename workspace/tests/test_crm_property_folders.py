"""تست‌های زونکن فایل شخصی."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, CRMPropertyFolder, CRMPropertyFolderItem
from workspace.services.crm import filter_properties
from workspace.services.crm_property_folders import (
    add_property_to_folder,
    create_property_folder,
    folders_for_property,
    list_property_folders,
    remove_property_from_folder,
    reorder_property_folders,
    serialize_folder,
    update_property_folder,
)


class CRMPropertyFolderTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='zonkan_user',
            password='x',
            phone='09121110001',
        )
        self.other = User.objects.create_user(
            username='other_user',
            password='x',
            phone='09121110002',
        )
        self.prop_a = CRMProperty.objects.create(
            user=self.user,
            title='ملک A',
            property_type='آپارتمان',
            deal_mode='فروش',
        )
        self.prop_b = CRMProperty.objects.create(
            user=self.user,
            title='ملک B',
            property_type='ویلا',
            deal_mode='فروش',
        )
        self.folder = create_property_folder(self.user, name='برج سپهر')

    def test_create_folder_requires_name(self):
        with self.assertRaises(ValueError):
            create_property_folder(self.user, name='   ')

    def test_add_and_remove_property_membership(self):
        add_property_to_folder(self.user, self.folder.pk, self.prop_a.pk)
        self.assertEqual(
            CRMPropertyFolderItem.objects.filter(folder=self.folder).count(),
            1,
        )
        removed = remove_property_from_folder(self.user, self.folder.pk, self.prop_a.pk)
        self.assertTrue(removed)
        self.assertFalse(CRMPropertyFolderItem.objects.filter(folder=self.folder).exists())

    def test_filter_properties_by_folder_id(self):
        add_property_to_folder(self.user, self.folder.pk, self.prop_a.pk)
        qs = filter_properties(self.user, {'folder_id': str(self.folder.pk)})
        ids = list(qs.values_list('pk', flat=True))
        self.assertEqual(ids, [self.prop_a.pk])

    def test_folders_for_property_serialization(self):
        add_property_to_folder(self.user, self.folder.pk, self.prop_a.pk)
        briefs = folders_for_property(self.prop_a)
        self.assertEqual(len(briefs), 1)
        self.assertEqual(briefs[0]['name'], 'برج سپهر')

    def test_list_property_folders_counts(self):
        add_property_to_folder(self.user, self.folder.pk, self.prop_a.pk)
        add_property_to_folder(self.user, self.folder.pk, self.prop_b.pk)
        rows = list_property_folders(self.user)
        self.assertEqual(len(rows), 1)
        payload = serialize_folder(rows[0])
        self.assertEqual(payload['property_count'], 2)

    def test_reorder_property_folders(self):
        folder_b = create_property_folder(self.user, name='مجتمع B')
        folder_c = create_property_folder(self.user, name='مجتمع C')
        rows = reorder_property_folders(self.user, [folder_c.pk, self.folder.pk, folder_b.pk])
        names = [serialize_folder(f)['name'] for f in rows]
        self.assertEqual(names[:3], ['مجتمع C', 'برج سپهر', 'مجتمع B'])

    def test_update_folder_pin(self):
        updated = update_property_folder(self.user, self.folder.pk, {'is_pinned': True})
        self.assertTrue(updated.is_pinned)

    def test_user_cannot_access_other_users_folder(self):
        other_folder = create_property_folder(self.other, name='خصوصی')
        with self.assertRaises(ValueError):
            add_property_to_folder(self.user, other_folder.pk, self.prop_a.pk)
