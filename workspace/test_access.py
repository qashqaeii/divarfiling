"""تست دسترسی لایه‌ای میزکار."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from licenses.models import License
from shop.models import LicensePlan, Order, Product

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
