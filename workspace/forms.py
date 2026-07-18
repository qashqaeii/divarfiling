"""فرم‌های workspace."""
import math

from django import forms
from django.utils import timezone

from workspace.constants import BUILDER_BUY_PROPERTY_TYPES
from workspace.constants import (
    ACTIVITY_TYPES, AUTOMATION_ACTIONS, AUTOMATION_TRIGGERS, DEAL_STAGES, DEAL_TYPES,
    INTEREST_LEVELS, LISTING_ROLES, LOST_REASONS, MESSAGE_CHANNELS,
    MESSAGE_TEMPLATE_CATEGORIES, REMINDER_RECURRENCE, VISIT_OUTCOMES, VISIT_REJECT_REASONS,
)
from workspace.services.jalali_input import (
    format_jalali_date,
    format_jalali_datetime,
    parse_jalali_date_string,
    parse_jalali_datetime_string,
)
from workspace.services.contact_channels import contact_channels_from_post
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
    if value is None or value == '':
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return int(value)
    if isinstance(value, int):
        return value
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
            'neighborhood', 'city', 'latitude', 'longitude',
            'business_type', 'description', 'link', 'is_expired',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'ws-input'}),
            'price': forms.NumberInput(attrs={'class': 'ws-input', 'placeholder': 'تومان'}),
            'deposit': forms.NumberInput(attrs={'class': 'ws-input', 'placeholder': 'تومان'}),
            'rent': forms.NumberInput(attrs={'class': 'ws-input', 'placeholder': 'تومان'}),
            'area': forms.NumberInput(attrs={'class': 'ws-input', 'step': '0.1'}),
            'rooms': forms.TextInput(attrs={'class': 'ws-input'}),
            'neighborhood': forms.TextInput(attrs={'class': 'ws-input'}),
            'city': forms.TextInput(attrs={'class': 'ws-input'}),
            'latitude': forms.NumberInput(attrs={'class': 'ws-input', 'step': 'any', 'dir': 'ltr'}),
            'longitude': forms.NumberInput(attrs={'class': 'ws-input', 'step': 'any', 'dir': 'ltr'}),
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
            'is_expired': forms.CheckboxInput(attrs={'class': 'ws-check'}),
        }


class CustomerForm(CRMMoneyFieldsMixin, forms.ModelForm):
    money_fields = (
        'budget_min', 'budget_max', 'deposit_min', 'deposit_max', 'rent_min', 'rent_max',
        'builder_buy_budget_min', 'builder_buy_budget_max',
    )

    builder_buy_types = forms.MultipleChoiceField(
        label='انواع ملک هدف خرید',
        choices=[(t, t) for t in BUILDER_BUY_PROPERTY_TYPES],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'crm-check-list'}),
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
        if not self.is_bound:
            raw_types = (self.instance.builder_buy_property_types or '').replace('،', ',')
            selected = [t.strip() for t in raw_types.split(',') if t.strip()]
            if selected:
                self.initial['builder_buy_types'] = selected
            elif self.instance.customer_type == 'سازنده':
                self.initial['builder_buy_types'] = list(BUILDER_BUY_PROPERTY_TYPES)
            if self.instance.customer_type == 'سازنده' and not self.instance.property_type:
                self.initial.setdefault('property_type', 'آپارتمان')
            if self.instance.pk and not self.instance.rooms_min and self.instance.rooms:
                digits = ''.join(ch for ch in self.instance.rooms if ch.isdigit())
                if digits:
                    self.initial.setdefault('rooms_min', int(digits))

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

    def save(self, commit=True):
        instance = super().save(commit=False)
        selected = self.cleaned_data.get('builder_buy_types') or []
        instance.builder_buy_property_types = ', '.join(selected)
        if instance.customer_type == 'سازنده' and not instance.property_type:
            instance.property_type = 'آپارتمان'
        if instance.rooms_min is not None and instance.rooms_max is not None:
            instance.rooms = f'{instance.rooms_min}-{instance.rooms_max}'
        elif instance.rooms_min is not None:
            instance.rooms = str(instance.rooms_min)
        elif instance.rooms_max is not None:
            instance.rooms = str(instance.rooms_max)
        if self.is_bound:
            active, links = contact_channels_from_post(self.data)
            instance.active_channels = active
            instance.social_links = links
        if commit:
            instance.save()
            self.save_m2m()
        return instance

    class Meta:
        model = Customer
        fields = [
            'name', 'phone', 'phone_alt', 'email', 'city', 'district', 'job',
            'is_legal_entity', 'company_name', 'national_id',
            'customer_type', 'status', 'priority', 'property_type', 'source',
            'budget_min', 'budget_max', 'deposit_min', 'deposit_max',
            'rent_min', 'rent_max', 'min_area', 'max_area',
            'rooms_min', 'rooms_max', 'year_min', 'year_max', 'floor_min', 'floor_max',
            'want_parking', 'want_storage', 'want_elevator', 'areas',
            'builder_buy_budget_min', 'builder_buy_budget_max',
            'builder_buy_areas', 'builder_buy_min_area', 'builder_buy_max_area',
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
            'property_type': forms.Select(attrs={'class': 'crm-select', 'data-crm-property-type': '1'}),
            'source': forms.Select(attrs={'class': 'crm-select'}),
            'budget_min': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'budget_max': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'deposit_min': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'deposit_max': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'rent_min': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'rent_max': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'min_area': forms.NumberInput(attrs={'class': 'crm-input', 'min': '0', 'placeholder': 'مثلاً ۷۵'}),
            'max_area': forms.NumberInput(attrs={'class': 'crm-input', 'min': '0', 'placeholder': 'مثلاً ۱۵۰'}),
            'rooms_min': forms.NumberInput(attrs={'class': 'crm-input', 'min': '0', 'placeholder': 'از'}),
            'rooms_max': forms.NumberInput(attrs={'class': 'crm-input', 'min': '0', 'placeholder': 'تا'}),
            'year_min': forms.NumberInput(attrs={'class': 'crm-input', 'min': '1300', 'max': '1500', 'placeholder': 'مثلاً ۱۳۹۵'}),
            'year_max': forms.NumberInput(attrs={'class': 'crm-input', 'min': '1300', 'max': '1500', 'placeholder': 'مثلاً ۱۴۰۳'}),
            'floor_min': forms.NumberInput(attrs={'class': 'crm-input', 'placeholder': 'از'}),
            'floor_max': forms.NumberInput(attrs={'class': 'crm-input', 'placeholder': 'تا'}),
            'want_parking': forms.CheckboxInput(attrs={'class': 'crm-checkbox'}),
            'want_storage': forms.CheckboxInput(attrs={'class': 'crm-checkbox'}),
            'want_elevator': forms.CheckboxInput(attrs={'class': 'crm-checkbox'}),
            'areas': forms.HiddenInput(attrs={'class': 'crm-areas-hidden', 'data-crm-areas-hidden': 'areas'}),
            'builder_buy_budget_min': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'builder_buy_budget_max': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'builder_buy_areas': forms.HiddenInput(attrs={
                'class': 'crm-areas-hidden',
                'data-crm-areas-hidden': 'builder_buy_areas',
            }),
            'builder_buy_min_area': forms.NumberInput(attrs={'class': 'crm-input'}),
            'builder_buy_max_area': forms.NumberInput(attrs={'class': 'crm-input'}),
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

    amenity_flags = forms.MultipleChoiceField(
        required=False,
        choices=[],
        widget=forms.CheckboxSelectMultiple,
    )
    amenities_extra = forms.CharField(
        required=False,
        label='سایر امکانات',
        widget=forms.Textarea(attrs={
            'class': 'crm-textarea',
            'rows': 2,
            'placeholder': 'مثلاً توضیح آزاد که در فیلدهای بالا نیست…',
        }),
    )

    class Meta:
        model = CRMProperty
        fields = [
            'title', 'property_type', 'deal_mode', 'transaction_status', 'publish_status',
            'business_type', 'phone', 'owner_name', 'tenant_phone', 'tenant_name',
            'address', 'city', 'district', 'neighborhood',
            'latitude', 'longitude', 'area', 'rooms', 'floor', 'total_floors',
            'has_parking', 'has_storage', 'has_elevator', 'is_vacant', 'build_year',
            'sale_price', 'deposit', 'monthly_rent', 'amenities', 'notes', 'link',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'crm-input'}),
            'property_type': forms.Select(attrs={'class': 'crm-select'}),
            'deal_mode': forms.Select(attrs={'class': 'crm-select', 'data-deal-mode': '1'}),
            'transaction_status': forms.Select(attrs={'class': 'crm-select'}),
            'publish_status': forms.Select(attrs={'class': 'crm-select'}),
            'business_type': forms.Select(
                choices=[('', '—'), ('شخصی', 'شخصی'), ('مشاور', 'مشاور املاک'), ('business', 'بنگاه / Business')],
                attrs={'class': 'crm-select'},
            ),
            'phone': forms.TextInput(attrs={'class': 'crm-input', 'dir': 'ltr', 'inputmode': 'tel', 'placeholder': '۰۹۱۲…'}),
            'owner_name': forms.TextInput(attrs={'class': 'crm-input', 'placeholder': 'نام و نام خانوادگی مالک'}),
            'tenant_phone': forms.TextInput(attrs={
                'class': 'crm-input',
                'dir': 'ltr',
                'inputmode': 'tel',
                'placeholder': '۰۹۱۲…',
                'data-tenant-field': '1',
            }),
            'tenant_name': forms.TextInput(attrs={
                'class': 'crm-input',
                'placeholder': 'نام و نام خانوادگی مستاجر فعلی',
                'data-tenant-field': '1',
            }),
            'address': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'crm-input'}),
            'district': forms.TextInput(attrs={
                'class': 'crm-input',
                'placeholder': 'مثلاً منطقه ۳',
                'autocomplete': 'off',
            }),
            'neighborhood': forms.TextInput(attrs={
                'class': 'crm-input',
                'placeholder': 'مثلاً نیاوران',
                'autocomplete': 'off',
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'crm-input',
                'step': 'any',
                'dir': 'ltr',
                'inputmode': 'decimal',
                'data-crm-form-map-lat': '1',
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'crm-input',
                'step': 'any',
                'dir': 'ltr',
                'inputmode': 'decimal',
                'data-crm-form-map-lng': '1',
            }),
            'area': forms.NumberInput(attrs={'class': 'crm-input', 'step': '0.1'}),
            'rooms': forms.TextInput(attrs={'class': 'crm-input'}),
            'floor': forms.NumberInput(attrs={'class': 'crm-input'}),
            'total_floors': forms.NumberInput(attrs={'class': 'crm-input'}),
            'build_year': forms.NumberInput(attrs={'class': 'crm-input'}),
            'sale_price': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'deposit': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'monthly_rent': forms.TextInput(attrs=_CRM_MONEY_WIDGET_ATTRS),
            'amenities': forms.HiddenInput(),
            'notes': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
            'link': forms.URLInput(attrs={'class': 'crm-input'}),
            'has_parking': forms.HiddenInput(),
            'has_storage': forms.HiddenInput(),
            'has_elevator': forms.HiddenInput(),
            'is_vacant': forms.CheckboxInput(attrs={
                'class': 'crm-checkbox',
                'data-vacant-checkbox': '1',
            }),
        }

    def __init__(self, *args, **kwargs):
        from workspace.constants import PROPERTY_AMENITY_CHECKBOX_GROUPS
        from workspace.services.property_features import feature_form_groups_with_values
        from workspace.services.property_public_share import (
            property_amenity_checkbox_choices,
            split_amenities_for_checkbox_form,
        )

        super().__init__(*args, **kwargs)
        self.fields['amenity_flags'].choices = property_amenity_checkbox_choices()
        self._amenity_groups_meta = PROPERTY_AMENITY_CHECKBOX_GROUPS

        instance = getattr(self, 'instance', None)
        if instance is not None and not self.is_bound and not (instance.district or '').strip():
            from workspace.services.crm import resolve_district_for_property
            resolved_district = resolve_district_for_property(instance)
            if resolved_district:
                self.initial['district'] = resolved_district

        if instance is not None and (instance.pk or instance.amenities or instance.has_parking
                                     or instance.has_storage or instance.has_elevator):
            selected, leftover = split_amenities_for_checkbox_form(
                instance.amenities or '',
                has_parking=bool(instance.has_parking),
                has_storage=bool(instance.has_storage),
                has_elevator=bool(instance.has_elevator),
            )
            self.fields['amenity_flags'].initial = selected
            self.fields['amenities_extra'].initial = leftover

        feature_data = {}
        if instance is not None and isinstance(getattr(instance, 'feature_data', None), dict):
            feature_data = instance.feature_data or {}
        self._feature_form_groups = feature_form_groups_with_values(feature_data)
        self._parsed_feature_data = feature_data

    def amenity_checkbox_groups(self):
        """گروه‌های امکانات با وضعیت تیک برای رندر در قالب."""
        if self.is_bound:
            selected = set(self.data.getlist('amenity_flags'))
        else:
            initial = self.fields['amenity_flags'].initial or []
            selected = set(initial)
        groups = []
        for group in self._amenity_groups_meta:
            items = [
                {
                    'label': label,
                    'icon': icon,
                    'checked': label in selected,
                }
                for label, icon in group['items']
            ]
            groups.append({
                'id': group['id'],
                'title': group['title'],
                'icon': group['icon'],
                'items': items,
            })
        return groups

    def feature_form_groups(self):
        """گروه‌های ویژگی تفصیلی برای رندر؛ در حالت bound از POST خوانده می‌شود."""
        from workspace.services.property_features import (
            feature_form_groups_with_values,
            parse_feature_data_from_post,
        )
        if self.is_bound:
            return feature_form_groups_with_values(parse_feature_data_from_post(self.data))
        return self._feature_form_groups

    def clean(self):
        from workspace.services.property_features import parse_feature_data_from_post
        from workspace.services.property_public_share import serialize_amenity_checkboxes

        cleaned = super().clean()
        selected = list(cleaned.get('amenity_flags') or [])
        leftover = (cleaned.get('amenities_extra') or '').strip()
        cleaned['has_parking'] = 'پارکینگ' in selected
        cleaned['has_storage'] = 'انباری' in selected
        cleaned['has_elevator'] = 'آسانسور' in selected
        cleaned['amenities'] = serialize_amenity_checkboxes(selected, leftover)
        if cleaned.get('is_vacant'):
            cleaned['tenant_phone'] = ''
            cleaned['tenant_name'] = ''
        if self.is_bound and self.data is not None:
            self._parsed_feature_data = parse_feature_data_from_post(self.data)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.feature_data = getattr(self, '_parsed_feature_data', None) or {}
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ActivityForm(forms.Form):
    activity_type = forms.ChoiceField(
        label='نوع فعالیت',
        choices=[(a, a) for a in ACTIVITY_TYPES],
        initial='تماس',
        widget=forms.Select(attrs={'class': 'crm-select crm-act-type-native'}),
    )
    title = forms.CharField(
        label='عنوان',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'crm-input',
            'placeholder': 'عنوان اختیاری',
            'autocomplete': 'off',
        }),
    )
    content = forms.CharField(
        label='توضیحات',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'crm-textarea crm-act-content',
            'rows': 4,
            'placeholder': 'توضیحات اختیاری',
        }),
    )
    duration_minutes = forms.IntegerField(
        label='مدت (دقیقه)',
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'crm-input',
            'placeholder': 'مثلاً ۱۵',
            'inputmode': 'numeric',
            'min': 0,
        }),
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


_JALALI_DATETIME_WIDGET = forms.TextInput(attrs={
    'class': 'crm-input crm-jalali-datetime',
    'data-jdp': '',
    'placeholder': '۱۴۰۴/۰۶/۱۵ ۱۴:۳۰',
    'autocomplete': 'off',
})


def _clean_jalali_due_at(raw, *, required: bool = True):
    if not raw:
        if required:
            raise forms.ValidationError('تاریخ و ساعت یادآور الزامی است.')
        return None
    if hasattr(raw, 'hour'):
        parsed = raw
    else:
        parsed = parse_jalali_datetime_string(str(raw))
        if parsed is None:
            raise forms.ValidationError('تاریخ و ساعت شمسی نامعتبر است. مثال: ۱۴۰۴/۰۶/۱۵ ۱۴:۳۰')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _default_reminder_due_initial():
    from datetime import timedelta
    return format_jalali_datetime(timezone.now() + timedelta(hours=1))


class ReminderForm(forms.ModelForm):
    due_at = forms.CharField(
        label='سررسید',
        required=True,
        widget=_JALALI_DATETIME_WIDGET,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.due_at:
            self.fields['due_at'].initial = format_jalali_datetime(self.instance.due_at)
        elif not self.data:
            self.fields['due_at'].initial = _default_reminder_due_initial()

    def clean_due_at(self):
        return _clean_jalali_due_at(self.cleaned_data.get('due_at'), required=True)

    class Meta:
        model = Reminder
        fields = ['title', 'note', 'due_at', 'token']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'crm-input'}),
            'note': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
            'token': forms.TextInput(attrs={'class': 'crm-input'}),
        }


class CRMReminderForm(forms.ModelForm):
    """یادآور با انتخاب مخاطب."""

    due_at = forms.CharField(
        label='سررسید',
        required=True,
        widget=_JALALI_DATETIME_WIDGET,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.due_at:
            self.fields['due_at'].initial = format_jalali_datetime(self.instance.due_at)
        elif not self.data:
            self.fields['due_at'].initial = _default_reminder_due_initial()

    def clean_due_at(self):
        return _clean_jalali_due_at(self.cleaned_data.get('due_at'), required=True)

    class Meta:
        model = Reminder
        fields = ['title', 'note', 'due_at', 'recurrence']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'crm-input'}),
            'note': forms.Textarea(attrs={'class': 'crm-textarea', 'rows': 2}),
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
    visit_date = forms.CharField(
        label='تاریخ بازدید',
        widget=forms.TextInput(attrs={
            'class': 'crm-input crm-jalali-date',
            'data-jdp': '',
            'data-jdp-only-date': '',
            'placeholder': '۱۴۰۴/۰۶/۱۵',
            'autocomplete': 'off',
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            from workspace.services.crm_scope import properties_qs
            self.fields['property'].queryset = properties_qs(user).order_by('-updated_at')
        self.fields['property'].required = True
        self.fields['property'].empty_label = 'انتخاب ملک'
        if self.instance.pk and self.instance.visit_date:
            self.fields['visit_date'].initial = format_jalali_date(self.instance.visit_date)
        elif not self.data:
            self.fields['visit_date'].initial = format_jalali_date(timezone.now().date())

    def clean_visit_date(self):
        raw = self.cleaned_data.get('visit_date')
        if not raw:
            raise forms.ValidationError('تاریخ بازدید الزامی است.')
        if hasattr(raw, 'year'):
            return raw
        parsed = parse_jalali_date_string(str(raw))
        if parsed is None:
            raise forms.ValidationError('تاریخ شمسی نامعتبر است. مثال: ۱۴۰۴/۰۶/۱۵')
        return parsed

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('property'):
            self.add_error('property', 'انتخاب ملک الزامی است.')
        if cleaned.get('outcome') == 'رد' and not cleaned.get('reject_reason'):
            self.add_error('reject_reason', 'دلیل رد الزامی است.')
        return cleaned

    def save(self, commit=True):
        visit = super().save(commit=False)
        if visit.property_id:
            visit.listing_token = visit.property.token or ''
            visit.listing_title = visit.property.title or ''
        if commit:
            visit.save()
        return visit

    class Meta:
        model = PropertyVisit
        fields = ['property', 'visit_date', 'outcome', 'reject_reason', 'notes']
        widgets = {
            'property': forms.Select(attrs={'class': 'crm-select'}),
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


class CRMPropertyImportForm(forms.Form):
    file = forms.FileField(
        label='فایل املاک',
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
        self.fields['action_status'] = forms.ChoiceField(
            label='وضعیت جدید',
            required=False,
            choices=[('', 'انتخاب وضعیت…')] + [(s, s) for s in CRM_STATUSES],
            widget=forms.Select(attrs={'class': 'crm-select'}),
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('action') == 'set_status' and not cleaned.get('action_status'):
            self.add_error('action_status', 'برای تغییر وضعیت، یک وضعیت جدید انتخاب کنید.')
        return cleaned


class WorkspaceSettingsForm(forms.ModelForm):
    class Meta:
        model = WorkspaceSettings
        fields = [
            'theme', 'font_scale', 'map_cluster', 'map_heatmap',
            'map_kmeans', 'agency_name', 'agency_logo',
            'agency_address', 'agency_city', 'agency_latitude', 'agency_longitude',
            'agency_landline', 'agency_landline_alt', 'agency_website',
            'consultant_photo', 'business_card_image',
        ]
        labels = {
            'theme': 'تم ظاهری',
            'font_scale': 'اندازه فونت',
            'map_cluster': 'خوشه‌بندی نقشه',
            'map_heatmap': 'نقشه حرارتی',
            'map_kmeans': 'خوشه‌بندی K-Means',
            'agency_name': 'نام آژانس',
            'agency_logo': 'لوگو آژانس',
            'agency_address': 'آدرس دفتر',
            'agency_city': 'شهر دفتر',
            'agency_latitude': 'عرض جغرافیایی',
            'agency_longitude': 'طول جغرافیایی',
            'agency_landline': 'تلفن ثابت',
            'agency_landline_alt': 'تلفن ثابت دوم',
            'agency_website': 'وبسایت آژانس',
            'consultant_photo': 'عکس مشاور',
            'business_card_image': 'کارت ویزیت',
        }
        help_texts = {
            'font_scale': 'بین ۰٫۸ تا ۱٫۵ — پیش‌فرض ۱٫۰',
            'map_cluster': 'نقاط نزدیک روی نقشه در یک خوشه نمایش داده می‌شوند',
            'map_heatmap': 'نمایش تراکم داده روی نقشه با گرادیان رنگی',
            'map_kmeans': '۰ یعنی غیرفعال · حداکثر ۱۰ خوشه',
            'agency_name': 'در صفحه اشتراک عمومی و CRM نمایش داده می‌شود',
            'agency_logo': 'PNG یا JPG — حداکثر ۲ مگابایت',
            'agency_website': 'در کارت مشاور صفحه عمومی نمایش داده می‌شود',
            'consultant_photo': 'عکس پروفایل مشاور در صفحه اشتراک',
            'business_card_image': 'پیش‌نمایش کارت ویزیت در صفحه مشتری',
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
            'agency_address': forms.Textarea(attrs={
                'class': 'ws-textarea', 'rows': 2, 'placeholder': 'خیابان، پلاک، واحد…',
            }),
            'agency_city': forms.TextInput(attrs={
                'class': 'ws-input', 'placeholder': 'تهران',
            }),
            'agency_latitude': forms.NumberInput(attrs={
                'class': 'ws-input', 'step': 'any', 'placeholder': '35.6892',
            }),
            'agency_longitude': forms.NumberInput(attrs={
                'class': 'ws-input', 'step': 'any', 'placeholder': '51.3890',
            }),
            'agency_landline': forms.TextInput(attrs={
                'class': 'ws-input', 'placeholder': '۰۲۱…', 'dir': 'ltr',
            }),
            'agency_landline_alt': forms.TextInput(attrs={
                'class': 'ws-input', 'placeholder': 'اختیاری', 'dir': 'ltr',
            }),
            'agency_website': forms.URLInput(attrs={
                'class': 'ws-input', 'placeholder': 'https://…', 'dir': 'ltr',
            }),
            'consultant_photo': forms.FileInput(attrs={
                'class': 'ws-input mk-share-file-input', 'accept': 'image/*',
            }),
            'business_card_image': forms.FileInput(attrs={
                'class': 'ws-input mk-share-file-input', 'accept': 'image/*',
            }),
        }

    def clean_agency_website(self):
        from workspace.services.public_share_common import normalize_agency_website
        return normalize_agency_website(self.cleaned_data.get('agency_website') or '')

    def clean_agency_latitude(self):
        val = self.cleaned_data.get('agency_latitude')
        if val is None:
            return None
        if not (-90 <= float(val) <= 90):
            raise forms.ValidationError('عرض جغرافیایی نامعتبر است.')
        return val

    def clean_agency_longitude(self):
        val = self.cleaned_data.get('agency_longitude')
        if val is None:
            return None
        if not (-180 <= float(val) <= 180):
            raise forms.ValidationError('طول جغرافیایی نامعتبر است.')
        return val


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


class TicketCreateForm(forms.Form):
    subject = forms.CharField(
        label='موضوع تیکت',
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'ws-input',
            'placeholder': 'مثال: خطا در آپلود فایل اکسل',
            'autocomplete': 'off',
        }),
    )
    category = forms.ChoiceField(
        label='دسته‌بندی',
        widget=forms.Select(attrs={'class': 'ws-select'}),
    )
    priority = forms.ChoiceField(
        label='اولویت',
        widget=forms.Select(attrs={'class': 'ws-select'}),
    )
    body = forms.CharField(
        label='توضیحات',
        widget=forms.Textarea(attrs={
            'class': 'ws-input ws-textarea',
            'rows': 6,
            'placeholder': 'مشکل را با جزئیات توضیح دهید…',
        }),
    )
    attachment = forms.FileField(
        label='فایل پیوست',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'ws-input ws-file-input',
            'accept': '.jpg,.jpeg,.png,.pdf,.doc,.docx,.xls,.xlsx,.txt,.zip',
        }),
    )

    def __init__(self, *args, **kwargs):
        from workspace.support_constants import TICKET_CATEGORY_CHOICES, TICKET_PRIORITY_CHOICES
        super().__init__(*args, **kwargs)
        self.fields['category'].choices = TICKET_CATEGORY_CHOICES
        self.fields['priority'].choices = TICKET_PRIORITY_CHOICES
        self.fields['priority'].initial = 'normal'

    def clean_attachment(self):
        from workspace.services.support_tickets import validate_attachment_file
        uploaded = self.cleaned_data.get('attachment')
        if not uploaded:
            return None
        error = validate_attachment_file(uploaded)
        if error:
            raise forms.ValidationError(error)
        return uploaded

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        if len(body) < 10:
            raise forms.ValidationError('لطفاً توضیحات را حداقل در ۱۰ کاراکتر بنویسید.')
        return body


class TicketReplyForm(forms.Form):
    body = forms.CharField(
        label='پاسخ شما',
        widget=forms.Textarea(attrs={
            'class': 'sup-compose-textarea',
            'rows': 2,
            'placeholder': 'پیام خود را بنویسید…',
        }),
    )
    attachment = forms.FileField(
        label='فایل پیوست',
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'ws-input ws-file-input',
            'accept': '.jpg,.jpeg,.png,.pdf,.doc,.docx,.xls,.xlsx,.txt,.zip',
        }),
    )

    def clean_attachment(self):
        from workspace.services.support_tickets import validate_attachment_file
        uploaded = self.cleaned_data.get('attachment')
        if not uploaded:
            return None
        error = validate_attachment_file(uploaded)
        if error:
            raise forms.ValidationError(error)
        return uploaded

    def clean_body(self):
        body = (self.cleaned_data.get('body') or '').strip()
        if not body:
            raise forms.ValidationError('متن پیام نمی‌تواند خالی باشد.')
        return body

