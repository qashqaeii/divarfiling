"""تست dedupe سفارش‌های معلق."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.services.pending_orders import get_pending_orders_for_display, pending_orders_queryset
from licenses.models import LicensePlan
from shop.models import Order, Product

User = get_user_model()


class PendingOrdersDedupeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dupuser', password='pass1234', phone='09128888888',
        )
        self.other = User.objects.create_user(
            username='otheruser', password='pass1234', phone='09129999999',
        )
        product = Product.objects.create(
            title='تست', slug='dedupe-test', description='x', is_active=True,
        )
        plan = LicensePlan.objects.create(
            product=product, name='ماهانه', plan_type='monthly',
            price=100000, duration_days=30, is_active=True,
        )
        for _ in range(4):
            Order.objects.create(
                user=self.user,
                product=product,
                plan=plan,
                amount=plan.price,
                status='pending',
            )
        Order.objects.create(
            user=self.other,
            product=product,
            plan=plan,
            amount=plan.price,
            status='pending_verification',
        )

    def test_dedupe_shows_one_row_per_user(self):
        rows = list(get_pending_orders_for_display(limit=20))
        user_ids = [o.user_id for o in rows]
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(set(user_ids)), 2)
        self.assertEqual(user_ids.count(self.user.id), 1)

    def test_all_pending_without_dedupe(self):
        self.assertEqual(pending_orders_queryset(dedupe_by_user=False).count(), 5)

    def test_dedupe_keeps_newest_order(self):
        newest = (
            pending_orders_queryset(dedupe_by_user=True)
            .filter(user=self.user)
            .get()
        )
        latest = (
            Order.objects.filter(user=self.user, status__in=('pending', 'pending_verification'))
            .order_by('-created_at')
            .first()
        )
        self.assertEqual(newest.id, latest.id)
