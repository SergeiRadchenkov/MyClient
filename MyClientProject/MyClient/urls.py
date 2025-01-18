from django.urls import path
from . import views

urlpatterns = [
    path('', views.schedule, name='schedule'),
    path('schedule/', views.schedule, name='schedule'),
    path('clients/', views.clients, name='clients'),
    path('profile/', views.profile, name='profile'),
    path('blocks/', views.blocks, name='blocks'),
    path('auth/', views.auth_redirect, name='auth'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
]
