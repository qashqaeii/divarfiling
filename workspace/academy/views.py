"""Viewهای آکادمی workspace."""
from __future__ import annotations

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView

from workspace.academy.curriculum import active_paths_qs
from workspace.academy.models import AcademyVideo, LearningPath
from workspace.academy.services.academy_service import (
    get_home_context,
    get_path_context,
    get_video_context,
    user_can_access_path,
)
from workspace.mixins import WorkspaceLoginMixin


class AcademyHomeView(WorkspaceLoginMixin, TemplateView):
    template_name = 'workspace/academy/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(get_home_context(self.request.user))
        ctx['academy_section'] = 'home'
        return ctx


class AcademyMissionView(WorkspaceLoginMixin, TemplateView):
    """ماموریت قدیمی — redirect به خانه آکادمی."""

    def get(self, request, *args, **kwargs):
        return redirect('workspace:academy_home')


class AcademyPathView(WorkspaceLoginMixin, TemplateView):
    template_name = 'workspace/academy/path.html'

    def get_context_data(self, **kwargs):
        path = get_object_or_404(LearningPath, slug=kwargs['slug'], is_active=True)
        ctx = super().get_context_data(**kwargs)
        active_slug = self.request.GET.get('v')
        ctx.update(get_path_context(self.request.user, path, active_slug=active_slug))
        ctx['academy_section'] = 'path'
        return ctx

    def get(self, request, *args, **kwargs):
        path = get_object_or_404(LearningPath, slug=kwargs['slug'], is_active=True)
        if path.slug not in {p.slug for p in active_paths_qs()}:
            messages.info(request, 'این مسیر آموزشی دیگر در دسترس نیست.')
            return redirect('workspace:academy_home')
        if not user_can_access_path(request.user, path):
            messages.info(request, 'این مسیر یادگیری برای نقش شما در دسترس نیست.')
            return redirect('workspace:academy_home')
        return super().get(request, *args, **kwargs)


class AcademyVideoView(TemplateView):
    template_name = 'workspace/academy/video.html'

    def get_context_data(self, **kwargs):
        video = get_object_or_404(AcademyVideo, slug=kwargs['slug'], is_active=True)
        user = self.request.user
        ctx = super().get_context_data(**kwargs)
        if not video.is_public:
            if not user.is_authenticated:
                return redirect('login')
        if not video.is_public and not user_can_access_path(user, video.path):
            raise Http404
        vctx = get_video_context(user, video, public_ok=video.is_public)
        if not vctx:
            raise Http404
        ctx.update(vctx)
        ctx['context_key'] = self.request.GET.get('context', '')
        ctx['academy_section'] = 'video'
        return ctx

    def dispatch(self, request, *args, **kwargs):
        video = get_object_or_404(AcademyVideo, slug=kwargs['slug'], is_active=True)
        if not video.is_public and not request.user.is_authenticated:
            return redirect('login')
        if not video.is_public and request.user.is_authenticated:
            if not user_can_access_path(request.user, video.path):
                raise Http404
        return super().dispatch(request, *args, **kwargs)


class AcademyTraditionalPathView(WorkspaceLoginMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        return redirect('workspace:academy_home')
