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
    path('clients/add/', views.add_client, name='add_client'),
    path('clients/<int:client_id>/', views.client_detail, name='client_detail'),
    path('clients/', views.clients, name='clients'),
    path('autocomplete/', views.autocomplete, name='autocomplete'),
    path('client/<int:client_id>/', views.client_settings, name='client_settings'),
    path('clients/<int:client_id>/edit/', views.edit_client, name='edit_client'),
    path('clients/<int:client_id>/delete/', views.delete_client, name='delete_client'),
    path('add_schedule/', views.add_schedule, name='add_schedule'),
    path('get_client_cost/<int:client_id>/', views.get_client_cost, name='get_client_cost'),
]
