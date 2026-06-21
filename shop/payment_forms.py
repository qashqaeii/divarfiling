"""فرم‌های پرداخت کارت به کارت."""
from django import forms

from workspace.services.jalali_input import (
    format_jalali_datetime,
    parse_jalali_datetime_string,
)

from .models import CardTransferSubmission


class CardTransferForm(forms.ModelForm):
    transferred_at = forms.CharField(
        required=False,
        label='زمان واریز',
        widget=forms.TextInput(attrs={
            'class': 'ck-input ctp-jalali-datetime',
            'data-jdp': '',
            'placeholder': '۱۴۰۴/۰۳/۲۵ ۱۴:۳۰',
            'autocomplete': 'off',
            'dir': 'ltr',
            'inputmode': 'numeric',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.transferred_at:
            self.fields['transferred_at'].initial = format_jalali_datetime(
                self.instance.transferred_at
            )

    def clean_transferred_at(self):
        raw = self.cleaned_data.get('transferred_at')
        if not raw:
            return None
        if hasattr(raw, 'hour'):
            return raw
        parsed = parse_jalali_datetime_string(str(raw))
        if parsed is None:
            raise forms.ValidationError(
                'تاریخ و ساعت شمسی نامعتبر است. مثال: ۱۴۰۴/۰۳/۲۵ ۱۴:۳۰'
            )
        return parsed

    class Meta:
        model = CardTransferSubmission
        fields = ['reference_number', 'payer_name', 'transferred_at', 'receipt_image', 'user_note']
        widgets = {
            'reference_number': forms.TextInput(attrs={
                'class': 'ck-input',
                'placeholder': 'شماره پیگیری بانکی یا کد رسید',
                'autocomplete': 'off',
            }),
            'payer_name': forms.TextInput(attrs={
                'class': 'ck-input',
                'placeholder': 'نام واریزکننده (اختیاری)',
            }),
            'receipt_image': forms.FileInput(attrs={
                'class': 'ck-file-input',
                'accept': 'image/*',
            }),
            'user_note': forms.Textarea(attrs={
                'class': 'ck-textarea',
                'rows': 3,
                'placeholder': 'توضیح تکمیلی (اختیاری)',
            }),
        }
        labels = {
            'reference_number': 'شماره پیگیری / رسید',
            'payer_name': 'نام پرداخت‌کننده',
            'transferred_at': 'زمان واریز',
            'receipt_image': 'تصویر رسید',
            'user_note': 'توضیحات',
        }

    def clean_reference_number(self):
        ref = (self.cleaned_data.get('reference_number') or '').strip()
        if len(ref) < 4:
            raise forms.ValidationError('شماره پیگیری باید حداقل ۴ کاراکتر باشد.')
        return ref

    def clean_receipt_image(self):
        image = self.cleaned_data.get('receipt_image')
        if not image:
            return image
        if image.size > 5 * 1024 * 1024:
            raise forms.ValidationError('حجم تصویر نباید بیشتر از ۵ مگابایت باشد.')
        return image
