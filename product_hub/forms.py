"""فرم‌های مرکز توسعه محصول."""
from django import forms

from product_hub.models import (
    BUG_SEVERITY_CHOICES,
    BUG_STATUS_CHOICES,
    REQUEST_STATUS_CHOICES,
    BugReport,
    FeatureRequest,
    ProductFeature,
    ProductRelease,
    ReleaseChange,
)


class FeatureRequestForm(forms.ModelForm):
    class Meta:
        model = FeatureRequest
        fields = ('title', 'category', 'problem', 'why_important', 'priority')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'ws-input', 'placeholder': 'عنوان پیشنهاد…',
            }),
            'category': forms.Select(attrs={'class': 'ws-select'}),
            'problem': forms.Textarea(attrs={
                'class': 'ws-input', 'rows': 4,
                'placeholder': 'این قابلیت چه مشکلی را حل می‌کند؟',
            }),
            'why_important': forms.Textarea(attrs={
                'class': 'ws-input', 'rows': 3,
                'placeholder': 'چرا برای شما مهم است؟',
            }),
            'priority': forms.Select(attrs={'class': 'ws-select'}),
        }
        labels = {
            'title': 'عنوان پیشنهاد',
            'category': 'دسته‌بندی',
            'problem': 'این قابلیت چه مشکلی را حل می‌کند؟',
            'why_important': 'چرا برای شما مهم است؟',
            'priority': 'اولویت',
        }


class BugReportForm(forms.ModelForm):
    class Meta:
        model = BugReport
        fields = ('title', 'description', 'severity')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'ws-input', 'placeholder': 'عنوان مشکل…',
            }),
            'description': forms.Textarea(attrs={
                'class': 'ws-input', 'rows': 5,
                'placeholder': 'توضیح کامل مشکل، مراحل بازتولید، و نتیجه مورد انتظار…',
            }),
            'severity': forms.Select(attrs={'class': 'ws-select'}),
        }
        labels = {
            'title': 'عنوان مشکل',
            'description': 'توضیح',
            'severity': 'شدت',
        }


class FeatureRequestStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=REQUEST_STATUS_CHOICES,
        label='وضعیت جدید',
        widget=forms.Select(attrs={'class': 'ws-select'}),
    )
    note = forms.CharField(
        required=False,
        label='توضیحات',
        widget=forms.Textarea(attrs={'class': 'ws-input', 'rows': 3}),
    )
    released_in = forms.ModelChoiceField(
        queryset=ProductRelease.objects.filter(is_published=True),
        required=False,
        label='نسخه مربوطه',
        widget=forms.Select(attrs={'class': 'ws-select'}),
        empty_label='— انتخاب نسخه —',
    )
    release_note = forms.CharField(
        required=False,
        label='توضیح انتشار',
        widget=forms.Textarea(attrs={
            'class': 'ws-input', 'rows': 3,
            'placeholder': 'این قابلیت در نسخه … اضافه شد.',
        }),
    )
    linked_feature = forms.ModelChoiceField(
        queryset=ProductFeature.objects.filter(is_published=True),
        required=False,
        label='قابلیت مرتبط',
        widget=forms.Select(attrs={'class': 'ws-select'}),
        empty_label='— بدون ارتباط —',
    )


class BugReportStatusForm(forms.Form):
    status = forms.ChoiceField(
        choices=BUG_STATUS_CHOICES,
        label='وضعیت جدید',
        widget=forms.Select(attrs={'class': 'ws-select'}),
    )
    note = forms.CharField(
        required=False,
        label='توضیحات مدیر',
        widget=forms.Textarea(attrs={'class': 'ws-input', 'rows': 2}),
    )
    resolution_note = forms.CharField(
        required=False,
        label='توضیح رفع مشکل',
        widget=forms.Textarea(attrs={'class': 'ws-input', 'rows': 3}),
    )


class ProductReleaseForm(forms.ModelForm):
    class Meta:
        model = ProductRelease
        fields = ('version', 'title', 'summary', 'released_at', 'is_published')
        widgets = {
            'version': forms.TextInput(attrs={'class': 'ws-input', 'placeholder': 'مثلاً 2.9.0', 'dir': 'ltr'}),
            'title': forms.TextInput(attrs={'class': 'ws-input'}),
            'summary': forms.Textarea(attrs={'class': 'ws-input', 'rows': 3}),
            'released_at': forms.DateTimeInput(
                attrs={'class': 'ws-input', 'type': 'datetime-local', 'dir': 'ltr'},
                format='%Y-%m-%dT%H:%M',
            ),
            'is_published': forms.CheckboxInput(attrs={'class': 'ws-checkbox'}),
        }
        labels = {
            'version': 'شماره نسخه',
            'title': 'عنوان بروزرسانی',
            'summary': 'خلاصه',
            'released_at': 'تاریخ و ساعت انتشار',
            'is_published': 'منتشر شود',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['released_at'].input_formats = [
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
        ]


class ReleaseChangeForm(forms.ModelForm):
    class Meta:
        model = ReleaseChange
        fields = ('change_type', 'platform', 'text', 'sort_order')
        widgets = {
            'change_type': forms.Select(attrs={'class': 'ws-select'}),
            'platform': forms.Select(attrs={'class': 'ws-select'}),
            'text': forms.TextInput(attrs={'class': 'ws-input'}),
            'sort_order': forms.NumberInput(attrs={'class': 'ws-input', 'dir': 'ltr'}),
        }


ReleaseChangeFormSet = forms.inlineformset_factory(
    ProductRelease,
    ReleaseChange,
    form=ReleaseChangeForm,
    extra=3,
    can_delete=True,
)


class ProductFeatureForm(forms.ModelForm):
    class Meta:
        model = ProductFeature
        fields = (
            'title', 'slug', 'summary', 'category', 'status',
            'added_at', 'last_changed_at', 'sort_order', 'is_published',
        )
        widgets = {
            'title': forms.TextInput(attrs={'class': 'ws-input'}),
            'slug': forms.TextInput(attrs={'class': 'ws-input', 'dir': 'ltr'}),
            'summary': forms.Textarea(attrs={'class': 'ws-input', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'ws-select'}),
            'status': forms.Select(attrs={'class': 'ws-select'}),
            'added_at': forms.DateInput(attrs={'class': 'ws-input', 'type': 'date', 'dir': 'ltr'}),
            'last_changed_at': forms.DateInput(attrs={'class': 'ws-input', 'type': 'date', 'dir': 'ltr'}),
            'sort_order': forms.NumberInput(attrs={'class': 'ws-input', 'dir': 'ltr'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'ws-checkbox'}),
        }
