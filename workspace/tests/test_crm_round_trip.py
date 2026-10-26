"""Round-trip ساده Export → Import مخاطب."""
import io

from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import Customer
from workspace.services.crm import customers_to_export_rows
from workspace.services.crm_import import import_contacts_from_file_result

User = get_user_model()


class DummyUpload(io.BytesIO):
    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name


class CRMContactRoundTripTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rt_user', password='x')
        self.customer = Customer.objects.create(
            user=self.user,
            name='=فرمول',
            phone='09121234567',
            customer_type='سرنخ',
            status='جدید',
            tags='VIP',
        )

    def test_export_row_formula_safe_and_reimport(self):
        rows = customers_to_export_rows([self.customer])
        self.assertTrue(str(rows[0]['نام']).startswith("'="))
        csv_line = (
            'نام,تلفن,برچسبها\n'
            'رضا جدید,09129876543,VIP\n'
        ).encode('utf-8-sig')
        result = import_contacts_from_file_result(self.user, DummyUpload(csv_line, 'r.csv'))
        self.assertEqual(result.created, 1)
        new = Customer.objects.get(pk=result.created_ids[0])
        self.assertEqual(new.name, 'رضا جدید')
        self.assertEqual(new.phone, '09129876543')
        self.assertEqual(new.tags, 'VIP')
