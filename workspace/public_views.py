"""ویوهای عمومی اشتراک‌گذاری آگهی — بدون احراز هویت."""
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.generic import DetailView

from workspace.models import CRMPropertyPublicShare, ListingPublicShare
from workspace.services.listing_public_share import build_public_listing_context, record_share_view
from workspace.services.property_public_share import (
    build_public_property_context,
    record_property_share_view,
)


class PublicListingShareView(DetailView):
    """صفحه عمومی نمایش آگهی برای مشتری."""
    model = ListingPublicShare
    template_name = 'workspace/public/listing_share.html'
    context_object_name = 'share'
    slug_field = 'share_token'
    slug_url_kwarg = 'share_token'

    def get_queryset(self):
        return ListingPublicShare.objects.select_related(
            'listing', 'listing__dataset', 'created_by',
        )

    def get_object(self, queryset=None):
        obj = get_object_or_404(
            self.get_queryset(),
            share_token=self.kwargs.get(self.slug_url_kwarg),
        )
        if not obj.listing or not obj.listing.dataset.is_active:
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        share = self.object
        if share.is_active:
            record_share_view(share)
            share.refresh_from_db(fields=['view_count', 'last_viewed_at'])
        ctx.update(build_public_listing_context(share, self.request))
        return ctx

    def render_to_response(self, context, **response_kwargs):
        share = context.get('share')
        if share and not share.is_active:
            return render(
                self.request,
                'workspace/public/listing_share_inactive.html',
                context,
                status=410,
            )
        return super().render_to_response(context, **response_kwargs)


class PublicPropertyShareView(DetailView):
    """صفحه عمومی فایل شخصی CRM برای مشتری."""
    model = CRMPropertyPublicShare
    template_name = 'workspace/public/listing_share.html'
    context_object_name = 'share'
    slug_field = 'share_token'
    slug_url_kwarg = 'share_token'

    def get_queryset(self):
        return CRMPropertyPublicShare.objects.select_related(
            'property', 'created_by',
        )

    def get_object(self, queryset=None):
        obj = get_object_or_404(
            self.get_queryset(),
            share_token=self.kwargs.get(self.slug_url_kwarg),
        )
        if not obj.property or obj.property.deleted_at is not None:
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        share = self.object
        if share.is_active:
            record_property_share_view(share)
            share.refresh_from_db(fields=['view_count', 'last_viewed_at'])
        ctx.update(build_public_property_context(share, self.request))
        return ctx

    def render_to_response(self, context, **response_kwargs):
        share = context.get('share')
        if share and not share.is_active:
            return render(
                self.request,
                'workspace/public/listing_share_inactive.html',
                context,
                status=410,
            )
        return super().render_to_response(context, **response_kwargs)
