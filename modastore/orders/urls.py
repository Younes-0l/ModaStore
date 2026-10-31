from django.urls import path
from . import views


app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout_address, name='checkout'),
    path('checkout/review/', views.checkout_review, name='review'),
    path('checkout/pay/<str:number>/', views.pay, name='pay'),
    path('checkout/cancel/<str:number>/', views.cancel, name='cancel'),
    path('checkout/result/<str:number>/', views.result, name='result'),
    path('payment/gateway/<str:authority>/', views.mock_gateway, name='mock_gateway'),
    path('orders/', views.order_list, name='list'),
    path('orders/<str:number>/', views.order_detail, name='detail'),
]