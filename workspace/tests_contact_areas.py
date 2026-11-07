"""تست انتخابگر محله و خیابان مخاطب."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.forms import CustomerForm
from workspace.models import CRMProperty, Customer, Dataset, Listing
from workspace.services.filters import get_user_dataset_neighborhoods, get_user_location_streets
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
            data={'خیابان': 'ولیعصر'},
        )
        Listing.objects.create(
            dataset=self.dataset,
            title='آگهی ۲',
            neighborhood='زعفرانیه',
            token='tok-2',
            data={'مکان_خیابان': 'فرشته'},
        )
        Listing.objects.create(
            dataset=self.dataset,
            title='آگهی ۳',
            neighborhood='ونک',
            token='tok-3',
            data={'خیابان': 'ولیعصر'},
        )
        CRMProperty.objects.create(
            user=self.user,
            title='فایل شخصی',
            neighborhood='نیاوران',
            district='منطقه ۱',
            feature_data={'خیابان': 'پاسداران'},
        )

    def test_get_user_dataset_neighborhoods_includes_personal(self):
        names = get_user_dataset_neighborhoods(self.user)
        self.assertEqual(names, ['زعفرانیه', 'منطقه ۱', 'نیاوران', 'ونک'])

    def test_get_user_location_streets_from_filing_and_personal(self):
        names = get_user_location_streets(self.user)
        self.assertEqual(set(names), {'پاسداران', 'فرشته', 'ولیعصر'})
        self.assertEqual(names, sorted(names))

    def test_split_areas_handles_persian_comma(self):
        self.assertEqual(split_areas('ونک، زعفرانیه'), ['ونک', 'زعفرانیه'])

    def test_customer_form_saves_areas_and_streets(self):
        form = CustomerForm({
            'name': 'خریدار',
            'phone': '09120001111',
            'customer_type': 'خریدار',
            'status': 'جدید',
            'priority': 'متوسط',
            'areas': 'ونک، زعفرانیه، نواب',
            'streets': 'ولیعصر، فرشته',
        })
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save(commit=False)
        customer.user = self.user
        customer.save()
        self.assertIn('ونک', customer.areas)
        self.assertIn('نواب', customer.areas)
        self.assertIn('ولیعصر', customer.streets)
        self.assertIn('فرشته', customer.streets)
