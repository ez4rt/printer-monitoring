from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from monitoring import models
from django.db.models.signals import post_save
from monitoring.signals import notify_error, printer_created
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth import logout, login
import json
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.contenttypes.models import ContentType
from unittest.mock import patch
from io import BytesIO
import pandas as pd
import unittest
from monitoring.views import (get_variables_stats, calculate_percentage, update_info, get_area_name, get_report_option,
                              create_events)
from django.contrib.auth.signals import user_logged_out
from monitoring.signals import log_user_logout


class TestGetVariablesStats(unittest.TestCase):
    class MockStats:
        def __init__(self, page, print_, scan, copies):
            self.page = page
            self.print = print_
            self.scan = scan
            self.copies = copies

    def test_empty_queryset(self):
        result = get_variables_stats([], 'test')
        expected = {
            'sum_total_testpage': 0,
            'sum_total_testprint': 0,
            'sum_total_testscan': 0,
            'sum_total_testcopies': 0
        }
        self.assertEqual(result, expected)

    def test_single_entry(self):
        queryset = [self.MockStats(1, 2, 3, 4)]
        result = get_variables_stats(queryset, 'test')
        expected = {
            'sum_total_testpage': 1,
            'sum_total_testprint': 2,
            'sum_total_testscan': 3,
            'sum_total_testcopies': 4
        }
        self.assertEqual(result, expected)

    def test_multiple_entries(self):
        queryset = [
            self.MockStats(1, 2, 3, 4),
            self.MockStats(5, 6, 7, 8)
        ]
        result = get_variables_stats(queryset, 'test')
        expected = {
            'sum_total_testpage': 6,
            'sum_total_testprint': 8,
            'sum_total_testscan': 10,
            'sum_total_testcopies': 12
        }
        self.assertEqual(result, expected)


class TestCalculatePercentage(unittest.TestCase):

    def test_positive_increase(self):
        self.assertEqual(calculate_percentage(150, 100), "+50.0")

    def test_positive_decrease(self):
        self.assertEqual(calculate_percentage(50, 100), "-50.0")

    def test_no_change(self):
        self.assertEqual(calculate_percentage(100, 100), "0.0")

    def test_current_zero(self):
        self.assertEqual(calculate_percentage(0, 100), "0.0")

    def test_yesterday_zero(self):
        self.assertEqual(calculate_percentage(100, 0), "0.0")

    def test_both_zero(self):
        self.assertEqual(calculate_percentage(0, 0), "0.0")


class TestGetAreaName(unittest.TestCase):

    def test_known_areas(self):
        self.assertEqual(get_area_name('abakan'), 'Абакан')
        self.assertEqual(get_area_name('sayanogorsk'), 'Саяногорск')
        self.assertEqual(get_area_name('chernogorsk'), 'Черногорск')
        self.assertEqual(get_area_name('shira'), 'Шира')

    def test_unknown_area(self):
        self.assertEqual(get_area_name('unknown_area'), 'unknown_area')

    def test_empty_string(self):
        self.assertEqual(get_area_name(''), '')

    def test_case_sensitivity(self):
        self.assertEqual(get_area_name('AbaKaN'), 'Абакан')


class TestGetReportOption(unittest.TestCase):

    def test_knows_report(self):
        self.assertEqual(get_report_option('page'), 'общего количества страниц')
        self.assertEqual(get_report_option('print'), 'количества страниц печати')
        self.assertEqual(get_report_option('copies'), 'количества копий')
        self.assertEqual(get_report_option('scan'), 'количества отсканированных страниц')
        self.assertEqual(get_report_option('event-log'), 'из журнала событий')
        self.assertEqual(get_report_option('print-log'), 'из журнала печати')

    def test_unknown_report(self):
        self.assertEqual(get_report_option('unknown'), 'unknown')

    def test_empty_string(self):
        self.assertEqual(get_report_option(''), '')

    def test_case_sensitivity(self):
        self.assertEqual(get_report_option('PAGE'), 'общего количества страниц')


class CreateDBTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='12345!"№')
        self.client.login(username='testuser', password='12345!"№')

        self.subnet = models.Subnet.objects.create(name='Test Subnet 1', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.1', subnet=self.subnet)

        post_save.disconnect(printer_created, sender=models.Printer)
        user_logged_out.disconnect(log_user_logout)

        self.stamp = models.PrinterStamp.objects.create(name='Pantum')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='BM51000')

        self.inventory_number = models.InventoryNumber.objects.create(number='in-00-01')

        self.cabinet = models.Cabinet.objects.create(number='Офис 101')
        self.department = models.Department.objects.create(name='Отдел продаж')
        self.location = models.Location.objects.create(department=self.department, cabinet=self.cabinet)

        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN9876543',
            inventory_number=self.inventory_number,
            location=self.location,
            date_of_commission='2024-10-22',
            is_active=True,
            is_archived=False,
            comment='Принтер в хорошем состоянии.'
        )

        self.cartridge = models.SupplyItem.objects.create(
            name='BM 202A',
            type='cartridge',
            color='black',
            price=1500.00
        )
        self.printer_cartridge = models.PrinterSupplyStatus.objects.create(
            printer=self.printer,
            supply=self.cartridge,
            remaining_supply_percentage=32,
            consumption=3000
        )

        self.drum_unit = models.SupplyItem.objects.create(
            name='BM 202A',
            type='drum_unit',
            color='black',
            price=1500.00
        )
        self.printer_drum_unit = models.PrinterSupplyStatus.objects.create(
            printer=self.printer,
            supply=self.drum_unit,
            remaining_supply_percentage=25,
            consumption=3000
        )

        self.supply_details = models.SupplyDetails.objects.create(
            supply=self.cartridge,
            qty=30
        )

        self.stat = models.Statistics.objects.create(
            printer=self.printer,
            page=10000,
            print=7000,
            copies=2000,
            scan=1000,
            time_collect=timezone.make_aware(datetime(2024, 10, 22, 8, 0, 0))
        )
        self.daily_stat = models.DailyStat.objects.create(
            printer=self.printer,
            page=100,
            print=70,
            copies=20,
            scan=10,
            time_collect=timezone.make_aware(datetime(2024, 10, 22, 8, 0, 0))
        )
        self.monthly_stat = models.MonthlyStat.objects.create(
            printer=self.printer,
            page=1000,
            print=700,
            copies=200,
            scan=100,
            time_collect=timezone.make_aware(datetime(2024, 10, 1, 8, 0, 0)),
        )

        self.change_supply = models.change_supply = models.ChangeSupply.objects.create(
            printer=self.printer,
            supply=self.cartridge,
            time_change=timezone.make_aware(datetime(2024, 10, 20, 8, 0, 0)),
        )

        self.forecast_stat = models.ForecastStat.objects.create(
            printer=self.printer,
            copies_printing=9000,
            time_collect=timezone.make_aware(datetime(2024, 10, 22, 8, 0, 0)),
        )
        self.forecast = models.Forecast.objects.create(
            printer=self.printer,
            qty_pages=9090,
            daily_pages=90,
            forecast_date=timezone.make_aware(datetime(2024, 10, 23, 8, 0, 0))
        )
        self.forecast_change_supplies = models.ForecastChangeSupplies.objects.create(
            printer=self.printer,
            supply=self.cartridge,
            forecast_date='2024-11-11'
        )
        self.maintenance_cost = models.MaintenanceCosts.objects.create(
            printer=self.printer,
            paper_cost=5000.00,
            supplies_cost=1500.00
        )
        post_save.disconnect(notify_error, sender=models.PrinterError)
        self.printer_error = models.PrinterError.objects.create(
            printer=self.printer,
            event_date=timezone.make_aware(datetime(2024, 10, 19, 8, 0, 0)),
            description="Ошибка печати"
        )


class UpdateInfoTests(CreateDBTest):
    def setUp(self):
        super().setUp()

        supply_log = models.SupplyItem.objects.create(
            name='Test Sup',
            type='cartridge',
            color='black',
            price=1500.00
        )
        self.admin_log = LogEntry.objects.create(
            user=self.user,
            content_type_id=ContentType.objects.get_for_model(models.SupplyItem).id,
            object_id=supply_log.id,
            object_repr=str(supply_log),
            action_flag=ADDITION,
        )

        self.subnet_new = models.Subnet.objects.create(name='Test Subnet 2', address='192.168.2.0', mask=24)
        self.ip_address_new1 = models.IPAddress.objects.create(address='192.168.2.1', subnet=self.subnet_new)
        self.ip_address_new2 = models.IPAddress.objects.create(address='192.168.2.2', subnet=self.subnet_new)

        self.cabinet_new = models.Cabinet.objects.create(number='Новый офис')
        self.department_new = models.Department.objects.create(name='Новый отдел')
        self.location_new = models.Location.objects.create(department=self.department_new, cabinet=self.cabinet_new)

        post_save.disconnect(printer_created, sender=models.Printer)

        self.printer_new1 = models.Printer.objects.create(
            ip_address=self.ip_address_new1,
            model=self.model,
            serial_number='SN513451',
            inventory_number=self.inventory_number,
            location=self.location_new,
            date_of_commission='2024-10-24',
            is_active=True,
            is_archived=False,
            comment='Принтер расположен около окна.'
        )

        self.printer_cartridge_new1 = models.PrinterSupplyStatus.objects.create(
            printer=self.printer_new1,
            supply=self.cartridge,
            remaining_supply_percentage=100,
            consumption=3000
        )

        self.printer_drum_unit_new1 = models.PrinterSupplyStatus.objects.create(
            printer=self.printer_new1,
            supply=self.drum_unit,
            remaining_supply_percentage=100,
            consumption=3000
        )

        self.stamp_new = models.PrinterStamp.objects.create(name='HP')
        self.model_new = models.PrinterModel.objects.create(stamp=self.stamp_new, name='ModernModel')

        self.printer_new2 = models.Printer.objects.create(
            ip_address=self.ip_address_new2,
            model=self.model,
            serial_number='513452SN',
            inventory_number=self.inventory_number,
            location=self.location_new,
            date_of_commission='2024-10-24',
            is_active=True,
            is_archived=False,
            comment='Принтер расположен около двери.'
        )

        self.cartridge_new = models.SupplyItem.objects.create(
            name='New cart',
            type='cartridge',
            color='black',
            price=1500.00
        )
        self.printer_cartridge_new2 = models.PrinterSupplyStatus.objects.create(
            printer=self.printer_new2,
            supply=self.cartridge_new,
            remaining_supply_percentage=100,
            consumption=3000
        )

        self.drum_unit_new = models.SupplyItem.objects.create(
            name='New drum',
            type='drum_unit',
            color='black',
            price=1500.00
        )
        self.printer_drum_unit_new2 = models.PrinterSupplyStatus.objects.create(
            printer=self.printer_new2,
            supply=self.drum_unit_new,
            remaining_supply_percentage=100,
            consumption=3000
        )

    def test_update_info_success(self):
        result = update_info()
        self.assertIn('printers', result)
        self.assertEqual(len(result['printers']), 3)
        self.assertIn('qty_printers', result)
        self.assertEqual(result['qty_printers'], 3)
        self.assertIn('events_small', result)
        self.assertEqual(len(result['events_small']), 1)
        self.assertIn('events_small', result)

    def test_update_info_low_toner(self):
        result = update_info()
        self.assertIn('printers_low_toner', result)
        self.assertEqual(len(result['printers_low_toner']), 3)

    def test_update_info_exception_handling(self):
        models.Printer.objects.all().delete()

        result = update_info()

        self.assertIn('printers', result)
        self.assertEqual(len(result['printers']), 0)


class CreateEventsTest(CreateDBTest):
    def setUp(self):
        super().setUp()
        supply_log = models.SupplyItem.objects.create(
            name='Test Sup',
            type='cartridge',
            color='black',
            price=1500.00
        )
        self.admin_log = LogEntry.objects.create(
            user=self.user,
            content_type_id=ContentType.objects.get_for_model(models.SupplyItem).id,
            object_id=supply_log.id,
            object_repr=str(supply_log),
            action_flag=ADDITION,
        )

    def test_create_events(self):
        changes_supplies = models.ChangeSupply.objects.all()
        errors = models.PrinterError.objects.all()
        admin_log = LogEntry.objects.all()
        events = create_events(changes_supplies, errors, admin_log)
        self.assertEqual(len(events), 3)
        self.assertIn('Пользователь: testuser, Действие: Добавление объекта', events[0]['description'])
        self.assertIn('Заменен Черный картридж BM 202A', events[1]['description'])
        self.assertIn('Ошибка печати', events[2]['description'])

    def test_create_events_empty_queryset(self):
        models.ChangeSupply.objects.all().delete()
        models.PrinterError.objects.all().delete()
        LogEntry.objects.all().delete()

        changes_supplies = models.ChangeSupply.objects.all()
        errors = models.PrinterError.objects.all()
        admin_log = LogEntry.objects.all()
        events = create_events(changes_supplies, errors, admin_log)
        self.assertEqual(len(events), 0)


class EmptyDatabaseViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='12345!"№')
        self.client.login(username='testuser', password='12345!"№')

    def test_index_view(self):
        response = self.client.get(reverse('monitoring:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/printers.html')

    def test_single_printer_view_invalid_printer(self):
        response = self.client.get(reverse('monitoring:printer', args=[1]))
        self.assertEqual(response.status_code, 404)

    def test_data_in_js_view(self):
        response = self.client.get(reverse('monitoring:data_in_js', kwargs={'nm_data': 'month-stats'}))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.content)
        self.assertIn('data_monthly_page', json_response)

    def test_reports_view(self):
        response = self.client.get(reverse('monitoring:reports'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/reports.html')

    def test_single_report_event_log_all_time(self):
        response = self.client.get(reverse('monitoring:report', args=['event-log', 'all-time']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-events.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/event-log/all-time')
        self.assertIn('events_all', response.context)
        self.assertContains(response, 'Отчёт из журнала событий за всё время')

    def test_single_report_event_log_7days(self):
        response = self.client.get(reverse('monitoring:report', args=['event-log', '7days']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-events.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/event-log/7days')
        self.assertContains(response, 'Отчёт из журнала событий за последние 7 дней')

    def test_single_report_event_log_30days(self):
        response = self.client.get(reverse('monitoring:report', args=['event-log', '30days']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-events.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/event-log/30days')
        self.assertContains(response, 'Отчёт из журнала событий за последние 30 дней')

    def test_single_report_print_log_all_time_shut_down_service(self):
        response = self.client.get(reverse('monitoring:report', args=['print-log', 'all-time']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-errors.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/print-log/all-time')
        self.assertContains(response, 'Ошибка генерации отчета')
        self.assertContains(response, 'Ошибка подключения')

    def test_single_report_print_log_30days_shut_down_service(self):
        response = self.client.get(reverse('monitoring:report', args=['print-log', '30days']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-errors.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/print-log/30days')
        self.assertContains(response, 'Ошибка генерации отчета')
        self.assertContains(response, 'Ошибка подключения')

    def test_single_report_print_log_7days_shut_down_service(self):
        response = self.client.get(reverse('monitoring:report', args=['print-log', '7days']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-errors.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/print-log/7days')
        self.assertContains(response, 'Ошибка генерации отчета')
        self.assertContains(response, 'Ошибка подключения')

    @patch('requests.get')
    def test_single_report_print_log(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [{}]

        response = self.client.get(reverse('monitoring:report', args=['print-log', '7days']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-print-log.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/print-log/7days')
        self.assertContains(response, 'Отчёт из журнала печати за последние 7 дней')

    def test_single_report_page(self):
        response = self.client.get(reverse('monitoring:report', args=['page', 'all-time']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/page/all-time')
        self.assertContains(response, 'Отчёт общего количества страниц за всё время')

    def test_single_report_print(self):
        response = self.client.get(reverse('monitoring:report', args=['print', '7days']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/print/7days')
        self.assertContains(response, 'Отчёт количества страниц печати за последние 7 дней')

    def test_single_report_copies(self):
        response = self.client.get(reverse('monitoring:report', args=['copies', '30days']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/copies/30days')
        self.assertContains(response, 'Отчёт количества копий за последние 30 дней')

    def test_single_report_scan(self):
        response = self.client.get(reverse('monitoring:report', args=['scan', 'all-time']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/scan/all-time')
        self.assertContains(response, 'Отчёт количества отсканированных страниц за всё время')

    def test_events_report(self):
        response = self.client.get(reverse('monitoring:events'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/events.html')

    def test_forecast_view(self):
        response = self.client.get(reverse('monitoring:forecast'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/forecast.html')
        self.assertIn('total_daily_pages', response.context)


class IndexViewTests(CreateDBTest):
    def test_index_view(self):
        response = self.client.get(reverse('monitoring:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/printers.html')
        self.assertNotIn('printer_id', self.client.session)

    def test_index_view_context(self):
        response = self.client.get(reverse('monitoring:index'))
        self.assertIn('sum_total_weekly_page', response.context)
        self.assertIn('sum_total_weekly_print', response.context)
        self.assertIn('sum_total_weekly_scan', response.context)
        self.assertIn('sum_total_weekly_copies', response.context)
        self.assertIn('total_sum_all_printers', response.context)

    def test_index_view_error_handling(self):
        models.DailyStat.objects.all().delete()
        response = self.client.get(reverse('monitoring:index'))
        self.assertEqual(response.status_code, 200)

    def test_percent_daily(self):
        models.DailyStat.objects.create(
            printer=self.printer,
            page=150,
            print=80,
            copies=60,
            scan=10,
            time_collect=timezone.make_aware(datetime(2024, 10, 23, 0, 0, 0))
        )
        response = self.client.get(reverse('monitoring:index'))
        self.assertIn('percent_daily_pages', response.context)
        self.assertIn('percent_daily_print', response.context)
        self.assertIn('percent_daily_scan', response.context)
        self.assertIn('percent_daily_copies', response.context)

    def test_index_not_authenticated(self):
        logout(self.client)
        response = self.client.get(reverse('monitoring:index'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/accounts/login?next=/')


class SinglePrinterViewTests(CreateDBTest):
    def test_single_printer_view(self):
        response = self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['printer_id'], self.printer.id)
        self.assertTemplateUsed(response, 'monitoring/single_printer.html')
        self.assertIn('percent_daily_pages', response.context)
        self.assertIn('percent_daily_print', response.context)
        self.assertIn('percent_daily_scan', response.context)
        self.assertIn('percent_daily_copies', response.context)
        self.assertIn('printer', response.context)
        self.assertIn('printer_stats', response.context)
        self.assertIn('printer_daily_stats', response.context)
        self.assertIn('total_month_sum', response.context)
        self.assertIn('printer_cost', response.context)
        self.assertIn('printer_forecast', response.context)
        self.assertIn('month_forecast', response.context)
        # self.assertIn('forecast_change_cart', response.context)

    def test_delete_daily_stat(self):
        models.DailyStat.objects.all().delete()
        response = self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        self.assertEqual(response.status_code, 200)

    def test_delete_statistics(self):
        models.Statistics.objects.all().delete()
        response = self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        self.assertEqual(response.status_code, 200)

    def test_delete_change_supplies(self):
        models.ChangeSupply.objects.all().delete()
        response = self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('events_single_printer_small', response.context)

    def test_delete_printer_error(self):
        models.PrinterError.objects.all().delete()
        response = self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('events_single_printer_small', response.context)

    def test_delete_maintenance_costs(self):
        models.MaintenanceCosts.objects.all().delete()
        response = self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('printer_forecast', response.context)
        self.assertNotIn('printer_cost', response.context)
        self.assertNotIn('month_forecast', response.context)

    def test_delete_forecast(self):
        models.Forecast.objects.all().delete()
        response = self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('printer_forecast', response.context)
        self.assertNotIn('printer_cost', response.context)
        self.assertNotIn('month_forecast', response.context)

    def test_delete_printer(self):
        models.Printer.objects.all().delete()
        response = self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        self.assertEqual(response.status_code, 404)

    def test_single_printer_not_authenticated(self):
        logout(self.client)
        response = self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/accounts/login?next=/{self.printer.id}')


class DataInJsTests(CreateDBTest):
    def test_weekly_stat_without_printer_id(self):
        response = self.client.get(reverse('monitoring:data_in_js', kwargs={'nm_data': 'week-stats'}))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.content)
        self.assertIn('data_weekly_stats', json_response)

    def test_monthly_stat_without_printer_id(self):
        response = self.client.get(reverse('monitoring:data_in_js', kwargs={'nm_data': 'month-stats'}))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.content)
        self.assertIn('data_monthly_page', json_response)

    def test_year_print_stats_without_printer_id(self):
        response = self.client.get(reverse('monitoring:data_in_js', kwargs={'nm_data': 'year-print-stats'}))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.content)
        self.assertIn('year_data_chart', json_response)

    def test_three_months_print_stats_without_printer_id(self):
        response = self.client.get(reverse('monitoring:data_in_js',
                                           kwargs={'nm_data': 'three-months-print-stats'}))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.content)
        self.assertIn('morris_donught_data', json_response)

    def test_forecast_stats_without_printer_id(self):
        response = self.client.get(reverse('monitoring:data_in_js', kwargs={'nm_data': 'forecast'}))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.content)
        self.assertIn('forecast_data_chart', json_response)

    def test_data_in_js_with_printer_id(self):
        self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        response = self.client.get(reverse('monitoring:data_in_js', kwargs={'nm_data': 'week-stats'}))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.content)
        self.assertIn('data_weekly_stats', json_response)

    def test_data_in_js_json_printer_id(self):
        daily_stats = []
        for i in range(40):
            stat = models.DailyStat(
                printer=self.printer,
                page=100 + (i * 3),
                print=70 + i,
                copies=20 + i,
                scan=10 + i,
                time_collect=timezone.make_aware(datetime(2024, 10, 23, 0, 0, 0) - timedelta(days=i)),
            )
            daily_stats.append(stat)
        models.DailyStat.objects.bulk_create(daily_stats)

        ip_address2 = models.IPAddress.objects.create(address='192.168.1.2', subnet=self.subnet)
        stamp_new = models.PrinterStamp.objects.create(name='HP')
        model_new = models.PrinterModel.objects.create(stamp=stamp_new, name='ModernModel')

        printer_new2 = models.Printer.objects.create(
            ip_address=ip_address2,
            model=model_new,
            serial_number='513452SN',
            date_of_commission='2024-10-24',
            is_active=True,
            is_archived=False,
        )
        daily_stats = []
        for i in range(40):
            stat = models.DailyStat(
                printer=printer_new2,
                page=500 + (i * 3),
                print=400 + i,
                copies=80 + i,
                scan=20 + i,
                time_collect=timezone.make_aware(datetime(2024, 10, 23, 0, 0, 0) - timedelta(days=i)),
            )
            daily_stats.append(stat)
        models.DailyStat.objects.bulk_create(daily_stats)

        response_printers = self.client.get(reverse('monitoring:data_in_js',
                                                    kwargs={'nm_data': 'week-stats'}))
        json_response_printers = json.loads(response_printers.content)

        self.client.get(reverse('monitoring:printer', args=[self.printer.id]))
        response_single_printer = self.client.get(reverse('monitoring:data_in_js',
                                                          kwargs={'nm_data': 'week-stats'}))
        self.assertEqual(response_single_printer.status_code, 200)

        json_response_single_printer = json.loads(response_single_printer.content)
        self.assertNotEqual(json_response_printers, json_response_single_printer)

    def test_data_in_js_not_authenticated(self):
        logout(self.client)
        response = self.client.get(reverse('monitoring:data_in_js', kwargs={'nm_data': 'week-stats'}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/accounts/login?next=/data-in-js/week-stats')


class ReportsViewTests(CreateDBTest):
    def test_printers_view(self):
        response = self.client.get(reverse('monitoring:reports'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/reports.html')
        self.assertIn('form_printers', response.context)
        self.assertIn('form_statistics', response.context)
        self.assertIn('form_day', response.context)
        self.assertIn('form_month', response.context)
        self.assertIn('form_supplies', response.context)
        self.assertContains(response, 'СПИСОК ОТЧЕТОВ')

    def test_printers_report_valid_area(self):
        models.Subnet.objects.create(name='abakan', address='192.168.2.0', mask=24)
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'abakan',
            'printers_report': True
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Принтеры (Абакан)')

    def test_printers_report_all_areas(self):
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'printers_report': True
        })
        self.assertEqual(response.status_code, 200)
        self.assertQuerysetEqual(response.context['printers'], [self.printer])
        self.assertTemplateUsed(response, 'monitoring/single_report/report-printers.html')
        self.assertContains(response, 'Принтеры')
        self.assertContains(response, '<table')
        self.assertContains(response, 'Модель')
        self.assertContains(response, 'Pantum BM51000')
        self.assertContains(response, 'Черный картридж BM 202A - Остаток: 32%')

    def test_statistics_report_all_valid(self):
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'option': 'all',
            'date_field': '2024-10-22',
            'statistics_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-usage-all.html')
        self.assertContains(response, 'Отчет об использовании принтеров на 2024-10-22')
        self.assertContains(response, '<table')
        self.assertContains(response, 'Pantum BM51000')
        self.assertContains(response, 'Общее количество страниц')
        self.assertContains(response, 'Количество страниц печати')
        self.assertContains(response, 'Количество копий')
        self.assertContains(response, 'Количество отсканированных страниц')
        self.assertContains(response, '10000')
        self.assertContains(response, '7000')
        self.assertContains(response, '2000')
        self.assertContains(response, '1000')

    def test_statistics_report_option_valid(self):
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'option': 'print',
            'date_field': '2024-10-22',
            'statistics_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-usage.html')
        self.assertContains(response, 'Отчет об использовании принтеров: количества страниц печати на 2024-10-22')
        self.assertContains(response, '<table')
        self.assertContains(response, 'Test Subnet 1/Кабинет: Офис 101, Отдел: Отдел продаж')
        self.assertContains(response, 'Страниц')
        self.assertContains(response, '7000')

    def test_statistics_report_area_valid(self):
        models.Subnet.objects.create(name='sayanogorsk', address='192.168.2.0', mask=24)
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'sayanogorsk',
            'option': 'all',
            'date_field': '2024-10-22',
            'statistics_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-usage-all.html')
        self.assertContains(response, 'Отчет об использовании принтеров (Саяногорск) на 2024-10-22')
        self.assertContains(response, '<table')

    def test_statistics_report_option_area_valid(self):
        models.Subnet.objects.create(name='chernogorsk', address='192.168.2.0', mask=24)
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'chernogorsk',
            'option': 'scan',
            'date_field': '2024-10-22',
            'statistics_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-usage.html')
        self.assertContains(response, 'Отчет об использовании принтеров: количества отсканированных страниц '
                                      '(Черногорск) на 2024-10-22')
        self.assertContains(response, '<table')

    def test_statistics_report_invalid_date(self):
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'option': 'all',
            'date_field': '2024-09-30',
            'statistics_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-errors.html')
        self.assertContains(response, 'Ошибка генерации отчета')
        self.assertContains(response, 'Введенная дата не входит в период функционирования программы.')

    def test_days_report_all_valid(self):
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'option': 'page',
            'date_start': '2024-10-22',
            'date_end': '2024-10-22',
            'days_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertContains(response, 'Отчет об ежедневной статистике общего количества страниц за период с '
                                      '2024-10-22 по 2024-10-22')
        self.assertContains(response, '<table')
        self.assertContains(response, '22.10.2024')
        self.assertContains(response, 'Pantum BM51000 (192.168.1.1), Test Subnet 1/Кабинет: Офис 101, Отдел: '
                                      'Отдел продаж')
        self.assertContains(response, '100')

    def test_days_report_area_valid(self):
        models.Subnet.objects.create(name='shira', address='192.168.2.0', mask=24)
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'shira',
            'option': 'copies',
            'date_start': '2024-10-22',
            'date_end': '2024-10-22',
            'days_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertContains(response, 'Отчет об ежедневной статистике количества копий за период с 2024-10-22 по '
                                      '2024-10-22 (Шира)')
        self.assertContains(response, '<table')

    def test_days_report_invalid_date_range(self):
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'option': 'page',
            'date_start': '2024-10-23',
            'date_end': '2024-10-01',
            'days_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-errors.html')
        self.assertContains(response, 'Ошибка генерации отчета')
        self.assertContains(response, 'Дата начала периода не может быть позже даты конца. Повторите ввод.')

    def test_days_report_out_of_range_dates(self):
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'option': 'page',
            'date_start': '2024-10-01',
            'date_end': '2024-10-29',
            'days_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-errors.html')
        self.assertContains(response, 'Ошибка генерации отчета')
        self.assertContains(response, 'Заданный период не входит в период функционирования программы. '
                                      'Пожалуйста введите период в промежутке от 22.10.2024 до 22.10.2024')

    def test_month_report_all_valid(self):
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'option': 'page',
            'date_start': '2024-10',
            'date_end': '2024-10',
            'months_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertContains(response, '<table')
        self.assertContains(response, 'Отчет об ежемесячной статистике общего количества страниц за период '
                                      'с Октябрь 2024 по Октябрь 2024')
        self.assertContains(response, 'Pantum BM51000 (192.168.1.1), Test Subnet 1/Кабинет: Офис 101, Отдел: '
                                      'Отдел продаж')
        self.assertContains(response, '1000')

    def test_month_report_area(self):
        models.Subnet.objects.create(name='abakan', address='192.168.2.0', mask=24)
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'abakan',
            'option': 'scan',
            'date_start': '2024-07',
            'date_end': '2024-11',
            'months_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertContains(response, '<table')
        self.assertContains(response, 'Отчет об ежемесячной статистике количества отсканированных '
                                      'страниц за период с Июль 2024 по Ноябрь 2024 (Абакан)')

    def test_supplies_report_valid(self):
        start_date = datetime(2024, 10, 1, 0, 0, 0)
        end_date = datetime(2024, 10, 21, 0, 0, 0)

        current_date = start_date

        while current_date <= end_date:
            models.Statistics.objects.create(
                printer=self.printer,
                page=10000,
                print=7000,
                copies=2000,
                scan=1000,
                time_collect=timezone.make_aware(current_date)
            )
            models.DailyStat.objects.create(
                printer=self.printer,
                page=100,
                print=70,
                copies=20,
                scan=10,
                time_collect=timezone.make_aware(current_date)
            )
            current_date += timedelta(days=1)

        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'date_start': '2024-10-01',
            'date_end': '2024-10-22',
            'supplies_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-supplies.html')
        self.assertContains(response, '<table')
        self.assertContains(response, 'Отчет по замене расходных материалов за период с 2024-10-01 по 2024-10-22')
        self.assertContains(response, 'Черный картридж BM 202A')
        self.assertContains(response, 'Количество')
        self.assertContains(response, '1')
        self.assertContains(response, 'Pantum BM51000 (192.168.1.1), Test Subnet 1/Кабинет: Офис 101, Отдел: '
                                      'Отдел продаж')
        self.assertContains(response, '20.10.2024')

    def test_supplies_report_invalid_date_range(self):
        start_date = datetime(2024, 10, 1, 0, 0, 0)
        end_date = datetime(2024, 10, 21, 0, 0, 0)

        current_date = start_date

        while current_date <= end_date:
            models.Statistics.objects.create(
                printer=self.printer,
                page=10000,
                print=7000,
                copies=2000,
                scan=1000,
                time_collect=timezone.make_aware(current_date)
            )
            models.DailyStat.objects.create(
                printer=self.printer,
                page=100,
                print=70,
                copies=20,
                scan=10,
                time_collect=timezone.make_aware(current_date)
            )
            current_date += timedelta(days=1)

        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'date_start': '2024-10-14',
            'date_end': '2024-10-08',
            'supplies_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-errors.html')
        self.assertContains(response, 'Дата начала периода не может быть позже даты конца. Повторите ввод.')

    def test_supplies_report_out_of_range_dates(self):
        response = self.client.post(reverse('monitoring:reports'), {
            'area': 'all',
            'date_start': '2022-10-14',
            'date_end': '2022-10-17',
            'supplies_report': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-errors.html')
        self.assertContains(response, 'Заданный период не входит в период функционирования программы.')


    def test_reports_not_authenticated(self):
        logout(self.client)
        response = self.client.get(reverse('monitoring:reports'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/accounts/login?next=/reports')


class SingleReportViewTests(CreateDBTest):
    def setUp(self):
        super().setUp()
        supply_log = models.SupplyItem.objects.create(
            name='Test Sup',
            type='cartridge',
            color='black',
            price=1500.00
        )
        self.admin_log = LogEntry.objects.create(
            user=self.user,
            content_type_id=ContentType.objects.get_for_model(models.SupplyItem).id,
            object_id=supply_log.id,
            object_repr=str(supply_log),
            action_flag=ADDITION,
        )

    def test_single_report_event_log_all_time(self):
        response = self.client.get(reverse('monitoring:report', args=['event-log', 'all-time']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-events.html')
        self.assertIn('events_all', response.context)
        self.assertContains(response, 'Отчёт из журнала событий за всё время')
        self.assertContains(response, 'Test Sup')
        self.assertContains(response, 'Пользователь: testuser, Действие: Добавление объекта')
        self.assertContains(response, (self.admin_log.action_time + timedelta(hours=7)).strftime('%Y/%m/%d %H:%M'))
        self.assertContains(response, 'Pantum BM51000 192.168.1.1')
        self.assertContains(response, 'Заменен Черный картридж BM 202A')
        self.assertContains(response, 'Ошибка печати')

    @patch('requests.get')
    def test_single_report_print_log(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {
                "TimeCreated": "2027-11-28T23:17:37.534000",
                "UserName": "user1",
                "Document": "TestFile",
                "PrinterName": "TestPrinter",
                "PrintSizeKb": 953,
                "Pages": "18",
                "Port": "1.1.1.1",
                "PSComputerName": "testComp"
            }
        ]

        response = self.client.get(reverse('monitoring:report', args=['print-log', '7days']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-print-log.html')
        self.assertIn('print_log', response.context)
        self.assertEqual(response.request['PATH_INFO'], '/report/print-log/7days')
        self.assertContains(response, 'Отчёт из журнала печати за последние 7 дней')
        self.assertContains(response, '28.11.2027 23:17')
        self.assertContains(response, 'user1 (testComp)')
        self.assertContains(response, 'TestFile')
        self.assertContains(response, '18')
        self.assertContains(response, '953')
        self.assertContains(response, 'TestPrinter (1.1.1.1)')

    def test_single_report_page(self):
        response = self.client.get(reverse('monitoring:report', args=['page', '7days']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/page/7days')
        self.assertContains(response, 'Отчёт общего количества страниц за последние не 7 дней(1д)')
        self.assertContains(response, '22.10.2024')
        self.assertContains(response, '100')
        self.assertContains(response, 'Test Subnet 1/Кабинет: Офис 101, Отдел: Отдел продаж')
        self.assertContains(response, '192.168.1.1')
        self.assertContains(response, 'Pantum BM51000 (192.168.1.1), Test Subnet 1/Кабинет: Офис 101, Отдел: '
                                      'Отдел продаж')


    def test_single_report_print(self):
        response = self.client.get(reverse('monitoring:report', args=['print', 'all-time']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/print/all-time')
        self.assertContains(response, 'Отчёт количества страниц печати за всё время')
        self.assertContains(response, 'Test Subnet 1/Кабинет: Офис 101, Отдел: Отдел продаж')
        self.assertContains(response, '192.168.1.1')
        self.assertContains(response, 'Pantum BM51000 (192.168.1.1), Test Subnet 1/Кабинет: Офис 101, Отдел: '
                                      'Отдел продаж')
        # self.assertContains(response, '22.10.2024')
        self.assertContains(response, '70')

    def test_single_report_copies(self):
        response = self.client.get(reverse('monitoring:report', args=['copies', 'all-time']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/copies/all-time')
        self.assertContains(response, 'Отчёт количества копий за всё время')
        self.assertContains(response, 'Test Subnet 1/Кабинет: Офис 101, Отдел: Отдел продаж')
        self.assertContains(response, '192.168.1.1')
        self.assertContains(response, 'Pantum BM51000 (192.168.1.1), Test Subnet 1/Кабинет: Офис 101, Отдел: '
                                      'Отдел продаж')
        self.assertContains(response, '22.10.2024')
        self.assertContains(response, '20')

    def test_single_report_scan(self):
        response = self.client.get(reverse('monitoring:report', args=['scan', '30days']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/single_report/report-qty-pages.html')
        self.assertEqual(response.request['PATH_INFO'], '/report/scan/30days')
        self.assertContains(response, 'Отчёт количества отсканированных страниц за последние не 30 дней(1д)')
        self.assertContains(response, 'Test Subnet 1/Кабинет: Офис 101, Отдел: Отдел продаж')
        self.assertContains(response, '192.168.1.1')
        self.assertContains(response, 'Pantum BM51000 (192.168.1.1), Test Subnet 1/Кабинет: Офис 101, Отдел: '
                                      'Отдел продаж')
        self.assertContains(response, '22.10.2024')
        self.assertContains(response, '10')

    def test_single_report_bad_request(self):
        response = self.client.get(reverse('monitoring:report', args=['unknown-report', 'invalid']))
        self.assertEqual(response.status_code, 400)

    def test_single_report_invalid_name_report(self):
        response = self.client.get(reverse('monitoring:report', args=['unknown-report', 'all-time']))
        self.assertEqual(response.status_code, 400)

    def test_single_report_invalid_qty_days(self):
        response = self.client.get(reverse('monitoring:report', args=['page', 'invalid']))
        self.assertEqual(response.status_code, 400)

    def test_single_report_not_authenticated(self):
        logout(self.client)
        response = self.client.get(reverse('monitoring:report', args=['page', 'all-time']))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/accounts/login?next=/report/page/all-time')


class ExportReportTests(CreateDBTest):
    def test_export_report_success(self):
        table_html = '<table><tr><th>Column1</th><th>Column2</th></tr><tr><td>Data1</td><td>Data2</td></tr></table>'
        data = {'table': table_html, 'totalParts': 1, 'part': 0}
        url = reverse('monitoring:export_report')
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="output.xlsx"')

        output = BytesIO(response.content)
        df = pd.read_excel(output)
        self.assertEqual(df.shape, (1, 2))
        self.assertEqual(list(df.columns), ['Column1', 'Column2'])
        self.assertEqual(df.iloc[0].tolist(), ['Data1', 'Data2'])

    def test_export_report_invalid_method(self):
        response = self.client.get('monitoring:export_report')
        self.assertEqual(response.status_code, 404)

    def test_export_report_not_authenticated(self):
        logout(self.client)
        table_html = '<table><tr><th>Column1</th><th>Column2</th></tr><tr><td>Data1</td><td>Data2</td></tr></table>'
        data = {'table': table_html}
        url = reverse('monitoring:export_report')
        response = self.client.post(url, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/accounts/login?next=/export_report/')


class EventsViewTests(CreateDBTest):
    def setUp(self):
        super().setUp()
        supply_log = models.SupplyItem.objects.create(
            name='Test Sup',
            type='cartridge',
            color='black',
            price=1500.00
        )
        self.admin_log = LogEntry.objects.create(
            user=self.user,
            content_type_id=ContentType.objects.get_for_model(models.SupplyItem).id,
            object_id=supply_log.id,
            object_repr=str(supply_log),
            action_flag=ADDITION,
        )

    def test_events_view_with_recent_changes(self):
        response = self.client.get(reverse('monitoring:events'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/events.html')
        self.assertIn('events_all', response.context)
        self.assertContains(response, 'Пользователь: testuser, Действие: Добавление объекта')

    def test_events_not_authenticated(self):
        logout(self.client)
        response = self.client.get(reverse('monitoring:events'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/accounts/login?next=/events')


class ForecastViewTests(CreateDBTest):
    def test_forecast_view(self):
        response = self.client.get(reverse('monitoring:forecast'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'monitoring/forecast.html')
        self.assertIn('month_forecast', response.context)
        self.assertIn('total_daily_pages', response.context)
        self.assertIn('total_costs', response.context)