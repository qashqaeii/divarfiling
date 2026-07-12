"""تست انتخابگر محله مخاطب."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.forms import CustomerForm
from workspace.models import Customer, Dataset, Listing
from workspace.services.filters import get_user_dataset_neighborhoods
from workspace.templatetags.crm_tags import split_areas

User = get_user_model()


class ContactAreasPickerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124445566', phone='09124445566', password='x')
        self.dataset = Dataset.objects.create(user=self.user, name='تست', is_active=True)
        Listing.objects.create(
            dataset=self.dataset,
            title='آگهی ۱',
            neighborhood='ونک',
            token='tok-1',
        )
        Listing.objects.create(
            dataset=self.dataset,
            title='آگهی ۲',
            neighborhood='زعفرانیه',
            token='tok-2',
        )
        Listing.objects.create(
            dataset=self.dataset,
            title='آگهی ۳',
            neighborhood='ونک',
            token='tok-3',
        )

    def test_get_user_dataset_neighborhoods_distinct_sorted(self):
        names = get_user_dataset_neighborhoods(self.user)
        self.assertEqual(names, ['زعفرانیه', 'ونک'])

    def test_split_areas_handles_persian_comma(self):
        self.assertEqual(split_areas('ونک، زعفرانیه'), ['ونک', 'زعفرانیه'])

    def test_customer_form_saves_areas_from_hidden_field(self):
        form = CustomerForm({
            'name': 'خریدار',
            'phone': '09120001111',
            'customer_type': 'خریدار',
            'status': 'جدید',
            'priority': 'متوسط',
            'areas': 'ونک، زعفرانیه، نواب',
        })
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save(commit=False)
        customer.user = self.user
        customer.save()
        self.assertIn('ونک', customer.areas)
        self.assertIn('نواب', customer.areas)
