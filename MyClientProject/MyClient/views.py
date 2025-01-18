from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages

def schedule(request):
    if not request.user.is_authenticated:
        return redirect('auth')
    return render(request, 'MyClient/schedule.html')

def clients(request):
    return render(request, 'MyClient/clients.html')

def profile(request):
    return render(request, 'MyClient/profile.html')

def blocks(request):
    return render(request, 'MyClient/blocks.html')

def auth_redirect(request):
    if request.user.is_authenticated:
        return redirect('schedule')
    return render(request, 'auth/auth_home.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST['email']
        password = request.POST['password']
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            return redirect('schedule')
        else:
            messages.error(request, 'Неправильный логин или пароль')
    return render(request, 'auth/login.html')

def register_view(request):
    if request.method == 'POST':
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        specialty = request.POST['specialty']
        email = request.POST['email']
        password = request.POST['password']
        password2 = request.POST['password2']
        if password == password2:
            try:
                user = User.objects.create_user(
                    username=email, email=email, password=password,
                    first_name=first_name, last_name=last_name
                )
                user.save()
                messages.success(request, 'Регистрация успешна!')
                return redirect('login')
            except:
                messages.error(request, 'Пользователь уже существует')
        else:
            messages.error(request, 'Пароли не совпадают')
    return render(request, 'auth/register.html')