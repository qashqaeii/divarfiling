"""
دستور مدیریتی برای ایجاد یک خرید فیک و تایید آن
"""
import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from shop.models import Product, LicensePlan, Order, Transaction
from licenses.models import License
from licenses.utils import generate_license_key

User = get_user_model()


class Command(BaseCommand):
    help = 'ایجاد یک خرید فیک و تایید آن برای کاربر ادمین'

    def add_arguments(self, parser):
        parser.add_argument(
            '--plan-id',
            type=int,
            help='شناسه پلن (اگر مشخص نشود، اولین پلن فعال استفاده می‌شود)',
        )
        parser.add_argument(
            '--product-slug',
            type=str,
            default='professional',
            help='نامک محصول (پیش‌فرض: professional)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('شروع ایجاد خرید فیک...\n'))
        
        # پیدا کردن یا ایجاد کاربر
        username = 'qashqaeii'
        email = 'qashqaeii.ps4@gmail.com'
        
        try:
            user = User.objects.get(username=username)
            self.stdout.write(self.style.SUCCESS(f'کاربر "{username}" پیدا شد.'))
        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING(f'کاربر "{username}" یافت نشد. در حال ایجاد...'))
            user = User.objects.create_user(
                username=username,
                email=email,
                password='temp_password_123',  # رمز موقت
                is_staff=True,
                is_superuser=True
            )
            self.stdout.write(self.style.SUCCESS(f'کاربر "{username}" ایجاد شد.'))
        
        # پیدا کردن محصول
        product_slug = options.get('product_slug', 'professional')
        try:
            product = Product.objects.get(slug=product_slug, is_active=True)
            self.stdout.write(self.style.SUCCESS(f'محصول "{product.title}" پیدا شد.'))
        except Product.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'محصول با نامک "{product_slug}" یافت نشد.'))
            self.stdout.write(self.style.WARNING('لطفاً ابتدا دستور import_product را اجرا کنید.'))
            return
        
        # پیدا کردن پلن
        plan_id = options.get('plan_id')
        if plan_id:
            try:
                plan = LicensePlan.objects.get(id=plan_id, product=product, is_active=True)
            except LicensePlan.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'پلن با شناسه {plan_id} یافت نشد.'))
                return
        else:
            plan = LicensePlan.objects.filter(product=product, is_active=True).first()
            if not plan:
                self.stdout.write(self.style.ERROR('هیچ پلن فعالی برای این محصول یافت نشد.'))
                return
        
        self.stdout.write(self.style.SUCCESS(f'پلن "{plan.name}" انتخاب شد.'))
        self.stdout.write(self.style.SUCCESS(f'قیمت: {plan.price:,} تومان\n'))
        
        # پیشوند FAKE- → از BI Production و payment_success حذف می‌شود
        # (is_bi_production_order). این مسیر عمداً fulfill مرکزی را صدا نمی‌زند.
        order = Order.objects.create(
            user=user,
            product=product,
            plan=plan,
            amount=plan.price,
            status='pending',
            zibal_track_id=f'FAKE-{uuid.uuid4().hex[:10].upper()}',
        )
        self.stdout.write(self.style.SUCCESS(f'✅ سفارش ایجاد شد:'))
        self.stdout.write(f'   شناسه سفارش: {order.id}')
        self.stdout.write(f'   کاربر: {user.username}')
        self.stdout.write(f'   محصول: {product.title}')
        self.stdout.write(f'   پلن: {plan.name}')
        self.stdout.write(f'   مبلغ: {order.amount:,} تومان')
        self.stdout.write(f'   وضعیت: {order.status}\n')
        
        # ایجاد تراکنش
        transaction = Transaction.objects.create(
            order=order,
            zibal_track_id=order.zibal_track_id,
            zibal_ref_number=f'REF-{uuid.uuid4().hex[:12].upper()}',
            amount=order.amount,
            status='pending',
        )
        self.stdout.write(self.style.SUCCESS(f'✅ تراکنش ایجاد شد:'))
        self.stdout.write(f'   کد پیگیری: {transaction.zibal_track_id}')
        self.stdout.write(f'   شماره مرجع: {transaction.zibal_ref_number}')
        self.stdout.write(f'   وضعیت: {transaction.status}\n')
        
        # تایید پرداخت - به‌روزرسانی سفارش
        order.status = 'paid'
        order.paid_at = timezone.now()
        order.save()
        self.stdout.write(self.style.SUCCESS('✅ سفارش به وضعیت "پرداخت شده" تغییر یافت.'))
        
        # تایید تراکنش
        transaction.status = 'paid'
        transaction.verified_at = timezone.now()
        transaction.save()
        self.stdout.write(self.style.SUCCESS('✅ تراکنش به وضعیت "پرداخت شده" تغییر یافت.\n'))
        
        # تولید لایسنس
        if not License.objects.filter(order=order).exists():
            license_key = generate_license_key(order)
            license_obj = License.objects.create(
                order=order,
                license_key=license_key,
                plan=plan,
                status='active',  # به صورت فعال ایجاد می‌شود
                max_activations=plan.max_activations,
            )
            
            # اگر پلن مدت اعتبار دارد، تاریخ انقضا را تنظیم کن
            if plan.duration_days:
                from datetime import timedelta
                license_obj.expires_at = timezone.now() + timedelta(days=plan.duration_days)
                license_obj.save()
            
            self.stdout.write(self.style.SUCCESS('✅ لایسنس تولید شد:'))
            self.stdout.write(f'   کلید لایسنس: {license_key}')
            self.stdout.write(f'   وضعیت: {license_obj.status}')
            self.stdout.write(f'   حداکثر فعال‌سازی: {license_obj.max_activations}')
            if license_obj.expires_at:
                self.stdout.write(f'   تاریخ انقضا: {license_obj.expires_at.strftime("%Y-%m-%d %H:%M:%S")}')
            self.stdout.write('')
        else:
            existing_license = License.objects.get(order=order)
            self.stdout.write(self.style.WARNING(f'⚠️  لایسنس از قبل وجود داشت:'))
            self.stdout.write(f'   کلید لایسنس: {existing_license.license_key}')
        
        # خلاصه نهایی
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('✅ خرید فیک با موفقیت ایجاد و تایید شد!'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'\n📋 خلاصه:')
        self.stdout.write(f'   کاربر: {user.username} ({user.email})')
        self.stdout.write(f'   شناسه سفارش: {order.id}')
        self.stdout.write(f'   محصول: {product.title}')
        self.stdout.write(f'   پلن: {plan.name}')
        self.stdout.write(f'   مبلغ: {order.amount:,} تومان')
        self.stdout.write(f'   تاریخ پرداخت: {order.paid_at.strftime("%Y-%m-%d %H:%M:%S")}')
        
        if License.objects.filter(order=order).exists():
            license_obj = License.objects.get(order=order)
            self.stdout.write(f'   کلید لایسنس: {license_obj.license_key}')
        
        self.stdout.write('')

