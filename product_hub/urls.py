"""URLهای مرکز توسعه محصول."""
from django.urls import path

from product_hub import views

app_name = 'product_hub'

urlpatterns = [
    path('', views.ProductHubView.as_view(), name='hub'),
    path('requests/create/', views.FeatureRequestCreateView.as_view(), name='request_create'),
    path('requests/<int:pk>/vote/', views.FeatureVoteToggleView.as_view(), name='request_vote'),
    path('requests/<int:pk>/follow/', views.FeatureFollowToggleView.as_view(), name='request_follow'),
    path('bugs/create/', views.BugReportCreateView.as_view(), name='bug_create'),
    path('notifications/', views.NotificationsView.as_view(), name='notifications'),
    path('notifications/mark-read/', views.NotificationMarkReadView.as_view(), name='notifications_mark_all'),
    path('notifications/<int:pk>/mark-read/', views.NotificationMarkReadView.as_view(), name='notification_mark'),
    path('notifications/unread-count/', views.NotificationUnreadCountView.as_view(), name='notifications_unread'),

    path('manage/', views.ManageDashboardView.as_view(), name='manage'),
    path('manage/requests/<int:pk>/', views.ManageRequestDetailView.as_view(), name='manage_request'),
    path('manage/bugs/<int:pk>/', views.ManageBugDetailView.as_view(), name='manage_bug'),
    path('manage/releases/', views.ManageReleasesView.as_view(), name='manage_releases'),
    path('manage/releases/<int:pk>/', views.ManageReleaseEditView.as_view(), name='manage_release_edit'),
    path('manage/features/', views.ManageFeaturesView.as_view(), name='manage_features'),
]
