"""Import مخاطبین — agency، نمایش، و ستون‌های alias."""
import io

from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMAgency, CRMAgencyMember, Customer
from workspace.services.crm_import import import_contacts_from_file_result
from workspace.services.crm_scope import customers_qs
from workspace.services.spreadsheet_io import spreadsheet_safe_cell, stable_union_fieldnames

User = get_user_model()


class DummyUpload(io.BytesIO):
    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name


class CRMContactImportAgencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='agency_imp', password='x')
        self.agency = CRMAgency.objects.create(name='آژانس تست', owner=self.user)
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.user, role='advisor', is_active=True,
        )

    def test_import_sets_agency_and_visible_in_list_scope(self):
        csv_content = (
            'نام مخاطب,موبایل\n'
            'رضا کریمی,09125556677\n'
        ).encode('utf-8-sig')
        result = import_contacts_from_file_result(
            self.user,
            DummyUpload(csv_content, 'c.csv'),
        )
        self.assertEqual(result.created, 1)
        self.assertEqual(result.aborted, False)
        customer = Customer.objects.get(pk=result.created_ids[0])
        self.assertEqual(customer.agency_id, self.agency.id)
        self.assertTrue(customers_qs(self.user).filter(pk=customer.pk).exists())
        self.assertEqual(result.visible_created_count(self.user), 1)

    def test_legacy_null_agency_still_visible_for_member(self):
        hidden = Customer.objects.create(
            user=self.user,
            agency=None,
            name='قدیمی',
            phone='09120001111',
            customer_type='سرنخ',
            status='جدید',
        )
        self.assertTrue(customers_qs(self.user).filter(pk=hidden.pk).exists())

    def test_aborts_without_name_column(self):
        csv_content = 'موبایل\n09121112222\n'.encode('utf-8')
        result = import_contacts_from_file_result(
            self.user,
            DummyUpload(csv_content, 'c.csv'),
        )
        self.assertTrue(result.aborted)
        self.assertEqual(result.created, 0)


class SpreadsheetExportHelperTests(TestCase):
    def test_stable_union_fieldnames(self):
        rows = [{'a': 1, 'b': 2}, {'b': 3, 'c': 4}]
        self.assertEqual(stable_union_fieldnames(rows), ['a', 'b', 'c'])

    def test_formula_injection_prefix(self):
        self.assertEqual(spreadsheet_safe_cell('=1+1'), "'=1+1")
