from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserChangeForm
import re
from django.core.exceptions import ValidationError
from .models import Profile
from .forms import CustomUserChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm


@login_required
def schedule(request):
    if not request.user.is_authenticated:
        return redirect('auth')
    return render(request, 'MyClient/schedule.html')

@login_required
def clients(request):
    return render(request, 'MyClient/clients.html')

@login_required
def profile(request):
    user = request.user
    if not hasattr(user, 'profile'):
        # Создаем профиль, если его нет
        Profile.objects.create(user=user)
    profile = user.profile  # Связанный профиль
    context = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'specialization': profile.specialization,
        'email': user.email,  # Используем email
        'profile': profile,
        'show_settings_btn': True,  # Шестерёнка видна
    }
    return render(request, 'MyClient/profile.html', context)

@login_required
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
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        specialty = request.POST.get('specialty', '')
        email = request.POST.get('email', '')
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        if password == password2:
            try:
                if User.objects.filter(username=email).exists():
                    messages.error(request, 'Пользователь с таким логином уже существует.')
                    return render(request, 'auth/register.html', {
                        'email': email, 'first_name': first_name,
                        'last_name': last_name, 'specialty': specialty})

                    # Проверка сложности пароля (если используется)
                check_password_complexity(password)
                user = User.objects.create_user(
                    username=email, password=password,
                    first_name=first_name, last_name=last_name
                )
                user.save()
                # Проверка на существование профиля и создание нового профиля
                if not hasattr(user, 'profile'):
                    Profile.objects.create(user=user, specialization=specialty)
                else:
                    # Если профиль уже существует, можно обновить данные
                    user.profile.specialization = specialty
                    user.profile.save()
                login(request, user)
                return redirect('schedule')
            except ValidationError as e:
                messages.error(request, ", ".join(e.messages))
        else:
            messages.error(request, 'Пароли не совпадают')

        # Возврат данных в случае ошибки
        context = {
            'first_name': first_name,
            'last_name': last_name,
            'specialty': specialty,
            'email': email,
        }
        return render(request, 'auth/register.html', context)

    return render(request, 'auth/register.html')


def check_password_complexity(password):
    # Проверка на минимальную длину (например, 8 символов)
    if len(password) < 8:
        raise ValidationError("Пароль должен содержать минимум 8 символов.")

    # Проверка на наличие хотя бы одной заглавной буквы
    if not re.search(r'[A-Z]', password):
        raise ValidationError("Пароль должен содержать хотя бы одну заглавную букву.")

    # Проверка на наличие хотя бы одной цифры
    if not re.search(r'[0-9]', password):
        raise ValidationError("Пароль должен содержать хотя бы одну цифру.")


@login_required
def settings_view(request):
    user = request.user
    return render(request, 'MyClient/settings.html', {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'specialization': user.profile.specialization,
        'email': user.email,
        'show_settings_btn': False,  # Шестерёнка скрыта
    })

@login_required
def edit_profile(request):
    user = request.user
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=request.user)
        if form.is_valid():
            # Обновите или сохраните профайл
            form.save()
            # Обновление поля специализации
            specialization = request.POST.get('specialization')
            user.profile.specialization = specialization
            user.profile.save()
            return redirect('settings')
    else:
        # Передаем специализацию в форму, если пользователь уже имеет профиль
        profile = user.profile
        form = CustomUserChangeForm(instance=request.user)
        form.fields['specialization'].initial = profile.specialization

    return render(request, 'MyClient/edit_profile.html', {'form': form})

@login_required
def delete_profile(request):
    user = request.user
    user.delete()
    logout(request)
    return redirect('auth')

def logout_view(request):
    logout(request)  # Выполняем выход пользователя
    return redirect('auth')  # Перенаправляем на страницу авторизации (или другую страницу)

@login_required
def reset_password(request):
    if request.method == 'POST':
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if password != password2:
            messages.error(request, 'Пароли не совпадают!')
            return render(request, 'MyClient/reset_password.html')

        try:
            check_password_complexity(password)
        except ValidationError as e:
            messages.error(request, ", ".join(e.messages))
            return redirect("reset_password")

        user = request.user
        user.set_password(password)
        user.save()

        # Обновляем сессию
        update_session_auth_hash(request, user)
        return redirect('settings')

    return render(request, 'MyClient/reset_password.html')
