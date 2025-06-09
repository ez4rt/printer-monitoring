from django.test import TestCase
from monitoring import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from monitoring.signals import notify_error, printer_created
from django.db.models import Max, Sum, Min
from unittest import skip
from datetime import datetime, timedelta, date
import json
from decimal import Decimal
import calendar


class SubnetModelTest(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)

    def test_subnet_creation(self):
        self.assertEqual(self.subnet.name, 'Test Subnet')
        self.assertEqual(self.subnet.address, '192.168.1.0')
        self.assertEqual(self.subnet.mask, 24)

    def test_subnet_str(self):
        self.assertEqual(str(self.subnet), 'Test Subnet')

    def test_unique_address(self):
        subnet = models.Subnet(name='Another Subnet', address='192.168.1.0', mask=24)
        with self.assertRaises(ValidationError):
            subnet.full_clean()

    def test_default_address(self):
        subnet = models.Subnet(name='Default Address Subnet', mask=24)
        self.assertEqual(subnet.address, '0.0.0.0')

    def test_add_subnet(self):
        subnet = models.Subnet.objects.create(name='New Subnet', address='192.168.2.0', mask=24)
        self.assertEqual(subnet.name, 'New Subnet')
        self.assertEqual(subnet.address, '192.168.2.0')

    def test_delete_subnet(self):
        self.subnet.delete()
        with self.assertRaises(models.Subnet.DoesNotExist):
            models.Subnet.objects.get(id=self.subnet.id)

        subnet = models.Subnet.objects.create(name='One More Subnet', address='192.168.1.0', mask=24)
        self.assertEqual(subnet.name, 'One More Subnet')
        self.assertEqual(subnet.address, '192.168.1.0')

    def test_subnet_meta(self):
        self.assertEqual(models.Subnet._meta.db_table, 'subnet')
        self.assertEqual(models.Subnet._meta.verbose_name, 'Подсеть')
        self.assertEqual(models.Subnet._meta.verbose_name_plural, '01. Подсети')
        self.assertEqual(models.Subnet._meta.db_table_comment, 'Таблица для хранения информации о подсетях.')


class IPAddressModelTest(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.1', subnet=self.subnet)

    def test_ip_address_creation(self):
        self.assertEqual(self.ip_address.address, '192.168.1.1')
        self.assertEqual(self.ip_address.subnet, self.subnet)

    def test_unique_ip_address(self):
        subnet2 = models.Subnet.objects.create(name='New Subnet', address='192.168.2.0', mask=24)
        with self.assertRaises(Exception):
            models.IPAddress.objects.create(address='192.168.1.1', subnet=self.subnet)
            models.IPAddress.objects.create(address='192.168.1.1', subnet=subnet2)

    def test_str_method(self):
        self.assertEqual(str(self.ip_address), '192.168.1.1')

    def test_default_ip_address(self):
        ip_address = models.IPAddress.objects.create(subnet=self.subnet)
        self.assertEqual(ip_address.address, '0.0.0.0')

    def test_delete_ip_address(self):
        self.ip_address.delete()
        with self.assertRaises(models.IPAddress.DoesNotExist):
            models.IPAddress.objects.get(id=self.ip_address.id)

        ip_address = models.IPAddress.objects.create(address='192.168.1.1', subnet=self.subnet)
        self.assertEqual(str(ip_address), '192.168.1.1')

    def test_ipaddress_meta(self):
        self.assertEqual(models.IPAddress._meta.db_table, 'ip_address')
        self.assertEqual(models.IPAddress._meta.verbose_name, 'IP-адрес')
        self.assertEqual(models.IPAddress._meta.verbose_name_plural, '02. IP-адреса')
        self.assertEqual(models.IPAddress._meta.db_table_comment, 'Таблица для хранения информации о IP-адресах.')


class CabinetModelTest(TestCase):
    def setUp(self):
        self.cabinet = models.Cabinet.objects.create(number='123')

    def test_cabinet_creation(self):
        self.assertEqual(self.cabinet.number, '123')

    def test_str_method(self):
        self.assertEqual(str(self.cabinet), '123')

    def test_delete(self):
        self.cabinet.delete()
        with self.assertRaises(models.Cabinet.DoesNotExist):
            models.Cabinet.objects.get(id=self.cabinet.id)

    def test_meta(self):
        self.assertEqual(models.Cabinet._meta.db_table, 'cabinet')
        self.assertEqual(models.Cabinet._meta.verbose_name, 'Кабинет')
        self.assertEqual(models.Cabinet._meta.verbose_name_plural, '08. Кабинеты')
        self.assertEqual(models.Cabinet._meta.db_table_comment, 'Таблица для хранения информации о кабинетах.')


class DepartmentModelTest(TestCase):
    def setUp(self):
        self.department = models.Department.objects.create(name='Test Department')

    def test_creation(self):
        self.assertEqual(self.department.name, 'Test Department')

    def test_str_method(self):
        self.assertEqual(str(self.department), 'Test Department')

    def test_delete(self):
        self.department.delete()
        with self.assertRaises(models.Department.DoesNotExist):
            models.Department.objects.get(id=self.department.id)

    def test_meta(self):
        self.assertEqual(models.Department._meta.db_table, 'department')
        self.assertEqual(models.Department._meta.verbose_name, 'Отдел')
        self.assertEqual(models.Department._meta.verbose_name_plural, '09. Отделы')
        self.assertEqual(models.Department._meta.db_table_comment, 'Таблица для хранения информации об отделах.')


class LocationModelTest(TestCase):
    def setUp(self):
        self.cabinet = models.Cabinet.objects.create(number='123')
        self.department = models.Department.objects.create(name='Test Department')
        self.location = models.Location.objects.create(department=self.department, cabinet=self.cabinet)

    def test_create_location_without_cabinet(self):
        location = models.Location.objects.create(department=self.department)
        self.assertEqual(location.department, self.department)
        self.assertIsNone(location.cabinet)
        self.assertEqual(str(location), f'Отдел: {self.department}')

    def test_create_location_with_cabinet(self):
        location = models.Location.objects.create(department=self.department, cabinet=self.cabinet)
        self.assertEqual(location.department, self.department)
        self.assertEqual(location.cabinet, self.cabinet)
        self.assertEqual(str(location), f'Кабинет: {self.cabinet}, Отдел: {self.department}')

    def test_location_str_method_without_cabinet(self):
        location = models.Location.objects.create(department=self.department)
        self.assertEqual(str(location), f'Отдел: {self.department}')

    def test_location_str_method_with_cabinet(self):
        location = models.Location.objects.create(department=self.department, cabinet=self.cabinet)
        self.assertEqual(str(location), f'Кабинет: {self.cabinet}, Отдел: {self.department}')

    def test_delete(self):
        self.location.delete()
        with self.assertRaises(models.Location.DoesNotExist):
            models.Location.objects.get(id=self.location.id)

    def test_meta(self):
        self.assertEqual(models.Location._meta.db_table, 'location')
        self.assertEqual(models.Location._meta.verbose_name, 'Расположение')
        self.assertEqual(models.Location._meta.verbose_name_plural, '10. Расположение')
        self.assertEqual(models.Location._meta.db_table_comment, 'Таблица для хранения информации о расположении.')


class PrinterStampModelTest(TestCase):
    def setUp(self):
        self.stamp = models.PrinterStamp.objects.create(name='Test Stamp')

    def test_creation(self):
        self.assertEqual(self.stamp.name, 'Test Stamp')

    def test_str_method(self):
        self.assertEqual(str(self.stamp), 'Test Stamp')


class PrinterModelModelTest(TestCase):
    def setUp(self):
        self.stamp = models.PrinterStamp.objects.create(name='Test Stamp')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='Model')

    def test_creation(self):
        self.assertEqual(self.model.name, 'Model')

    def test_str_method(self):
        self.assertEqual(str(self.model), 'Test Stamp Model')


class InventoryNumberModelTest(TestCase):
    def setUp(self):
        self.inventory_number = models.InventoryNumber.objects.create(number='in-00-01')

    def test_creation(self):
        self.assertEqual(self.inventory_number.number, 'in-00-01')

    def test_str_method(self):
        self.assertEqual(str(self.inventory_number), 'in-00-01')


class SupplyItemModelTest(TestCase):
    def setUp(self):
        self.supply_item = models.SupplyItem.objects.create(
            name='Black Cart test',
            type='cartridge',
            color='black',
            price=1500.00
        )

    def test_create_supply_item(self):
        self.assertEqual(self.supply_item.name, 'Black Cart test')
        self.assertEqual(self.supply_item.type, 'cartridge')
        self.assertEqual(self.supply_item.color, 'black')
        self.assertEqual(self.supply_item.price, 1500.00)

    def test_supply_item_str_method(self):
        expected_str = f"{self.supply_item.get_color_name().capitalize()} {self.supply_item.get_type_name()} {self.supply_item.name}"
        self.assertEqual(str(self.supply_item), expected_str)

    def test_get_type_name(self):
        self.assertEqual(self.supply_item.get_type_name(), 'картридж')

    def test_get_color_name(self):
        self.assertEqual(self.supply_item.get_color_name(), 'черный')


class BaseSetUpPrinterModelTest(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.cabinet = models.Cabinet.objects.create(number='Office 201')
        self.department = models.Department.objects.create(name='IT')
        self.location = models.Location.objects.create(department=self.department, cabinet=self.cabinet)
        self.stamp = models.PrinterStamp.objects.create(name='HP')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        self.inventory_number = models.InventoryNumber.objects.create(number='in-00-01')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
            inventory_number=self.inventory_number,
            location=self.location,
            date_of_commission=timezone.now(),
            is_active=True,
            is_archived=False,
        )


class PrinterModelTest(BaseSetUpPrinterModelTest):
    def test_printer_creation(self):
        self.assertEqual(self.printer.ip_address, self.ip_address)
        self.assertEqual(self.printer.model, self.model)
        self.assertEqual(self.printer.serial_number, 'SN123456')
        self.assertEqual(self.printer.inventory_number, self.inventory_number)
        self.assertEqual(self.printer.location, self.location)
        self.assertTrue(self.printer.is_active)
        self.assertFalse(self.printer.is_archived)

    def test_printer_str(self):
        self.assertEqual(str(self.printer), 'HP LaserJet 192.168.1.123')

    def test_unique_ip_address(self):
        with self.assertRaises(ValueError):
            printer = models.Printer(
                ip_address=self.ip_address,
                stamp='Canon',
                model='Pixma',
                serial_number='SN654321',
                is_active=True
            )
            printer.save()

    def test_delete_ip_address(self):
        self.printer.delete()
        with self.assertRaises(models.Printer.DoesNotExist):
            models.Printer.objects.get(id=self.printer.id)
        printer = models.Printer.objects.create(
                ip_address=self.ip_address,
                model=self.model,
                serial_number='SN654321',
            )
        self.assertEqual(str(printer.ip_address), '192.168.1.123')

    def test_get_is_active(self):
        self.assertEqual(self.printer.get_is_active(), 'Включен')
        self.printer.is_active = False
        self.printer.save()
        self.assertEqual(self.printer.get_is_active(), 'Выключен')

    def test_get_subnet_name(self):
        self.assertEqual(self.printer.get_subnet_name(), 'Test Subnet')

    def test_delete_printer(self):
        self.printer.delete()
        with self.assertRaises(models.Printer.DoesNotExist):
            models.Printer.objects.get(id=self.printer.id)

        printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN654321',
        )
        self.assertEqual(str(printer.ip_address), '192.168.1.123')

    def test_update_printer(self):
        ip_address = models.IPAddress.objects.create(address='192.168.1.221', subnet=self.subnet)
        model = models.PrinterModel.objects.create(stamp=self.stamp, name='New')

        self.printer.ip_address = ip_address
        self.printer.model = model

        self.assertEqual(str(self.printer.ip_address), '192.168.1.221')
        self.assertEqual(str(self.printer.model), 'HP New')

    def test_printer_meta(self):
        self.assertEqual(models.Printer._meta.db_table, 'printer')
        self.assertEqual(models.Printer._meta.verbose_name, 'Принтер')
        self.assertEqual(models.Printer._meta.verbose_name_plural, '05. Принтеры')
        self.assertEqual(models.Printer._meta.db_table_comment, 'Таблица для хранения информации о принтерах.')


class BaseSetUpPrinterSupplyStatusModelTest(BaseSetUpPrinterModelTest):
    def setUp(self):
        super().setUp()
        supplies_test = SupplyItemModelTest()
        supplies_test.setUp()
        self.supply_item = supplies_test.supply_item
        self.printer_supply = models.PrinterSupplyStatus.objects.create(
            printer=self.printer,
            supply=self.supply_item,
            remaining_supply_percentage=10,
            consumption=6000
        )
        self.supply_details = models.SupplyDetails.objects.create(
            supply=self.supply_item,
            qty=100
        )


class PrinterSupplyStatusModelTest(BaseSetUpPrinterSupplyStatusModelTest):
    def test_creation(self):
        self.assertEqual(self.printer_supply.printer, self.printer)
        self.assertEqual(self.printer_supply.supply, self.supply_item)
        self.assertEqual(self.printer_supply.remaining_supply_percentage, 10)
        self.assertEqual(self.printer_supply.consumption, 6000)

    def test_str(self):
        self.assertEqual(
            str(self.printer_supply),
            f'{self.printer_supply.printer} {self.printer_supply.supply} - '
            f'{self.printer_supply.remaining_supply_percentage}%'
        )


class SupplyDetailsModelTest(BaseSetUpPrinterSupplyStatusModelTest):
    def test_create(self):
        self.assertEqual(self.supply_details.supply, self.supply_item)
        self.assertEqual(self.supply_details.qty, 100)

    def test_str_method(self):
        expected_str = f'{self.supply_item} {self.supply_details.qty}'
        self.assertEqual(str(self.supply_details), expected_str)


class BaseStatModelTests(BaseSetUpPrinterModelTest):
    def test_statistics_creation(self):
        stat = models.Statistics.objects.create(
            printer=self.printer,
            page=10000,
            print=7000,
            copies=2000,
            scan=1000,
            time_collect=timezone.now()
        )
        self.assertEqual(stat.page, 10000)
        self.assertEqual(stat.print, 7000)
        self.assertEqual(stat.copies, 2000)
        self.assertEqual(stat.scan, 1000)

    def test_sum_statistics(self):
        stat = models.Statistics.objects.create(
            printer=self.printer,
            page=10000,
            print=7000,
            copies=2000,
            scan=1000,
            time_collect=timezone.now()
        )
        total_pages = stat.print + stat.copies + stat.scan
        self.assertEqual(total_pages, stat.page)
        zero_pages = stat.page - stat.print - stat.copies - stat.scan
        self.assertEqual(zero_pages, 0)

    def test_daily_stat_formatted_time_collect(self):
        daily_stat = models.DailyStat.objects.create(
            printer=self.printer,
            page=50,
            print=100,
            time_collect=timezone.now()
        )
        self.assertEqual(daily_stat.formatted_time_collect(), daily_stat.time_collect.strftime('%d-%m-%Y'))

    def test_monthly_stat_formatted_time_collect(self):
        monthly_stat = models.MonthlyStat.objects.create(
            printer=self.printer,
            page=150,
            print=300,
            time_collect=timezone.now()
        )
        self.assertEqual(monthly_stat.formatted_time_collect(), monthly_stat.time_collect.strftime('%m-%Y'))

    def test_statistics_meta(self):
        self.assertEqual(models.Statistics._meta.db_table, 'statistics')
        self.assertEqual(models.Statistics._meta.db_table_comment, 'Таблица для хранения информации о статистике '
                                                                   'использования принтеров.')

    def test_daily_stat_meta(self):
        self.assertEqual(models.DailyStat._meta.db_table, 'daily_statistics')
        self.assertEqual(models.DailyStat._meta.db_table_comment, 'Таблица для хранения информации о ежедневной '
                                                                'статистике использования принтеров.')

    def test_monthly_stat_meta(self):
        self.assertEqual(models.MonthlyStat._meta.db_table, 'monthly_statistics')
        self.assertEqual(models.MonthlyStat._meta.db_table_comment, 'Таблица для хранения информации о ежемесячной '
                                                                    'статистике использования принтеров.')


class ChangeSupplyModelTest(BaseSetUpPrinterSupplyStatusModelTest):
    def setUp(self):
        super().setUp()
        self.change_supply = models.change_supply = models.ChangeSupply.objects.create(
            printer=self.printer,
            supply=self.supply_item,
            time_change=timezone.now()
        )

    def test_create_change_supplies(self):
        self.assertIsInstance(self.change_supply, models.ChangeSupply)
        self.assertEqual(self.change_supply.printer, self.printer)
        self.assertEqual(self.change_supply.supply, self.supply_item)

    def test_formatted_time_change(self):
        time_now = timezone.now()
        change_supply_new = models.ChangeSupply.objects.create(
            printer=self.printer,
            supply=self.supply_item,
            time_change=time_now
        )
        formatted_time = change_supply_new.formatted_time_change()
        self.assertEqual(formatted_time, time_now.strftime('%d-%m-%Y'))

    def test_change_supplies_consumption_meta(self):
        self.assertEqual(models.ChangeSupply._meta.db_table, 'change_supply')
        self.assertEqual(models.ChangeSupply._meta.db_table_comment,
                         'Таблица для хранения информации о событиях замены расходных материалов.')


class ForecastStatModelTest(BaseSetUpPrinterModelTest):
    def setUp(self):
        super().setUp()
        self.forecast_stat = models.ForecastStat.objects.create(
            printer=self.printer,
            copies_printing=100,
            time_collect=timezone.now()
        )

    def test_forecast_stat_creation(self):
        self.assertEqual(self.forecast_stat.printer, self.printer)
        self.assertEqual(self.forecast_stat.copies_printing, 100)
        self.assertIsNotNone(self.forecast_stat.time_collect)

    def test_forecast_stat_meta(self):
        self.assertEqual(models.ForecastStat._meta.db_table, 'forecast_statistics')
        self.assertEqual(models.ForecastStat._meta.db_table_comment,
                         'Таблица для хранения информации о статистике для подготовки прогноза.')


class ForecastModelTest(BaseSetUpPrinterModelTest):
    def setUp(self):
        super().setUp()
        self.forecast = models.Forecast.objects.create(
            printer=self.printer,
            qty_pages=1000,
            daily_pages=200,
            forecast_date=timezone.now()
        )

    def test_forecast_creation(self):
        self.assertEqual(self.forecast.printer, self.printer)
        self.assertEqual(self.forecast.qty_pages, 1000)
        self.assertEqual(self.forecast.daily_pages, 200)
        self.assertIsNotNone(self.forecast.forecast_date)

    def test_forecast_meta(self):
        self.assertEqual(models.Forecast._meta.db_table, 'forecast')
        self.assertEqual(models.Forecast._meta.db_table_comment, 'Таблица для хранения информации о прогнозе печати.')


class ForecastChangeSuppliesModelTest(BaseSetUpPrinterSupplyStatusModelTest):
    def setUp(self):
        super().setUp()
        self.forecast_change_supplies = models.ForecastChangeSupplies.objects.create(
            printer=self.printer,
            supply=self.supply_item,
            forecast_date=timezone.now()
        )

    def test_forecast_change_supplies_creation(self):
        self.assertEqual(self.forecast_change_supplies.printer, self.printer)
        self.assertEqual(self.forecast_change_supplies.supply, self.supply_item)
        self.assertIsNotNone(self.forecast_change_supplies.forecast_date)

    def test_forecast_change_supplies_meta(self):
        self.assertEqual(models.ForecastChangeSupplies._meta.db_table, 'forecast_change_supplies')
        self.assertEqual(models.ForecastChangeSupplies._meta.db_table_comment,
                         'Таблица для хранения информации о прогнозе замены расходных материалов.')


class MaintenanceCostsModelTest(BaseSetUpPrinterModelTest):
    def setUp(self):
        super().setUp()
        self.maintenance_cost = models.MaintenanceCosts.objects.create(
            printer=self.printer,
            paper_cost=1000.00,
            supplies_cost=5000.00
        )

    def test_maintenance_costs_creation(self):
        self.assertEqual(self.maintenance_cost.printer, self.printer)
        self.assertEqual(self.maintenance_cost.paper_cost, 1000.00)
        self.assertEqual(self.maintenance_cost.supplies_cost, 5000.00)

    def test_change_cost(self):
        self.maintenance_cost.paper_cost = 2000.00
        self.maintenance_cost.supplies_cost += 500.00
        self.assertEqual(self.maintenance_cost.paper_cost, 2000.00)
        self.assertEqual(self.maintenance_cost.supplies_cost, 5500.00)

    def test_sum_costs(self):
        total_costs = self.maintenance_cost.paper_cost + self.maintenance_cost.supplies_cost
        self.assertEqual(total_costs, 6000.00)

    def test_maintenance_costs_meta(self):
        self.assertEqual(models.MaintenanceCosts._meta.db_table, 'maintenance_costs')
        self.assertEqual(models.MaintenanceCosts._meta.db_table_comment,
                         'Таблица для хранения информации о прогнозе затрат.')


class PrinterErrorModelTest(BaseSetUpPrinterModelTest):
    def setUp(self):
        super().setUp()
        post_save.disconnect(notify_error, sender=models.PrinterError)
        self.printer_error = models.PrinterError.objects.create(
            printer=self.printer,
            event_date=timezone.now(),
            description="Ошибка печати"
        )

    def test_printer_error_creation(self):
        self.assertEqual(self.printer_error.printer, self.printer)
        self.assertIsInstance(self.printer_error.event_date, timezone.datetime)
        self.assertEqual(self.printer_error.description, "Ошибка печати")

    def test_printer_error_str(self):
        self.assertEqual(str(self.printer_error), f"{self.printer} - Ошибка печати")

    def test_printer_error_meta(self):
        self.assertEqual(models.PrinterError._meta.db_table, 'printer_error')
        self.assertEqual(models.PrinterError._meta.db_table_comment,
                         'Таблица для хранения информации о cобытиях ошибка принтера.')


class CreateStressDBTests(TestCase):
    def setUp(self):
        post_save.disconnect(printer_created, sender=models.Printer)
        self.subnet_1 = models.Subnet.objects.create(name='Test Subnet One', address='192.168.10.0', mask=24)
        self.subnet_2 = models.Subnet.objects.create(name='Test Subnet Two', address='192.168.20.0', mask=24)
        self.subnet_3 = models.Subnet.objects.create(name='Test Subnet Three', address='192.168.30.0', mask=24)
        self.subnet_4 = models.Subnet.objects.create(name='Test Subnet Four', address='192.168.40.0', mask=24)

        self.cartridges = models.SupplyItem.objects.create(
            name='BM 202A',
            type='cartridge',
            color='black',
            price=4500.00
        )
        self.cartridge_detail = models.SupplyDetails.objects.create(
            supply=self.cartridges,
            qty=1000
        )

        self.drum_units = models.SupplyItem.objects.create(
            name='DU 1000',
            type='drum_unit',
            color='black',
            price=7500.00
        )
        self.drum_units_detail = models.SupplyDetails.objects.create(
            supply=self.drum_units,
            qty=500
        )

        self.stamp = models.PrinterStamp.objects.create(name='Pantum')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='BM51000')
        self.inventory_number = models.InventoryNumber.objects.create(number='011-123')

        self.ip_addresses = {}
        self.printers = {}
        self.stats = {}
        self.daily_stats = {}
        self.monthly_stats = {}
        for i in range(1, 51):
            self.ip_addresses[i] = models.IPAddress.objects.create(address=f'192.168.10.{i}', subnet=self.subnet_1)

            self.cabinet = models.Cabinet.objects.create(number=f'Офис {i}')
            self.department = models.Department.objects.create(name=f'Отдел {i}')
            self.location = models.Location.objects.create(department=self.department, cabinet=self.cabinet)

            self.printers[i] = models.Printer.objects.create(
                ip_address=self.ip_addresses[i],
                model=self.model,
                serial_number=f'SN0000{i}',
                inventory_number=self.inventory_number,
                location=self.location,
                date_of_commission=datetime.now() - timedelta(days=1000),
                is_active=True,
                is_archived=False,
                comment='Принтер в хорошем состоянии.'
            )
            self.printer_cartridge = models.PrinterSupplyStatus.objects.create(
                printer=self.printers[i],
                supply=self.cartridges,
                remaining_supply_percentage=100-i,
                consumption=6000
            )
            self.printer_drum_unit = models.PrinterSupplyStatus.objects.create(
                printer=self.printers[i],
                supply=self.drum_units,
                remaining_supply_percentage=round(100 - i * 0,5),
                consumption=20000
            )
            current_date = datetime.now() - timedelta(days=1000)
            for j in range(1, 1001):
                self.stats[j] = models.Statistics.objects.create(
                    printer=self.printers[i],
                    page=10000 + 300,
                    print=7000 + 100,
                    copies=2000 + 100,
                    scan=1000 + 100,
                    time_collect=timezone.make_aware(current_date)
                )
                self.daily_stats[j] = models.DailyStat.objects.create(
                    printer=self.printers[i],
                    page=300,
                    print=100,
                    copies=100,
                    scan=100,
                    time_collect=timezone.make_aware(current_date)
                )
                current_date += timedelta(days=1)

            current_month = datetime.now().month - 1
            for j in range(current_month, 0, -1):
                models.MonthlyStat.objects.create(
                    printer=self.printers[i],
                    page=9000,
                    print=3000,
                    copies=3000,
                    scan=3000,
                    time_collect=timezone.make_aware(
                        datetime(datetime.now().year, j, 1, 7, 0, 0)
                    )
                )
            for j in range(12, 0, -1):
                models.MonthlyStat.objects.create(
                    printer=self.printers[i],
                    page=9000,
                    print=3000,
                    copies=3000,
                    scan=3000,
                    time_collect=timezone.make_aware(
                        datetime(datetime.now().year - 1, j, 1, 7, 0, 0)
                    )
                )

            current_date = datetime.now() - timedelta(days=1000)
            for _ in range(30):
                models.change_supply = models.ChangeSupply.objects.create(
                    printer=self.printers[i],
                    supply=self.cartridges,
                    time_change=timezone.make_aware(current_date),
                )
                current_date += timedelta(days=33)
            current_date = datetime.now() - timedelta(days=1000)
            for _ in range(15):
                models.change_supply = models.ChangeSupply.objects.create(
                    printer=self.printers[i],
                    supply=self.drum_units,
                    time_change=timezone.make_aware(current_date),
                )
                current_date += timedelta(days=67)
            for n in range(1, 32):
                days_in_month = calendar.monthrange(datetime.now().year, datetime.now().month)[1]
                if n <= days_in_month:
                    models.Forecast.objects.create(
                        printer=self.printers[i],
                        qty_pages=209000 + (n * 200),
                        daily_pages=200,
                        forecast_date=timezone.make_aware(datetime(datetime.now().year, datetime.now().month, n, 0, 0, 0))
                    )
                else:
                    break
            models.ForecastChangeSupplies.objects.create(
                printer=self.printers[i],
                supply=self.cartridges,
                forecast_date=datetime.now() + timedelta(days=6)
            )
            models.ForecastChangeSupplies.objects.create(
                printer=self.printers[i],
                supply=self.drum_units,
                forecast_date=datetime.now() + timedelta(days=13)
            )
            models.MaintenanceCosts.objects.create(
                printer=self.printers[i],
                paper_cost=5000.00,
                supplies_cost=1500.00
            )
            post_save.disconnect(notify_error, sender=models.PrinterError)
            models.PrinterError.objects.create(
                printer=self.printers[i],
                event_date=timezone.make_aware(datetime.now() - timedelta(days=16)),
                description="Ошибка печати"
            )
        for i in range(51, 101):
            self.ip_addresses[i] = models.IPAddress.objects.create(address=f'192.168.20.{i}', subnet=self.subnet_2)

            self.cabinet = models.Cabinet.objects.create(number=f'Офис {i}')
            self.department = models.Department.objects.create(name=f'Отдел {i}')
            self.location = models.Location.objects.create(department=self.department, cabinet=self.cabinet)

            self.printers[i] = models.Printer.objects.create(
                ip_address=self.ip_addresses[i],
                model=self.model,
                serial_number=f'SN0000{i}',
                inventory_number=self.inventory_number,
                location=self.location,
                date_of_commission=datetime.now() - timedelta(days=1000),
                is_active=True,
                is_archived=False,
                comment='Принтер расположен у входа.'
            )
            self.printer_cartridge = models.PrinterSupplyStatus.objects.create(
                printer=self.printers[i],
                supply=self.cartridges,
                remaining_supply_percentage=100 - (i - 40),
                consumption=6000
            )
            self.printer_drum_unit = models.PrinterSupplyStatus.objects.create(
                printer=self.printers[i],
                supply=self.drum_units,
                remaining_supply_percentage=100 - (i - 50),
                consumption=20000
            )

            current_date = datetime.now() - timedelta(days=1000)
            for j in range(1001, 2001):
                self.stats[j] = models.Statistics.objects.create(
                    printer=self.printers[i],
                    page=10000 + 30,
                    print=7000 + 10,
                    copies=2000 + 10,
                    scan=1000 + 10,
                    time_collect=timezone.make_aware(current_date)
                )
                self.daily_stats[j] = models.DailyStat.objects.create(
                    printer=self.printers[i],
                    page=30,
                    print=10,
                    copies=10,
                    scan=10,
                    time_collect=timezone.make_aware(current_date)
                )
                current_date += timedelta(days=1)

            current_month = datetime.now().month - 1
            for j in range(current_month, 0, -1):
                models.MonthlyStat.objects.create(
                    printer=self.printers[i],
                    page=900,
                    print=300,
                    copies=300,
                    scan=300,
                    time_collect=timezone.make_aware(
                        datetime(datetime.now().year, j, 1, 7, 0, 0)
                    )
                )
            for j in range(12, 0, -1):
                models.MonthlyStat.objects.create(
                    printer=self.printers[i],
                    page=900,
                    print=300,
                    copies=300,
                    scan=300,
                    time_collect=timezone.make_aware(
                        datetime(datetime.now().year - 1, j, 1, 7, 0, 0)
                    )
                )
            current_date = datetime.now() - timedelta(days=1000)
            for _ in range(33):
                models.change_supply = models.ChangeSupply.objects.create(
                    printer=self.printers[i],
                    supply=self.cartridges,
                    time_change=timezone.make_aware(current_date),
                )
                current_date += timedelta(days=30)
            current_date = datetime.now() - timedelta(days=1000)
            for _ in range(25):
                models.change_supply = models.ChangeSupply.objects.create(
                    printer=self.printers[i],
                    supply=self.cartridges,
                    time_change=timezone.make_aware(current_date),
                )
                current_date += timedelta(days=39)
            current_date = datetime.now() - timedelta(days=1000)
            for _ in range(12):
                models.change_supply = models.ChangeSupply.objects.create(
                    printer=self.printers[i],
                    supply=self.drum_units,
                    time_change=timezone.make_aware(current_date),
                )
                current_date += timedelta(days=83)
            for n in range(1, 32):
                days_in_month = calendar.monthrange(datetime.now().year, datetime.now().month)[1]
                if n <= days_in_month:
                    models.Forecast.objects.create(
                        printer=self.printers[i],
                        qty_pages=209000 + (n * 200),
                        daily_pages=200,
                        forecast_date=timezone.make_aware(datetime(datetime.now().year, datetime.now().month, n, 0, 0, 0))
                    )
                else:
                    break
            models.ForecastChangeSupplies.objects.create(
                printer=self.printers[i],
                supply=self.cartridges,
                forecast_date=datetime.now() + timedelta(days=13)
            )
            models.ForecastChangeSupplies.objects.create(
                printer=self.printers[i],
                supply=self.drum_units,
                forecast_date=datetime.now() + timedelta(days=3)
            )
            models.MaintenanceCosts.objects.create(
                printer=self.printers[i],
                paper_cost=5000.00,
                supplies_cost=1500.00
            )
            post_save.disconnect(notify_error, sender=models.PrinterError)
            models.PrinterError.objects.create(
                printer=self.printers[i],
                event_date=timezone.make_aware(datetime.now() - timedelta(days=4)),
                description="Ошибка печати"
            )
        for i in range(101, 151):
            self.ip_addresses[i] = models.IPAddress.objects.create(address=f'192.168.30.{i}', subnet=self.subnet_3)

            self.cabinet = models.Cabinet.objects.create(number=f'Офис {i}')
            self.department = models.Department.objects.create(name=f'Отдел {i}')
            self.location = models.Location.objects.create(department=self.department, cabinet=self.cabinet)

            self.printers[i] = models.Printer.objects.create(
                ip_address=self.ip_addresses[i],
                model=self.model,
                serial_number=f'SN0000{i}',
                inventory_number=self.inventory_number,
                location=self.location,
                date_of_commission=datetime.now() - timedelta(days=1000),
                is_active=True,
                is_archived=False,
                comment='Принтер в хорошем состоянии.'
            )
            self.printer_cartridge = models.PrinterSupplyStatus.objects.create(
                printer=self.printers[i],
                supply=self.cartridges,
                remaining_supply_percentage=100 - (i - 75),
                consumption=6000
            )
            self.printer_drum_unit = models.PrinterSupplyStatus.objects.create(
                printer=self.printers[i],
                supply=self.drum_units,
                remaining_supply_percentage=100 - (i - 75),
                consumption=20000
            )

            current_date = datetime.now() - timedelta(days=1000)
            for j in range(2001, 3001):
                self.stats[j] = models.Statistics.objects.create(
                    printer=self.printers[i],
                    page=10000 + (i * 3),
                    print=7000 + i,
                    copies=2000 + i,
                    scan=1000 + i,
                    time_collect=timezone.make_aware(current_date)
                )
                self.daily_stats[j] = models.DailyStat.objects.create(
                    printer=self.printers[i],
                    page=i * 3,
                    print=i,
                    copies=i,
                    scan=i,
                    time_collect=timezone.make_aware(current_date)
                )
                current_date += timedelta(days=1)

            current_month = datetime.now().month - 1
            for j in range(current_month, 0, -1):
                models.MonthlyStat.objects.create(
                    printer=self.printers[i],
                    page=i * 3 * 30,
                    print=i,
                    copies=i,
                    scan=i,
                    time_collect=timezone.make_aware(
                        datetime(datetime.now().year, j, 1, 7, 0, 0)
                    )
                )
            for j in range(12, 0, -1):
                models.MonthlyStat.objects.create(
                    printer=self.printers[i],
                    page=i * 3 * 30,
                    print=i,
                    copies=i,
                    scan=i,
                    time_collect=timezone.make_aware(
                        datetime(datetime.now().year - 1, j, 1, 7, 0, 0)
                    )
                )

            current_date = datetime.now() - timedelta(days=1000)
            for _ in range(21):
                models.change_supply = models.ChangeSupply.objects.create(
                    printer=self.printers[i],
                    supply=self.cartridges,
                    time_change=timezone.make_aware(current_date),
                )
                current_date += timedelta(days=47)
            current_date = datetime.now() - timedelta(days=1000)
            for _ in range(11):
                models.change_supply = models.ChangeSupply.objects.create(
                    printer=self.printers[i],
                    supply=self.drum_units,
                    time_change=timezone.make_aware(current_date),
                )
                current_date += timedelta(days=90)
            for n in range(1, 32):
                days_in_month = calendar.monthrange(datetime.now().year, datetime.now().month)[1]
                if n <= days_in_month:
                    models.Forecast.objects.create(
                        printer=self.printers[i],
                        qty_pages=209000 + (n * 200),
                        daily_pages=200,
                        forecast_date=timezone.make_aware(datetime(datetime.now().year, datetime.now().month, n, 0, 0, 0))
                    )
                else:
                    break
            models.ForecastChangeSupplies.objects.create(
                printer=self.printers[i],
                supply=self.cartridges,
                forecast_date=datetime.now() + timedelta(days=2)
            )
            models.ForecastChangeSupplies.objects.create(
                printer=self.printers[i],
                supply=self.drum_units,
                forecast_date=datetime.now() + timedelta(days=3)
            )
            models.MaintenanceCosts.objects.create(
                printer=self.printers[i],
                paper_cost=5000.00,
                supplies_cost=1500.00
            )
            post_save.disconnect(notify_error, sender=models.PrinterError)
            models.PrinterError.objects.create(
                printer=self.printers[i],
                event_date=timezone.make_aware(datetime.now() - timedelta(days=20)),
                description="Ошибка печати № 3 "
            )
        for i in range(151, 201):
            self.ip_addresses[i] = models.IPAddress.objects.create(address=f'192.168.40.{i}', subnet=self.subnet_4)

            self.cabinet = models.Cabinet.objects.create(number=f'Офис {i}')
            self.department = models.Department.objects.create(name=f'Отдел {i}')
            self.location = models.Location.objects.create(department=self.department, cabinet=self.cabinet)

            self.printers[i] = models.Printer.objects.create(
                ip_address=self.ip_addresses[i],
                model=self.model,
                serial_number=f'SN0000{i}',
                inventory_number=self.inventory_number,
                location=self.location,
                date_of_commission=datetime.now() - timedelta(days=1000),
                is_active=True,
                is_archived=False,
                comment='Расходные материалы всегда полные.'
            )
            self.printer_cartridge = models.PrinterSupplyStatus.objects.create(
                printer=self.printers[i],
                supply=self.cartridges,
                remaining_supply_percentage=100,
                consumption=6000
            )
            self.printer_drum_unit = models.PrinterSupplyStatus.objects.create(
                printer=self.printers[i],
                supply=self.drum_units,
                remaining_supply_percentage=100,
                consumption=20000
            )

            current_date = datetime.now() - timedelta(days=1000)
            for j in range(3001, 4001):
                self.stats[j] = models.Statistics.objects.create(
                    printer=self.printers[i],
                    page=10000 + 1000,
                    print=7000 + 800,
                    copies=2000 + 150,
                    scan=1000 + 50,
                    time_collect=timezone.make_aware(current_date)
                )
                self.daily_stats[j] = models.DailyStat.objects.create(
                    printer=self.printers[i],
                    page=1000,
                    print=800,
                    copies=150,
                    scan=50,
                    time_collect=timezone.make_aware(current_date)
                )
                current_date += timedelta(days=1)

            current_month = datetime.now().month - 1
            for j in range(current_month, 0, -1):
                models.MonthlyStat.objects.create(
                    printer=self.printers[i],
                    page=30000,
                    print=24000,
                    copies=4500,
                    scan=1500,
                    time_collect=timezone.make_aware(
                        datetime(datetime.now().year, j, 1, 7, 0, 0)
                    )
                )
            for j in range(12, 0, -1):
                models.MonthlyStat.objects.create(
                    printer=self.printers[i],
                    page=30000,
                    print=24000,
                    copies=4500,
                    scan=1500,
                    time_collect=timezone.make_aware(
                        datetime(datetime.now().year - 1, j, 1, 7, 0, 0)
                    )
                )

            current_date = datetime.now() - timedelta(days=1000)
            for _ in range(39):
                models.change_supply = models.ChangeSupply.objects.create(
                    printer=self.printers[i],
                    supply=self.cartridges,
                    time_change=timezone.make_aware(current_date),
                )
                current_date += timedelta(days=25)
            current_date = datetime.now() - timedelta(days=1000)
            for _ in range(19):
                models.change_supply = models.ChangeSupply.objects.create(
                    printer=self.printers[i],
                    supply=self.drum_units,
                    time_change=timezone.make_aware(current_date),
                )
                current_date += timedelta(days=52)
            for n in range(1, 32):
                days_in_month = calendar.monthrange(datetime.now().year, datetime.now().month)[1]
                if n <= days_in_month:
                    models.Forecast.objects.create(
                        printer=self.printers[i],
                        qty_pages=209000 + (n * 200),
                        daily_pages=200,
                        forecast_date=timezone.make_aware(datetime(datetime.now().year, datetime.now().month, n, 0, 0, 0))
                    )
                else:
                    break
            models.ForecastChangeSupplies.objects.create(
                printer=self.printers[i],
                supply=self.cartridges,
                forecast_date=datetime.now() + timedelta(days=2)
            )
            models.ForecastChangeSupplies.objects.create(
                printer=self.printers[i],
                supply=self.drum_units,
                forecast_date=datetime.now() + timedelta(days=5)
            )
            models.MaintenanceCosts.objects.create(
                printer=self.printers[i],
                paper_cost=5000.00,
                supplies_cost=1500.00
            )
            post_save.disconnect(notify_error, sender=models.PrinterError)
            models.PrinterError.objects.create(
                printer=self.printers[i],
                event_date=timezone.make_aware(datetime.now() - timedelta(days=2)),
                description="Ошибка печати № 4"
            )
    def test_create_db(self):
        printers = models.Printer.objects.all()
        qty_printers = printers.count()
        self.assertEqual(qty_printers, 200)

        subnets = models.Subnet.objects.all()
        qty_subnets = subnets.count()
        self.assertEqual(qty_subnets, 4)

        ip_addresses = models.IPAddress.objects.all()
        qty_ip_addr = ip_addresses.count()
        self.assertEqual(qty_ip_addr, 200)

        stats = models.Statistics.objects.all()
        qty_stats = stats.count()
        self.assertEqual(qty_stats, 200000)

        daily_stats = models.DailyStat.objects.all()
        qty_daily_stats = daily_stats.count()
        self.assertEqual(qty_daily_stats, 200000)

        last_date_stat = models.Statistics.objects.aggregate(Max('time_collect'))['time_collect__max']
        last_date_daily_stat = models.DailyStat.objects.aggregate(Max('time_collect'))['time_collect__max']
        last_date_stat += timedelta(hours=7)
        last_date_daily_stat += timedelta(hours=7)
        formatted_last_date_stat = last_date_stat.strftime('%Y-%m-%d') if last_date_stat else None
        self.assertEqual(last_date_stat, last_date_daily_stat)
        self.assertEqual(formatted_last_date_stat, (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))

        first_date_monthly_stat = models.MonthlyStat.objects.aggregate(Min('time_collect'))['time_collect__min']
        last_date_monthly_stat = models.MonthlyStat.objects.aggregate(Max('time_collect'))['time_collect__max']
        formatted_first_date_monthly_stat = first_date_monthly_stat.strftime('%Y-%m') if first_date_monthly_stat else None
        formatted_last_date_monthly_stat = last_date_monthly_stat.strftime('%Y-%m') if last_date_monthly_stat else None

        self.assertEqual(formatted_first_date_monthly_stat, f'{datetime.now().year - 1}-01')
        test_month = datetime.now().month - 1
        test_year = datetime.now().year
        if datetime.now().month - 1 == 0:
            test_month = 12
            test_year -= 1
        test_month = str(test_month)
        if len(test_month) == 1:
            test_month = '0' + test_month

        self.assertEqual(formatted_last_date_monthly_stat, f'{test_year}-{test_month}')

        self.assertIsNotNone(self.cartridges.id)
        self.assertEqual(self.cartridges.name, 'BM 202A')
        self.assertEqual(self.cartridges.type, 'cartridge')
        self.assertEqual(self.cartridges.color, 'black')
        self.assertEqual(self.cartridges.price, 4500.00)

        self.assertIsNotNone(self.drum_units.id)
        self.assertEqual(self.drum_units.name, 'DU 1000')
        self.assertEqual(self.drum_units.type, 'drum_unit')
        self.assertEqual(self.drum_units.color, 'black')
        self.assertEqual(self.drum_units.price, 7500.00)

        count_change_sup1 = models.ChangeSupply.objects.filter(
            printer=self.printers[1],
            supply=self.cartridges
        ).count()
        self.assertEqual(count_change_sup1, 30)

        count_change_sup2 = models.ChangeSupply.objects.filter(
            printer=self.printers[74],
            supply=self.drum_units
        ).count()
        self.assertEqual(count_change_sup2, 12)

        count_change_sup3 = models.ChangeSupply.objects.filter(
            printer=self.printers[122],
            supply=self.drum_units
        ).count()
        self.assertEqual(count_change_sup3, 11)

        count_change_sup4 = models.ChangeSupply.objects.filter(
            printer=self.printers[200],
            supply=self.cartridges
        ).count()
        self.assertEqual(count_change_sup4, 39)

        forecasts = models.Forecast.objects.filter(printer=self.printers[77])

        today = datetime.now()
        current_month = today.month
        current_year = today.year

        days_in_month = calendar.monthrange(current_year, current_month)[1]
        self.assertEqual(forecasts.count(), days_in_month)

        changes = models.ForecastChangeSupplies.objects.filter(printer=self.printers[55])
        self.assertEqual(changes.count(), 2)

        costs = models.MaintenanceCosts.objects.filter(printer=self.printers[177])
        self.assertEqual(costs.count(), 1)

        errors = models.PrinterError.objects.filter(printer=self.printers[115])
        self.assertEqual(errors.count(), 1)

    def test_save_data_to_json(self):
        subnets = models.Subnet.objects.all().values()
        ip_addresses = models.IPAddress.objects.all().values()
        cabinets = models.Cabinet.objects.all().values()
        departments = models.Department.objects.all().values()
        locations = models.Location.objects.all().values()
        printer_stamps = models.PrinterStamp.objects.all().values()
        printer_models = models.PrinterModel.objects.all().values()
        supply_items = models.SupplyItem.objects.all().values()
        inventory_numbers = models.InventoryNumber.objects.all().values()
        printers = models.Printer.objects.all().values()
        printers_supplies = models.PrinterSupplyStatus.objects.all().values()
        supply_details = models.SupplyDetails.objects.all().values()
        statistics = models.Statistics.objects.all().values()
        daily_stats = models.DailyStat.objects.all().values()
        monthly_stats = models.MonthlyStat.objects.all().values()
        change_supplies = models.ChangeSupply.objects.all().values()
        forecast_stats = models.ForecastStat.objects.all().values()
        forecast = models.Forecast.objects.all().values()
        forecast_change_supplies = models.ForecastChangeSupplies.objects.all().values()
        maintenance_costs = models.MaintenanceCosts.objects.all().values()
        printer_errors = models.PrinterError.objects.all().values()

        data = {
            'subnets': list(subnets),
            'ip_addresses': list(ip_addresses),
            'cabinets': list(cabinets),
            'departments': list(departments),
            'locations': list(locations),
            'printer_stamps': list(printer_stamps),
            'printer_models': list(printer_models),
            'supply_items': list(supply_items),
            'inventory_numbers': list(inventory_numbers),
            'printers_supplies': list(printers_supplies),
            'supply_details': list(supply_details),
            'printers': list(printers),
            'statistics': list(statistics),
            'daily_stats': list(daily_stats),
            'monthly_stats': list(monthly_stats),
            'change_supplies': list(change_supplies),
            'forecast_stats': list(forecast_stats),
            'forecast': list(forecast),
            'forecast_change_supplies': list(forecast_change_supplies),
            'maintenance_costs': list(maintenance_costs),
            'printer_errors': list(printer_errors),
        }

        with open('tests/monitoring/test_data_new.json', 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4, default=custom_converter)


def custom_converter(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    elif isinstance(o, Decimal):
        return float(o)

