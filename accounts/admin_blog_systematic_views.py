"""ویوهای مقالات سیستماتیک — پنل ادمین بلاگ."""
from __future__ import annotations

import json

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from accounts.admin_views import StaffRequiredMixin
from blog.models import MarketArticleRun
from blog.services.market_article_eligibility import (
    count_eligible_datasets,
    filter_options,
    list_eligible_datasets,
)
from blog.services.market_article_pipeline import (
    MarketArticleError,
    build_preview,
    create_draft,
    preview_context,
    save_seo_edits,
    update_existing_post,
)
from workspace.models import Dataset
from workspace.views import DatasetAnalyzeView


class AdminBlogSystematicListView(StaffRequiredMixin, TemplateView):
    template_name = 'accounts/admin_blog_systematic.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        req = self.request.GET
        try:
            page = int(req.get('page') or 1)
        except (TypeError, ValueError):
            page = 1
        try:
            min_rows = int(req.get('min_rows') or 100)
        except (TypeError, ValueError):
            min_rows = 100

        listing = list_eligible_datasets(
            city=req.get('city', ''),
            district=req.get('district', ''),
            transaction_type=req.get('transaction_type', ''),
            subcategory=req.get('subcategory', ''),
            article_status=req.get('article_status', ''),
            min_rows=max(100, min_rows),
            sort=req.get('sort') or 'rows',
            page=page,
        )
        ctx.update(listing)
        ctx['filter_options'] = filter_options()
        ctx['eligible_total'] = count_eligible_datasets()
        return ctx


class AdminBlogSystematicBuildPreviewView(StaffRequiredMixin, View):
    def post(self, request, dataset_id):
        dataset = get_object_or_404(Dataset, pk=dataset_id, is_active=True)
        try:
            run = build_preview(dataset, request.user)
        except MarketArticleError as exc:
            messages.error(request, str(exc))
            return redirect('admin_panel_blog_systematic')
        except Exception as exc:  # noqa: BLE001 — surface to admin
            messages.error(request, f'خطا در ساخت پیش‌نمایش: {exc}')
            return redirect('admin_panel_blog_systematic')
        messages.success(request, 'پیش‌نمایش مقاله ساخته شد.')
        return redirect('admin_panel_blog_systematic_preview', run_id=run.pk)


class AdminBlogSystematicPreviewView(StaffRequiredMixin, TemplateView):
    template_name = 'accounts/admin_blog_systematic_preview.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        run = get_object_or_404(MarketArticleRun, pk=self.kwargs['run_id'])
        ctx.update(preview_context(run))
        ctx['schema_preview'] = json.dumps(
            {
                '@type': 'Article',
                'headline': ctx['title'],
                'description': ctx['excerpt'],
                'dateModified': run.updated_at.isoformat() if run.updated_at else None,
            },
            ensure_ascii=False,
            indent=2,
        )
        return ctx


class AdminBlogSystematicSeoView(StaffRequiredMixin, View):
    def post(self, request, run_id):
        run = get_object_or_404(MarketArticleRun, pk=run_id)
        save_seo_edits(
            run,
            title=request.POST.get('title', ''),
            excerpt=request.POST.get('excerpt', ''),
            slug=request.POST.get('slug') or None,
        )
        messages.success(request, 'اطلاعات SEO ذخیره شد.')
        return redirect('admin_panel_blog_systematic_preview', run_id=run.pk)


class AdminBlogSystematicDraftView(StaffRequiredMixin, View):
    def post(self, request, run_id):
        run = get_object_or_404(MarketArticleRun, pk=run_id)
        # Persist SEO from form if posted together
        if request.POST.get('title') or request.POST.get('excerpt'):
            save_seo_edits(
                run,
                title=request.POST.get('title', ''),
                excerpt=request.POST.get('excerpt', ''),
                slug=request.POST.get('slug') or None,
            )
            run.refresh_from_db()
        try:
            post = create_draft(run, request.user)
        except MarketArticleError as exc:
            messages.error(request, str(exc))
            return redirect('admin_panel_blog_systematic_preview', run_id=run.pk)
        messages.success(request, f'پیش‌نویس «{post.title}» ایجاد شد.')
        return redirect('admin_panel_blog_systematic_preview', run_id=run.pk)


class AdminBlogSystematicUpdatePostView(StaffRequiredMixin, View):
    def post(self, request, run_id):
        run = get_object_or_404(MarketArticleRun, pk=run_id)
        if request.POST.get('title') or request.POST.get('excerpt'):
            save_seo_edits(
                run,
                title=request.POST.get('title', ''),
                excerpt=request.POST.get('excerpt', ''),
            )
            run.refresh_from_db()
        try:
            post = update_existing_post(run)
        except MarketArticleError as exc:
            messages.error(request, str(exc))
            return redirect('admin_panel_blog_systematic_preview', run_id=run.pk)
        messages.success(request, f'مقاله «{post.title}» به‌روزرسانی شد (اسلاگ ثابت ماند).')
        return redirect('admin_panel_blog_systematic_preview', run_id=run.pk)


class AdminBlogSystematicRebuildView(StaffRequiredMixin, View):
    def post(self, request, run_id):
        old = get_object_or_404(MarketArticleRun, pk=run_id)
        dataset = old.dataset
        old.status = MarketArticleRun.Status.DISCARDED
        old.save(update_fields=['status', 'updated_at'])
        try:
            run = build_preview(dataset, request.user)
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f'خطا در تولید مجدد: {exc}')
            return redirect('admin_panel_blog_systematic')
        messages.success(request, 'پیش‌نمایش دوباره ساخته شد.')
        return redirect('admin_panel_blog_systematic_preview', run_id=run.pk)


class StaffDatasetAnalyzeView(StaffRequiredMixin, DatasetAnalyzeView):
    """مشاهده تحلیل هر دیتاست برای staff — بدون مالکیت."""

    def get_dataset(self):
        return get_object_or_404(Dataset, pk=self.kwargs['dataset_id'])

    def dispatch(self, request, *args, **kwargs):
        # Bypass LicenseRequiredMixin / DatasetOwnerMixin — staff only
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            return self.handle_no_permission()
        return TemplateView.dispatch(self, request, *args, **kwargs)
