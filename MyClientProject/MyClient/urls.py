from django.urls import path
from . import views

urlpatterns = [
    path('', views.schedule, name='schedule'),
    path('schedule/', views.schedule, name='schedule'),
    path('clients/', views.clients, name='clients'),
    path('profile/', views.profile, name='profile'),
    path('blocks/', views.blocks, name='blocks'),
    path('auth/', views.auth_redirect, name='auth'),
    path('accounts/login/', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('settings/', views.settings_view, name='settings'),
    path('edit_profile/', views.edit_profile, name='edit_profile'),
    path('delete_profile/', views.delete_profile, name='delete_profile'),
    path('logout/', views.logout_view, name='logout'),
    path('reset-password/', views.reset_password, name='reset_password'),
]
