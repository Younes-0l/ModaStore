from django.urls import path
from . import views


app_name = 'catalog'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('products/', views.ProductListView.as_view(), name='product_list'),
    # <str:...> because slugs can contain Persian characters
    path('category/<str:category_slug>/', views.ProductListView.as_view(), name='category'),
    path('product/<str:slug>/', views.ProductDetailView.as_view(), name='product_detail'),
]