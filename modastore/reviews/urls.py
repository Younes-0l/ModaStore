from django.urls import path
from . import views


app_name = 'reviews'

urlpatterns = [
    path('product/<str:slug>/write/', views.review_write, name='write'),
    path('<int:pk>/delete/', views.review_delete, name='delete'),
    path('<int:pk>/helpful/', views.review_helpful, name='helpful'),
]