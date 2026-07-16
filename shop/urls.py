"""
URLهای فروشگاه
"""
from django.urls import path, include
from . import notice_views, views
from .seo_landings import landing_urlpatterns

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('', include('shop.platform.urls')),
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<slug:slug>/buy/', views.BuyView.as_view(), name='buy'),
    path('products/<slug:slug>/apply-discount/', views.apply_discount_code, name='apply_discount'),
    path('products/<slug:slug>/rating/', views.submit_rating, name='submit_rating'),
    path('products/<slug:slug>/review/', views.submit_review, name='submit_review'),
    path('reviews/<int:review_id>/helpful/', views.mark_review_helpful, name='mark_review_helpful'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('contact/', views.ContactView.as_view(), name='contact'),
    path('terms/', views.TermsView.as_view(), name='terms'),
    path('license-guide/', views.LicenseGuideView.as_view(), name='license_guide'),
    path('download/android/', views.AndroidAppDownloadView.as_view(), name='android_app_download'),
    path('amoozesh/', views.EducationView.as_view(), name='education'),
    path('amoozesh/android/', views.AndroidTutorialView.as_view(), name='android_tutorial'),
    path('author/hossein-qashqaeii/', views.AuthorPageView.as_view(), name='author_hossein_qashqaeii'),
    path('66998772.txt', views.verification_file, name='verification_file'),
    path('api/notices/dismiss/', notice_views.DismissNoticeView.as_view(), name='dismiss_notice'),
] + landing_urlpatterns()

