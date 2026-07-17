"""
URLهای بلاگ
"""
from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'blog'

# slugهای کوتاه/قدیمی → slug منتشرشده (جلوگیری از 404 در ایندکس و لینک‌های داخلی)
BLOG_SLUG_REDIRECTS = {
    'gheymat-robot-estekhraj-divar-roi': 'gheymat-robot-estekhraj-divar-roi-rahnama',
    'agency-tv-dashboard-amlak': 'agency-tv-dashboard-ajans-amlak',
    'malke-vaghei-moshaver-penhan': 'tashkhis-malek-vaghei-divar-rahnama',
}

urlpatterns = [
    path('', views.PostListView.as_view(), name='post_list'),
    *[
        path(
            f'{old}/',
            RedirectView.as_view(
                url=f'/blog/{new}/',
                permanent=True,
            ),
            name=f'redirect_{old.replace("-", "_")}',
        )
        for old, new in BLOG_SLUG_REDIRECTS.items()
    ],
    path('<slug:slug>/', views.PostDetailView.as_view(), name='post_detail'),
]

