"""
مدل‌های همکاری در فروش
"""
import secrets
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from shop.models import Order

User = get_user_model()


class Affiliate(models.Model):
    """مشاور/افیلیت"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate', verbose_name='کاربر')
    code = models.CharField(max_length=20, unique=True, db_index=True, verbose_name='کد معرف')
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=settings.AFFILIATE_DEFAULT_COMMISSION,
        verbose_name='درصد کمیسیون'
    )
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=settings.AFFILIATE_DEFAULT_DISCOUNT,
        verbose_name='درصد تخفیف برای کاربران دعوت‌شده'
    )
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    bank_account = models.CharField(max_length=50, blank=True, verbose_name='شماره حساب بانکی')
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='نام بانک')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    
    class Meta:
        verbose_name = 'مشاور فروش'
        verbose_name_plural = 'مشاوران فروش'
    
    def __str__(self):
        return f'{self.user.username} - {self.code}'
    
    def save(self, *args, **kwargs):
        if not self.code:
            # تولید کد یکتا
            while True:
                code = secrets.token_urlsafe(8)[:12].upper()
                if not Affiliate.objects.filter(code=code).exists():
                    self.code = code
                    break
        super().save(*args, **kwargs)


class AffiliateSale(models.Model):
    """فروش افیلیت"""
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('paid', 'پرداخت شده'),
        ('cancelled', 'لغو شده'),
    ]
    
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='sales', verbose_name='مشاور')
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='affiliate_sale', verbose_name='سفارش')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='درصد کمیسیون')
    commission_amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='مبلغ کمیسیون (تومان)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ پرداخت')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    
    class Meta:
        verbose_name = 'فروش افیلیت'
        verbose_name_plural = 'فروش‌های افیلیت'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.affiliate.code} - {self.commission_amount} تومان'


class AffiliatePayout(models.Model):
    """تسویه حساب افیلیت"""
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('processing', 'در حال پردازش'),
        ('paid', 'پرداخت شده'),
        ('failed', 'ناموفق'),
    ]
    
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='payouts', verbose_name='مشاور')
    amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='مبلغ (تومان)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    sales = models.ManyToManyField(AffiliateSale, verbose_name='فروش‌ها')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ پرداخت')
    
    class Meta:
        verbose_name = 'تسویه حساب'
        verbose_name_plural = 'تسویه حساب‌ها'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.affiliate.code} - {self.amount} تومان'


class Wallet(models.Model):
    """کیف پول کاربر"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet', verbose_name='کاربر')
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='موجودی (تومان)'
    )
    total_earned = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='کل درآمد (تومان)'
    )
    total_withdrawn = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='کل برداشت شده (تومان)'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    
    class Meta:
        verbose_name = 'کیف پول'
        verbose_name_plural = 'کیف پول‌ها'
    
    def __str__(self):
        return f'کیف پول {self.user.username} - {self.balance} تومان'
    
    def add_balance(self, amount, description='', related_sale=None):
        """افزودن موجودی به کیف پول"""
        from decimal import Decimal
        self.balance += Decimal(amount)
        self.total_earned += Decimal(amount)
        self.save()
        
        # ثبت تراکنش
        transaction = WalletTransaction.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='credit',
            description=description,
            related_sale=related_sale
        )
        return transaction
    
    def deduct_balance(self, amount, description=''):
        """کسر موجودی از کیف پول"""
        from decimal import Decimal
        if self.balance >= Decimal(amount):
            self.balance -= Decimal(amount)
            self.save()
            
            # ثبت تراکنش
            WalletTransaction.objects.create(
                wallet=self,
                amount=amount,
                transaction_type='debit',
                description=description
            )
            return True
        return False


class WalletTransaction(models.Model):
    """تراکنش‌های کیف پول"""
    TRANSACTION_TYPES = [
        ('credit', 'واریز'),
        ('debit', 'برداشت'),
    ]
    
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions', verbose_name='کیف پول')
    amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='مبلغ (تومان)')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name='نوع تراکنش')
    description = models.CharField(max_length=200, blank=True, verbose_name='توضیحات')
    related_sale = models.ForeignKey(
        AffiliateSale,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions',
        verbose_name='فروش مرتبط'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    
    class Meta:
        verbose_name = 'تراکنش کیف پول'
        verbose_name_plural = 'تراکنش‌های کیف پول'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.wallet.user.username} - {self.amount} تومان - {self.get_transaction_type_display()}'


class Withdrawal(models.Model):
    """درخواست برداشت از کیف پول"""
    STATUS_CHOICES = [
        ('pending', 'در انتظار بررسی'),
        ('approved', 'تایید شده'),
        ('processing', 'در حال پردازش'),
        ('completed', 'پرداخت شده'),
        ('rejected', 'رد شده'),
    ]
    
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='withdrawals', verbose_name='کیف پول')
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(10000)],  # حداقل 10 هزار تومان
        verbose_name='مبلغ (تومان)'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    bank_account = models.CharField(max_length=50, verbose_name='شماره حساب بانکی')
    bank_name = models.CharField(max_length=100, verbose_name='نام بانک')
    account_holder = models.CharField(max_length=100, verbose_name='صاحب حساب')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    admin_notes = models.TextField(blank=True, verbose_name='یادداشت ادمین')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ درخواست')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ پردازش')
    
    class Meta:
        verbose_name = 'درخواست برداشت'
        verbose_name_plural = 'درخواست‌های برداشت'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'برداشت {self.wallet.user.username} - {self.amount} تومان - {self.get_status_display()}'
    
    def approve(self):
        """تایید درخواست برداشت"""
        if self.status == 'pending' and self.wallet.balance >= self.amount:
            self.status = 'approved'
            self.wallet.deduct_balance(self.amount, f'برداشت - {self.id}')
            self.save()
            return True
        return False
    
    def complete(self):
        """تکمیل پرداخت برداشت"""
        if self.status in ['approved', 'processing']:
            self.status = 'completed'
            self.processed_at = timezone.now()
            self.wallet.total_withdrawn += self.amount
            self.wallet.save()
            self.save()
            return True
        return False
    
    def reject(self, reason=''):
        """رد درخواست برداشت"""
        if self.status == 'pending':
            self.status = 'rejected'
            self.admin_notes = reason
            self.save()
            return True
        return False

