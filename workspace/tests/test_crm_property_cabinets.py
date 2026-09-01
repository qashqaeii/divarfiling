"""تست‌های کمد فایل شخصی."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, CRMPropertyFolder, CRMPropertyFolderItem
from workspace.services.crm import filter_properties
from workspace.services.crm_property_cabinets import (
    assign_folder_to_cabinet,
    create_property_cabinet,
    delete_property_cabinet,
    list_property_cabinets,
    remove_folder_from_cabinet,
    reorder_property_cabinets,
    serialize_cabinet,
    update_property_cabinet,
)
from workspace.services.crm_property_folders import (
    add_property_to_folder,
    create_property_folder,
    list_property_folders,
)


class CRMPropertyCabinetTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='cabinet_user',
            password='x',
            phone='09121110011',
        )
        self.other = User.objects.create_user(
            username='cabinet_other',
            password='x',
            phone='09121110012',
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
        self.cabinet = create_property_cabinet(self.user, name='فروش')
        self.folder_a = create_property_folder(self.user, name='برج سپهر', cabinet_id=self.cabinet.pk)
        self.folder_b = create_property_folder(self.user, name='فوری')
        add_property_to_folder(self.user, self.folder_a.pk, self.prop_a.pk)
        add_property_to_folder(self.user, self.folder_b.pk, self.prop_a.pk)
        add_property_to_folder(self.user, self.folder_b.pk, self.prop_b.pk)

    def test_create_cabinet(self):
        cab = create_property_cabinet(self.user, name='اجاره')
        self.assertEqual(cab.name, 'اجاره')

    def test_unique_cabinet_name_per_user(self):
        with self.assertRaises(ValueError):
            create_property_cabinet(self.user, name='فروش')

    def test_cross_user_cabinet_access_denied(self):
        other_cab = create_property_cabinet(self.other, name='خصوصی')
        with self.assertRaises(ValueError):
            assign_folder_to_cabinet(self.user, self.folder_b.pk, other_cab.pk)

    def test_assign_folder_to_cabinet(self):
        folder = assign_folder_to_cabinet(self.user, self.folder_b.pk, self.cabinet.pk)
        self.assertEqual(folder.cabinet_id, self.cabinet.pk)

    def test_cannot_assign_another_users_folder(self):
        other_folder = create_property_folder(self.other, name='دیگر')
        with self.assertRaises(ValueError):
            assign_folder_to_cabinet(self.user, other_folder.pk, self.cabinet.pk)

    def test_cannot_assign_folder_to_another_users_cabinet(self):
        other_cab = create_property_cabinet(self.other, name='کمد دیگر')
        with self.assertRaises(ValueError):
            assign_folder_to_cabinet(self.user, self.folder_b.pk, other_cab.pk)

    def test_move_folder_between_cabinets(self):
        cab2 = create_property_cabinet(self.user, name='اجاره')
        assign_folder_to_cabinet(self.user, self.folder_b.pk, self.cabinet.pk)
        folder = assign_folder_to_cabinet(self.user, self.folder_b.pk, cab2.pk)
        self.assertEqual(folder.cabinet_id, cab2.pk)
        self.assertEqual(CRMPropertyFolderItem.objects.filter(folder=self.folder_b).count(), 2)

    def test_remove_folder_from_cabinet(self):
        folder = remove_folder_from_cabinet(self.user, self.folder_a.pk)
        self.assertIsNone(folder.cabinet_id)

    def test_delete_cabinet_does_not_delete_folders(self):
        delete_property_cabinet(self.user, self.cabinet.pk)
        self.assertTrue(CRMPropertyFolder.objects.filter(pk=self.folder_a.pk).exists())
        self.folder_a.refresh_from_db()
        self.assertIsNone(self.folder_a.cabinet_id)

    def test_delete_cabinet_does_not_delete_properties(self):
        delete_property_cabinet(self.user, self.cabinet.pk)
        self.assertEqual(CRMProperty.objects.filter(user=self.user).count(), 2)

    def test_cabinet_folder_count(self):
        assign_folder_to_cabinet(self.user, self.folder_b.pk, self.cabinet.pk)
        rows = list_property_cabinets(self.user)
        payload = serialize_cabinet(rows[0])
        self.assertEqual(payload['folder_count'], 2)

    def test_cabinet_distinct_property_count(self):
        assign_folder_to_cabinet(self.user, self.folder_b.pk, self.cabinet.pk)
        rows = list_property_cabinets(self.user)
        payload = serialize_cabinet(rows[0])
        self.assertEqual(payload['property_count'], 2)

    def test_filter_properties_by_cabinet_id(self):
        assign_folder_to_cabinet(self.user, self.folder_b.pk, self.cabinet.pk)
        qs = filter_properties(self.user, {'cabinet_id': str(self.cabinet.pk)})
        ids = sorted(qs.values_list('pk', flat=True))
        self.assertEqual(ids, sorted([self.prop_a.pk, self.prop_b.pk]))
        self.assertEqual(qs.count(), 2)

    def test_no_duplicate_properties_in_cabinet_filter(self):
        assign_folder_to_cabinet(self.user, self.folder_b.pk, self.cabinet.pk)
        qs = filter_properties(self.user, {'cabinet_id': str(self.cabinet.pk)})
        self.assertEqual(qs.count(), qs.distinct().count())

    def test_reorder_cabinets(self):
        cab2 = create_property_cabinet(self.user, name='B')
        cab3 = create_property_cabinet(self.user, name='C')
        rows = reorder_property_cabinets(self.user, [cab3.pk, cab2.pk, self.cabinet.pk])
        names = [serialize_cabinet(c)['name'] for c in rows[:3]]
        self.assertEqual(names, ['C', 'B', 'فروش'])

    def test_pin_cabinet(self):
        updated = update_property_cabinet(self.user, self.cabinet.pk, {'is_pinned': True})
        self.assertTrue(updated.is_pinned)

    def test_list_folders_by_cabinet(self):
        rows = list_property_folders(self.user, cabinet_id=self.cabinet.pk)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, 'برج سپهر')

    def test_list_folders_unassigned(self):
        rows = list_property_folders(self.user, cabinet_id='none')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, 'فوری')
