from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from mobile_api.models import MobileDevice, MobileNotification, MobileNotificationBroadcast
from mobile_api.services.broadcast_service import queue_broadcast, target_users
from mobile_api.services.notification_catalog import BROADCAST_DEEP_LINKS, BROADCAST_TYPES


def _mask_token(token: str) -> str:
    raw = (token or '').strip()
    if not raw:
        return '—'
    if len(raw) <= 12:
        return '••••'
    return f'{raw[:8]}…{raw[-4:]}'


@admin.register(MobileDevice)
class MobileDeviceAdmin(admin.ModelAdmin):
    list_display = (
        'short_device', 'user', 'device_model', 'app_version',
        'is_active', 'has_token', 'last_seen_at',
    )
    list_filter = ('is_active', 'app_version')
    search_fields = ('device_id', 'user__phone', 'user__username')
    readonly_fields = ('registered_at', 'last_seen_at', 'masked_fcm_token')
    exclude = ('fcm_token',)

    def short_device(self, obj):
        return obj.device_id[:16]
    short_device.short_description = 'دستگاه'

    def has_token(self, obj):
        return bool((obj.fcm_token or '').strip())
    has_token.boolean = True
    has_token.short_description = 'توکن فعال'

    def masked_fcm_token(self, obj):
        return _mask_token(obj.fcm_token)
    masked_fcm_token.short_description = 'FCM token'


@admin.register(MobileNotification)
class MobileNotificationAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'user', 'notification_type', 'is_read',
        'push_status', 'created_at',
    )
    list_filter = ('notification_type', 'is_read', 'push_status')
    search_fields = ('title', 'user__phone', 'dedup_key')
    readonly_fields = ('created_at', 'read_at', 'dedup_key', 'push_status')


class BroadcastAdminForm(forms.ModelForm):
    confirm_send = forms.BooleanField(
        required=False,
        label='تأیید ارسال / زمان‌بندی',
        help_text='بدون این تیک، اعلان به‌صورت پیش‌نویس ذخیره می‌شود. ارسال به همه کاربران فقط پس از تأیید انجام می‌شود.',
    )
    notification_type = forms.ChoiceField(
        choices=[(t, t) for t in BROADCAST_TYPES],
        initial='announcement',
        label='نوع',
    )
    deep_link = forms.ChoiceField(
        choices=BROADCAST_DEEP_LINKS,
        initial='divarfiling://notifications',
        label='مقصد',
    )

    class Meta:
        model = MobileNotificationBroadcast
        fields = (
            'title', 'body', 'notification_type', 'deep_link', 'priority',
            'target', 'selected_users', 'scheduled_at', 'confirm_send',
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('target') == MobileNotificationBroadcast.TARGET_ALL and cleaned.get('confirm_send'):
            if not cleaned.get('title') or not cleaned.get('body'):
                raise forms.ValidationError('عنوان و متن برای ارسال الزامی است.')
        if cleaned.get('target') == MobileNotificationBroadcast.TARGET_SELECTED:
            if self.instance.pk is None and not self.data.getlist('selected_users'):
                raise forms.ValidationError('برای مخاطب انتخاب‌شده حداقل یک کاربر لازم است.')
        return cleaned


@admin.register(MobileNotificationBroadcast)
class MobileNotificationBroadcastAdmin(admin.ModelAdmin):
    form = BroadcastAdminForm
    list_display = (
        'title', 'notification_type', 'target', 'status',
        'scheduled_at', 'target_user_count', 'success_count',
        'fail_count', 'sent_at',
    )
    list_filter = ('status', 'target', 'notification_type')
    search_fields = ('title', 'body')
    filter_horizontal = ('selected_users',)
    readonly_fields = (
        'status', 'created_by', 'created_at', 'sent_at',
        'target_user_count', 'target_device_count',
        'success_count', 'fail_count', 'last_error', 'audience_preview',
    )
    fieldsets = (
        (None, {
            'fields': (
                'title', 'body', 'notification_type', 'deep_link', 'priority',
            ),
        }),
        ('مخاطب', {
            'fields': ('target', 'selected_users', 'audience_preview'),
        }),
        ('زمان‌بندی', {
            'fields': ('scheduled_at', 'confirm_send'),
        }),
        ('نتیجه', {
            'fields': (
                'status', 'target_user_count', 'target_device_count',
                'success_count', 'fail_count', 'sent_at', 'last_error',
                'created_by', 'created_at',
            ),
        }),
    )

    def audience_preview(self, obj):
        if not obj.pk:
            return 'پس از ذخیره قابل محاسبه است.'
        try:
            count = len(target_users(obj))
        except Exception:
            count = 0
        return format_html('{} کاربر هدف (تقریبی)', count)
    audience_preview.short_description = 'پیش‌نمایش مخاطب'

    def has_add_permission(self, request):
        return request.user.is_staff and (
            request.user.is_superuser or request.user.has_perm('mobile_api.send_broadcast')
            or request.user.has_perm('mobile_api.add_mobilenotificationbroadcast')
        )

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        locked = obj.status in (
            MobileNotificationBroadcast.STATUS_SENDING,
            MobileNotificationBroadcast.STATUS_SENT,
            MobileNotificationBroadcast.STATUS_PARTIAL,
        )
        super().save_model(request, obj, form, change)
        if locked:
            messages.warning(request, 'این ارسال قبلاً انجام شده و دوباره ارسال نمی‌شود.')
            return
        self._pending_confirm = bool(form.cleaned_data.get('confirm_send'))

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if obj.status in (
            MobileNotificationBroadcast.STATUS_SENDING,
            MobileNotificationBroadcast.STATUS_SENT,
            MobileNotificationBroadcast.STATUS_PARTIAL,
        ):
            return
        if not getattr(self, '_pending_confirm', False):
            if obj.status != MobileNotificationBroadcast.STATUS_DRAFT:
                obj.status = MobileNotificationBroadcast.STATUS_DRAFT
                obj.save(update_fields=['status'])
            return
        immediate = not obj.scheduled_at or obj.scheduled_at <= timezone_now()
        if obj.target == MobileNotificationBroadcast.TARGET_ALL:
            messages.warning(
                request,
                'ارسال به همه کاربران تأیید شد. پردازش در پس‌زمینه شروع می‌شود.',
            )
        queue_broadcast(obj, immediate=immediate)
        if immediate:
            messages.success(request, 'ارسال اعلان در صف پس‌زمینه قرار گرفت.')
        else:
            messages.success(request, 'اعلان برای زمان مشخص‌شده زمان‌بندی شد.')


def timezone_now():
    from django.utils import timezone
    return timezone.now()
