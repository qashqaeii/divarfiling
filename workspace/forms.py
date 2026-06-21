"""فرم‌های workspace."""
from django import forms

from workspace.constants import ACTIVITY_TYPES, DEAL_TYPES, INTEREST_LEVELS, LISTING_ROLES
from workspace.constants import (
    AUTOMATION_ACTIONS, AUTOMATION_TRIGGERS, DEAL_STAGES, LOST_REASONS, MESSAGE_CHANNELS,
    MESSAGE_TEMPLATE_CATEGORIES, REMINDER_RECURRENCE, VISIT_OUTCOMES, VISIT_REJECT_REASONS,
)
from workspace.services.jalali_input import (
    format_jalali_date,
    format_jalali_datetime,
    parse_jalali_date_string,
    parse_jalali_datetime_string,
)
from workspace.models import (
    CRMAutomationRule, CRMDeal, CRMMessageTemplate, CRMProperty, Customer, CustomerDocument,
    Dataset, Listing, ListingMeta, PropertyContact, PropertyVisit, Reminder, WorkspaceSettings,
)

_CRM_MONEY_WIDGET_ATTRS = {
    'class': 'crm-input crm-input-money',
    'data-money': '1',
    'inputmode': 'numeric',
    'autocomplete': 'off',
    'placeholder': 'مثال: 25,000,000',
}


def format_money_input(value) -> str:
    if value in (None, ''):
        return ''
    return f'{int(value):,}'


def parse_money_input(value):
    if value in (None, ''):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
    s = s.replace(',', '').replace('،', '').replace(' ', '')
    if not s:
        return None
    try:
        return int(s)
    except ValueError as exc:
        raise forms.ValidationError('مبلغ نامعتبر است.') from exc


class CRMMoneyFieldsMixin:
    money_fields: tuple = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            return
        for fname in self.money_fields:
            val = getattr(self.instance, fname, None)
            if val is not None:
                self.initial[fname] = format_money_input(val)

    def clean(self):
        cleaned_data = super().clean()
        for fname in self.money_fields:
            if fname in cleaned_data:
                cleaned_data[fname] = parse_money_input(cleaned_data.get(fname))
        return cleaned_data


class DatasetUploadForm(forms.Form):
    file = forms.FileField(
        label='فایل داده',
        help_text='فرمت‌های مجاز: Excel (.xlsx), CSV, JSON',
        widget=forms.ClearableFileInput(attrs={'accept': '.xlsx,.xls,.csv,.json', 'class': 'ws-file-input'}),
    )
    name = forms.CharField(
        label='نام مجموعه‌داده',
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'ws-input', 'placeholder': 'نام دلخواه (اختیاری)'}),
    )


class DatasetRenameForm(forms.ModelForm):
    class Meta:
        model = Dataset
        fields = ['name']
        widgets = {'name': forms.TextInput(attrs={'class': 'ws-input'})}


class ListingMetaForm(forms.ModelForm):
    class Meta:
        model = ListingMeta
        fields = ['tag', 'note', 'is_favorite']
        widgets = {
            'tag': forms.Select(attrs={'class': 'ws-select'}),
            'note': forms.Textarea(attrs={'class': 'ws-textarea', 'rows': 3}),
            'is_favorite': forms.CheckboxInput(attrs={'class': 'ws-checkbox'}),
        }


class ListingEditForm(forms.ModelForm):
    class Meta:
        model = Listing
        fields = [
            'title', 'price', 'deposit', 'rent', 'area', 'rooms',
            'neighborhood', 'business_type', 'description', 'link',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'ws-input'}),
            'price': forms.NumberInput(attrs={'class': 'ws-input', 'placeholder': 'تومان'}),
            'deposit': forms.NumberInput(attrs={'class': 'ws-input', 'placeholder': 'تومان'}),
            'rent': forms.NumberInput(attrs={'class': 'ws-input', 'placeholder': 'تومان'}),
            'area': forms.NumberInput(attrs={'class': 'ws-input', 'step': '0.1'}),
            'rooms': forms.TextInput(attrs={'class': 'ws-input'}),
            'neighborhood': forms.TextInput(attrs={'class': 'ws-input'}),
            'business_type': forms.Select(
                choices=[
                    ('', '—'),
                    ('شخصی', 'شخصی'),
                    ('مشاور', 'مشاور املاک'),
                    ('business', 'Business'),
                ],
                attrs={'class': 'ws-select'},
            ),
            'description': forms.Textarea(attrs={'class': 'ws-textarea', 'rows': 3}),
            'link': forms.URLInput(attrs={'class': 'ws-input', 'dir': 'ltr'}),
        }


class CustomerForm(CRMMoneyFieldsMixin, forms.ModelForm):
    money_fields = (
        'budget_min', 'budget_max', 'deposit_min', 'deposit_max', 'rent_min', 'rent_max',
    )

    next_follow_up = forms.CharField(
        label='پیگیری بعدی',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'crm-input crm-jalali-date',
            'data-jdp': '',
            'data-jdp-only-date': '',
            'placeholder': '۱۴۰۴/۰۶/۱۵',
            'autocomplete': 'off',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.next_follow_up and not self.is_bound:
            jalali = format_jalali_date(self.instance.next_follow_up)
            self.initial['next_follow_up'] = jalali

    def clean_next_follow_up(self):
        raw = self.cleaned_data.get('next_follow_up')
        if not raw:
            return None
        if hasattr(raw, 'year'):
            return raw
        parsed = parse_jalali_date_string(str(raw))
        if parsed is None:
            raise forms.ValidationError('تاریخ شمسی نامعتبر است. مثال: ۱۴۰۴/۰۶/۱۵')
        return parsed

    class Meta:
        model = Customer
        fields = [
            'name', 'phone', 'phone_alt', 'email', 'city', 'district', 'job',
            'is_legal_entity', 'company_name', 'national_id',
            'customer_type', 'status', 'priority', 'property_type', 'source',
            'budget_min', 'budget_max', 'deposit_min', 'deposit_max',
            'rent_min', 'rent_max', 'min_area', 'max_area', 'rooms', 'areas',
            'tags', 'notes', 'next_follow_up',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'crm-input',
                'placeholder': 'نام و نام خانوادگی',
                'required': 'required',
                'aria-required': 'true',
            }),
            'phone': forms.TextInput(attrs={'class': 'crm-input', 'placeholder': '۰۹۱۲...'}),
            'phone_alt': forms.TextInput(attrs={'class': 'crm-input', 'placeholder': 'اختیاری'}),
            'email': forms.EmailInput(attrs={'class': 'crm-input'}),
            'city': forms.TextInput(attrs={'class': 'crm-input'}),
            'district': forms.TextInput(attrs={'class': 'crm-input'}),
            'job': forms.TextInput(attrs={'class': 'crm-input'}),
            'company_name': forms.TextInput(attrs={'class': 'crm-input'}),
            'national_id': forms.TextInput(attrs={'class': 'crm-input'}),
            'customer_type': forms.Select(attrs={'class': 'crm-select', 'data-crm-type': '1'}),
            'status': forms.Select(attrs={'class': 'crm-select'}),
            'priority': forms.Select(attrs={'class': 'crm-select'}),
            'property_type': forms.Select(attrs={'class': 'crm-select'}),
            'source': forms.Select(attrs={'class': 'crm-select'}),
            'budget_min': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'budget_max': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'deposit_min': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'deposit_max': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'rent_min': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'rent_max': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'min_area': forms.NumberInput(attrs={'class': 'crm-input'}),
            'max_area': forms.NumberInput(attrs={'class': 'crm-input'}),
            'rooms': forms.TextInput(attrs={'class': 'crm-input'}),
            'areas': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
            'tags': forms.TextInput(attrs={'class': 'crm-input', 'placeholder': 'با کاما جدا کنید'}),
            'notes': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 3}),
            'is_legal_entity': forms.CheckboxInput(attrs={'class': 'crm-checkbox'}),
        }


class QuickLeadForm(forms.ModelForm):
    """ثبت سریع سرنخ — نام، تلفن، منبع."""

    class Meta:
        model = Customer
        fields = ['name', 'phone', 'source']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'crm-input crm-input-lg',
                'placeholder': 'نام و نام خانوادگی',
                'autocomplete': 'name',
                'required': 'required',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'crm-input crm-input-lg',
                'placeholder': '۰۹۱۲۳۴۵۶۷۸۹',
                'dir': 'ltr',
                'inputmode': 'tel',
                'autocomplete': 'tel',
            }),
            'source': forms.Select(attrs={'class': 'crm-select'}),
        }

    def save(self, commit=True, *, user=None):
        instance = super().save(commit=False)
        if user:
            instance.user = user
            from workspace.services.crm_scope import get_agency
            instance.agency = get_agency(user)
        instance.customer_type = 'سرنخ'
        instance.status = 'جدید'
        instance.priority = 'متوسط'
        if commit:
            instance.save()
        return instance


class CRMPropertyForm(CRMMoneyFieldsMixin, forms.ModelForm):
    money_fields = ('sale_price', 'deposit', 'monthly_rent')

    class Meta:
        model = CRMProperty
        fields = [
            'title', 'property_type', 'deal_mode', 'transaction_status', 'publish_status',
            'address', 'city', 'district', 'neighborhood',
            'latitude', 'longitude', 'area', 'rooms', 'floor', 'total_floors',
            'has_parking', 'has_storage', 'has_elevator', 'build_year',
            'sale_price', 'deposit', 'monthly_rent', 'amenities', 'notes', 'link',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'crm-input'}),
            'property_type': forms.Select(attrs={'class': 'crm-select'}),
            'deal_mode': forms.Select(attrs={'class': 'crm-select', 'data-deal-mode': '1'}),
            'transaction_status': forms.Select(attrs={'class': 'crm-select'}),
            'publish_status': forms.Select(attrs={'class': 'crm-select'}),
            'address': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'crm-input'}),
            'district': forms.TextInput(attrs={'class': 'crm-input'}),
            'neighborhood': forms.TextInput(attrs={'class': 'crm-input'}),
            'latitude': forms.NumberInput(attrs={'class': 'crm-input', 'step': 'any'}),
            'longitude': forms.NumberInput(attrs={'class': 'crm-input', 'step': 'any'}),
            'area': forms.NumberInput(attrs={'class': 'crm-input', 'step': '0.1'}),
            'rooms': forms.TextInput(attrs={'class': 'crm-input'}),
            'floor': forms.NumberInput(attrs={'class': 'crm-input'}),
            'total_floors': forms.NumberInput(attrs={'class': 'crm-input'}),
            'build_year': forms.NumberInput(attrs={'class': 'crm-input'}),
            'sale_price': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'deposit': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'monthly_rent': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'amenities': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
            'link': forms.URLInput(attrs={'class': 'crm-input'}),
            'has_parking': forms.CheckboxInput(attrs={'class': 'crm-checkbox'}),
            'has_storage': forms.CheckboxInput(attrs={'class': 'crm-checkbox'}),
            'has_elevator': forms.CheckboxInput(attrs={'class': 'crm-checkbox'}),
        }


class ActivityForm(forms.Form):
    activity_type = forms.ChoiceField(
        label='نوع فعالیت',
        choices=[(a, a) for a in ACTIVITY_TYPES],
        widget=forms.Select(attrs={'class': 'ws-select'}),
    )
    title = forms.CharField(
        label='عنوان', required=False,
        widget=forms.TextInput(attrs={'class': 'ws-input'}),
    )
    content = forms.CharField(
        label='توضیحات',
        widget=forms.Textarea(attrs={'class': 'ws-textarea', 'rows': 3}),
    )
    duration_minutes = forms.IntegerField(
        label='مدت (دقیقه)', required=False,
        widget=forms.NumberInput(attrs={'class': 'ws-input'}),
    )
    next_follow_up = forms.CharField(
        label='پیگیری بعدی',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'crm-input crm-jalali-date',
            'data-jdp': '',
            'data-jdp-only-date': '',
            'placeholder': '۱۴۰۴/۰۶/۱۵',
            'autocomplete': 'off',
        }),
    )

    def clean_next_follow_up(self):
        raw = self.cleaned_data.get('next_follow_up')
        if not raw:
            return None
        if hasattr(raw, 'year'):
            return raw
        parsed = parse_jalali_date_string(str(raw))
        if parsed is None:
            raise forms.ValidationError('تاریخ شمسی نامعتبر است.')
        return parsed


class FollowUpForm(forms.Form):
    next_follow_up = forms.CharField(
        label='تاریخ پیگیری',
        widget=forms.TextInput(attrs={
            'class': 'crm-input crm-jalali-date',
            'data-jdp': '',
            'data-jdp-only-date': '',
            'placeholder': '۱۴۰۴/۰۶/۱۵',
            'autocomplete': 'off',
        }),
    )
    note = forms.CharField(
        label='یادداشت',
        required=False,
        widget=forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 3, 'placeholder': 'موضوع تماس بعدی...'}),
    )

    def clean_next_follow_up(self):
        raw = self.cleaned_data.get('next_follow_up')
        if not raw:
            raise forms.ValidationError('تاریخ پیگیری الزامی است.')
        if hasattr(raw, 'year'):
            return raw
        parsed = parse_jalali_date_string(str(raw))
        if parsed is None:
            raise forms.ValidationError('تاریخ شمسی نامعتبر است. مثال: ۱۴۰۴/۰۶/۱۵')
        return parsed


class PropertyLinkForm(forms.Form):
    role = forms.ChoiceField(
        label='نقش',
        choices=[(r, r) for r in LISTING_ROLES],
        widget=forms.Select(attrs={'class': 'ws-select'}),
    )
    deal_type = forms.ChoiceField(
        label='نوع معامله',
        choices=[(d, d) for d in DEAL_TYPES],
        widget=forms.Select(attrs={'class': 'ws-select'}),
    )
    interest_level = forms.ChoiceField(
        label='سطح علاقه', required=False,
        choices=[('', '—')] + [(i, i) for i in INTEREST_LEVELS],
        widget=forms.Select(attrs={'class': 'ws-select'}),
    )
    is_primary = forms.BooleanField(
        label='نقش اصلی', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'ws-checkbox'}),
    )
    notes = forms.CharField(
        label='یادداشت', required=False,
        widget=forms.Textarea(attrs={'class': 'ws-textarea', 'rows': 2}),
    )


class ConvertLeadForm(forms.Form):
    new_type = forms.ChoiceField(
        label='تبدیل به',
        widget=forms.Select(attrs={'class': 'crm-select ws-select'}),
    )

    def __init__(self, customer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from workspace.services.crm import get_convert_options
        opts = get_convert_options(customer.customer_type)
        self.fields['new_type'].choices = [(o, o) for o in opts]
        self.fields['new_type'].widget.attrs.update({'class': 'ws-select'})


class CustomerDocumentForm(forms.ModelForm):
    class Meta:
        model = CustomerDocument
        fields = ['title', 'file', 'doc_type']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'ws-input'}),
            'file': forms.ClearableFileInput(attrs={'class': 'ws-file-input'}),
            'doc_type': forms.TextInput(attrs={'class': 'ws-input', 'placeholder': 'قرارداد، کارت ملی، ...'}),
        }


class ReminderForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.due_at:
            self.fields['due_at'].initial = format_jalali_datetime(self.instance.due_at)

    def clean_due_at(self):
        raw = self.cleaned_data.get('due_at')
        if not raw:
            return None
        if hasattr(raw, 'hour'):
            return raw
        parsed = parse_jalali_datetime_string(str(raw))
        if parsed is None:
            raise forms.ValidationError('تاریخ و ساعت شمسی نامعتبر است.')
        return parsed

    class Meta:
        model = Reminder
        fields = ['title', 'note', 'due_at', 'token']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'crm-input'}),
            'note': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
            'due_at': forms.TextInput(attrs={
                'class': 'crm-input crm-jalali-datetime',
                'data-jdp': '',
                'placeholder': '۱۴۰۴/۰۶/۱۵ ۱۴:۳۰',
                'autocomplete': 'off',
            }),
            'token': forms.TextInput(attrs={'class': 'crm-input'}),
        }


class CRMReminderForm(forms.ModelForm):
    """یادآور با انتخاب مخاطب."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.due_at:
            self.fields['due_at'].initial = format_jalali_datetime(self.instance.due_at)
        self.fields['due_at'].required = True

    def clean_due_at(self):
        raw = self.cleaned_data.get('due_at')
        if not raw:
            raise forms.ValidationError('تاریخ و ساعت یادآور الزامی است.')
        if hasattr(raw, 'hour'):
            return raw
        parsed = parse_jalali_datetime_string(str(raw))
        if parsed is None:
            raise forms.ValidationError('تاریخ و ساعت شمسی نامعتبر است. مثال: ۱۴۰۴/۰۶/۱۵ ۱۴:۳۰')
        return parsed

    class Meta:
        model = Reminder
        fields = ['title', 'note', 'due_at', 'recurrence']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'crm-input'}),
            'note': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
            'due_at': forms.TextInput(attrs={
                'class': 'crm-input crm-jalali-datetime',
                'data-jdp': '',
                'placeholder': '۱۴۰۴/۰۶/۱۵ ۱۴:۳۰',
                'autocomplete': 'off',
            }),
            'recurrence': forms.Select(attrs={'class': 'crm-select'}),
        }


class CRMDealForm(CRMMoneyFieldsMixin, forms.ModelForm):
    money_fields = ('value', 'commission_amount', 'contract_amount')

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user:
            from workspace.services.crm_scope import customers_qs, properties_qs
            self.fields['customer'].queryset = customers_qs(user).order_by('name')
            self.fields['property'].queryset = properties_qs(user).order_by('-updated_at')
            from workspace.services.crm_deal_stages import get_user_deal_stages
            stages = get_user_deal_stages(user)
            self.fields['stage'].widget = forms.Select(
                attrs={'class': 'crm-select'},
                choices=[(s, s) for s in stages],
            )
        for fname in ('expected_close_date', 'contract_date'):
            if self.instance.pk and getattr(self.instance, fname, None):
                self.fields[fname].initial = format_jalali_date(getattr(self.instance, fname))

    def clean_expected_close_date(self):
        return self._clean_jalali_date('expected_close_date')

    def clean_contract_date(self):
        return self._clean_jalali_date('contract_date')

    def _clean_jalali_date(self, field_name):
        raw = self.cleaned_data.get(field_name)
        if not raw:
            return None
        if hasattr(raw, 'year'):
            return raw
        parsed = parse_jalali_date_string(str(raw))
        if parsed is None:
            raise forms.ValidationError('تاریخ شمسی نامعتبر است.')
        return parsed

    def save(self, commit=True):
        deal = super().save(commit=False)
        if self.user and not deal.user_id:
            deal.user = self.user
        if self.user and not deal.agency_id:
            from workspace.services.crm_scope import get_agency
            deal.agency = get_agency(self.user)
        if deal.value and deal.commission_rate and not deal.commission_amount:
            from workspace.services.crm_deals import calculate_commission
            deal.commission_amount = calculate_commission(deal.value, deal.commission_rate)
        if commit:
            deal.save()
            from workspace.services.crm_deal_checklist import ensure_deal_checklist
            ensure_deal_checklist(deal)
        return deal

    class Meta:
        model = CRMDeal
        fields = [
            'customer', 'property', 'listing_token', 'title', 'stage',
            'value', 'probability', 'expected_close_date', 'lost_reason',
            'commission_rate', 'commission_amount',
            'contract_number', 'contract_amount', 'contract_date', 'notes',
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'crm-select'}),
            'property': forms.Select(attrs={'class': 'crm-select'}),
            'listing_token': forms.TextInput(attrs={'class': 'crm-input', 'dir': 'ltr'}),
            'title': forms.TextInput(attrs={'class': 'crm-input'}),
            'stage': forms.Select(attrs={'class': 'crm-select'}),
            'value': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'probability': forms.NumberInput(attrs={'class': 'crm-input', 'min': 0, 'max': 100}),
            'expected_close_date': forms.TextInput(attrs={
                'class': 'crm-input crm-jalali-date', 'data-jdp': '', 'data-jdp-only-date': '',
                'placeholder': '۱۴۰۴/۰۶/۱۵', 'autocomplete': 'off',
            }),
            'lost_reason': forms.Select(attrs={'class': 'crm-select'}),
            'commission_rate': forms.NumberInput(attrs={'class': 'crm-input', 'step': '0.1', 'min': 0}),
            'commission_amount': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'contract_number': forms.TextInput(attrs={'class': 'crm-input'}),
            'contract_amount': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'contract_date': forms.TextInput(attrs={
                'class': 'crm-input crm-jalali-date', 'data-jdp': '', 'data-jdp-only-date': '',
                'autocomplete': 'off',
            }),
            'notes': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 3}),
        }


class PropertyVisitForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            from workspace.services.crm_scope import properties_qs
            self.fields['property'].queryset = properties_qs(user).order_by('-updated_at')
        self.fields['property'].required = False
        if self.instance.pk and self.instance.visit_date:
            self.fields['visit_date'].initial = format_jalali_date(self.instance.visit_date)

    def clean_visit_date(self):
        raw = self.cleaned_data.get('visit_date')
        if not raw:
            raise forms.ValidationError('تاریخ بازدید الزامی است.')
        if hasattr(raw, 'year'):
            return raw
        parsed = parse_jalali_date_string(str(raw))
        if parsed is None:
            raise forms.ValidationError('تاریخ شمسی نامعتبر است.')
        return parsed

    class Meta:
        model = PropertyVisit
        fields = [
            'property', 'listing_token', 'listing_title',
            'visit_date', 'outcome', 'reject_reason', 'notes',
        ]
        widgets = {
            'property': forms.Select(attrs={'class': 'crm-select'}),
            'listing_token': forms.TextInput(attrs={'class': 'crm-input', 'dir': 'ltr'}),
            'listing_title': forms.TextInput(attrs={'class': 'crm-input'}),
            'visit_date': forms.TextInput(attrs={
                'class': 'crm-input crm-jalali-date', 'data-jdp': '', 'data-jdp-only-date': '',
                'autocomplete': 'off',
            }),
            'outcome': forms.Select(attrs={'class': 'crm-select', 'data-visit-outcome': '1'}),
            'reject_reason': forms.Select(attrs={'class': 'crm-select'}),
            'notes': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
        }


class CustomerImportForm(forms.Form):
    file = forms.FileField(
        label='فایل مخاطبین',
        widget=forms.ClearableFileInput(attrs={
            'class': 'crm-input', 'accept': '.xlsx,.xls,.csv',
        }),
    )


class CRMMessageTemplateForm(forms.ModelForm):
    class Meta:
        model = CRMMessageTemplate
        fields = ['name', 'category', 'channel', 'body']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'crm-input'}),
            'category': forms.Select(attrs={'class': 'crm-select'}),
            'channel': forms.Select(attrs={'class': 'crm-select'}),
            'body': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 6}),
        }


class CRMAutomationRuleForm(forms.ModelForm):
    class Meta:
        model = CRMAutomationRule
        fields = [
            'name', 'is_active', 'trigger', 'trigger_days', 'trigger_statuses',
            'action', 'action_status', 'action_reminder_title', 'action_reminder_days',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'crm-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'crm-checkbox'}),
            'trigger': forms.Select(attrs={'class': 'crm-select'}),
            'trigger_days': forms.NumberInput(attrs={'class': 'crm-input', 'min': 1, 'max': 90}),
            'trigger_statuses': forms.TextInput(attrs={
                'class': 'crm-input', 'placeholder': 'جدید,در حال پیگیری',
            }),
            'action': forms.Select(attrs={'class': 'crm-select', 'data-automation-action': '1'}),
            'action_status': forms.Select(attrs={'class': 'crm-select'}),
            'action_reminder_title': forms.TextInput(attrs={'class': 'crm-input'}),
            'action_reminder_days': forms.NumberInput(attrs={'class': 'crm-input', 'min': 0, 'max': 30}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from workspace.constants import CRM_STATUSES
        self.fields['action_status'].choices = [('', '—')] + [(s, s) for s in CRM_STATUSES]


class WorkspaceSettingsForm(forms.ModelForm):
    class Meta:
        model = WorkspaceSettings
        fields = [
            'theme', 'font_scale', 'map_cluster', 'map_heatmap',
            'map_kmeans', 'agency_name', 'agency_logo',
        ]
        labels = {
            'theme': 'تم ظاهری',
            'font_scale': 'اندازه فونت',
            'map_cluster': 'خوشه‌بندی نقشه',
            'map_heatmap': 'نقشه حرارتی',
            'map_kmeans': 'خوشه‌بندی K-Means',
            'agency_name': 'نام آژانس',
            'agency_logo': 'لوگو آژانس',
        }
        help_texts = {
            'font_scale': 'بین ۰٫۸ تا ۱٫۵ — پیش‌فرض ۱٫۰',
            'map_cluster': 'نقاط نزدیک روی نقشه در یک خوشه نمایش داده می‌شوند',
            'map_heatmap': 'نمایش تراکم داده روی نقشه با گرادیان رنگی',
            'map_kmeans': '۰ یعنی غیرفعال · حداکثر ۱۰ خوشه',
            'agency_name': 'در خروجی‌ها و برندینگ CRM نمایش داده می‌شود',
            'agency_logo': 'PNG یا JPG — حداکثر ۲ مگابایت',
        }
        widgets = {
            'theme': forms.RadioSelect(attrs={'class': 'ws-settings-theme-input'}),
            'font_scale': forms.NumberInput(attrs={
                'class': 'ws-settings-font-input', 'step': '0.1', 'min': '0.8', 'max': '1.5',
            }),
            'map_cluster': forms.CheckboxInput(attrs={'class': 'ws-settings-toggle-input'}),
            'map_heatmap': forms.CheckboxInput(attrs={'class': 'ws-settings-toggle-input'}),
            'map_kmeans': forms.NumberInput(attrs={
                'class': 'ws-settings-kmeans-input', 'min': '0', 'max': '10', 'step': '1',
            }),
            'agency_name': forms.TextInput(attrs={
                'class': 'ws-input', 'placeholder': 'مثلاً آژانس املاک نمونه',
            }),
            'agency_logo': forms.FileInput(attrs={
                'class': 'ws-settings-logo-input', 'accept': 'image/png,image/jpeg,image/webp,image/svg+xml',
            }),
        }


class CompareForm(forms.Form):
    dataset_a = forms.ModelChoiceField(
        queryset=Dataset.objects.none(),
        label='فایل قدیمی',
        widget=forms.Select(attrs={'class': 'ws-select'}),
    )
    dataset_b = forms.ModelChoiceField(
        queryset=Dataset.objects.none(),
        label='فایل جدید',
        widget=forms.Select(attrs={'class': 'ws-select'}),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Dataset.objects.filter(user=user, is_active=True).order_by('-created_at')
        self.fields['dataset_a'].queryset = qs
        self.fields['dataset_b'].queryset = qs
