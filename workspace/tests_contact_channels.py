"""تست کانال‌های پیام‌رسانی مخاطب."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.forms import CustomerForm
from workspace.models import Customer
from workspace.services.contact_channels import (
    contact_channels_for_display,
    contact_channels_from_post,
    merge_contact_channels,
)

User = get_user_model()


class ContactChannelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09123334444', phone='09123334444', password='x')

    def _base_form_data(self, **extra):
        data = {
            'name': 'مخاطب تست',
            'phone': '09121112233',
            'customer_type': 'خریدار',
            'status': 'جدید',
            'priority': 'متوسط',
        }
        data.update(extra)
        return data

    def test_customer_form_saves_active_channels_and_social_links(self):
        data = self._base_form_data(
            contact_active_whatsapp='on',
            contact_active_telegram='on',
            contact_social_telegram='myuser',
        )
        form = CustomerForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save(commit=False)
        customer.user = self.user
        customer.save()
        self.assertIn('whatsapp', customer.active_channels)
        self.assertIn('telegram', customer.active_channels)
        self.assertEqual(customer.social_links.get('telegram'), 'myuser')

    def test_contact_channels_from_post_normalizes_social(self):
        active, links = contact_channels_from_post({
            'phone': '09120001111',
            'contact_active_instagram': 'on',
            'contact_social_instagram': '@shop.test',
        })
        self.assertIn('instagram', active)
        self.assertEqual(links.get('instagram'), 'shop.test')

    def test_contact_channels_for_display_builds_whatsapp_link(self):
        customer = Customer.objects.create(
            user=self.user,
            name='نمونه',
            phone='09120001111',
            active_channels=['whatsapp', 'telegram'],
            social_links={'telegram': 'sampleuser'},
        )
        channels = contact_channels_for_display(customer, message='سلام')
        keys = [c['key'] for c in channels]
        self.assertIn('whatsapp', keys)
        self.assertIn('telegram', keys)
        wa = next(c for c in channels if c['key'] == 'whatsapp')
        self.assertIn('wa.me', wa['href'])
        self.assertIn('text=', wa['href'])

    def test_merge_contact_channels_combines_both_customers(self):
        primary = Customer.objects.create(
            user=self.user,
            name='اصلی',
            phone='09120001111',
            active_channels=['whatsapp'],
            social_links={},
        )
        secondary = Customer.objects.create(
            user=self.user,
            name='فرعی',
            phone='09129998877',
            active_channels=['telegram'],
            social_links={'telegram': 'other'},
        )
        merge_contact_channels(primary, secondary)
        self.assertIn('telegram', primary.active_channels)
        self.assertEqual(primary.social_links.get('telegram'), 'other')
