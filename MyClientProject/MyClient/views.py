'''views.py'''
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import re
from django.core.exceptions import ValidationError
from .models import Profile, Client
from .forms import CustomUserChangeForm, ClientForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404
from django.http import JsonResponse


@login_required
def schedule(request):
    if not request.user.is_authenticated:
        return redirect('auth')
    return render(request, 'MyClient/schedule.html')

@login_required
def clients(request):
    search_query = request.GET.get('search', '').strip().lower()  # Удаляем лишние пробелы
    sort_by = request.GET.get('sort', '')

    clients = Client.objects.all().order_by('-created_at')  # Новые клиенты сверху
    results = []

    if search_query:
        # Разделяем запрос на слова (например, "Иван Иванов")
        search_terms = search_query.split()
        if len(search_terms) == 2:  # Если два слова (имя и фамилия)
            first_name, last_name = search_terms
            for client in clients:
                if first_name in client.first_name.lower() and last_name in client.last_name.lower():
                    results.append({
                        'id': client.id,
                        'first_name': client.first_name,
                        'last_name': client.last_name,
                        'metro': client.metro,
                        'street': client.street,
                        'house_number': client.house_number,
                        'entrance': client.entrance,
                        'floor': client.floor,
                    })
        else:  # Если одно слово или больше двух
            for client in clients:
                if any(term in client.first_name.lower() for term in search_terms) or \
                        any(term in client.last_name.lower() for term in search_terms) or \
                        any(term in client.metro.lower() for term in search_terms) or \
                        any(term in client.street.lower() for term in search_terms):
                    results.append({
                        'id': client.id,
                        'first_name': client.first_name,
                        'last_name': client.last_name,
                        'metro': client.metro,
                        'street': client.street,
                        'house_number': client.house_number,
                        'entrance' : client.entrance,
                        'floor': client.floor,
                    })
        return render(request, 'MyClient/clients.html', {'clients': results})


    def get_key_func(field):
        def key_func(client):
            value = getattr(client, field, "").lower()  # Преобразуем в нижний регистр
            return value
        return key_func

    # Проверка на допустимые поля для сортировки
    valid_sort_fields = ['first_name', 'last_name', 'metro',
                         'street', 'created_at', 'price_online', 'price_offline']
    if sort_by and sort_by in valid_sort_fields:
        if sort_by == 'price_online':
            clients = clients.order_by('-price_online')
        elif sort_by == 'price_offline':
            clients = clients.order_by('-price_offline')
        else:
            sort_key = get_key_func(sort_by)
            clients = quicksort(clients, sort_key)
    else:
        # Если сортировка не указана или указано неправильное поле, по умолчанию сортировка по created_at
        clients = clients.order_by('-created_at')

    return render(request, 'MyClient/clients.html', {'clients': clients})


def autocomplete(request):
    query = request.GET.get('query', '').lower()
    results = Client.objects.all()  # Получаем всех клиентов
    clients = []

    for result in results:
        # Приводим к нижнему регистру и проверяем наличие подстроки в нужных полях
        if (query in result.first_name.lower() or
                query in result.last_name.lower() or
                query in result.metro.lower() or
                query in result.street.lower()):
            # Добавляем клиента в список
            clients.append({
                'id': result.id,
                'name': f'{result.first_name} {result.last_name}, метро {result.metro}, улица {result.street}'
            })

    # Возвращаем результат в формате JSON
    return JsonResponse(clients, safe=False)


@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    return render(request, 'MyClient/client_detail.html', {'client': client})


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


@login_required
def add_client(request):
    # Чтение станций метро из файла
    metro_stations = []
    try:
        # Открытие файла и чтение станций метро
        with open('metro_stations.txt', 'r', encoding='utf-8') as f:
            metro_stations = [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        # В случае если файл не найден
        messages.error(request, 'Файл с метростанциями не найден.')

    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('clients')
        else:
            messages.error(request, 'Ошибка при добавлении клиента. Проверьте данные.')
    else:
        form = ClientForm()
    return render(request, 'MyClient/add_client.html', {'form': form,
                                                        'metro_stations': metro_stations})


def quicksort(arr, key_func, reverse=False):
    if len(arr) <= 1:
        return arr
    pivot = arr[0]
    less = [x for x in arr[1:] if key_func(x) <= key_func(pivot)]
    greater = [x for x in arr[1:] if key_func(x) > key_func(pivot)]
    if reverse:
        return quicksort(greater, key_func, reverse) + [pivot] + quicksort(less, key_func, reverse)
    else:
        return quicksort(less, key_func, reverse) + [pivot] + quicksort(greater, key_func, reverse)
