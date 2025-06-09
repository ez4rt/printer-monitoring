import json
from collections import defaultdict
from datetime import datetime, timedelta
import time
import locale
from django.shortcuts import render, get_object_or_404
from .models import (Printer, Statistics, DailyStat, MonthlyStat, Forecast, MaintenanceCosts, ForecastChangeSupplies,
                     ChangeSupply, PrinterError, Subnet, PrinterSupplyStatus, SupplyItem)
from django.contrib.admin.models import LogEntry
from django.db.models import Max
from django.db.models.query import QuerySet
from django.http import JsonResponse
from django.shortcuts import redirect
from django.db import connection
import pandas as pd
from django.db.models import F, Sum, Min, Count
from . import forms
from django.views.decorators.csrf import csrf_exempt
from bs4 import BeautifulSoup
from io import StringIO, BytesIO
from django.http import HttpResponse
from django.utils import timezone
import requests
from django.contrib.auth.decorators import login_required
from django.views import View
from django.http import HttpResponseBadRequest
from django.db.models.functions import TruncDate, TruncMonth
from django.db.models import OuterRef, Subquery
from dateutil.relativedelta import relativedelta
import calendar
import os
import logging
from functools import wraps


def get_variables_stats(queryset: dict, name_key: str) -> dict:
    variables_dict = {f'sum_total_{name_key}page': 0, f'sum_total_{name_key}print': 0,
                      f'sum_total_{name_key}scan': 0, f'sum_total_{name_key}copies': 0}

    for stats in queryset:
        variables_dict[f'sum_total_{name_key}page'] += stats.page
        variables_dict[f'sum_total_{name_key}print'] += stats.print
        variables_dict[f'sum_total_{name_key}scan'] += stats.scan
        variables_dict[f'sum_total_{name_key}copies'] += stats.copies

    return variables_dict


def calculate_percentage(current: int, yesterday: int) -> str:
    if current != 0 and yesterday != 0:
        percent = round(current / yesterday * 100 - 100, 1)
        if percent > 0:
            return "{:+}".format(percent)
        return str(percent)
    return '0.0'


def update_info():
    try:
        printers = Printer.objects.all()
        qty_printers = printers.count()

        archived_printers = Printer.objects.filter(is_archived=True)

        unique_stamps = (
            Printer.objects
            .values('ip_address__subnet__name', 'model__stamp__name')
            .distinct()
        )

        subnet_printer_count = (
            Subnet.objects
            .annotate(printer_count=Count('ipaddress__printer'))
            .values('name', 'printer_count')
            .order_by('id'))

        for subnet in subnet_printer_count:
            subnet['area_name'] = get_area_name(subnet['name'])

        latest_events = timezone.now() - timedelta(days=10)
        recent_changes_supplies = ChangeSupply.objects.filter(time_change__gte=latest_events)
        recent_errors = PrinterError.objects.filter(event_date__gte=latest_events)
        recent_admin_log = LogEntry.objects.filter(action_time__gte=latest_events)
        events_small = create_events(recent_changes_supplies, recent_errors, recent_admin_log)[:10]

    except Exception as e:
        logger_main.warning(f'def update_info: {e}. Lack of data in the database: main info')

    try:
        printers_low_toner = PrinterSupplyStatus.objects.filter(supply__type='cartridge'
                                                                    ).order_by('remaining_supply_percentage')[:3]
        first_printer_low_toner = printers_low_toner[0]
        second_printer_low_toner = printers_low_toner[1]
        third_printer_low_toner = printers_low_toner[2]

    except Exception as e:
        logger_main.warning(f'def update_info: {e}, Lack of data in the database: low toner')

    standard_keys = ['printers', 'qty_printers', 'printers_low_toner', 'first_printer_low_toner',
                     'second_printer_low_toner', 'third_printer_low_toner', 'events_small', 'subnet_names',
                     'unique_stamps', 'subnet_printer_count', 'archived_printers']
    return {key: value for key, value in locals().items() if key in standard_keys}


def get_area_name(nm_area:str) -> str:
    lower_str = nm_area.lower()
    areas_mapping = {
        'abakan': 'Абакан',
        'sayanogorsk': 'Саяногорск',
        'chernogorsk': 'Черногорск',
        'shira': 'Шира',
        'ust-abakan': 'Усть-Абакан',
        'kopyovo': 'Копьево',
        'bograd': 'Боград',
        'sorsk': 'Сорск',
        'tashtyp': 'Таштып',
        'askiz': 'Аскиз',
        'beya': 'Бея',
        'abaza': 'Абаза',
        'bely_yar': 'Белый Яр',
        'vershina_tyoi': 'Вершина Тёи',
    }
    return areas_mapping.get(lower_str, nm_area)


def get_report_option(nm_report: str) -> str:
    lower_str = nm_report.lower()
    options_dict = {
        'page': 'общего количества страниц',
        'print': 'количества страниц печати',
        'copies': 'количества копий',
        'scan': 'количества отсканированных страниц',
        'event-log': 'из журнала событий',
        'print-log': 'из журнала печати',
    }
    return options_dict.get(lower_str, nm_report)


def create_events(supplies_query: QuerySet[ChangeSupply], errors_query: QuerySet[PrinterError],
                  admin_log_query: QuerySet[LogEntry]) -> list:
    formatted_changes_supplies = []
    for event in supplies_query:
        event.time_change += timedelta(hours=7)
        formatted_time = event.time_change.strftime('%Y/%m/%d %H:%M')
        formatted_changes_supplies.append({
            'action_time': formatted_time,
            'object_repr': event.printer,
            'description': f'Заменен {event.supply}',
            'type': 'Расходный материал',
        })
    formatted_errors = []
    for event in errors_query:
        event.event_date += timedelta(hours=7)
        formatted_time = event.event_date.strftime('%Y/%m/%d %H:%M')
        formatted_errors.append({
            'action_time': formatted_time,
            'object_repr': event.printer,
            'description': event.description,
            'type': 'Ошибка',
        })

    formatted_admin_log = []
    for event in admin_log_query:
        change_message = event.change_message
        if event.action_flag == 1:
            event.change_message = 'Добавление объекта'
        elif event.action_flag == 2:
            event.change_message = 'Изменены поля ('
            parsed_data = json.loads(change_message)
            for item in parsed_data:
                try:
                    fields = item['changed']['fields']
                except KeyError as e:
                    continue
                for field in fields:
                    event.change_message += f'{field}, '
            event.change_message = f'{event.change_message[:-2]})'
        elif event.action_flag == 3:
            event.change_message = 'Удаление объекта'
        else:
            event.change_message = 'Масоны'

        event.action_time += timedelta(hours=7)
        formatted_time = event.action_time.strftime('%Y/%m/%d %H:%M')

        formatted_admin_log.append({
            'action_time': formatted_time,
            'object_repr': event.object_repr,
            'description': f'Пользователь: {event.user}, Действие: {event.change_message}',
            'type': 'Информация',
        })

    all_events = formatted_changes_supplies + formatted_errors + formatted_admin_log
    sorted_events = sorted(all_events,
                           key=lambda x: x.get('time_change') or x.get('event_date') or x.get('action_time'),
                           reverse=True)

    return sorted_events


def log_user_action(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        logger_user_actions.info(f'User {request.user.username} "GET {request.build_absolute_uri()}"')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@login_required(login_url='/accounts/login')
@log_user_action
def index(request):
    if 'printer_id' in request.session:
        printer_id = request.session.pop('printer_id')

    return_dict = update_info()
    printers_with_black_cart = PrinterSupplyStatus.objects.filter(supply__type='cartridge',
                                                                  supply__color='black')
    return_dict['printers_with_black_cart'] = printers_with_black_cart

    try:
        black_cart_printer_ids = {status.printer_id for status in printers_with_black_cart}
        printers_without_black_cart = [printer for printer in return_dict['printers'] if printer.id not in
                                       black_cart_printer_ids]
        return_dict['printers_without_black_cart'] = printers_without_black_cart
    except Exception as e:
        logger_main.warning(f'def update_info: {e}, Lack of data in the database: printers_with_black_cart')

    latest_stats = Statistics.objects.values('printer_id').annotate(max_time=Max('time_collect')).values('printer_id',
                                                                                                         'max_time')

    printers_latest_stats = Statistics.objects.filter(printer_id__in=latest_stats.values('printer_id'),
                                                        time_collect__in=latest_stats.values('max_time'))

    printers_total_stats = get_variables_stats(printers_latest_stats, '')
    return_dict.update(printers_total_stats)

    latest_daily_stats = DailyStat.objects.values('printer_id').annotate(max_time=Max('time_collect')).values(
        'printer_id', 'max_time')

    printers_latest_daily_stats = DailyStat.objects.filter(printer_id__in=latest_daily_stats.values('printer_id'),
                                                           time_collect__in=latest_daily_stats.values('max_time'))
    printers_total_daily_stats = get_variables_stats(printers_latest_daily_stats, 'daily_')
    return_dict.update(printers_total_daily_stats)

    try:
        latest_time_collect = DailyStat.objects.order_by('-time_collect').values_list('time_collect',
                                                                                      flat=True).distinct()[1]
        latest_time_collect -= timedelta(days=1)
        formatted_latest_time_collect = latest_time_collect.strftime('%Y-%m-%d') if latest_time_collect else None
        second_latest_stats = DailyStat.objects.filter(time_collect__date=formatted_latest_time_collect)
        printers_total_yesterday_stats = get_variables_stats(second_latest_stats, 'yesterday_')
        return_dict.update(printers_total_yesterday_stats)
        return_dict['percent_daily_pages'] = calculate_percentage(printers_total_daily_stats['sum_total_daily_page'],
                                                                  printers_total_yesterday_stats[
                                                                      'sum_total_yesterday_page'])
        return_dict['percent_daily_print'] = calculate_percentage(printers_total_daily_stats['sum_total_daily_print'],
                                                                  printers_total_yesterday_stats[
                                                                      'sum_total_yesterday_print'])
        return_dict['percent_daily_scan'] = calculate_percentage(printers_total_daily_stats['sum_total_daily_scan'],
                                                                 printers_total_yesterday_stats[
                                                                     'sum_total_yesterday_scan'])
        return_dict['percent_daily_copies'] = calculate_percentage(printers_total_daily_stats['sum_total_daily_copies'],
                                                                   printers_total_yesterday_stats[
                                                                       'sum_total_yesterday_copies'])
    except Exception as e:
        logger_main.warning(f'def index: {e}, Lack of data in the database: percent daily statistics')

    with connection.cursor() as cursor:
        cursor.execute('''
                WITH ranked_stats AS (
                    SELECT *,
                           ROW_NUMBER() OVER (PARTITION BY printer_id ORDER BY time_collect DESC) AS rn
                      FROM daily_statistics
                )
                SELECT id, page, print, copies, scan, time_collect AT TIME ZONE 'UTC' AT TIME ZONE 
                'UTC+7' as time_collect, printer_id, rn
                  FROM ranked_stats
                 WHERE rn <= 7;
            ''')
        printer_all_week_stats = cursor.fetchall()
    df_printer_all_week_stats = pd.DataFrame(printer_all_week_stats,
                                                 columns=['id', 'page', 'print', 'copies',
                                                          'scan', 'time_collect', 'printer_id', 'rn'])
    daily_stats = df_printer_all_week_stats.groupby('time_collect').sum()
    sum_total_weekly_page = daily_stats['page'].sum()
    sum_total_weekly_print = daily_stats['print'].sum()
    sum_total_weekly_scan = daily_stats['scan'].sum()
    sum_total_weekly_copies = daily_stats['copies'].sum()

    end_date_months = (DailyStat.objects.aggregate(Max('time_collect'))['time_collect__max'])
    if end_date_months is not None:
        start_date_months = end_date_months - timedelta(days=30)
        start_date_months = start_date_months.replace(hour=0, minute=0, second=0, microsecond=0)
        total_sum_all_printers = DailyStat.objects.filter(
            time_collect__range=(start_date_months, end_date_months)).aggregate(Sum('page'))
    else:
        total_sum_all_printers = 0

    update_return_dict = {'sum_total_weekly_page': sum_total_weekly_page, 'sum_total_weekly_print':
            sum_total_weekly_print, 'sum_total_weekly_scan': sum_total_weekly_scan, 'sum_total_weekly_copies':
                                  sum_total_weekly_copies, 'total_sum_all_printers': total_sum_all_printers}

    return_dict.update(update_return_dict)

    return render(request, 'monitoring/printers.html', return_dict)


@login_required(login_url='/accounts/login')
@log_user_action
def single_printer(request, printer_id):
    printer = get_object_or_404(Printer, pk=printer_id)

    request.session['printer_id'] = printer_id

    return_dict = update_info()

    printer_supplies = PrinterSupplyStatus.objects.filter(printer=printer)
    return_dict['printer_supplies'] = printer_supplies

    printer_stats = Statistics.objects.filter(printer_id=printer_id).order_by('-time_collect')[:1]
    printer_daily_stats = DailyStat.objects.filter(printer_id=printer_id).order_by('-time_collect')[:1]
    printer_yesterday_daily_stats = DailyStat.objects.filter(printer_id=printer_id).order_by('-time_collect')[1:2]
    printer_weekly_stats = DailyStat.objects.filter(printer_id=printer_id).order_by('-time_collect')[:7]
    last_monthly_stats = DailyStat.objects.filter(printer_id=printer_id).order_by('-time_collect')[:30]

    printers_total_daily_stats = get_variables_stats(printer_daily_stats, 'daily_')
    return_dict.update(printers_total_daily_stats)

    printers_total_yesterday_stats = get_variables_stats(printer_yesterday_daily_stats, 'yesterday_')
    return_dict.update(printers_total_yesterday_stats)

    return_dict['percent_daily_pages'] = calculate_percentage(printers_total_daily_stats['sum_total_daily_page'],
                                               printers_total_yesterday_stats['sum_total_yesterday_page'])
    return_dict['percent_daily_print'] = calculate_percentage(printers_total_daily_stats['sum_total_daily_print'],
                                               printers_total_yesterday_stats['sum_total_yesterday_print'])
    return_dict['percent_daily_scan'] = calculate_percentage(printers_total_daily_stats['sum_total_daily_scan'],
                                              printers_total_yesterday_stats['sum_total_yesterday_scan'])
    return_dict['percent_daily_copies'] = calculate_percentage(printers_total_daily_stats['sum_total_daily_copies'],
                                                printers_total_yesterday_stats['sum_total_yesterday_copies'])

    printers_weekly_stats = get_variables_stats(printer_weekly_stats, 'weekly_')
    return_dict.update(printers_weekly_stats)

    total_month_sum = last_monthly_stats.aggregate(total_sum=Sum(F('page')))['total_sum']

    update_return_dict = {'printer': printer, 'printer_stats': printer_stats, 'printer_daily_stats':
        printer_daily_stats, 'total_month_sum': total_month_sum}

    latest_events = timezone.now() - timedelta(days=30)
    recent_changes_supplies = ChangeSupply.objects.filter(printer_id=printer_id, time_change__gte=latest_events)
    recent_errors = PrinterError.objects.filter(printer_id=printer_id, event_date__gte=latest_events)
    recent_admin_log = LogEntry.objects.filter(object_repr=printer, action_time__gte=latest_events)
    events_single_printer_small = create_events(recent_changes_supplies, recent_errors, recent_admin_log)[:10]
    return_dict['events_single_printer_small'] = events_single_printer_small

    try:
        printer_cost = MaintenanceCosts.objects.filter(
            printer_id=printer_id).order_by('id')[0]

        printer_forecast = Forecast.objects.filter(
            printer_id=printer_id).aggregate(
            total_pages=Sum('daily_pages'))

        first_forecast_date = Forecast.objects.aggregate(first_forecast_date=Min('forecast_date'))['first_forecast_date']
        month_forecast = first_forecast_date.strftime("%B %Y")

        update_return_dict['printer_cost'] = printer_cost
        update_return_dict['printer_forecast'] = printer_forecast
        update_return_dict['month_forecast'] = month_forecast

    except Exception as e:
        logger_main.warning(f'def single_printer: {e}, Lack of data in the database: forecast info')

    return_dict.update(update_return_dict)

    return render(request, 'monitoring/single_printer.html', return_dict)


@login_required(login_url='/accounts/login')
def data_in_js(request, nm_data):
    def switch_case(value: str):
        printer_id = request.session.get('printer_id')
        switcher = {
            'week-stats': lambda: process_few_days_printer_stats(printer_id, 7, '%A'),
            'month-stats': lambda: process_few_days_printer_stats(printer_id, 30, '%d.%m'),
            'year-print-stats': lambda: get_few_months_print_stats(12),
            'three-months-print-stats': lambda: get_few_months_print_stats(3),
            'forecast': lambda: get_forecast_stats(printer_id)
        }
        return switcher.get(value, lambda: {"error": "Invalid value", "code": 400})()

    def process_few_days_printer_stats(printer_id, qty_days: int, time_format: str) -> dict:
        stats = create_printer_stats(qty_days)
        filling_printer_stats(printer_id, stats, qty_days, time_format)

        if qty_days == 30:
            return {'data_monthly_page': stats}
        elif qty_days == 7:
            max_val = calculate_max_values(stats)
            return prepare_weekly_stats(stats, max_val)
        return {}

    def create_printer_stats(qty_days: int) -> dict:
        stats = {'print': [], 'scan': [], 'copies': [], 'day': []}
        if qty_days == 7:
            stats['total'] = []
        return stats

    def filling_printer_stats(printer_id, stats: dict, qty_days: int, time_format: str):
        if printer_id:
            printer_stats = DailyStat.objects.filter(printer_id=printer_id).order_by('-time_collect')[:qty_days]
            process_printer_stats(printer_stats, stats, time_format)
        else:
            printers_stats = get_all_printer_stats(qty_days)
            process_all_printers_stats(printers_stats, stats, time_format, qty_days)

    def process_printer_stats(queryset: dict, stats: dict, time_format: str):
        for stat in reversed(queryset):
            if 'total' in stats:
                stats['total'].append(stat.page)
            stats['print'].append(stat.print)
            stats['scan'].append(stat.scan)
            stats['copies'].append(stat.copies)
            str_day = str(stat.time_collect)
            datetime_obj = datetime.fromisoformat(str_day) + timedelta(hours=7)
            stats['day'].append(datetime_obj.strftime(time_format).capitalize())
        if len(stats['print']) < 7:
            missing_count = 7 - len(stats['print'])
            zero_fill = [0] * missing_count
            for key in stats.keys():
                stats[key] += zero_fill

    def get_all_printer_stats(qty_days):
        with connection.cursor() as cursor:
            cursor.execute(f'''
                WITH ranked_stats AS (
                    SELECT *,
                           ROW_NUMBER() OVER (PARTITION BY printer_id ORDER BY time_collect DESC) AS rn
                      FROM daily_statistics
                )
                SELECT id, page, print, copies, scan, time_collect AT TIME ZONE 'UTC' AT TIME ZONE 
                'UTC+7' as time_collect, printer_id, rn
                  FROM ranked_stats
                 WHERE rn <= {qty_days};
            ''')
            return cursor.fetchall()

    def calculate_max_values(week_stats):
        return {
            key: max(val) * 1.2 if val and all(isinstance(v, int) for v in val) else 0
            for key, val in week_stats.items()
        }

    def process_all_printers_stats(queryset: dict, stats: dict, time_format: str, qty_days: int):
        df_printer_all_stats = pd.DataFrame(queryset, columns=['id', 'page', 'print', 'copies',
                                                               'scan', 'time_collect', 'printer_id', 'rn'])

        df_printer_all_stats['time_collect'] = pd.to_datetime(df_printer_all_stats['time_collect']).dt.strftime(
            '%Y-%m-%d')
        daily_stats = df_printer_all_stats.groupby('time_collect').sum()

        daily_stats = check_compliance_qty_days(daily_stats, qty_days)

        if 'total' in stats:
            stats['total'] = daily_stats['page'].tolist()
        stats['print'] = daily_stats['print'].tolist()
        stats['scan'] = daily_stats['scan'].tolist()
        stats['copies'] = daily_stats['copies'].tolist()
        day_stats_res = daily_stats.index.tolist()
        for day in day_stats_res:
            str_day = str(day)
            datetime_obj = datetime.fromisoformat(str_day)
            stats['day'].append(datetime_obj.strftime(time_format).capitalize())

    def check_compliance_qty_days(statistics, qty_days):
        if len(statistics) > qty_days:
            statistics = statistics.iloc[1:]
        return statistics

    def prepare_weekly_stats(week_stats, max_val):
        data_weekly_stats = {}
        datasets = ['total', 'print', 'scan', 'copies']

        for dataset in datasets:
            data_weekly_stats[dataset] = {
                'labels': week_stats['day'],
                'datasets': [
                    {
                        'label': "Страниц",
                        'data': week_stats[dataset],
                        'borderColor': "#a0bfff",
                        'backgroundColor': "#a0bfff",
                        'hoverBackgroundColor': "#a0bfff"
                    }
                ],
                'max': max_val[dataset]
            }

        return {'data_weekly_stats': data_weekly_stats}

    def get_few_months_print_stats(qty_months: int):
        print_stats = fetch_few_months_print_stats(qty_months)
        labels, values = process_few_months_print_stats(print_stats)

        if qty_months == 3:
            return get_three_months_print_stats(labels, values)
        if qty_months == 12:
            return get_year_print_stats(labels, values)

        return {}

    def fetch_few_months_print_stats(qty_months):
        with connection.cursor() as cursor:
            cursor.execute(f'''
                SELECT DATE_TRUNC('month', time_collect) AS month_date, SUM(print) AS total_sum
                FROM (
                    SELECT printer_id, print, time_collect,
                           ROW_NUMBER() OVER (PARTITION BY printer_id ORDER BY time_collect DESC) AS rn
                    FROM public.monthly_statistics
                ) AS sub
                WHERE rn <= {qty_months}
                GROUP BY DATE_TRUNC('month', time_collect)
                ORDER BY DATE_TRUNC('month', time_collect) DESC;
            ''')
            return cursor.fetchall()

    def process_few_months_print_stats(year_print_stats):
        df_year_print_stats = pd.DataFrame(year_print_stats, columns=['month_date', 'total_sum'])

        labels = [
            f"{months_map[datetime.fromisoformat(str(day)).month - 1]} {datetime.fromisoformat(str(day)).year}"
            for day in reversed(df_year_print_stats['month_date'].tolist())
        ]

        values = [str(value) for value in reversed(df_year_print_stats['total_sum'].tolist())]

        return labels, values

    def get_year_print_stats(labels_year, values_year) -> dict:
        year_data_chart = {'labels_year': labels_year, 'values_year': values_year}
        return {'year_data_chart': year_data_chart}

    def get_three_months_print_stats(labels_year, values_year) -> dict:
        values_three_month = values_year if len(values_year) == 3 else values_year + ['0'] * (3 - len(values_year))
        labels_three_month = labels_year if len(labels_year) == 3 else labels_year + ['0'] * (3 - len(labels_year))
        labels_three_month = ['Месяц' if date == '0' else date.split()[0] for date in labels_three_month]

        morris_donught_data = {
            'label_first': f"\xa0 \xa0 {labels_three_month[0]} \xa0 \xa0",
            'value_first': values_three_month[0],
            'label_second': f"\xa0 \xa0 {labels_three_month[1]} \xa0 \xa0",
            'value_second': values_three_month[1],
            'label_third': f"\xa0 \xa0 {labels_three_month[2]} \xa0 \xa0",
            'value_third': values_three_month[2],
        }

        return {'morris_donught_data': morris_donught_data}

    def get_forecast_stats(printer_id):
        forecast_stats = {'total': [], 'day': []}
        if printer_id:
            printer_forecast = (Forecast.objects.filter(printer_id=printer_id).
                                order_by('id').values('forecast_date', 'daily_pages'))
            value_field = 'daily_pages'
        else:
            printer_forecast = (Forecast.objects.values('forecast_date').
                                annotate(total_daily_pages=Sum('daily_pages')).
                                order_by('forecast_date'))
            value_field = 'total_daily_pages'

        df_printer_forecast = pd.DataFrame(printer_forecast, columns=['forecast_date', value_field])
        forecast_stats['total'] = df_printer_forecast[value_field].tolist()
        day_month_forecast_res = df_printer_forecast['forecast_date'].tolist()
        for day in day_month_forecast_res:
            str_day = str(day)
            datetime_obj = datetime.fromisoformat(str_day)
            forecast_stats['day'].append(datetime_obj.strftime('%d.%m').capitalize())

        return {'forecast_data_chart': forecast_stats}

    return JsonResponse(switch_case(nm_data))


@login_required(login_url='/accounts/login')
@csrf_exempt
@log_user_action
def reports(request):
    return_dict = update_info()

    form_printers = forms.PrintersReportForm()
    form_statistics = forms.StatisticsReportForm()
    form_day = forms.DayReportForm()
    form_month = forms.MonthReportForm()
    form_supplies = forms.SuppliesReportForm()

    if request.method == 'POST':
        if 'printers_report' in request.POST:
            form_printers = forms.PrintersReportForm(request.POST)
            html_name_report = 'Принтеры '
            if form_printers.is_valid():
                selected_area = form_printers.cleaned_data['area']
                if selected_area != 'all':
                    html_name_report += f'({get_area_name(selected_area)})'
                    printers_supplies = PrinterSupplyStatus.objects.filter(
                        printer__ip_address__subnet__name=selected_area
                    )
                    printers_without_supplies = Printer.objects.annotate(
                        supplies_count=Count('printersupplystatus')
                    ).filter(supplies_count=0, ip_address__subnet__name=selected_area)
                else:
                    printers_supplies = PrinterSupplyStatus.objects.all()
                    printers_without_supplies = Printer.objects.annotate(
                        supplies_count=Count('printersupplystatus')
                    ).filter(supplies_count=0)

                supplies = defaultdict(list)
                for printer in printers_supplies:
                    supplies[printer.printer].append({printer.supply: printer.remaining_supply_percentage})
                for printer in printers_without_supplies:
                    supplies[printer].append({'No': 'Нет расходных материалов'})
                supplies_dict = dict(supplies)

                return_dict['printers'] = supplies_dict
            else:
                pass
            return_dict['html_name_report'] = html_name_report
            return render(request, 'monitoring/single_report/report-printers.html', return_dict)
        elif 'statistics_report' in request.POST:
            form_statistics = forms.StatisticsReportForm(request.POST)
            html_name_report = 'Отчет об использовании принтеров'
            if form_statistics.is_valid():
                selected_area = form_statistics.cleaned_data['area']
                selected_option = form_statistics.cleaned_data['option']
                date_field = form_statistics.cleaned_data['date_field']

                first_time_collect = Statistics.objects.earliest('time_collect').time_collect.date()
                last_time_collect = Statistics.objects.latest('time_collect').time_collect.date()

                if first_time_collect <= date_field <= last_time_collect:
                    context = dict()
                    if selected_option == 'all':
                        if selected_area != 'all':
                            html_name_report += f' ({get_area_name(selected_area)}) на {date_field}'
                            printers = Printer.objects.filter(ip_address__subnet__name=selected_area)
                            printers_list = list()
                            for printer in printers:
                                stats = Statistics.objects.filter(printer_id=printer, time_collect__date=date_field)
                                printers_list.append({'printer': printer, 'stats': stats})
                                context['printers'] = printers_list
                        else:
                            html_name_report += f' на {date_field}'
                            printers_list = list()
                            for printer in return_dict['printers']:
                                stats = Statistics.objects.filter(printer_id=printer, time_collect__date=date_field)
                                printers_list.append({'printer': printer, 'stats': stats})
                            context['printers'] = printers_list
                        context['html_name_report'] = html_name_report
                        return render(request, 'monitoring/single_report/report-usage-all.html', context)
                    else:
                        html_name_report += f': {get_report_option(selected_option)}'
                        if selected_area != 'all':
                            html_name_report += f' ({get_area_name(selected_area)}) на {date_field}'
                            printers = Printer.objects.filter(ip_address__subnet__name=selected_area)
                            printers_list = list()
                            for printer in printers:
                                stats = Statistics.objects.filter(printer_id=printer,
                                                                  time_collect__date=date_field).annotate(
                                    page_count=F(selected_option)).values('page_count')
                                printers_list.append({'printer': printer, 'stats': stats})
                            context['printers'] = printers_list
                        else:
                            html_name_report += f' на {date_field}'
                            printers_list = list()
                            for printer in return_dict['printers']:
                                stats = Statistics.objects.filter(printer_id=printer,
                                                                  time_collect__date=date_field).annotate(
                                    page_count=F(selected_option)).values('page_count')
                                printers_list.append({'printer': printer, 'stats': stats})
                            context['printers'] = printers_list
                        context['html_name_report'] = html_name_report
                        return render(request, 'monitoring/single_report/report-usage.html', context)
                else:
                    context = {'error': f'Введенная дата не входит в период функционирования программы. Пожалуйста '
                                        f'введите дату в промежутке от {first_time_collect.strftime("%d.%m.%Y")} '
                                        f'до {last_time_collect.strftime("%d.%m.%Y")}'}
                    return render(request, 'monitoring/single_report/report-errors.html', context)
            else:
                context = {'form_errors': form_statistics.errors}
                return render(request, 'monitoring/single_report/report-errors.html', context)

        elif 'days_report' in request.POST:
            form_day = forms.DayReportForm(request.POST)
            html_name_report = 'Отчет об ежедневной статистике '
            if form_day.is_valid():
                selected_area = form_day.cleaned_data['area']
                selected_option = form_day.cleaned_data['option']
                date_start = form_day.cleaned_data['date_start']
                date_end = form_day.cleaned_data['date_end']

                if date_start > date_end:
                    context = {'error': 'Дата начала периода не может быть позже даты конца. Повторите ввод.'}
                    return render(request, 'monitoring/single_report/report-errors.html', context)

                first_time_collect = Statistics.objects.earliest('time_collect').time_collect.date()
                last_time_collect = Statistics.objects.latest('time_collect').time_collect.date()

                if (first_time_collect <= date_start <= last_time_collect
                        and first_time_collect <= date_end <= last_time_collect):
                    start_datetime = datetime.strptime(date_start.strftime('%Y-%m-%d'), '%Y-%m-%d')
                    end_datetime = datetime.strptime(date_end.strftime('%Y-%m-%d'), '%Y-%m-%d')
                    start_datetime = start_datetime.replace(hour=0, minute=0)
                    end_datetime = end_datetime.replace(hour=23, minute=59)

                    context = dict()

                    html_name_report += f'{get_report_option(selected_option)} за период с {date_start} по {date_end} '

                    formatted_dates = []
                    current_date = date_start

                    while current_date <= date_end:
                        formatted_dates.append(current_date.strftime('%d.%m.%Y'))
                        current_date += timedelta(days=1)

                    context['dates'] = formatted_dates

                    if selected_area != 'all':
                        html_name_report += f'({get_area_name(selected_area)})'

                        return_dict['printers'] = Printer.objects.filter(ip_address__subnet__name=selected_area)

                        printers_list = list()
                        for printer in return_dict['printers']:
                            values = DailyStat.objects.filter(
                                printer=printer,
                                time_collect__range=(start_datetime, end_datetime)
                            ).order_by('-time_collect').values('printer_id', selected_option, 'time_collect')
                            page_generator = [item[selected_option] for item in values]
                            if values:
                                if len(values) != len(formatted_dates):
                                    if values[len(values) - 1]['time_collect'].date() > first_time_collect:
                                        qty_val_add = (values[len(values) - 1][
                                                           'time_collect'].date() - first_time_collect).days
                                        for val in range(qty_val_add):
                                            page_generator.append(0)
                                    if values[0]['time_collect'].date() < last_time_collect:
                                        qty_val_add = (last_time_collect - values[0]['time_collect'].date()).days
                                        zeros_list = [0] * qty_val_add
                                        page_generator = zeros_list + page_generator
                            else:
                                page_generator = [0] * len(formatted_dates)
                            page_generator = page_generator[::-1]
                            printers_list.append(
                                {'printer': printer, 'page': page_generator, 'total_page': sum(page_generator)})
                        context['printers'] = printers_list

                        total_stats = DailyStat.objects.filter(
                            time_collect__range=(start_datetime, end_datetime),
                            printer__ip_address__subnet__name=selected_area
                        ).values('time_collect__date').annotate(
                            total_pages=Sum(selected_option)
                        ).order_by('time_collect__date')
                        total_sum = total_stats.aggregate(total=Sum('total_pages'))['total']
                        context['total_stats'] = total_stats
                        context['total_sum'] = total_sum
                    else:

                        printers_list = list()
                        for printer in return_dict['printers']:
                            values = DailyStat.objects.filter(
                                printer=printer,
                                time_collect__range=(start_datetime, end_datetime)
                            ).order_by('-time_collect').values('printer_id', selected_option, 'time_collect')
                            page_generator = [item[selected_option] for item in values]
                            if values:
                                if len(values) != len(formatted_dates):
                                    if values[len(values) - 1]['time_collect'].date() > first_time_collect:
                                        qty_val_add = (values[len(values) - 1][
                                                           'time_collect'].date() - first_time_collect).days
                                        for val in range(qty_val_add):
                                            page_generator.append(0)
                                    if values[0]['time_collect'].date() < last_time_collect:
                                        qty_val_add = (last_time_collect - values[0]['time_collect'].date()).days
                                        zeros_list = [0] * qty_val_add
                                        page_generator = zeros_list + page_generator
                            else:
                                page_generator = [0] * len(formatted_dates)
                            page_generator = page_generator[::-1]
                            printers_list.append(
                                {'printer': printer, 'page': page_generator, 'total_page': sum(page_generator)})
                        context['printers'] = printers_list

                        total_stats = DailyStat.objects.filter(time_collect__range=(start_datetime, end_datetime)) \
                            .values('time_collect__date') \
                            .annotate(total_pages=Sum(selected_option)) \
                            .order_by('time_collect__date')
                        total_sum = total_stats.aggregate(total=Sum('total_pages'))['total']
                        context['total_stats'] = total_stats
                        context['total_sum'] = total_sum

                    context['html_name_report'] = html_name_report

                    return render(request, 'monitoring/single_report/report-qty-pages.html', context)
                else:
                    context = {'error': f'Заданный период не входит в период функционирования программы. Пожалуйста '
                                        f'введите период в промежутке от {first_time_collect.strftime("%d.%m.%Y")} '
                                        f'до {last_time_collect.strftime("%d.%m.%Y")}'}
                    return render(request, 'monitoring/single_report/report-errors.html', context)
            else:
                context = {'form_errors': form_day.errors}
                return render(request, 'monitoring/single_report/report-errors.html', context)

        elif 'months_report' in request.POST:
            form_month = forms.MonthReportForm(request.POST)
            html_name_report = 'Отчет об ежемесячной статистике '
            if form_month.is_valid():
                selected_area = form_month.cleaned_data['area']
                selected_option = form_month.cleaned_data['option']
                date_start = form_month.cleaned_data['date_start']
                date_end = form_month.cleaned_data['date_end']

                end_datetime = datetime.strptime(date_end.strftime('%Y-%m-%d'), '%Y-%m-%d')
                last_day = calendar.monthrange(end_datetime.year, end_datetime.month)[1]
                end_datetime = end_datetime.replace(day=last_day, hour=23, minute=59)

                context = dict()

                month_start_index = date_start.month - 1
                formated_month_start = months_map[month_start_index]
                month_end_index = date_end.month - 1
                formated_month_end = months_map[month_end_index]
                html_name_report += (f'{get_report_option(selected_option)} за период '
                                     f'с {formated_month_start} {date_start.year} по {formated_month_end} '
                                     f'{date_end.year} ')

                formatted_dates = []
                current_date = date_start

                while current_date <= date_end:
                    month_index = current_date.month - 1
                    formated_month = months_map[month_index]
                    formatted_dates.append(f"{formated_month} {current_date.year}")
                    current_date += relativedelta(months=1)

                context['dates'] = formatted_dates
                if selected_area != 'all':
                    html_name_report += f'({get_area_name(selected_area)})'

                    values = MonthlyStat.objects.filter(
                        printer__in=return_dict['printers'],
                        time_collect__range=(date_start, end_datetime),
                        printer__ip_address__subnet__name=selected_area
                    ).order_by('id').values('printer_id', selected_option, 'time_collect')
                    return_dict['printers'] = Printer.objects.filter(ip_address__subnet__name=selected_area)

                    total_stats = MonthlyStat.objects.filter(
                        time_collect__range=(date_start, end_datetime),
                        printer__ip_address__subnet__name=selected_area
                    ).annotate(
                        month=TruncMonth('time_collect')
                    ).values('month').annotate(
                        total_pages=Sum(selected_option)
                    ).order_by('month')
                    total_sum = total_stats.aggregate(total=Sum('total_pages'))['total']
                    context['total_stats'] = total_stats
                    context['total_sum'] = total_sum
                else:
                    values = MonthlyStat.objects.filter(
                        printer__in=return_dict['printers'],
                        time_collect__range=(date_start, end_datetime)
                    ).order_by('id').values('printer_id', selected_option, 'time_collect')

                    total_stats = MonthlyStat.objects.filter(
                        time_collect__range=(date_start, end_datetime)
                    ).annotate(
                        month=TruncMonth('time_collect')
                    ).values('month').annotate(
                        total_pages=Sum(selected_option)
                    ).order_by('month')
                    total_sum = total_stats.aggregate(total=Sum('total_pages'))['total']
                    context['total_stats'] = total_stats
                    context['total_sum'] = total_sum

                context['html_name_report'] = html_name_report

                page_generator = (item[selected_option] for item in values)
                printers_list = list()
                for printer in return_dict['printers']:
                    list_page = list()
                    for j in range(len(formatted_dates)):
                        try:
                            list_page.append(next(page_generator))
                        except StopIteration:
                            break
                    printers_list.append({'printer': printer, 'page': list_page, 'total_page': sum(list_page)})
                context['printers'] = printers_list

                return render(request, 'monitoring/single_report/report-qty-pages.html', context)

        elif 'supplies_report' in request.POST:
            form_supplies = forms.SuppliesReportForm(request.POST)
            html_name_report = 'Отчет по замене расходных материалов '
            if form_supplies.is_valid():
                selected_area = form_supplies.cleaned_data['area']
                date_start = form_supplies.cleaned_data['date_start']
                date_end = form_supplies.cleaned_data['date_end']
                printers = return_dict['printers']
                context = dict()

                if date_start > date_end:
                    context = {'error': 'Дата начала периода не может быть позже даты конца. Повторите ввод.'}
                    return render(request, 'monitoring/single_report/report-errors.html', context)

                first_time_collect = Statistics.objects.earliest('time_collect').time_collect.date()
                last_time_collect = Statistics.objects.latest('time_collect').time_collect.date()

                if (first_time_collect <= date_start <= last_time_collect
                        and first_time_collect <= date_end <= last_time_collect):

                    html_name_report += f'за период с {date_start} по {date_end} '

                    start_datetime = datetime.strptime(date_start.strftime('%Y-%m-%d'), '%Y-%m-%d')
                    end_datetime = datetime.strptime(date_end.strftime('%Y-%m-%d'), '%Y-%m-%d')
                    start_datetime = start_datetime.replace(hour=0, minute=0)
                    end_datetime = end_datetime.replace(hour=23, minute=59)

                    formatted_dates = []
                    current_date = date_start

                    while current_date <= date_end:
                        formatted_dates.append(current_date.strftime('%d.%m.%Y'))
                        current_date += timedelta(days=1)

                    if selected_area != 'all':
                        html_name_report += f' ({get_area_name(selected_area)})'
                        printers = Printer.objects.filter(ip_address__subnet__name=selected_area)
                        qty_supplies = ChangeSupply.objects.filter(
                            time_change__range=(start_datetime, end_datetime),
                            printer__ip_address__subnet__name=selected_area
                        ).values('supply').annotate(
                            total_time_change=Count('time_change')
                        )
                    else:
                        qty_supplies = ChangeSupply.objects.filter(
                            time_change__range=(start_datetime, end_datetime),
                        ).values('supply').annotate(
                            total_time_change=Count('time_change')
                        )

                    supply_ids = [item['supply'] for item in qty_supplies]

                    supplies = SupplyItem.objects.filter(id__in=supply_ids)

                    result_qty_supplies = []
                    for supply in supplies:
                        total_time_change = next(
                            (item['total_time_change'] for item in qty_supplies if item['supply'] == supply.id), 0)
                        result_qty_supplies.append({
                            'supply': supply,
                            'total_time_change': total_time_change
                        })

                    context['qty_supplies'] = result_qty_supplies
                    context['html_name_report'] = html_name_report

                    dicts_all_change = list()
                    printers_list = list()
                    for printer in printers:
                        dict_change = dict.fromkeys(formatted_dates, '')
                        changes = ChangeSupply.objects.filter(
                            printer_id=printer,
                            time_change__gte=start_datetime,
                            time_change__lte=end_datetime
                        ).annotate(time_change_adjusted=F('time_change') + timedelta(hours=7))
                        for change in changes:
                            key = change.time_change_adjusted.strftime('%d.%m.%Y')
                            dict_change[key] += ', ' if dict_change[key] != '' else ''
                            dict_change[key] += f"{change.supply}"
                        dicts_all_change.append(dict_change)
                        printers_list.append({'printer': printer,})
                    context['printers'] = printers_list

                    dates_new = list()
                    for d in dicts_all_change:
                        for date, value in d.items():
                            if value:
                                dates_new.append(date)
                    unique_dates = list(set(dates_new))
                    sorted_dates = sorted(unique_dates, key=lambda x: datetime.strptime(x, '%d.%m.%Y'))

                    context['dates'] = sorted_dates

                    for d in dicts_all_change:
                        for date in list(d.keys()):
                            if date not in sorted_dates:
                                del d[date]
                    for printer in range(len(printers_list)):
                        list_change = list(dicts_all_change[printer].values())
                        printers_list[printer]['changes'] = list_change

                    return render(request, 'monitoring/single_report/report-supplies.html', context)

                else:
                    context = {'error': f'Заданный период не входит в период функционирования программы. Пожалуйста '
                                        f'введите период в промежутке от {first_time_collect.strftime("%d.%m.%Y")} '
                                        f'до {last_time_collect.strftime("%d.%m.%Y")}'}
                    return render(request, 'monitoring/single_report/report-errors.html', context)
            else:
                context = {'form_errors': form_supplies.errors}
                return render(request, 'monitoring/single_report/report-errors.html', context)

    return_dict['form_printers'] = form_printers
    return_dict['form_statistics'] = form_statistics
    return_dict['form_day'] = form_day
    return_dict['form_month'] = form_month
    return_dict['form_supplies'] = form_supplies
    return render(request, 'monitoring/reports.html', return_dict)


@login_required(login_url='/accounts/login')
@log_user_action
def single_report(request, nm_report, qty_days):
    printers = Printer.objects.all()
    context = dict()
    context['printers'] = printers
    str_time = 'за новое время '
    int_days = 30
    str_nm_report = f'{get_report_option(nm_report)} '
    url_fast_api = 'http://lw10-219:8001/print-log/'

    if qty_days == '7days':
        str_time = 'за последние 7 дней '
        int_days = 7
    elif qty_days == '30days':
        str_time = 'за последние 30 дней '
    elif qty_days == 'all-time':
        pass
    else:
        return HttpResponseBadRequest('Неверные параметры для отчета')

    tuple_report_name = {'event-log', 'print-log', 'page', 'print', 'copies', 'scan'}
    if nm_report not in tuple_report_name:
        return HttpResponseBadRequest('Неверные параметры для отчета')

    if qty_days == 'all-time':
        str_time = 'за всё время '
        if nm_report == 'event-log':
            all_changes_supplies = ChangeSupply.objects.all()
            all_errors = PrinterError.objects.all()
            all_admin_log = LogEntry.objects.all()

            context['events_all'] = create_events(all_changes_supplies, all_errors, all_admin_log)
            context['html_name_report'] = 'Отчёт ' + str_nm_report + str_time

            return render(request, 'monitoring/single_report/report-events.html', context)
        elif nm_report == 'print-log':
            context['html_name_report'] = 'Отчёт ' + str_nm_report + str_time
            try:
                response = requests.get(url_fast_api)
                response.raise_for_status()
                print_log = response.json()
                for event in print_log:
                    time_created_str = event['TimeCreated']
                    dt = datetime.fromisoformat(time_created_str)
                    timestamp = dt.timestamp()
                    event['TimeCreated'] = datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M')
                context['print_log'] = print_log
                return render(request, 'monitoring/single_report/report-print-log.html', context)
            except requests.exceptions.RequestException as e:
                context = {'error': f'Ошибка подключения: {str(e)}'}
                logger_main.error(f'def single_report: {str(e)}, Connection error: The Fast API (print_log) server '
                                  f'is unavailable.')
                return render(request, 'monitoring/single_report/report-errors.html', context)

        else:
            try:
                first_time_collect = DailyStat.objects.earliest('time_collect').time_collect.date()
                last_time_collect = DailyStat.objects.latest('time_collect').time_collect.date()

                start_datetime = datetime.strptime(first_time_collect.strftime('%Y-%m-%d'), '%Y-%m-%d')
                end_datetime = datetime.strptime(last_time_collect.strftime('%Y-%m-%d'), '%Y-%m-%d')
                start_datetime = start_datetime.replace(hour=0, minute=0)
                end_datetime = end_datetime.replace(hour=23, minute=59)

                formatted_dates = []
                current_date = first_time_collect

                while current_date <= last_time_collect:
                    formatted_dates.append(current_date.strftime('%d.%m.%Y'))
                    current_date += timedelta(days=1)

                context['dates'] = formatted_dates

                printers_list = list()
                for printer in printers:
                    values = DailyStat.objects.filter(
                        printer=printer,
                        time_collect__range=(start_datetime, end_datetime)
                    ).order_by('-time_collect').values('printer_id', nm_report, 'time_collect')
                    page_generator = [item[nm_report] for item in values]
                    if values:
                        if len(values) != len(formatted_dates):
                            if values[len(values) - 1]['time_collect'].date() > first_time_collect:
                                qty_val_add = (values[len(values) - 1]['time_collect'].date() - first_time_collect).days
                                for val in range(qty_val_add):
                                    page_generator.append(0)
                            if values[0]['time_collect'].date() < last_time_collect:
                                qty_val_add = (last_time_collect - values[0]['time_collect'].date()).days
                                zeros_list = [0] * qty_val_add
                                page_generator = zeros_list + page_generator
                    else:
                        page_generator = [0] * len(formatted_dates)
                    page_generator = page_generator[::-1]
                    printers_list.append(
                        {'printer': printer, 'page': page_generator, 'total_page': sum(page_generator)})
                context['printers'] = printers_list

                total_stats = DailyStat.objects.filter(time_collect__range=(start_datetime, end_datetime)) \
                    .values('time_collect__date') \
                    .annotate(total_pages=Sum(nm_report)) \
                    .order_by('time_collect__date')

                total_sum = total_stats.aggregate(total=Sum('total_pages'))['total']
                context['total_stats'] = total_stats
                context['total_sum'] = total_sum
                context['html_name_report'] = 'Отчёт ' + str_nm_report + str_time
                return render(request, 'monitoring/single_report/report-qty-pages.html', context)
            except Exception as e:
                context['html_name_report'] = 'Отчёт ' + str_nm_report + str_time
                logger_main.warning('def single_report: all statistics. There is no data in the database.')
                return render(request, 'monitoring/single_report/report-qty-pages.html', context)

    elif qty_days == '7days' or '30days':
        if nm_report == 'event-log':
            last_days = timezone.now() - timedelta(days=int_days)

            recent_changes_supplies = ChangeSupply.objects.filter(time_change__gte=last_days)
            recent_errors = PrinterError.objects.filter(event_date__gte=last_days)
            recent_admin_log = LogEntry.objects.filter(action_time__gte=last_days)

            context['html_name_report'] = 'Отчёт ' + str_nm_report + str_time
            context['events_all'] = create_events(recent_changes_supplies, recent_errors, recent_admin_log)

            return render(request, 'monitoring/single_report/report-events.html', context)
        elif nm_report == 'print-log':
            context['html_name_report'] = 'Отчёт ' + str_nm_report + str_time
            start_date = timezone.now() + timedelta(days=1)
            end_date = start_date - timedelta(days=int_days)
            url_fast_api += f"?start_date={end_date.strftime('%Y-%m-%d')}&end_date={start_date.strftime('%Y-%m-%d')}"

            try:
                response = requests.get(url_fast_api)
                response.raise_for_status()
                print_log = response.json()
                for event in print_log:
                    if 'TimeCreated' in event:
                        time_created_str = event['TimeCreated']
                    else:
                        continue
                    dt = datetime.fromisoformat(time_created_str)
                    timestamp = dt.timestamp()
                    event['TimeCreated'] = datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M')
                context['print_log'] = print_log
                return render(request, 'monitoring/single_report/report-print-log.html', context)
            except requests.exceptions.RequestException as e:
                context = {'error': f'Ошибка подключения: {str(e)}'}
                logger_main.error(f'def single_report: {str(e)}, Connection error: The Fast API (print_log) server '
                                  f'is unavailable.')
                return render(request, 'monitoring/single_report/report-errors.html', context)
        else:
            try:
                first_time_collect = DailyStat.objects.earliest('time_collect').time_collect.date()
                last_time_collect = DailyStat.objects.latest('time_collect').time_collect.date()

                difference = last_time_collect - first_time_collect

                if difference.days == 0:
                    str_time = f'за последние не {int_days} дней(1д)'
                    int_days = difference.days + 1
                elif difference.days + 1 < int_days and difference.days != 0:
                    str_time = f'за последние не {int_days} '
                    int_days = difference.days + 1
                    str_time += f'({int_days}д)'
                else:
                    first_time_collect = last_time_collect - timedelta(days=int_days)

                formatted_dates = []
                current_date = first_time_collect

                while current_date <= last_time_collect:
                    formatted_dates.append(current_date.strftime('%d.%m.%Y'))
                    current_date += timedelta(days=1)

                context['dates'] = formatted_dates

                printers_list = list()
                for printer in printers:
                    values = DailyStat.objects.filter(
                        printer=printer).order_by('-time_collect')[:int_days].values('printer_id', nm_report, 'time_collect')
                    page_generator = [item[nm_report] for item in values]
                    if values:
                        if len(values) != len(formatted_dates):
                            if values[len(values) - 1]['time_collect'].date() > first_time_collect:
                                qty_val_add = (values[len(values) - 1]['time_collect'].date() - first_time_collect).days
                                for val in range(qty_val_add):
                                    page_generator.append(0)
                            if values[0]['time_collect'].date() < last_time_collect:
                                qty_val_add = (last_time_collect - values[0]['time_collect'].date()).days
                                zeros_list = [0] * qty_val_add
                                page_generator = zeros_list + page_generator
                    else:
                        page_generator = [0] * len(formatted_dates)
                    page_generator = page_generator[::-1]
                    printers_list.append({'printer': printer, 'page': page_generator, 'total_page': sum(page_generator)})
                context['printers'] = printers_list

                total_stats = list()
                if printers_list and 'page' in printers_list[0]:
                    for i in range(len(printers_list[0]['page'])):
                        total_page = sum(printer['page'][i] for printer in printers_list if i < len(printer['page']))
                        total_stats.append({'total_pages': total_page})
                context['total_stats'] = total_stats
                context['total_sum'] = sum(stat['total_pages'] for stat in total_stats)
                context['html_name_report'] = 'Отчёт ' + str_nm_report + str_time
                return render(request, 'monitoring/single_report/report-qty-pages.html', context)
            except Exception as e:
                context['html_name_report'] = 'Отчёт ' + str_nm_report + str_time
                logger_main.warning('def single_report: range statistics. There is no data in the database.')
                return render(request, 'monitoring/single_report/report-qty-pages.html', context)

    else:
        render(request, 'monitoring/single_report/report-printers.html', context)

@login_required(login_url='/accounts/login')
@log_user_action
@csrf_exempt
def export_report(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        table_html = data.get('table')
        part = data.get('part')
        total_parts = data.get('totalParts')
        html_string = str(table_html)
        user = request.user
        username = user.username

        with open(f'export_report/temp_{username}_report_part_{part}.html', 'w', encoding='utf-8-sig') as f:
            f.write(html_string)

        if part == total_parts - 1:
            fact_parts = check_file_count(total_parts)
            if not fact_parts:
                return HttpResponse("Ошибка доступа к файлу. Попробуйте позже.", status=500)

            final_report_path = 'export_report/final_report.html'
            with open(final_report_path, 'w', encoding='utf-8-sig') as final_file:
                for i in range(total_parts):
                    temp_file_path = f'export_report/temp_{username}_report_part_{i}.html'
                    try:
                        if os.path.exists(temp_file_path):
                            with open(temp_file_path, 'r', encoding='utf-8-sig') as temp_file:
                                final_file.write(temp_file.read())
                            os.remove(temp_file_path)
                        else:
                            return HttpResponse("Временный файл не найден.", status=404)
                    except PermissionError:
                        return HttpResponse("Ошибка доступа к файлу. Попробуйте позже.", status=500)

            tables = pd.read_html(final_report_path)
            os.remove(final_report_path)
            df = tables[0]
            output = BytesIO()

            try:
                df.to_excel(output, index=False)
            except NotImplementedError as e:
                df.to_excel(output, index=True)

            output.seek(0)

            response = HttpResponse(output,
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="output.xlsx"'
            return response

        return HttpResponse(status=200)


def check_file_count(total_parts):
    fact_parts = 0
    max_attempts = 10
    attempt = 0

    while total_parts != fact_parts:
        fact_parts = count_files_in_directory('export_report')
        time.sleep(1)
        attempt += 1

        if attempt >= max_attempts:
            return

    return fact_parts


def count_files_in_directory(directory):
    items = os.listdir(directory)

    count = 0

    for item in items:
        if os.path.isfile(os.path.join(directory, item)):
            count += 1

    return count



def check_file_count(total_parts):
    fact_parts = 0
    max_attempts = 10
    attempt = 0

    while total_parts != fact_parts:
        fact_parts = count_files_in_directory('export_report')
        time.sleep(1)
        attempt += 1

        if attempt >= max_attempts:
            return

    return fact_parts


def count_files_in_directory(directory):
    items = os.listdir(directory)

    count = 0

    for item in items:
        if os.path.isfile(os.path.join(directory, item)):
            count += 1

    return count



@login_required(login_url='/accounts/login')
@log_user_action
@csrf_exempt
def export_report(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        table_html = data.get('table')
        part = data.get('part')
        total_parts = data.get('totalParts')
        html_string = str(table_html)
        user = request.user
        username = user.username

        with open(f'temp_{username}_report_part_{part}.html', 'w', encoding='utf-8-sig') as f:
            f.write(html_string)

        if part == total_parts - 1:
            final_report_path = 'final_report.html'
            with open(final_report_path, 'w', encoding='utf-8-sig') as final_file:
                for i in range(total_parts):
                    temp_file_path = f'temp_{username}_report_part_{i}.html'
                    try:
                        if os.path.exists(temp_file_path):
                            with open(temp_file_path, 'r', encoding='utf-8-sig') as temp_file:
                                final_file.write(temp_file.read())
                            os.remove(temp_file_path)
                        else:
                            return HttpResponse("Временный файл не найден.", status=404)
                    except PermissionError:
                        return HttpResponse("Ошибка доступа к файлу. Попробуйте позже.", status=500)

            tables = pd.read_html(final_report_path)
            os.remove(final_report_path)
            df = tables[0]
            output = BytesIO()

            try:
                df.to_excel(output, index=False)
            except NotImplementedError as e:
                df.to_excel(output, index=True)

            output.seek(0)

            response = HttpResponse(output,
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="output.xlsx"'
            return response

        return HttpResponse(status=200)


@login_required(login_url='/accounts/login')
@log_user_action
def events(request):
    return_dict = update_info()

    date_90_days = timezone.now() - timedelta(days=90)

    recent_changes_supplies = ChangeSupply.objects.filter(time_change__gte=date_90_days)
    recent_errors = PrinterError.objects.filter(event_date__gte=date_90_days)
    recent_admin_log = LogEntry.objects.filter(action_time__gte=date_90_days)

    return_dict['events_all'] = create_events(recent_changes_supplies, recent_errors, recent_admin_log)

    return render(request, 'monitoring/events.html', return_dict)


@login_required(login_url='/accounts/login')
@log_user_action
def forecast(request):
    if 'printer_id' in request.session:
        printer_id = request.session.pop('printer_id')

    return_dict = update_info()

    first_forecast_date = Forecast.objects.aggregate(
        first_forecast_date=Min('forecast_date'))['first_forecast_date']

    try:
        month_forecast = first_forecast_date.strftime("%B %Y")
        return_dict['month_forecast'] = month_forecast

    except Exception as e:
        logger_main.warning(f'def forecast: {e}, Lack of data in the database: month forecast')

    total_daily_pages = Forecast.objects.aggregate(
        total_daily_pages=Sum('daily_pages'))

    total_costs = MaintenanceCosts.objects.aggregate(
        total_paper_cost=Sum('paper_cost'),
        total_supplies_cost=Sum('supplies_cost'))

    update_return_dict = {'total_daily_pages': total_daily_pages, 'total_costs': total_costs,}
                              # 'table_forecast': table_forecast

    return_dict.update(update_return_dict)

    return render(request, 'monitoring/forecast.html', return_dict)


locale.setlocale(locale.LC_TIME, 'ru_RU')
logger_user_actions = logging.getLogger('user_actions')
logger_main = logging.getLogger('django')

months_map = [
                'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь',
                'Ноябрь', 'Декабрь'
            ]


class CustomErrorView(View):
    def get(self, request, *args, **kwargs):
        return render(request, '404.html', status=404)

    def post(self, request, *args, **kwargs):
        return render(request, '500.html', status=500)

    def handle_400(self, request, *args, **kwargs):
        return render(request, '400.html', status=400)

    def handle_403(self, request, *args, **kwargs):
        return render(request, '403.html', status=403)

    def handle_503(self, request, *args, **kwargs):
        return render(request, '503.html', status=503)

    def handle_504(self, request, *args, **kwargs):
        return render(request, '504.html', status=504)

