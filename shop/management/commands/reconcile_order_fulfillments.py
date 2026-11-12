"""بازیابی تکمیل سفارش پس از پرداخت — کرون پیشنهادی هر ۵–۱۵ دقیقه."""
from django.core.management.base import BaseCommand

from shop.models import Order
from shop.services.order_fulfillment_recovery import (
    reconcile_gateway_payment_mismatch,
    reconcile_order_fulfillment,
    run_fulfillment_reconcile_batch,
)


class Command(BaseCommand):
    help = 'همگام‌سازی paid درگاه با سفارش و تلاش مجدد تمدید/صدور لایسنس ناقص'

    def add_arguments(self, parser):
        parser.add_argument(
            '--order-id',
            type=str,
            default='',
            help='فقط یک سفارش UUID',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='حداکثر سفارش در هر اجرا',
        )
        parser.add_argument(
            '--gateway-only',
            action='store_true',
            help='فقط ناهمگامی تراکنش paid / سفارش غیرpaid',
        )

    def handle(self, *args, **options):
        order_id = (options.get('order_id') or '').strip()
        limit = max(1, int(options.get('limit') or 100))

        if order_id:
            try:
                order = Order.objects.get(pk=order_id)
            except Order.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Order not found: {order_id}'))
                return
            reconcile_order_fulfillment(order)
            order.refresh_from_db(fields=['status', 'fulfillment_status', 'fulfillment_error'])
            self.stdout.write(
                f'order {order_id} status={order.status} fulfillment={order.fulfillment_status}'
            )
            return

        if options.get('gateway_only'):
            n = reconcile_gateway_payment_mismatch(limit=min(limit, 50))
            self.stdout.write(self.style.SUCCESS(f'gateway mismatch fixed: {n}'))
            return

        stats = run_fulfillment_reconcile_batch(limit=limit)
        self.stdout.write(self.style.SUCCESS(str(stats)))
