"""URLهای عمومی اشتراک آگهی."""
from django.urls import path

from workspace import public_views

app_name = 'listing_public'

urlpatterns = [
    path('<str:share_token>/', public_views.PublicListingShareView.as_view(), name='view'),
]
