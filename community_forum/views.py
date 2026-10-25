"""صفحه تالار گفتگو."""
from django.http import Http404

from workspace.mixins import WorkspaceLoginMixin
from django.views.generic import TemplateView

from community_forum.services.access import user_can_access_forum


class ForumPageView(WorkspaceLoginMixin, TemplateView):
    template_name = 'community_forum/forum.html'

    def dispatch(self, request, *args, **kwargs):
        if not user_can_access_forum(request.user):
            raise Http404()
        return super().dispatch(request, *args, **kwargs)
