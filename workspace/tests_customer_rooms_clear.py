"""پاک کردن محدودیت اتاق — فیلد legacy rooms."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.forms import CustomerForm
from workspace.models import Customer

User = get_user_model()


class CustomerRoomsClearTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128889999', phone='09128889999', password='x')
        self.customer = Customer.objects.create(
            user=self.user,
            name='تست اتاق',
            phone='09128889999',
            customer_type='خریدار',
            rooms='3',
            rooms_min=3,
            rooms_max=3,
        )

    def test_clearing_min_max_clears_legacy_rooms(self):
        form = CustomerForm(
            {
                'name': self.customer.name,
                'phone': self.customer.phone,
                'customer_type': 'خریدار',
                'status': self.customer.status or 'در حال پیگیری',
                'priority': self.customer.priority or 'متوسط',
                'property_type': self.customer.property_type or '',
                'source': self.customer.source or '',
                'rooms_min': '',
                'rooms_max': '',
            },
            instance=self.customer,
            user=self.user,
        )
        self.assertTrue(form.is_valid())
        saved = form.save()
        self.assertIsNone(saved.rooms_min)
        self.assertIsNone(saved.rooms_max)
        self.assertEqual(saved.rooms, '')
