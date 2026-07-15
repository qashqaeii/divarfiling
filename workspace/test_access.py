"""تست دسترسی لایه‌ای میزکار."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from workspace.models import CRMAgency, CRMAgencyMember, CRMProperty, Dataset, Listing
from workspace.services.access import get_bot_license_display
from workspace.templatetags.workspace_tags import ws_subcategory_short

User = get_user_model()


class WorkspaceAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='freeuser', password='pass1234', phone='09124444444',
        )
        self.product = Product.objects.create(
            title='ربات تست',
            slug='test-bot',
            description='محصول تست',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس یک‌ماهه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )

    def _create_active_license(self, user=None):
        user = user or self.user
        order = Order.objects.create(
            user=user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        return License.objects.create(
            order=order,
            plan=self.plan,
            license_key='TEST-1234-5678-9ABC',
            status='active',
            max_activations=1,
        )

    def test_crm_accessible_without_license(self):
        self.client.login(username='freeuser', password='pass1234')
        for url_name in (
            'workspace:crm_dashboard',
            'workspace:crm_contacts',
            'workspace:crm_properties',
            'workspace:crm_reminders',
        ):
            with self.subTest(url=url_name):
                resp = self.client.get(reverse(url_name))
                self.assertEqual(resp.status_code, 200)

    def test_workspace_home_accessible_without_license(self):
        self.client.login(username='freeuser', password='pass1234')
        resp = self.client.get(reverse('workspace:home'))
        self.assertEqual(resp.status_code, 200)

    def test_dataset_list_blocked_without_license(self):
        self.client.login(username='freeuser', password='pass1234')
        resp = self.client.get(reverse('workspace:dataset_list'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/workspace/upgrade/', resp.url)

    def test_dataset_list_allowed_with_license(self):
        self._create_active_license()
        self.client.login(username='freeuser', password='pass1234')
        resp = self.client.get(reverse('workspace:dataset_list'))
        self.assertEqual(resp.status_code, 200)

    def test_import_alias_opens_upload_modal(self):
        """ربات دسکتاپ به /workspace/import/ لینک می‌دهد — نباید ۴۰۴ بدهد."""
        self._create_active_license()
        self.client.login(username='freeuser', password='pass1234')
        resp = self.client.get(reverse('workspace:import'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('open=modal-upload', resp.url)
        self.assertIn('/workspace/datasets/', resp.url)

    def test_import_blocked_without_license(self):
        self.client.login(username='freeuser', password='pass1234')
        resp = self.client.get(reverse('workspace:import'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/workspace/upgrade/', resp.url)

    def test_upgrade_redirects_when_licensed(self):
        self._create_active_license()
        self.client.login(username='freeuser', password='pass1234')
        resp = self.client.get(reverse('workspace:upgrade'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('workspace:home'))

    def test_tools_blocked_without_license(self):
        self.client.login(username='freeuser', password='pass1234')
        resp = self.client.get(reverse('workspace:tools'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/workspace/upgrade/', resp.url)

    def test_pending_order_does_not_unlock_workspace(self):
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
        )
        self.client.login(username='freeuser', password='pass1234')
        resp = self.client.get(reverse('workspace:dataset_list'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/workspace/upgrade/', resp.url)

    def test_staff_without_bypass_does_not_unlock(self):
        staff = User.objects.create_user(
            username='staffuser', password='pass1234', phone='09125555555', is_staff=True,
        )
        self.client.login(username='staffuser', password='pass1234')
        resp = self.client.get(reverse('workspace:dataset_list'))
        self.assertEqual(resp.status_code, 302)

    def test_paid_inactive_license_does_not_unlock(self):
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        License.objects.create(
            order=order,
            plan=self.plan,
            license_key='PEND-1234-5678-9ABC',
            status='inactive',
            max_activations=1,
        )
        self.client.login(username='freeuser', password='pass1234')
        resp = self.client.get(reverse('workspace:dataset_list'))
        self.assertEqual(resp.status_code, 302)

    def test_bot_license_display_without_license(self):
        display = get_bot_license_display(self.user)
        self.assertEqual(display['status_key'], 'none')
        self.assertEqual(display['label'], 'بدون لایسنس')

    def test_bot_license_display_active_with_days_remaining(self):
        lic = self._create_active_license()
        lic.expires_at = timezone.now() + timedelta(days=15)
        lic.save(update_fields=['expires_at'])
        display = get_bot_license_display(self.user)
        self.assertTrue(display['active'])
        self.assertEqual(display['days_remaining'], 15)
        self.assertIn('۱۵ روز تا انقضا', display['label'])

    def test_workspace_home_shows_license_pill(self):
        lic = self._create_active_license()
        lic.expires_at = timezone.now() + timedelta(days=10)
        lic.save(update_fields=['expires_at'])
        self.client.login(username='freeuser', password='pass1234')
        resp = self.client.get(reverse('workspace:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'mk-hub-head-pill--license')
        self.assertContains(resp, 'روز تا انقضا')

    def test_ws_subcategory_short_labels(self):
        self.assertEqual(
            ws_subcategory_short('تجاری دفتر کار، اتاق اداری، مطب'),
            'تجاری',
        )
        self.assertEqual(
            ws_subcategory_short('دفتر کار، اتاق اداری، مطب'),
            'تجاری',
        )
        self.assertEqual(
            ws_subcategory_short('دفتر کار اتاق اداری مطب'),
            'تجاری',
        )
        self.assertEqual(ws_subcategory_short('خانه و ویلا'), 'ویلایی')
        self.assertEqual(ws_subcategory_short('آپارتمان'), 'آپارتمان')
        self.assertEqual(ws_subcategory_short('مغازه و غرفه'), 'مغازه و غرفه')


class PersonalFileFromListingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='agentuser', password='pass1234', phone='09126666666',
        )
        self.product = Product.objects.create(
            title='ربات تست',
            slug='test-bot-personal',
            description='محصول تست',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس یک‌ماهه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        License.objects.create(
            order=order,
            plan=self.plan,
            license_key='PERS-1234-5678-9ABC',
            status='active',
            max_activations=1,
        )
        self.agency = CRMAgency.objects.create(
            name='آژانس تست',
            slug='test-agency-personal',
            owner=self.user,
        )
        CRMAgencyMember.objects.create(agency=self.agency, user=self.user, role='owner')
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست',
            original_filename='test.xlsx',
            file_format='xlsx',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='divar-token-001',
            title='آپارتمان تست',
            area=85,
            city='تهران',
            neighborhood='ونک',
        )

    def test_property_from_listing_sets_agency(self):
        from workspace.services.crm import add_listing_to_personal_files
        from workspace.services.crm_scope import property_for_user, properties_qs

        prop, created = add_listing_to_personal_files(self.user, self.listing)
        self.assertTrue(created)
        self.assertEqual(prop.agency_id, self.agency.pk)
        self.assertIsNotNone(property_for_user(self.user, prop.pk))
        self.assertIn(prop.pk, list(properties_qs(self.user).values_list('pk', flat=True)))

    def test_legacy_null_agency_property_still_visible(self):
        from workspace.services.crm_scope import property_for_user, properties_qs

        prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک قدیمی',
            property_type='آپارتمان',
            deal_mode='فروش',
        )
        self.assertIsNone(prop.agency_id)
        self.assertIsNotNone(property_for_user(self.user, prop.pk))
        self.assertIn(prop.pk, list(properties_qs(self.user).values_list('pk', flat=True)))

    def test_add_personal_redirects_to_property_detail(self):
        self.client.login(username='agentuser', password='pass1234')
        url = reverse(
            'workspace:listing_add_personal',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.post(url, {'redirect': 'property'})
        self.assertEqual(resp.status_code, 302)
        follow = self.client.get(resp.url)
        self.assertEqual(follow.status_code, 200)

    def test_property_image_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        prop = CRMProperty.objects.create(
            user=self.user,
            agency=self.agency,
            title='ملک تست تصویر',
            property_type='آپارتمان',
            deal_mode='فروش',
        )
        url = reverse('workspace:crm_property_images', kwargs={'property_id': prop.pk})
        self.client.login(username='agentuser', password='pass1234')
        img = SimpleUploadedFile('photo.jpg', b'jpeg-content', content_type='image/jpeg')
        resp = self.client.post(url, {'image': img})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(len(data['images']), 1)
        prop.refresh_from_db()
        self.assertEqual(len(prop.images), 1)

    def test_property_edit_saves_images_json(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            agency=self.agency,
            title='ملک تست',
            property_type='آپارتمان',
            deal_mode='فروش',
            images=['https://example.com/a.jpg'],
        )
        self.client.login(username='agentuser', password='pass1234')
        edit_url = reverse('workspace:crm_property_edit', kwargs={'property_id': prop.pk})
        payload = {
            'title': prop.title,
            'property_type': prop.property_type,
            'deal_mode': prop.deal_mode,
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'property_images_json': '["https://example.com/b.jpg","https://example.com/c.jpg"]',
        }
        resp = self.client.post(edit_url, payload)
        self.assertEqual(resp.status_code, 302)
        prop.refresh_from_db()
        self.assertEqual(len(prop.images), 2)
        self.assertEqual(prop.images[0], 'https://example.com/b.jpg')
