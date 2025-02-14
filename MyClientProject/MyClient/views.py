'''views.py'''
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import re
from django.core.exceptions import ValidationError
from .models import Profile, Client, Schedule, Block
from .forms import CustomUserChangeForm, ClientForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from datetime import date, timedelta, datetime
from django.views.decorators.csrf import csrf_exempt
from django.db.models import F, Sum, Count, Q
from django.utils.timezone import localtime
from dateutil.relativedelta import relativedelta

# месяца для русификации календаря
months = {
    "January": "Январь",
    "February": "Февраль",
    "March": "Март",
    "April": "Апрель",
    "May": "Май",
    "June": "Июнь",
    "July": "Июль",
    "August": "Август",
    "September": "Сентябрь",
    "October": "Октябрь",
    "November": "Ноябрь",
    "December": "Декабрь",
}


@login_required
def schedule(request):
    # Проверяем, авторизован ли пользователь, и перенаправляем на страницу авторизации, если нет
    if not request.user.is_authenticated:
        return redirect('auth')

    # Получаем ID клиента из GET-запроса (если передан)
    client_id = request.GET.get('client_id')
    # Получаем начальную дату из GET-запроса или устанавливаем текущую дату по умолчанию
    start_date_str = request.GET.get('start_date', date.today().strftime('%Y-%m-%d'))
    # Преобразуем строку в объект даты
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()

    # Определяем диапазон отображаемых дат (9 дней начиная с `start_date`)
    date_range = [start_date + timedelta(days=i) for i in range(9)]

    # Получение расписания
    schedules = Schedule.objects.filter(date__gte=start_date, date__lte=max(date_range), user=request.user)

    if client_id:
        try:
            # Если указан клиент, получаем объект клиента
            client = Client.objects.get(id=client_id)
            # Фильтруем расписание по клиенту
            schedules = schedules.filter(client=client)

            # Группировка расписания по датам
            schedule_data = {
                date: schedules.filter(date=date) for date in date_range
            }

            # Сортировка данных по времени внутри каждого дня
            for day, schedules in schedule_data.items():
                schedule_data[day] = sorted(schedules, key=lambda x: x.time)

            # Рендерим страницу с расписанием для конкретного клиента
            return render(request, 'MyClient/schedule.html', {
                'schedule_data': schedule_data,
                'client': client,
                'start_date': start_date,
            })
        except Exception as e:
            # Если клиент с таким ID не найден
            return render(request, 'MyClient/schedule.html', {
                'error': 'Клиент не найден.',
                'start_date': start_date,
            })

    # Группировка по датам
    schedule_data = {day: [] for day in date_range}
    totals = {day: {'plan': 0, 'due': 0, 'paid': 0, 'cancel': 0} for day in date_range}
    totals_for_template = {str(date): values for date, values in totals.items()}

    # Заполняем данные расписания и подсчитываем суммы для каждого дня
    for schedule in schedules:
        day = schedule.date
        if day in schedule_data:
            schedule_data[day].append(schedule)
            totals[day]['plan'] += schedule.get_plan()
            totals[day]['due'] += schedule.get_due()
            totals[day]['paid'] += schedule.get_paid()
            totals[day]['cancel'] += schedule.get_cancel()

    # Сортировка данных по времени внутри каждого дня
    for day, schedules in schedule_data.items():
        schedule_data[day] = sorted(schedules, key=lambda x: x.time)

    # Рендерим страницу с общим расписанием
    return render(request, 'MyClient/schedule.html', {
        'schedule_data': schedule_data,
        'totals': totals,
        'start_date': start_date,
        'totals_for_template': totals_for_template,
    })


@csrf_exempt
@login_required
def complete_schedule(request, schedule_id):
    # Проверяем, что запрос POST
    if request.method == 'POST':
        try:
            # Ищем расписание с заданным ID, если не найдено - 404 ошибка
            schedule = get_object_or_404(Schedule, id=schedule_id)
            # Переключаем статус "Выполнено" (если было выполнено, становится не выполнено, и наоборот)
            schedule.is_completed = not schedule.is_completed  # Переключаем состояние
            # Если задание было помечено как не выполненное, отменяем оплату
            if not schedule.is_completed:
                schedule.is_paid = False  # Отжимаем "Оплачено" при снятии "Выполнено"
            schedule.save()
            # Возвращаем успешный ответ с обновленным состоянием
            return JsonResponse({'status': 'success', 'is_completed': schedule.is_completed, 'is_paid': schedule.is_paid})
        except Exception as e:
            # Если возникла ошибка (например, не найдено расписание), возвращаем ошибку 404
            return JsonResponse({'status': 'error', 'message': 'Schedule not found'}, status=404)
    # Если запрос не POST, возвращаем ошибку с кодом 400
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@csrf_exempt
@login_required
def pay_schedule(request, schedule_id):
    # Проверяем запрос POST
    if request.method == 'POST':
        try:
            # Ищем расписание с заданным ID, если не найдено - 404 ошибка
            schedule = get_object_or_404(Schedule, id=schedule_id)
            # Меняем статус оплаты на противоположный (если было оплачено, снимаем оплату, и наоборот)
            new_paid_status = not schedule.is_paid

            # Принудительно обновляем блок только при установке оплаты
            if new_paid_status:
                active_block = Block.objects.filter(
                    client=schedule.client,
                    status='active'
                ).order_by('block_number').first()

                schedule.block = active_block

            # Обновляем статус оплаты
            schedule.is_paid = new_paid_status
            schedule.save()

            # Возвращаем успешный ответ с информацией о статусе оплаты и блоке
            return JsonResponse({
                'status': 'success',
                'is_paid': schedule.is_paid,
                'block_id': schedule.block.id if schedule.block else None
            })

        except Exception as e:
            # Если возникла ошибка, возвращаем ошибку с деталями
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    # Если запрос не POST, возвращаем ошибку с кодом 400
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@csrf_exempt
@login_required
def cancel_schedule(request, schedule_id):
    # Проверяем, что запрос POST
    if request.method == 'POST':
        try:
            # Ищем расписание с заданным ID
            schedule = get_object_or_404(Schedule, id=schedule_id)
            # Переключаем статус "Отменено"
            schedule.is_canceled  = not schedule.is_canceled  # Переключаем состояние
            # Если отменено, сбрасываем статус оплаты и выполнения
            if schedule.is_canceled:
                schedule.is_paid = False  # Сбросить оплату при отмене
                schedule.is_completed = False  # Сбросить выполнение при отмене
            schedule.save()
            # Возвращаем успешный ответ с текущим статусом отмены
            return JsonResponse({'status': 'success', 'is_canceled': schedule.is_canceled})
        except Exception as e:
            # Если возникла ошибка (например, не найдено расписание), возвращаем ошибку 404
            return JsonResponse({'status': 'error', 'message': 'Schedule not found'}, status=404)
    # Если запрос не POST, возвращаем ошибку с кодом 400
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required
@csrf_exempt
def add_schedule(request):
    # Проверяем, что запрос POST
    if request.method == 'POST':
        try:
            # Получаем данные из POST-запроса
            client_id = request.POST.get('client_id')
            date = request.POST.get('schedule_date')
            hour = request.POST.get('schedule_hour')
            minute = request.POST.get('schedule_minute')
            is_online = request.POST.get('is_online') == 'true'  # Преобразование строки в булево значение
            use_block = request.POST.get('is_block_payment') == 'true'  # Получение значения галочки
            cost = request.POST.get('schedule_cost')

            # Проверка наличия клиента
            client = Client.objects.get(id=client_id, user=request.user)

            # Форматирование времени
            time = datetime.strptime(f"{hour}:{minute}", "%H:%M").time()

            # Получаем текущего пользователя
            user = request.user

            # Создание объекта расписания
            Schedule.objects.create(
                user=user,
                client=client,
                date=date,
                time=time,
                is_online=is_online,
                cost=cost,
                use_block=use_block
            )

            # Возвращаем успешный ответ
            return JsonResponse({'success': True})
        except Exception as e:
            # Если возникла ошибка, возвращаем ошибку с деталями
            return JsonResponse({'success': False, 'error': str(e)})
    # Если запрос не POST, возвращаем ошибку с кодом 400
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
@csrf_exempt
def edit_schedule(request, schedule_id):
    # Проверяем, что запрос POST
    if request.method == "POST":
        # Ищем расписание с заданным ID и текущим пользователем
        schedule = get_object_or_404(Schedule, id=schedule_id, user=request.user)
        # Обновляем данные расписания
        schedule.client_id = request.POST.get('client_id')
        schedule.cost = request.POST.get('schedule_cost')
        schedule.is_online = request.POST.get('is_online') == 'true'
        schedule.use_block = request.POST.get('is_block_payment') == 'true'
        schedule.date = request.POST.get('schedule_date')
        schedule.time = f"{request.POST.get('schedule_hour')}:{request.POST.get('schedule_minute')}"
        schedule.save()
        # Возвращаем успешный ответ
        return JsonResponse({'success': True})
    # Если запрос не POST, возвращаем ошибку с кодом 400
    return JsonResponse({'success': False, 'error': 'Invalid request'})


def schedule_detail(request, schedule_id):
    # Ищем расписание по ID
    schedule = get_object_or_404(Schedule, id=schedule_id)
    # Формируем контекст для передачи в шаблон
    context = {
        'schedule': schedule,
        'client': schedule.client,
    }
    # Отображаем страницу с деталями расписания
    return render(request, 'MyClient/schedule_detail.html', context)


def get_client_cost(request, client_id):
    # Ищем клиента по ID
    client = get_object_or_404(Client, id=client_id)
    # Возвращаем стоимость для онлайн и оффлайн услуг клиента
    return JsonResponse({"price_online": client.price_online, "price_offline": client.price_offline})


@login_required  # Декоратор для проверки, что пользователь авторизован
def clients(request):
    # Получаем строку поиска из GET-запроса, удаляем пробелы, приводим к нижнему регистру
    search_query = request.GET.get('search', '').strip().lower()  # Удаляем лишние пробелы
    # Получаем поле сортировки из GET-запроса
    sort_by = request.GET.get('sort', '')
    # Номер текущей страницы, по умолчанию 1
    page_number = request.GET.get('page', 1)  # Номер текущей страницы, по умолчанию 1

    # Получаем список клиентов текущего пользователя, отсортированный по убыванию даты создания
    clients = Client.objects.filter(user=request.user).order_by('-created_at')  # Новые клиенты сверху
    results = []  # Инициализация пустого списка для хранения результатов поиска

    # Если строка поиска не пуста
    if search_query:
        # Разделяем запрос на слова (например, "Иван Иванов")
        search_terms = search_query.split()
        if len(search_terms) == 2:  # Если два слова (имя и фамилия)
            # Разделяем слова на имя и фамилию
            first_name, last_name = search_terms
            # Перебираем всех клиентов
            for client in clients:
                # Если оба слова совпадают с именем и фамилией клиента
                if first_name in client.first_name.lower() and last_name in client.last_name.lower():
                    # Добавляем информацию о клиенте в список результатов
                    results.append({
                        'id': client.id,
                        'first_name': client.first_name,
                        'last_name': client.last_name,
                        'metro': client.metro,
                        'street': client.street,
                        'house_number': client.house_number,
                        'entrance': client.entrance,
                        'floor': client.floor,
                        'flat_number': client.flat_number,
                        'intercom': client.intercom
                    })
            # Если результатов больше 20
            if len(results) > 20:
                paginator = Paginator(results, 20)  # 20 клиентов на страницу
                page_obj = paginator.get_page(page_number)  # Получаем текущую страницу
        else:  # Если одно слово или больше двух
            # Перебираем всех клиентов
            for client in clients:
                # Проверяем совпадение каждого термина в строке поиска с полями клиента
                if any(term in client.first_name.lower() for term in search_terms) or \
                        any(term in client.last_name.lower() for term in search_terms) or \
                        any(term in client.metro.lower() for term in search_terms) or \
                        any(term in client.street.lower() for term in search_terms):
                    # Добавляем информацию о клиенте в список результатов
                    results.append({
                        'id': client.id,
                        'first_name': client.first_name,
                        'last_name': client.last_name,
                        'metro': client.metro,
                        'street': client.street,
                        'house_number': client.house_number,
                        'entrance': client.entrance,
                        'floor': client.floor,
                        'flat_number': client.flat_number,
                        'intercom': client.intercom
                    })
            # Если результатов больше 20
            if len(results) > 20:
                paginator = Paginator(results, 20)  # 20 клиентов на страницу
                page_obj = paginator.get_page(page_number)  # Получаем текущую страницу

        # Отображаем результаты поиска в шаблоне с текущими данными
        return render(request, 'MyClient/clients.html', {'page_obj': page_obj, 'clients': results, 'search_query': search_query, 'sort_by': sort_by})

    # Вспомогательная функция для создания ключа сортировки
    def get_key_func(field):
        def key_func(client):
            value = getattr(client, field, "").lower()  # Преобразуем в нижний регистр
            return value
        return key_func

    # Проверка на допустимые поля для сортировки
    valid_sort_fields = ['first_name', 'last_name', 'metro',
                         'street', 'created_at', 'price_online', 'price_offline']
    # Если указано поле сортировки и оно допустимо
    if sort_by and sort_by in valid_sort_fields:
        # Если поле сортировки — цена онлайн
        if sort_by == 'price_online':
            # Сортируем по убыванию цены онлайн
            clients = clients.order_by('-price_online')
        # Если поле сортировки — цена оффлайн
        elif sort_by == 'price_offline':
            # Сортируем по убыванию цены оффлайн
            clients = clients.order_by('-price_offline')
        else:
            # Получаем ключ сортировки
            sort_key = get_key_func(sort_by)
            # Применяем быструю сортировку
            clients = quicksort(clients, sort_key)
    else:
        # Если сортировка не указана или указано неправильное поле, по умолчанию сортировка по created_at
        clients = clients.order_by('-created_at')

    # Пагинация
    paginator = Paginator(clients, 20)  # 20 клиентов на страницу
    page_obj = paginator.get_page(page_number)  # Получаем текущую страницу

    # Отображаем данные в шаблоне с текущими настройками
    return render(request, 'MyClient/clients.html', {'page_obj': page_obj, 'clients': page_obj, 'search_query': search_query, 'sort_by': sort_by})


# Функция для автозаполнения (autocomplete)
def autocomplete(request):
    # Получаем значение параметра 'query' из GET-запроса, приводим к нижнему регистру
    query = request.GET.get('query', '').lower()
    # Получаем значение параметра 'search_schedules' из GET-запроса, приводим к нижнему регистру
    query_schedule = request.GET.get('search_schedules', '').lower()
    # Фильтруем клиентов, привязанных к текущему пользователю
    results = Client.objects.filter(user=request.user)  # Получаем всех клиентов
    # Список клиентов для автозаполнения
    clients = []

    # Устанавливаем основной запрос в зависимости от переданного параметра
    if query:
        main_query = query
    elif query_schedule:
        main_query = query_schedule

    # Устанавливаем основной запрос в зависимости от переданного параметра
    for result in results:
        # Приводим к нижнему регистру и проверяем наличие подстроки в нужных полях
        if (main_query in result.first_name.lower() or
                main_query in result.last_name.lower() or
                main_query in result.metro.lower() or
                main_query in result.street.lower()):
            # Добавляем клиента в список
            clients.append({
                'id': result.id,
                'name': f"{result.first_name}{' ' + result.last_name if result.last_name != 'яя' else ''}{', метро ' + result.metro if result.metro != 'яя' else ''}{', улица ' + result.street if result.street != 'яя' else ''}"
            })

    # Возвращаем результат в формате JSON
    return JsonResponse(clients, safe=False)


# Функция для отображения информации о клиенте
@login_required
def client_detail(request, client_id):
    # Получаем клиента по ID и текущему пользователю, или возвращаем 404
    client = get_object_or_404(Client, id=client_id, user=request.user)
    # Рендерим страницу с деталями клиента
    return render(request, 'MyClient/client_detail.html', {'client': client, 'show_settings_btn': True})


# Функция для отображения настроек клиента
@login_required
def client_settings(request, client_id):
    # Получаем клиента по ID и текущему пользователю, или возвращаем 404
    client = get_object_or_404(Client, id=client_id, user=request.user)
    # Рендерим страницу настроек клиента
    return render(request, 'MyClient/client_settings.html', {'client': client})


# Функция для отображения профиля пользователя
@login_required
def profile(request):
    # Получаем текущего пользователя
    user = request.user
    # Проверяем, есть ли профиль, и создаем его, если отсутствует
    if not hasattr(user, 'profile'):
        # Создаем профиль, если его нет
        Profile.objects.create(user=user)
    # Получаем связанный профиль
    profile = user.profile  # Связанный профиль

    # Текущая дата и время
    today = localtime()

    # Фильтруем незавершенные встречи до текущего момента, исключая оплаченные и отмененные
    unfinished_meetings = Schedule.objects.filter(
        date__lt=today, user=request.user
    ).exclude(
        Q(is_paid=True) | Q(is_canceled=True)
    ).select_related('client')

    # Периоды для анализа
    periods = [
        get_week_stats(user),
        get_month_stats(user),
        get_previous_month_stats(user)
    ]

    # Общая статистика
    lifetime_stats = {
        'completed': Schedule.objects.filter(is_completed=True, user=request.user).count(),
        'total_paid': Schedule.objects.filter(is_paid=True, user=request.user).aggregate(Sum('cost'))['cost__sum'] or 0,
        'blocks_paid': Block.objects.filter(user=request.user).aggregate(Sum('cost'))['cost__sum'] or 0,
        'cancelled': Schedule.objects.filter(is_canceled=True, user=request.user).count(),
    }

    # Подготовка контекста для передачи в шаблон
    context = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'specialization': profile.specialization,
        'email': user.email,  # Используем email
        'profile': profile,
        'show_settings_btn': True,  # Шестерёнка видна
        'unfinished_meetings': unfinished_meetings,
        'periods': periods,
        'lifetime_stats': lifetime_stats,
    }
    # Рендерим страницу профиля
    return render(request, 'MyClient/profile.html', context)


# Функция для получения статистики за текущий месяц
def get_month_stats(user):
    # Текущая дата и первый день месяца
    today = localtime()
    first_day_of_month = today.replace(day=1)

    # Фильтр для текущего месяца (с 1 числа до текущего дня)
    month_filter = Q(date__gte=first_day_of_month) & Q(date__lte=today)

    # Сумма блоков за месяц
    blocks_stats = Block.objects.filter(
        created_at__gte=first_day_of_month,
        created_at__lte=today,
        user=user
    ).aggregate(
        blocks_total=Sum('cost')
    )

    # Статистика по клиентам за месяц
    blocks_stats_clients = Block.objects.filter(
        created_at__gte=first_day_of_month,
        created_at__lte=today,
        user=user
    ).values(
        'client__id'
    ).annotate(
        blocks_total=Sum('cost')
    )

    # Преобразование в словарь для быстрого доступа
    blocks_stats_dict = {b['client__id']: b['blocks_total'] for b in blocks_stats_clients}

    # Основная статистика
    stats = Schedule.objects.filter(month_filter, user=user).aggregate(
        completed=Count('id', filter=Q(is_completed=True)),
        total_paid=Sum('cost', filter=Q(is_paid=True)),
        cancelled=Count('id', filter=Q(is_canceled=True))
    )

    # Статистика по клиентам
    clients_stats = Schedule.objects.filter(month_filter, user=user).values(
        'client__id', 'client__first_name', 'client__last_name'
    ).annotate(
        completed=Count('id', filter=Q(is_completed=True)),
        total_paid=Sum('cost', filter=Q(is_paid=True)),
        cancelled=Count('id', filter=Q(is_canceled=True)),
    ).order_by('-total_paid')

    # Возвращаем собранные данные
    return {
        'title': f'Текущий месяц ({months[first_day_of_month.strftime("%B")]})',
        'completed': stats['completed'] or 0,
        'total_paid': stats['total_paid'] or 0,
        'blocks_paid': blocks_stats['blocks_total'] or 0,
        'cancelled': stats['cancelled'] or 0,
        # Форматируем данные по каждому клиенту
        'clients_stats': [{
            'name': f"{c['client__first_name']} {c['client__last_name'] if c['client__last_name'] != 'яя' else ''}".strip(),
            'completed': c['completed'],
            'cancelled': c['cancelled'],
            'total_paid': c['total_paid'],
            'blocks_paid': blocks_stats_dict.get(c['client__id'], 0),
        } for c in clients_stats]
    }


# Функция для получения статистики за прошлый месяц
def get_previous_month_stats(user):
    # Получение текущей даты и времени
    today = localtime()
    # Определение первого дня предыдущего месяца
    first_day_prev_month = (today - relativedelta(months=1)).replace(day=1)
    # Определение последнего дня предыдущего месяца
    last_day_prev_month = first_day_prev_month + relativedelta(day=31)

    # Фильтр для прошлого месяца (весь месяц)
    prev_month_filter = Q(date__gte=first_day_prev_month) & Q(date__lte=last_day_prev_month)

    # Расчет общей суммы расходов (cost) по всем блокам пользователя за прошлый месяц
    blocks_stats = Block.objects.filter(
        created_at__gte=first_day_prev_month,
        created_at__lte=last_day_prev_month,
        user=user
    ).aggregate(
        blocks_total=Sum('cost')  # Суммирование стоимости блоков
    )

    # Сумма расходов по блокам с группировкой по клиентам
    blocks_stats_clients = Block.objects.filter(
        created_at__gte=first_day_prev_month,
        created_at__lte=last_day_prev_month,
        user=user
    ).values(
        'client__id'  # Группировка по ID клиента
    ).annotate(
        blocks_total=Sum('cost')  # Суммирование стоимости блоков по каждому клиенту
    )

    # Преобразование в словарь для быстрого доступа
    blocks_stats_dict = {b['client__id']: b['blocks_total'] for b in blocks_stats_clients}

    # Основная статистика
    stats = Schedule.objects.filter(prev_month_filter, user=user).aggregate(
        completed=Count('id', filter=Q(is_completed=True)),
        total_paid=Sum('cost', filter=Q(is_paid=True)),
        cancelled=Count('id', filter=Q(is_canceled=True))
    )

    # Статистика по клиентам
    clients_stats = Schedule.objects.filter(prev_month_filter, user=user).values(
        'client__id', 'client__first_name', 'client__last_name'
    ).annotate(
        # Завершенные задачи
        completed=Count('id', filter=Q(is_completed=True)),
        # Оплаченные задачи
        total_paid=Sum('cost', filter=Q(is_paid=True)),
        # Отмененные задачи
        cancelled=Count('id', filter=Q(is_canceled=True))
    ).order_by('-total_paid') # Сортировка по оплате (от большего к меньшему)

    # Формирование итогового результата
    return {
        'title': f'Прошлый месяц ({months[first_day_prev_month.strftime("%B")]})',
        'completed': stats['completed'] or 0,
        'total_paid': stats['total_paid'] or 0,
        'blocks_paid': blocks_stats['blocks_total'] or 0,
        'cancelled': stats['cancelled'] or 0,
        # Статистика по каждому клиенту
        'clients_stats': [{
            'name': f"{c['client__first_name']} {c['client__last_name'] if c['client__last_name'] != 'яя' else ''}".strip(),
            'completed': c['completed'],
            'cancelled': c['cancelled'],
            'total_paid': c['total_paid'],
            'blocks_paid': blocks_stats_dict.get(c['client__id'], 0), # Сумма расходов по блокам для клиента
        } for c in clients_stats]
    }


# Функция для получения статистики за последнюю неделю
def get_week_stats(user):
    # Получение текущей даты и времени
    today = localtime()
    # Определение даты 7 дней назад
    week_ago = today - timedelta(days=7)

    # Общая сумма по блокам за последнюю неделю
    blocks_stats = Block.objects.filter(
        created_at__gte=week_ago,
        created_at__lt=today,
        user=user
    ).aggregate(
        blocks_total=Sum('cost')  # Суммирование стоимости блоков
    )

    # Расчет суммы расходов по клиентам за неделю
    blocks_stats_clients = Block.objects.filter(
        created_at__gte=week_ago,
        created_at__lt=today,
        user=user
    ).values(
        'client__id'  # Группировка по клиенту
    ).annotate(
        blocks_total=Sum('cost')  # Суммирование стоимости блоков
    )

    # Преобразование в словарь для быстрого доступа
    blocks_stats_dict = {b['client__id']: b['blocks_total'] for b in blocks_stats_clients}

    # Статистика по расписанию за неделю
    stats = Schedule.objects.filter(
        date__range=[week_ago, today], user=user
    ).aggregate(
        # Завершенные задачи
        completed=Count('id', filter=Q(is_completed=True)),
        # Оплаченные задачи
        total_paid=Sum('cost', filter=Q(is_paid=True)),
        # Отмененные задачи
        cancelled=Count('id', filter=Q(is_canceled=True))
    )

    # Статистика по клиентам за неделю
    clients_stats = Schedule.objects.filter(
        date__range=[week_ago, today], user=user
    ).values(
        'client__id', 'client__first_name', 'client__last_name'
    ).annotate(
        # Завершенные задачи
        completed=Count('id', filter=Q(is_completed=True)),
        # Оплаченные задачи
        total_paid=Sum('cost', filter=Q(is_paid=True)),
        # Отмененные задачи
        cancelled=Count('id', filter=Q(is_canceled=True))
    ).order_by('-total_paid')  # Сортировка по общей оплате

    # Формирование итогового результата
    return {
        'title': 'Последняя неделя',  # Заголовок статистики
        'completed': stats['completed'] or 0,  # Количество завершенных встреч
        'total_paid': stats['total_paid'] or 0,  # Общая оплаченная сумма
        'blocks_paid': blocks_stats['blocks_total'] or 0,   # Общая сумма по блокам
        'cancelled': stats['cancelled'] or 0,  # Количество отмен
        'clients_stats': [{  # Детализация по каждому клиенту
            'name': f"{c['client__first_name']} {c['client__last_name'] if c['client__last_name'] != 'яя' else ''}".strip(),
            'completed': c['completed'],
            'cancelled': c['cancelled'],
            'total_paid': c['total_paid'],
            'blocks_paid': blocks_stats_dict.get(c['client__id'], 0),
        } for c in clients_stats]
    }


@login_required  # Декоратор, требующий авторизации для доступа к представлению.
def blocks(request):
    # Получение фильтра из GET-параметров (по умолчанию 'active').
    choice_filter = request.GET.get('choice_block', 'active')
    # Получение идентификатора клиента из GET-параметров (если указан).
    client_id = request.GET.get('client_id')

    # Фильтрация блоков
    blocks = Block.objects.filter(user=request.user)
    if client_id:
        # Если указан клиент, фильтруем блоки по клиенту.
        client = Client.objects.get(id=client_id)
        blocks = blocks.filter(client=client)
    if choice_filter == 'active':
        # Фильтруем только активные блоки.
        blocks = blocks.filter(status='active')
    elif choice_filter == 'completed':
        # Фильтруем только завершенные блоки.
        blocks = blocks.filter(status='completed')

    # Сортировка блоков по дате создания (новые сверху)
    blocks = blocks.order_by('-id')

    # Ограничение количества блоков на странице (не более 30)
    blocks = blocks[:30]

    # Формирование контекста для шаблона.
    context = {
        'blocks': blocks,
        'request': request,
    }

    # Рендеринг страницы 'blocks.html' с переданным контекстом.
    return render(request, 'MyClient/blocks.html', context)


@csrf_exempt  # Отключение проверки CSRF для этого представления.
def add_block(request):
    if request.method == 'POST':
        try:
            # Получение данных из POST-запроса.
            client_id = request.POST.get('client_id')
            total_meetings = int(request.POST.get('total_meetings', 0))
            completed_meetings = int(request.POST.get('completed_meetings', 0))
            cost = request.POST.get('block_cost')

            # Проверка наличия клиента
            client = Client.objects.get(id=client_id)

            # Проверка входных данных
            if completed_meetings > total_meetings:
                return JsonResponse({'success': False,
                                     'error': 'Количество завершенных встреч не может превышать общее количество встреч.'})

            user = request.user

            # Создание нового блока.
            Block.create_block(
                user=user,
                client=client,
                total_meetings=total_meetings,
                completed_meetings=completed_meetings,
                cost=cost
            )

            # Возврат успешного ответа.
            return JsonResponse({'success': True})
        except Exception as e:
            # Обработка ошибок и возврат их текста.
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def block_detail(request, block_id):
    # Получение блока или возврат 404, если не найден.
    blocks = get_object_or_404(Block, id=block_id)

    # Вычисление стоимости одной встречи (если общее число встреч > 0).
    cost_per_meeting = blocks.cost / blocks.total_meetings if blocks.total_meetings > 0 else 0
    # Получение всех клиентов для возможного отображения.
    clients = Client.objects.all()

    # Формирование контекста для шаблона.
    context = {
        'blocks': blocks,
        'client': blocks.client,
        'clients': clients,
        'cost_per_meeting': cost_per_meeting
    }
    # Рендеринг страницы 'block_detail.html' с переданным контекстом.
    return render(request, 'MyClient/block_detail.html', context)


@login_required  # Требует авторизации для доступа к представлению.
@csrf_exempt  # Отключает проверку CSRF.
def edit_block(request, block_id):
    if request.method == "POST":
        # Получение блока по идентификатору или возврат 404.
        block = get_object_or_404(Block, id=block_id)
        # Обновление данных блока из POST-запроса.
        block.client_id = request.POST.get('client_id')
        block.total_meetings = int(request.POST.get('total_meetings', 0))
        block.completed_meetings = int(request.POST.get('completed_meetings', 0))
        block.cost = request.POST.get('block_cost')

        # Проверка входных данных
        if block.completed_meetings > block.total_meetings:
            return JsonResponse({'success': False,
                                 'error': 'Количество завершенных встреч не может превышать общее количество встреч.'})

        # Сохранение изменений блока.
        block.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


def delete_block(request, block_id):
    # Получение блока по идентификатору или возврат 404.
    block = get_object_or_404(Block, id=block_id)
    if request.method == "POST":
        # Удаление блока.
        block.delete()
        # Перенаправление на список блоков.
        return redirect('blocks')
    # Если метод не POST, перенаправление на страницу с деталями блока.
    return redirect('block_detail', block_id=block_id)


def auth_redirect(request):
    # Если пользователь авторизован, перенаправляем его на страницу расписания
    if request.user.is_authenticated:
        return redirect('schedule')
    # Если пользователь не авторизован, отображаем страницу авторизации
    return render(request, 'auth/auth_home.html')


def login_view(request):
    # Обрабатываем только POST-запросы
    if request.method == 'POST':
        # Получаем email и пароль из формы
        email = request.POST['email']
        password = request.POST['password']
        # Аутентифицируем пользователя
        user = authenticate(request, username=email, password=password)
        if user:
            # Если аутентификация успешна, выполняем вход и перенаправляем на расписание
            login(request, user)
            return redirect('schedule')
        else:
            # Если аутентификация не удалась, отображаем сообщение об ошибке
            messages.error(request, 'Неправильный логин или пароль')
    # Если запрос не POST, отображаем страницу входа
    return render(request, 'auth/login.html')


def register_view(request):
    # Обрабатываем только POST-запросы
    if request.method == 'POST':
        # Получаем данные из формы
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        specialty = request.POST.get('specialty', '')
        email = request.POST.get('email', '')
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        # Проверяем совпадение паролей
        if password == password2:
            try:
                # Проверяем, существует ли пользователь с таким email
                if User.objects.filter(username=email).exists():
                    messages.error(request, 'Пользователь с таким логином уже существует.')
                    return render(request, 'auth/register.html', {
                        'email': email, 'first_name': first_name,
                        'last_name': last_name, 'specialty': specialty})

                # Проверка сложности пароля (если используется)
                check_password_complexity(password)
                # Создаем нового пользователя
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
                # Выполняем вход и перенаправляем на расписание
                login(request, user)
                return redirect('schedule')
            except ValidationError as e:
                # Отображаем ошибки валидации
                messages.error(request, ", ".join(e.messages))
        else:
            # Если пароли не совпадают, отображаем ошибку
            messages.error(request, 'Пароли не совпадают')

        # Возврат данных в случае ошибки
        context = {
            'first_name': first_name,
            'last_name': last_name,
            'specialty': specialty,
            'email': email,
        }
        return render(request, 'auth/register.html', context)

    # Если запрос не POST, отображаем форму регистрации
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
    # Отображаем страницу настроек для авторизованного пользователя
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
        # Используем форму для изменения данных пользователя
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
    # Удаляем учетную запись текущего пользователя
    user = request.user
    user.delete()
    # Выполняем выход после удаления профиля
    logout(request)
    return redirect('auth')


def logout_view(request):
    logout(request)  # Выполняем выход пользователя
    return redirect('auth')  # Перенаправляем на страницу авторизации (или другую страницу)


@login_required
def reset_password(request):
    if request.method == 'POST':
        # Получаем новый пароль и его подтверждение
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        # Проверяем совпадение паролей
        if password != password2:
            messages.error(request, 'Пароли не совпадают!')
            return render(request, 'MyClient/reset_password.html')

        try:
            # Проверяем сложность пароля
            check_password_complexity(password)
        except ValidationError as e:
            messages.error(request, ", ".join(e.messages))
            return redirect("reset_password")

        # Сохраняем новый пароль
        user = request.user
        user.set_password(password)
        user.save()

        # Обновляем сессию
        update_session_auth_hash(request, user)
        return redirect('settings')

    # Отображаем форму для смены пароля
    return render(request, 'MyClient/reset_password.html')


@login_required  # Требует авторизации пользователя для доступа к функции.
def add_client(request):  # Функция для добавления нового клиента.
    # Чтение станций метро из файла
    metro_stations = []  # Инициализация списка для станций метро.
    try:
        # Открытие файла и чтение станций метро
        with open('metro_stations.txt', 'r', encoding='utf-8') as f:  # Открытие файла в режиме чтения.
            metro_stations = [line.strip() for line in f.readlines()]  # Считывание строк и удаление пробелов.
    except FileNotFoundError:
        # В случае если файл не найден
        messages.error(request, 'Файл с метростанциями не найден.')  # Сообщение об ошибке пользователю.

    if request.method == 'POST':  # Если метод запроса POST (отправка формы).
        form = ClientForm(request.POST)  # Создание формы с данными из запроса.
        if form.is_valid():  # Проверка формы на корректность.
            client = form.save(commit=False)  # Сохранение формы без записи в базу.

            # Установка текущего пользователя для клиента
            client.user = request.user  # Здесь мы сохраняем пользователя как текущего

            # Проверка длины телефона
            phone = client.phone  # Получение телефона из формы.
            if phone and len(phone) != 18:  # Проверяем, что телефон имеет длину 18 (например, "+7 (XXX) XXX-XX-XX")
                messages.error(request, 'Телефон должен быть в формате +7 (XXX) XXX-XX-XX')
                return render(request, 'MyClient/add_client.html', {'form': form, 'metro_stations': metro_stations})
            # Установка значений по умолчанию для полей.
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
            if not client.flat_number:
                client.flat_number = 'яя'
            if not client.intercom:
                client.intercom = 'яя'
            if not client.phone:
                client.phone = 'яя'
            client.save()  # Сохранение клиента в базе данных.
            return redirect('clients')  # Перенаправление на список клиентов.
        else:
            messages.error(request, 'Ошибка при добавлении клиента. Проверьте данные.')
            for field in form:  # Для каждого поля формы.
                for error in field.errors:  # Перебор ошибок поля.
                    messages.error(request, f" Ошибка в поле {field.label}: {error}")
    else:
        form = ClientForm()  # Создание пустой формы.
    return render(request, 'MyClient/add_client.html', {'form': form,
                                                        'metro_stations': metro_stations})


def quicksort(arr, key_func, reverse=False):  # Функция быстрой сортировки.
    if len(arr) <= 1:  # Базовый случай: массив из одного или нуля элементов.
        return arr
    pivot = arr[0]  # Выбор опорного элемента.
    less = [x for x in arr[1:] if key_func(x) <= key_func(pivot)]  # Элементы меньше или равны опорному.
    greater = [x for x in arr[1:] if key_func(x) > key_func(pivot)]  # Элементы больше опорного.
    if reverse:  # Если требуется сортировка в обратном порядке.
        return quicksort(greater, key_func, reverse) + [pivot] + quicksort(less, key_func, reverse)
    else:  # Обычная сортировка.
        return quicksort(less, key_func, reverse) + [pivot] + quicksort(greater, key_func, reverse)


def edit_client(request, client_id):  # Функция редактирования клиента.

    client = get_object_or_404(Client, id=client_id)  # Получение клиента или возврат ошибки 404.

    # Чтение станций метро из файла
    metro_stations = []
    try:
        # Открытие файла и чтение станций метро
        with open('metro_stations.txt', 'r', encoding='utf-8') as f:
            metro_stations = [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        # В случае если файл не найден
        messages.error(request, 'Файл с метростанциями не найден.')

    if request.method == 'POST':  # Если запрос POST.
        form = ClientForm(request.POST, instance=client)  # Форма для редактирования с текущими данными.
        if form.is_valid():  # Проверка формы на корректность.
            client = form.save(commit=False)

            # Проверка длины телефона
            phone = client.phone
            if phone and len(phone) != 18:  # Проверяем, что телефон имеет длину 18 (например, "+7 (XXX) XXX-XX-XX")
                messages.error(request, 'Телефон должен быть в формате +7 (XXX) XXX-XX-XX')
                return render(request, 'MyClient/add_client.html', {'form': form, 'metro_stations': metro_stations})
            # Установка значений по умолчанию, если поля не заполнены.
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
            if not client.flat_number:
                client.flat_number = 'яя'
            if not client.intercom:
                client.intercom = 'яя'
            if not client.phone:
                client.phone = 'яя'
            # Сохранение изменений.
            client.save()
            return redirect('clients')  # Перенаправление на список клиентов.
        else:
            messages.error(request, 'Ошибка при добавлении клиента. Проверьте данные.')
    else:
        form = ClientForm(instance=client)  # Инициализация формы с текущими данными клиента.
    return render(request, 'MyClient/edit_client.html',
                  {'form': form, 'client': client, 'metro_stations': metro_stations})


def delete_client(request, client_id):
    # Получаем объект клиента по переданному ID, либо выдаем ошибку 404, если клиент не найден
    client = get_object_or_404(Client, id=client_id)
    # Проверяем, что запрос выполнен методом POST (удаление должно быть подтверждено через POST)
    if request.method == 'POST':
        # Удаляем клиента из базы данных
        client.delete()
        # Перенаправляем пользователя на страницу списка клиентов после успешного удаления
        return redirect('clients')  # Возврат на страницу списка клиентов
    # Если запрос не POST, перенаправляем на страницу с подробной информацией о клиенте
    return redirect('client_detail', id=client_id)


def delete_schedule(request, schedule_id):
    # Получаем объект расписания по переданному ID, либо выдаем ошибку 404, если расписание не найдено
    schedule = get_object_or_404(Schedule, id=schedule_id)
    # Проверяем, что запрос выполнен методом POST (удаление должно быть подтверждено через POST)
    if request.method == "POST":
        # Удаляем расписание из базы данных
        schedule.delete()
        # Перенаправляем пользователя на страницу общего расписания после успешного удаления
        return redirect('schedule')
    # Если запрос не POST, перенаправляем на страницу с подробной информацией о расписании
    return redirect('schedule_detail', schedule_id=schedule_id)


def check_client_block(request, client_id):
    try:
        # Пытаемся получить объект клиента по переданному ID
        client = Client.objects.get(id=client_id)
        # Проверяем, существуют ли активные блоки клиента, у которых количество завершенных встреч меньше общего количества встреч
        has_block = Block.objects.filter(
            client=client,  # Фильтруем блоки по клиенту
            status='active',  # Фильтруем только активные блоки
            completed_meetings__lt=F('total_meetings')  # Учитываем блоки с незавершенными встречами
        ).exists()
        # Возвращаем JSON-ответ с результатом проверки
        return JsonResponse({'has_block': has_block})
    except Client.DoesNotExist:
        # Если клиент не найден, возвращаем JSON-ответ с ошибкой и статусом 404
        return JsonResponse({'error': 'Client not found'}, status=404)
