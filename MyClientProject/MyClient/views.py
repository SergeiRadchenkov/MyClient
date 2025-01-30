'''views.py'''
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import re
from django.core.exceptions import ValidationError
from .models import Profile, Client, Schedule
from .forms import CustomUserChangeForm, ClientForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from datetime import date, timedelta, datetime
from django.views.decorators.csrf import csrf_exempt


@login_required
def schedule(request):
    if not request.user.is_authenticated:
        return redirect('auth')

    search_query = request.GET.get('search_client', '').strip().lower()
    start_date_str = request.GET.get('start_date', date.today().strftime('%Y-%m-%d'))
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()

    clients = Client.objects.all()  # Список всех клиентов

    # Определяем диапазон отображаемых дат (9 дней начиная с `start_date`)
    date_range = [start_date + timedelta(days=i) for i in range(9)]

    # Получение расписания
    schedules = Schedule.objects.filter(date__gte=start_date)

    results = []
    if search_query:
        schedules = schedules.filter(client__first_name__icontains=search_query)
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
                        'intercom': client.intercom
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
                        'entrance': client.entrance,
                        'floor': client.floor,
                        'intercom': client.intercom
                    })
            return render(request, 'MyClient/clients.html',
                          {'clients': results, 'search_query': search_query})


    # Группировка по датам
    schedule_data = {day: [] for day in date_range}
    totals = {day: {'plan': 0, 'due': 0, 'paid': 0} for day in date_range}

    for schedule in schedules:
        day = schedule.date
        if day in schedule_data:
            schedule_data[day].append(schedule)
            totals[day]['plan'] += float(schedule.cost if not schedule.is_completed else 0)
            totals[day]['due'] += float(schedule.cost if schedule.is_completed and not schedule.is_paid else 0)
            totals[day]['paid'] += float(schedule.cost if schedule.is_paid else 0)

    return render(request, 'MyClient/schedule.html', {
        'schedule_data': schedule_data,
        'totals': totals,
        'start_date': start_date,
        'today': date.today(),  # Добавление переменной `today`
        'clients': clients,
        'search_query': search_query,
    })


@login_required
@csrf_exempt
def add_schedule(request):
    if request.method == 'POST':
        try:
            client_id = request.POST.get('client_id')
            date = request.POST.get('schedule_date')
            hour = request.POST.get('schedule_hour')
            minute = request.POST.get('schedule_minute')
            is_online = request.POST.get('is_online') == 'true'  # Преобразование строки в булево значение
            cost = request.POST.get('schedule_cost')

            # Проверка наличия клиента
            client = Client.objects.get(id=client_id)

            # Форматирование времени
            time = datetime.strptime(f"{hour}:{minute}", "%H:%M").time()

            # Создание объекта расписания
            Schedule.objects.create(
                client=client,
                date=date,
                time=time,
                is_online=is_online,
                cost=cost
            )

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
@csrf_exempt
def edit_schedule(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)

    if request.method == "POST":
        try:
            # Получаем client_id из формы
            client_id = request.POST.get('client_id')
            schedule.client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            messages.error(request, "Выбранный клиент не существует.")
            return redirect('schedule_detail', schedule_id=schedule.id)

        # Обновляем другие поля расписания
        schedule.date = request.POST.get('schedule_date')
        hour = int(request.POST.get('schedule_hour'))
        minute = int(request.POST.get('schedule_minute'))
        schedule.cost = request.POST.get('schedule_cost')
        schedule.is_online = 'is_online' in request.POST

        # Формируем время
        schedule.time = f"{hour:02}:{minute:02}"

        schedule.save()
        messages.success(request, "Встреча успешно обновлена.")
        return redirect('schedule_detail', schedule_id=schedule.id)

    return redirect('schedule_detail', schedule_id=schedule.id)


def schedule_detail(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)
    context = {
        'schedule': schedule,
        'client': schedule.client,
    }
    return render(request, 'MyClient/schedule_detail.html', context)


def get_client_cost(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    return JsonResponse({"price_online": client.price_online, "price_offline": client.price_offline})


@login_required
def clients(request):
    search_query = request.GET.get('search', '').strip().lower()  # Удаляем лишние пробелы
    sort_by = request.GET.get('sort', '')
    page_number = request.GET.get('page', 1)  # Номер текущей страницы, по умолчанию 1

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
                        'intercom': client.intercom
                    })
            if len(results) > 20:
                paginator = Paginator(results, 20)  # 20 клиентов на страницу
                results = paginator.get_page(page_number)  # Получаем текущую страницу
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
                        'entrance': client.entrance,
                        'floor': client.floor,
                        'intercom': client.intercom
                    })
            if len(results) > 20:
                paginator = Paginator(results, 20)  # 20 клиентов на страницу
                results = paginator.get_page(page_number)  # Получаем текущую страницу

        return render(request, 'MyClient/clients.html', {'page_obj': results, 'clients': results, 'search_query': search_query, 'sort_by': sort_by})


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

    # Пагинация
    paginator = Paginator(clients, 20)  # 20 клиентов на страницу
    page_obj = paginator.get_page(page_number)  # Получаем текущую страницу

    return render(request, 'MyClient/clients.html', {'page_obj': page_obj, 'clients': page_obj, 'search_query': search_query, 'sort_by': sort_by})


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
                'name': f'{result.first_name}{' ' + result.last_name if result.last_name != 'яя' else ''}{', метро ' + result.metro if result.metro != 'яя' else ''}{', улица ' + result.street if result.street != 'яя' else ''}'
            })

    # Возвращаем результат в формате JSON
    return JsonResponse(clients, safe=False)


@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    return render(request, 'MyClient/client_detail.html', {'client': client, 'show_settings_btn': True})


@login_required
def client_settings(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    return render(request, 'MyClient/client_settings.html', {'client': client})


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
            client = form.save(commit=False)

            # Проверка длины телефона
            phone = client.phone
            if phone and len(phone) != 18:  # Проверяем, что телефон имеет длину 18 (например, "+7 (XXX) XXX-XX-XX")
                messages.error(request, 'Телефон должен быть в формате +7 (XXX) XXX-XX-XX')
                return render(request, 'MyClient/add_client.html', {'form': form, 'metro_stations': metro_stations})
            if not client.price_offline:
                client.price_offline = 0
            if not client.price_online:
                client.price_online = 0
            if not client.last_name:
                client.last_name = 'яя'
            if not client.metro:
                client.metro = 'яя'
            if not client.street:
                client.street = 'яя'
            if not client.house_number:
                client.house_number = 'яя'
            if not client.entrance:
                client.entrance = 'яя'
            if not client.floor:
                client.floor = 'яя'
            if not client.intercom:
                client.intercom = 'яя'
            if not client.phone:
                client.phone = 'яя'
            client.save()
            return redirect('clients')
        else:
            for field in form:
                print(field.errors)
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


def edit_client(request, client_id):

    client = get_object_or_404(Client, id=client_id)

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
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save(commit=False)

            # Проверка длины телефона
            phone = client.phone
            if phone and len(phone) != 18:  # Проверяем, что телефон имеет длину 18 (например, "+7 (XXX) XXX-XX-XX")
                messages.error(request, 'Телефон должен быть в формате +7 (XXX) XXX-XX-XX')
                return render(request, 'MyClient/add_client.html', {'form': form, 'metro_stations': metro_stations})
            if not client.price_offline:
                client.price_offline = 0
            if not client.price_online:
                client.price_online = 0
            if not client.last_name:
                client.last_name = 'яя'
            if not client.metro:
                client.metro = 'яя'
            if not client.street:
                client.street = 'яя'
            if not client.house_number:
                client.house_number = 'яя'
            if not client.entrance:
                client.entrance = 'яя'
            if not client.floor:
                client.floor = 'яя'
            if not client.intercom:
                client.intercom = 'яя'
            if not client.phone:
                client.phone = 'яя'
            client.save()
            return redirect('clients')
        else:
            messages.error(request, 'Ошибка при добавлении клиента. Проверьте данные.')
    else:
        form = ClientForm(instance=client)
    return render(request, 'MyClient/edit_client.html',
                  {'form': form, 'client': client, 'metro_stations': metro_stations})


def delete_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        client.delete()
        return redirect('clients')  # Возврат на страницу списка клиентов
    return redirect('client_detail', id=client_id)


def delete_schedule(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)
    if request.method == "POST":
        schedule.delete()
        return redirect('schedule')  # Замените на нужную страницу
    return redirect('schedule_detail', schedule_id=schedule_id)
