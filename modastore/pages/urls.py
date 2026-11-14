from django.urls import path
from django.views.generic import TemplateView
from . import views


app_name = 'pages'

urlpatterns = [
    path('about/', TemplateView.as_view(template_name='pages/about.html'), name='about'),
    path('contact/', views.contact, name='contact'),
    path('faq/', TemplateView.as_view(template_name='pages/faq.html'), name='faq'),
    path('terms/', TemplateView.as_view(template_name='pages/terms.html'), name='terms'),
    path('returns/', TemplateView.as_view(template_name='pages/returns.html'), name='returns'),
]
