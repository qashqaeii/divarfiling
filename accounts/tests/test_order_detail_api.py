from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from shop.models import LicensePlan, Order, Product

User = get_user_model()


class OrderDetailApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='orderuser',
            phone='09125555555',
            password='ComplexPass123!',
        )
        self.other = User.objects.create_user(
            username='otheruser',
            phone='09126666666',
            password='ComplexPass123!',
        )
        self.client.login(username='09125555555', password='ComplexPass123!')
        self.product = Product.objects.create(
            title='ربات استخراج دیوار',
            slug='bot-test',
            description='تست',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='لایسنس یک‌ماهه',
            plan_type='monthly',
            duration_days=30,
            max_activations=2,
            price=891000,
            is_active=True,
        )
        self.order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=891000,
            status='pending',
        )

    def test_order_detail_returns_json_for_owner(self):
        url = reverse('dashboard_order_detail', kwargs={'order_id': self.order.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['order']['id'], str(self.order.id))
        self.assertEqual(data['order']['product_title'], self.product.title)
        self.assertTrue(any(a.get('url') for a in data['order']['actions']))

    def test_order_detail_forbidden_for_other_user(self):
        other_order = Order.objects.create(
            user=self.other,
            product=self.product,
            plan=self.plan,
            amount=891000,
            status='pending',
        )
        url = reverse('dashboard_order_detail', kwargs={'order_id': other_order.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_orders_tab_renders_detail_triggers(self):
        resp = self.client.get(reverse('dashboard_tab', kwargs={'tab': 'orders'}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-order-detail="' + str(self.order.id) + '"')
        self.assertContains(resp, 'mkOrderDetailModal')
