"""
URLهای پرداخت
"""
from django.urls import path
from . import payment_views

app_name = 'payment'

urlpatterns = [
    path('checkout/<uuid:order_id>/', payment_views.PaymentCheckoutView.as_view(), name='checkout'),
    path('initiate/<uuid:order_id>/', payment_views.PaymentInitiateView.as_view(), name='initiate'),
    path('card/<uuid:order_id>/', payment_views.CardTransferView.as_view(), name='card_transfer'),
    path('card/<uuid:order_id>/pending/', payment_views.CardTransferPendingView.as_view(), name='card_pending'),
    path('callback/', payment_views.PaymentCallbackView.as_view(), name='callback'),
    path('success/<uuid:order_id>/', payment_views.PaymentSuccessView.as_view(), name='success'),
    path('download/<uuid:order_id>/', payment_views.OrderDownloadView.as_view(), name='download'),
    path('failed/', payment_views.PaymentFailedView.as_view(), name='failed'),
]

