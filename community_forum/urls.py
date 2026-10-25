"""URLهای تالار گفتگو."""
from django.urls import path

from community_forum import api_views, views

app_name = 'community_forum'

urlpatterns = [
    path('', views.ForumPageView.as_view(), name='home'),
    path('api/bootstrap/', api_views.ForumBootstrapAPIView.as_view(), name='api_bootstrap'),
    path('api/messages/', api_views.ForumMessagesAPIView.as_view(), name='api_messages'),
    path('api/messages/<int:message_id>/', api_views.ForumMessageDetailAPIView.as_view(), name='api_message_detail'),
    path('api/messages/<int:message_id>/reactions/', api_views.ForumReactionAPIView.as_view(), name='api_reaction'),
    path('api/messages/<int:message_id>/report/', api_views.ForumReportAPIView.as_view(), name='api_report'),
    path('api/read/', api_views.ForumReadAPIView.as_view(), name='api_read'),
    path('api/search/', api_views.ForumSearchAPIView.as_view(), name='api_search'),
    path('api/profile/', api_views.ForumProfileAPIView.as_view(), name='api_profile'),
    path('api/unread/', api_views.ForumUnreadAPIView.as_view(), name='api_unread'),
    path('api/sync/', api_views.ForumSyncAPIView.as_view(), name='api_sync'),
]
