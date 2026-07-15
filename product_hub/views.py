"""ویوهای مرکز توسعه فایلینگ دیوار (Product Hub)."""
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from product_hub.forms import (
    BugReportForm,
    BugReportStatusForm,
    FeatureRequestForm,
    FeatureRequestStatusForm,
    ProductFeatureForm,
    ProductReleaseForm,
    ReleaseChangeFormSet,
)
from product_hub.models import (
    FEATURE_CATEGORY_CHOICES,
    FEATURE_STATUS_CHOICES,
    BugReport,
    FeatureFollow,
    FeatureRequest,
    FeatureVote,
    ProductFeature,
    ProductHubNotification,
    ProductRelease,
)
from product_hub.services import notifications as notif_svc
from product_hub.services import stats as stats_svc
from product_hub.services import workflow as workflow_svc
from workspace.mixins import WorkspaceLoginMixin
from workspace.services.access import has_active_bot_license


def _wants_json(request):
    accept = request.headers.get('Accept', '')
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in accept
    )


class LicenseActionMixin:
    """گیت لایسنس برای اکشن‌های تعاملی؛ staff بدون نیاز به لایسنس."""

    license_denied_message = (
        'برای ثبت پیشنهاد، رای، دنبال کردن یا گزارش باگ به لایسنس فعال نیاز دارید.'
    )

    def require_license(self, request):
        user = request.user
        if user.is_staff or has_active_bot_license(user):
            return None
        if _wants_json(request):
            return JsonResponse({
                'ok': False,
                'error': 'license_required',
                'message': self.license_denied_message,
                'upgrade_url': reverse('workspace:upgrade'),
            }, status=403)
        messages.info(request, self.license_denied_message)
        return redirect(reverse('workspace:upgrade') + '?feature=product_hub')


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def handle_no_permission(self):
        messages.error(self.request, 'فقط مدیر سیستم به این بخش دسترسی دارد.')
        return redirect('workspace:product_hub:hub')


class ProductHubView(WorkspaceLoginMixin, TemplateView):
    """صفحه اصلی مرکز توسعه با تب‌ها."""

    template_name = 'workspace/product_hub/hub.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        tab = self.request.GET.get('tab', 'overview')
        allowed = {
            'overview', 'changelog', 'features', 'requests', 'bugs', 'roadmap', 'my',
        }
        if tab not in allowed:
            tab = 'overview'

        licensed = user.is_staff or has_active_bot_license(user)
        ctx.update({
            'active_tab': tab,
            'hub_stats': stats_svc.get_hub_stats(),
            'has_product_action_access': licensed,
            'category_choices': FEATURE_CATEGORY_CHOICES,
            'feature_status_choices': FEATURE_STATUS_CHOICES,
            'request_form': FeatureRequestForm(),
            'bug_form': BugReportForm(),
            'unread_notifications': (
                ProductHubNotification.objects.filter(user=user, is_read=False)[:5]
            ),
            'unread_count': notif_svc.unread_count(user),
            'is_product_staff': user.is_staff,
        })

        # Changelog
        ctx['releases'] = (
            ProductRelease.objects.filter(is_published=True)
            .prefetch_related('changes')[:20]
        )

        # Features filters
        fq = self.request.GET.get('fq', '').strip()
        fcat = self.request.GET.get('fcat', '').strip()
        fstatus = self.request.GET.get('fstatus', '').strip()
        features = ProductFeature.objects.filter(is_published=True).order_by('sort_order', 'title')
        if fq:
            features = features.filter(
                Q(title__icontains=fq) | Q(summary__icontains=fq),
            )
        if fcat:
            features = features.filter(category=fcat)
        if fstatus:
            features = features.filter(status=fstatus)
        feature_list = list(features)
        feature_groups = []
        for cat_key, cat_label in FEATURE_CATEGORY_CHOICES:
            items = [f for f in feature_list if f.category == cat_key]
            if items:
                feature_groups.append({
                    'key': cat_key,
                    'label': cat_label,
                    'count': len(items),
                    'items': items,
                })
        ctx.update({
            'features': feature_list,
            'feature_groups': feature_groups,
            'features_count': len(feature_list),
            'feature_q': fq,
            'feature_cat': fcat,
            'feature_status': fstatus,
        })

        # Requests
        requests_qs = (
            FeatureRequest.objects.filter(is_public=True)
            .select_related('user', 'released_in')
            .order_by('-votes_count', '-created_at')[:50]
        )
        voted_ids = set()
        followed_ids = set()
        if licensed:
            voted_ids = set(
                FeatureVote.objects.filter(user=user).values_list('request_id', flat=True)
            )
            followed_ids = set(
                FeatureFollow.objects.filter(user=user).values_list('request_id', flat=True)
            )
        ctx.update({
            'feature_requests': requests_qs,
            'voted_ids': voted_ids,
            'followed_ids': followed_ids,
        })

        # Bugs (public + own)
        bugs = BugReport.objects.filter(is_public=True).select_related('user')[:40]
        ctx['bug_reports'] = bugs

        # Roadmap
        ctx['roadmap'] = stats_svc.get_roadmap_data()

        # My items
        ctx['my_requests'] = FeatureRequest.objects.filter(user=user).order_by('-created_at')[:30]
        ctx['my_bugs'] = BugReport.objects.filter(user=user).order_by('-created_at')[:30]
        ctx['my_follows'] = (
            FeatureFollow.objects.filter(user=user)
            .select_related('request')
            .order_by('-created_at')[:20]
        )
        return ctx


class FeatureRequestCreateView(WorkspaceLoginMixin, LicenseActionMixin, View):
    def post(self, request):
        denied = self.require_license(request)
        if denied:
            return denied
        form = FeatureRequestForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            # auto-follow + auto-vote own request
            FeatureVote.objects.get_or_create(request=obj, user=request.user)
            FeatureFollow.objects.get_or_create(request=obj, user=request.user)
            obj.votes_count = 1
            obj.follows_count = 1
            obj.save(update_fields=['votes_count', 'follows_count'])
            messages.success(request, 'پیشنهاد شما ثبت شد.')
            return redirect(reverse('workspace:product_hub:hub') + '?tab=requests')
        messages.error(request, 'لطفاً فرم پیشنهاد را کامل کنید.')
        return redirect(reverse('workspace:product_hub:hub') + '?tab=requests')


class BugReportCreateView(WorkspaceLoginMixin, LicenseActionMixin, View):
    def post(self, request):
        denied = self.require_license(request)
        if denied:
            return denied
        form = BugReportForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            messages.success(request, 'گزارش مشکل ثبت شد.')
            return redirect(reverse('workspace:product_hub:hub') + '?tab=bugs')
        messages.error(request, 'لطفاً فرم گزارش باگ را کامل کنید.')
        return redirect(reverse('workspace:product_hub:hub') + '?tab=bugs')


class FeatureVoteToggleView(WorkspaceLoginMixin, LicenseActionMixin, View):
    def post(self, request, pk):
        denied = self.require_license(request)
        if denied:
            return denied
        obj = get_object_or_404(FeatureRequest, pk=pk, is_public=True)
        voted, count = workflow_svc.toggle_vote(obj, request.user)
        if _wants_json(request):
            return JsonResponse({'ok': True, 'voted': voted, 'votes_count': count})
        return redirect(reverse('workspace:product_hub:hub') + '?tab=requests')


class FeatureFollowToggleView(WorkspaceLoginMixin, LicenseActionMixin, View):
    def post(self, request, pk):
        denied = self.require_license(request)
        if denied:
            return denied
        obj = get_object_or_404(FeatureRequest, pk=pk, is_public=True)
        following, count = workflow_svc.toggle_follow(obj, request.user)
        if _wants_json(request):
            return JsonResponse({'ok': True, 'following': following, 'follows_count': count})
        return redirect(reverse('workspace:product_hub:hub') + '?tab=requests')


class NotificationsView(WorkspaceLoginMixin, TemplateView):
    template_name = 'workspace/product_hub/notifications.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['notifications'] = ProductHubNotification.objects.filter(
            user=self.request.user,
        )[:50]
        return ctx


class NotificationMarkReadView(WorkspaceLoginMixin, View):
    def post(self, request, pk=None):
        if pk:
            notif_svc.mark_read(request.user, pk)
        else:
            notif_svc.mark_all_read(request.user)
        if _wants_json(request):
            return JsonResponse({'ok': True, 'unread': notif_svc.unread_count(request.user)})
        return redirect('workspace:product_hub:notifications')


class NotificationUnreadCountView(WorkspaceLoginMixin, View):
    def get(self, request):
        return JsonResponse({'unread': notif_svc.unread_count(request.user)})


# ─── Staff manage ───────────────────────────────────────────

class ManageDashboardView(WorkspaceLoginMixin, StaffRequiredMixin, TemplateView):
    template_name = 'workspace/product_hub/manage/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['manage_stats'] = stats_svc.get_manage_stats()
        ctx['pending_requests'] = FeatureRequest.objects.filter(
            status__in=('submitted', 'reviewing', 'approved', 'in_development'),
        ).select_related('user')[:30]
        ctx['open_bugs'] = BugReport.objects.exclude(
            status='resolved',
        ).select_related('user')[:30]
        ctx['releases'] = ProductRelease.objects.all()[:10]
        return ctx


class ManageRequestDetailView(WorkspaceLoginMixin, StaffRequiredMixin, TemplateView):
    template_name = 'workspace/product_hub/manage/request_detail.html'

    def get_object(self):
        return get_object_or_404(
            FeatureRequest.objects.select_related('user', 'released_in', 'linked_feature'),
            pk=self.kwargs['pk'],
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.get_object()
        ctx['req'] = obj
        ctx['status_logs'] = obj.status_logs.select_related('actor')[:30]
        ctx['status_form'] = FeatureRequestStatusForm(initial={
            'status': obj.status,
            'released_in': obj.released_in_id,
            'release_note': obj.release_note,
            'linked_feature': obj.linked_feature_id,
            'note': obj.staff_note,
        })
        return ctx

    def post(self, request, pk):
        obj = self.get_object()
        form = FeatureRequestStatusForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'فرم وضعیت نامعتبر است.')
            return redirect('workspace:product_hub:manage_request', pk=pk)
        data = form.cleaned_data
        try:
            workflow_svc.change_request_status(
                obj,
                to_status=data['status'],
                actor=request.user,
                note=data.get('note') or '',
                released_in=data.get('released_in'),
                release_note=data.get('release_note') or '',
                linked_feature=data.get('linked_feature'),
            )
            messages.success(request, 'وضعیت پیشنهاد به‌روز شد.')
        except workflow_svc.WorkflowError as exc:
            messages.error(request, str(exc))
        return redirect('workspace:product_hub:manage_request', pk=pk)


class ManageBugDetailView(WorkspaceLoginMixin, StaffRequiredMixin, TemplateView):
    template_name = 'workspace/product_hub/manage/bug_detail.html'

    def get_object(self):
        return get_object_or_404(BugReport.objects.select_related('user'), pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.get_object()
        ctx['bug'] = obj
        ctx['status_form'] = BugReportStatusForm(initial={
            'status': obj.status,
            'note': obj.staff_note,
            'resolution_note': obj.resolution_note,
        })
        return ctx

    def post(self, request, pk):
        obj = self.get_object()
        form = BugReportStatusForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'فرم وضعیت نامعتبر است.')
            return redirect('workspace:product_hub:manage_bug', pk=pk)
        data = form.cleaned_data
        try:
            workflow_svc.change_bug_status(
                obj,
                to_status=data['status'],
                actor=request.user,
                note=data.get('note') or '',
                resolution_note=data.get('resolution_note') or '',
            )
            messages.success(request, 'وضعیت باگ به‌روز شد.')
        except workflow_svc.WorkflowError as exc:
            messages.error(request, str(exc))
        return redirect('workspace:product_hub:manage_bug', pk=pk)


class ManageReleasesView(WorkspaceLoginMixin, StaffRequiredMixin, TemplateView):
    template_name = 'workspace/product_hub/manage/releases.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['releases'] = ProductRelease.objects.prefetch_related('changes').all()
        ctx['release_form'] = ProductReleaseForm()
        ctx['change_formset'] = ReleaseChangeFormSet()
        return ctx

    def post(self, request):
        form = ProductReleaseForm(request.POST)
        formset = ReleaseChangeFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            release = form.save(commit=False)
            release.created_by = request.user
            release.save()
            formset.instance = release
            formset.save()
            messages.success(request, f'نسخه {release.version} ثبت شد.')
            return redirect('workspace:product_hub:manage_releases')
        messages.error(request, 'خطا در ثبت نسخه. فیلدها را بررسی کنید.')
        ctx = self.get_context_data()
        ctx['release_form'] = form
        ctx['change_formset'] = formset
        return self.render_to_response(ctx)


class ManageReleaseEditView(WorkspaceLoginMixin, StaffRequiredMixin, TemplateView):
    template_name = 'workspace/product_hub/manage/release_edit.html'

    def get_object(self):
        return get_object_or_404(ProductRelease, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        release = self.get_object()
        ctx['release'] = release
        ctx['release_form'] = ProductReleaseForm(instance=release)
        ctx['change_formset'] = ReleaseChangeFormSet(instance=release)
        return ctx

    def post(self, request, pk):
        release = self.get_object()
        form = ProductReleaseForm(request.POST, instance=release)
        formset = ReleaseChangeFormSet(request.POST, instance=release)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'نسخه به‌روز شد.')
            return redirect('workspace:product_hub:manage_releases')
        messages.error(request, 'خطا در ویرایش نسخه.')
        ctx = self.get_context_data()
        ctx['release_form'] = form
        ctx['change_formset'] = formset
        return self.render_to_response(ctx)


class ManageFeaturesView(WorkspaceLoginMixin, StaffRequiredMixin, TemplateView):
    template_name = 'workspace/product_hub/manage/features.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['features'] = ProductFeature.objects.all()
        ctx['feature_form'] = ProductFeatureForm()
        return ctx

    def post(self, request):
        form = ProductFeatureForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'قابلیت ثبت شد.')
            return redirect('workspace:product_hub:manage_features')
        messages.error(request, 'خطا در ثبت قابلیت.')
        ctx = self.get_context_data()
        ctx['feature_form'] = form
        return self.render_to_response(ctx)
