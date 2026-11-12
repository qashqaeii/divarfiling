"""دادهٔ نمونه برای تأیید پنل مدیریت در محیط توسعه."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import LicensePlan, Order, Product
from workspace.models import Ticket, TicketMessage

User = get_user_model()

STAFF_USERNAME = 'admin_panel_demo'
STAFF_PASSWORD = 'AdminPanelDemo!2026'
STAFF_PHONE = '09129990001'


class Command(BaseCommand):
    help = 'ایجاد کاربر staff و دادهٔ نمونه (فروش امروز، fulfillment ناقص، تیکت خوانده‌نشده)'

    def handle(self, *args, **options):
        today = timezone.localdate()
        now = timezone.now()

        staff, created = User.objects.get_or_create(
            username=STAFF_USERNAME,
            defaults={
                'phone': STAFF_PHONE,
                'email': 'admin-panel-demo@local.test',
                'is_staff': True,
                'is_active': True,
            },
        )
        if created or not staff.check_password(STAFF_PASSWORD):
            staff.set_password(STAFF_PASSWORD)
            staff.is_staff = True
            staff.is_active = True
            staff.save()

        buyer, _ = User.objects.get_or_create(
            username='demo_buyer_panel',
            defaults={'phone': '09129990002', 'is_active': True},
        )
        product, _ = Product.objects.get_or_create(
            slug='admin-demo-product',
            defaults={'title': 'محصول دمو پنل', 'is_active': True},
        )
        plan, _ = LicensePlan.objects.get_or_create(
            product=product,
            plan_type='monthly',
            defaults={
                'name': 'ماهانه دمو',
                'price': 250000,
                'duration_days': 30,
                'is_active': True,
            },
        )

        paid_at = timezone.make_aware(datetime.combine(today, time(10, 30)))
        Order.objects.filter(fulfillment_error__startswith='دمو: پنل').delete()
        Order.objects.create(
            user=buyer,
            product=product,
            plan=plan,
            status='paid',
            fulfillment_status=Order.FulfillmentStatus.COMPLETE,
            amount=Decimal('250000'),
            paid_at=paid_at,
        )
        Order.objects.create(
            user=buyer,
            product=product,
            plan=plan,
            status='paid',
            fulfillment_status=Order.FulfillmentStatus.PENDING,
            amount=Decimal('250000'),
            paid_at=paid_at,
            fulfillment_error='دمو: پنل — صف صدور ناقص',
        )

        ticket_user, _ = User.objects.get_or_create(
            username='demo_ticket_user',
            defaults={'phone': '09129990003', 'is_active': True},
        )
        ticket, t_created = Ticket.objects.get_or_create(
            subject='تیکت دمو پنل — نیاز به پاسخ',
            user=ticket_user,
            defaults={
                'status': 'open',
                'staff_has_unread': True,
                'last_message_at': now - timedelta(hours=14),
            },
        )
        if t_created:
            TicketMessage.objects.create(
                ticket=ticket,
                author=ticket_user,
                body='سلام، این یک تیکت آزمایشی برای پنل مدیریت است.',
                is_staff_reply=False,
            )

        self.stdout.write(self.style.SUCCESS('دادهٔ دمو آماده است.'))
        self.stdout.write(f'  staff: {STAFF_USERNAME} / {STAFF_PASSWORD}')
        self.stdout.write(f'  URL: /accounts/admin-panel/ (پس از login)')
