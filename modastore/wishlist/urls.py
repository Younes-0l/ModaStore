from django.urls import path
from . import views


app_name = 'wishlist'

urlpatterns = [
    path('', views.wishlist_list, name='list'),
    path('set/', views.wishlist_set, name='set'),
]