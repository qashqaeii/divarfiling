"""
فرم‌های افیلیت
"""
from django import forms
from django.conf import settings
from .models import Withdrawal


class WithdrawalForm(forms.ModelForm):
    """فرم درخواست برداشت"""
    
    class Meta:
        model = Withdrawal
        fields = ['amount', 'bank_account', 'bank_name', 'account_holder', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': settings.AFFILIATE_MIN_WITHDRAWAL,
                'step': '1000'
            }),
            'bank_account': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره حساب یا کارت بانکی'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نام بانک'
            }),
            'account_holder': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نام صاحب حساب'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'یادداشت اختیاری'
            }),
        }
        labels = {
            'amount': 'مبلغ برداشت (تومان)',
            'bank_account': 'شماره حساب بانکی',
            'bank_name': 'نام بانک',
            'account_holder': 'صاحب حساب',
            'notes': 'یادداشت',
        }
    
    def __init__(self, *args, **kwargs):
        self.wallet = kwargs.pop('wallet', None)
        super().__init__(*args, **kwargs)
        
        if self.wallet:
            self.fields['amount'].widget.attrs['max'] = float(self.wallet.balance)
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and self.wallet:
            if amount < settings.AFFILIATE_MIN_WITHDRAWAL:
                raise forms.ValidationError(
                    f'حداقل مبلغ برداشت {settings.AFFILIATE_MIN_WITHDRAWAL:,} تومان است.'
                )
            if amount > self.wallet.balance:
                raise forms.ValidationError(
                    f'موجودی کیف پول شما کافی نیست. موجودی: {self.wallet.balance:,} تومان'
                )
        return amount

