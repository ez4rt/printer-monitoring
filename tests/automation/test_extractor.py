from datetime import timedelta
from django.test import TestCase
from unittest.mock import patch, MagicMock

from snmp import SNMPv2c

from automation.data_extractor import scan_subnet

from monitoring import models
from automation.snmp_oid_map import device_snmp_map
from automation.data_extractor import (printer_init_resource, update_printer_resource, create_new_supply_item,
                                       split_nm_supply, create_new_supply_details, get_printer_stamp,
                                       add_supply_in_printer, update_printer_resource, get_printer_supply_status,
                                       update_printer_supply_status, update_qty_supply, create_change_supply,
                                       calculate_average_printer_supply_consumption, parsing_snmp_avision,
                                       parsing_snmp_hp, parsing_snmp_kyosera, parsing_snmp_sindoh, parsing_pantum,
                                       save_printer_stats_to_database, add_printer_parsing_snmp, parsing_snmp, parsing_snmp_katusha, add_missing_statistics_to_db, detect_device_errors, fetch_snmp_data_to_str, fetch_snmp_data_to_int, checking_activity)
from django.db.models.signals import post_save
from monitoring.signals import printer_created
from django.utils import timezone


class ScanSubnetTests(TestCase):
    @patch('subprocess.Popen')
    def test_scan_subnet_with_active_ips(self, mock_popen):
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"Nmap scan report for 192.168.1.1\n"
                                                 b"Host is up\n"
                                                 b"Nmap scan report for 192.168.1.2\n"
                                                 b"Host is up\n", b"")
        mock_popen.return_value = mock_process

        result = scan_subnet('192.168.1.0/24')

        self.assertEqual(result, ['192.168.1.1', '192.168.1.2'])

    @patch('subprocess.Popen')
    def test_scan_subnet_with_no_active_ips(self, mock_popen):
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"No hosts found\n", b"")
        mock_popen.return_value = mock_process

        result = scan_subnet('192.168.1.0/24')

        self.assertEqual(result, [])

    @patch('subprocess.Popen')
    def test_scan_subnet_with_malformed_output(self, mock_popen):
        mock_process = MagicMock()
        mock_process.communicate.return_value = (b"Some random text\n"
                                                 b"Another line\n", b"")
        mock_popen.return_value = mock_process
        result = scan_subnet('192.168.1.0/24')
        self.assertEqual(result, [])


class PrinterInitResourceTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='KYOCERA')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_str')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.create_new_supply_item')
    @patch('automation.data_extractor.create_new_supply_details')
    @patch('automation.data_extractor.add_supply_in_printer')
    @patch('automation.data_extractor.get_printer_stamp')
    def test_printer_init_resource_success(self, mock_get_printer_stamp, mock_add_supply_in_printer,
                                           mock_create_new_supply_details, mock_create_new_supply_item,
                                           mock_fetch_snmp_data_to_int, mock_fetch_snmp_data_to_str,
                                           mock_engine):
        mock_printer = MagicMock()
        mock_printer.ip_address.address = "192.168.1.1"
        mock_get_printer_stamp.return_value = "hewlett-packard"

        mock_engine.return_value.__enter__.return_value.Manager.return_value = MagicMock()
        mock_engine.return_value.__enter__.return_value.Manager.return_value = MagicMock()

        printer_supplies_dict = {'supply': ['black_cartridge']}
        device_snmp_map = {'hewlett-packard': ['black_cartridge']}
        mock_fetch_snmp_data_to_str.return_value = "C1234A"
        mock_fetch_snmp_data_to_int.return_value = 50

        printer_init_resource(mock_printer)

        mock_get_printer_stamp.assert_called_once_with(mock_printer)
        mock_fetch_snmp_data_to_str.assert_called_once_with(
            mock_engine.return_value.__enter__.return_value.Manager.return_value, "hewlett-packard", 'black_cartridge')
        mock_create_new_supply_item.assert_called_once_with('black_cartridge', "C1234A")
        mock_create_new_supply_details.assert_called_once()
        mock_add_supply_in_printer.assert_called_once_with(mock_printer, mock_create_new_supply_item.return_value, 50,
                                                           3000)
        mock_engine.assert_called_once_with(SNMPv2c, defaultCommunity=b"public")

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.get_printer_stamp')
    def test_printer_init_resource_no_stamp(self, mock_get_printer_stamp, mock_engine):
        mock_printer = MagicMock()
        mock_get_printer_stamp.return_value = None

        printer_init_resource(mock_printer)

        mock_engine.assert_not_called()

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.logger_main')
    def test_printer_init_resource_with_exception(self, mock_logger, mock_engine):
        mock_engine.side_effect = Exception("SNMP error")
        printer_init_resource(self.printer)

        mock_logger.error.assert_called_once_with(
            f"{self.printer}: SNMP error - Error in launching the SNMP engine in the printer_init_resource function")


class CreateNewSupplyItemTests(TestCase):
    @patch('monitoring.models.SupplyItem.objects.get_or_create')
    @patch('automation.data_extractor.split_nm_supply')
    def test_create_new_supply_item(self, mock_split_nm_supply, mock_get_or_create):
        mock_split_nm_supply.return_value = ("black", "cartridge")
        mock_supply_item = MagicMock()
        mock_get_or_create.return_value = (mock_supply_item, True)

        result = create_new_supply_item("C1234A", "Черный картридж")

        mock_get_or_create.assert_called_once_with(
            name="Черный картридж",
            defaults={
                'type': "cartridge",
                'color': "black",
                'price': 0.00
            }
        )

        self.assertEqual(result, mock_supply_item)

    @patch('monitoring.models.SupplyItem.objects.get_or_create')
    @patch('automation.data_extractor.split_nm_supply')
    def test_get_existing_supply_item(self, mock_split_nm_supply, mock_get_or_create):
        mock_split_nm_supply.return_value = ("black", "cartridge")
        mock_supply_item = MagicMock()
        mock_get_or_create.return_value = (mock_supply_item, False)

        result = create_new_supply_item("C1234A", "Черный картридж")

        mock_get_or_create.assert_called_once_with(
            name="Черный картридж",
            defaults={
                'type': "cartridge",
                'color': "black",
                'price': 0.00
            }
        )

        self.assertEqual(result, mock_supply_item)


class SplitNmSupplyTests(TestCase):
    def test_split_nm_supply_with_color_and_type(self):
        nm_oid = "black_cartridge"
        color, type_ = split_nm_supply(nm_oid)

        self.assertEqual(color, "black")
        self.assertEqual(type_, "cartridge")

    def test_split_nm_supply_with_multiple_underscores(self):
        nm_oid = "black_drum_unit"
        color, type_ = split_nm_supply(nm_oid)

        self.assertEqual(color, "black")
        self.assertEqual(type_, "drum_unit")


class CreateNewSupplyDetailsTests(TestCase):
    @patch('monitoring.models.SupplyDetails.objects.get_or_create')
    def test_create_new_supply_details(self, mock_get_or_create):
        mock_supply = MagicMock()
        mock_supply_detail = MagicMock()
        mock_get_or_create.return_value = (mock_supply_detail, True)

        result = create_new_supply_details(mock_supply)

        mock_get_or_create.assert_called_once_with(
            supply=mock_supply,
            defaults={
                'supply': mock_supply,
                'qty': 0,
            }
        )

        self.assertEqual(result, mock_supply_detail)

    @patch('monitoring.models.SupplyDetails.objects.get_or_create')
    def test_get_existing_supply_details(self, mock_get_or_create):
        mock_supply = MagicMock()
        mock_supply_detail = MagicMock()
        mock_get_or_create.return_value = (mock_supply_detail, False)

        result = create_new_supply_details(mock_supply)

        mock_get_or_create.assert_called_once_with(
            supply=mock_supply,
            defaults={
                'supply': mock_supply,
                'qty': 0,
            }
        )

        self.assertEqual(result, mock_supply_detail)


class GetPrinterStampTest(TestCase):
    @patch('automation.data_extractor.device_snmp_map', device_snmp_map)
    def test_get_printer_stamp_valid(self):
        mock_printer = MagicMock()
        mock_printer.model.stamp.name = "Hewlett-Packard"
        mock_printer.model.name = "Hewlett-Packard LaserJet M283fdn"

        result = get_printer_stamp(mock_printer)

        self.assertEqual(result, "hewlett-packard-color")

    @patch('automation.data_extractor.device_snmp_map', device_snmp_map)
    def test_get_printer_stamp_invalid_stamp(self):
        mock_printer = MagicMock()
        mock_printer.model.stamp.name = "UnknownBrand"
        mock_printer.model.name = "Some Model"

        result = get_printer_stamp(mock_printer)

        self.assertEqual(result, "katusha")

    @patch('automation.data_extractor.device_snmp_map', device_snmp_map)
    def test_get_printer_stamp_no_color(self):
        mock_printer = MagicMock()
        mock_printer.model.stamp.name = "Hewlett-Packard"
        mock_printer.model.name = "FS-1028MFP"

        result = get_printer_stamp(mock_printer)

        self.assertIsNone(result)

    @patch('automation.data_extractor.device_snmp_map', device_snmp_map)
    def test_get_printer_stamp_without_stamp(self):
        mock_printer = MagicMock()
        mock_printer.model.stamp.name = ""
        mock_printer.model.name = "HP LaserJet"

        result = get_printer_stamp(mock_printer)

        self.assertEqual(result, "katusha")


class AddSupplyInPrinterTest(TestCase):
    @patch('monitoring.models.PrinterSupplyStatus.objects.create')
    def test_add_supply_in_printer(self, mock_create):
        mock_printer = MagicMock()
        mock_supply = MagicMock()
        remaining_supply_percentage = 75
        qty_page = 300

        add_supply_in_printer(mock_printer, mock_supply, remaining_supply_percentage, qty_page)

        mock_create.assert_called_once_with(
            printer=mock_printer,
            supply=mock_supply,
            remaining_supply_percentage=remaining_supply_percentage,
            consumption=qty_page,
        )


class UpdatePrinterResourceTest(TestCase):

    @patch('monitoring.models.Printer.objects.get')
    @patch('automation.data_extractor.get_printer_stamp')
    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.get_printer_supply_status')
    @patch('automation.data_extractor.update_printer_supply_status')
    @patch('automation.data_extractor.logger_main')
    def test_update_printer_resource_success(self, mock_logger, mock_get_supply_status,
                                             mock_update_supply_status, mock_fetch_snmp_data,
                                             mock_engine, mock_get_printer_stamp, mock_get):
        mock_printer = MagicMock()
        mock_printer.is_active = True
        mock_printer.ip_address.address = "192.168.1.1"
        mock_get.return_value = mock_printer
        mock_get_printer_stamp.return_value = "hewlett-packard"

        mock_engine.return_value.__enter__.return_value.Manager.return_value = MagicMock()
        mock_engine.return_value.__enter__.return_value.Manager.return_value = MagicMock()

        printer_supplies_dict = {'supply': ['black_cartridge']}
        device_snmp_map = {'hewlett-packard': ['resource_black_cartridge']}
        mock_fetch_snmp_data.return_value = 50
        mock_get_supply_status.return_value = MagicMock()

        update_printer_resource(1)

        mock_get.assert_called_once_with(pk=1)
        mock_get_printer_stamp.assert_called_once_with(mock_printer)
        mock_engine.assert_called_once_with(SNMPv2c, defaultCommunity=b"public")
        mock_fetch_snmp_data.assert_called_once_with(
            mock_engine.return_value.__enter__.return_value.Manager.return_value,
            "hewlett-packard",
            'resource_black_cartridge'
        )
        mock_get_supply_status.assert_called_once()
        mock_update_supply_status.assert_called_once()

    @patch('monitoring.models.Printer.objects.get')
    @patch('automation.data_extractor.logger_main')
    def test_update_printer_resource_inactive_printer(self, mock_logger, mock_get):
        mock_printer = MagicMock()
        mock_printer.is_active = False
        mock_get.return_value = mock_printer

        update_printer_resource(1)

        mock_get.assert_called_once_with(pk=1)

    @patch('monitoring.models.Printer.objects.get')
    @patch('automation.data_extractor.get_printer_stamp')
    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.logger_main')
    def test_update_printer_resource_exception(self, mock_logger, mock_engine, mock_get_printer_stamp, mock_get):
        mock_printer = MagicMock()
        mock_printer.is_active = True
        mock_printer.ip_address.address = "192.168.1.1"
        mock_get.return_value = mock_printer
        mock_get_printer_stamp.return_value = "hewlett-packard"
        mock_engine.side_effect = Exception("SNMP error")

        update_printer_resource(1)

        mock_logger.error.assert_called_once_with(
            f"{mock_printer}: SNMP error - Error in launching the SNMP engine in the update_printer_resource function"
        )


class GetPrinterSupplyStatusTest(TestCase):
    @patch('automation.data_extractor.split_nm_supply')
    @patch('monitoring.models.PrinterSupplyStatus.objects.filter')
    def test_get_printer_supply_status_found(self, mock_filter, mock_split_nm_supply):
        mock_printer = MagicMock()
        nm_supply_oid = "black_cartridge"
        mock_split_nm_supply.return_value = ("black", "cartridge")

        mock_supply_status = MagicMock()
        mock_filter.return_value.first.return_value = mock_supply_status

        result = get_printer_supply_status(mock_printer, nm_supply_oid)

        mock_filter.assert_called_once_with(
            printer=mock_printer,
            supply__type="cartridge",
            supply__color="black"
        )

        self.assertEqual(result, mock_supply_status)

    @patch('automation.data_extractor.split_nm_supply')
    @patch('monitoring.models.PrinterSupplyStatus.objects.filter')
    def test_get_printer_supply_status_not_found(self, mock_filter, mock_split_nm_supply):
        mock_printer = MagicMock()
        nm_supply_oid = "black_cartridge"
        mock_split_nm_supply.return_value = ("black", "cartridge")

        mock_filter.return_value.first.return_value = None

        result = get_printer_supply_status(mock_printer, nm_supply_oid)

        mock_filter.assert_called_once_with(
            printer=mock_printer,
            supply__type="cartridge",
            supply__color="black"
        )

        self.assertIsNone(result)


class UpdatePrinterSupplyStatusTest(TestCase):
    @patch('automation.data_extractor.update_qty_supply')
    @patch('automation.data_extractor.create_change_supply')
    @patch('automation.data_extractor.calculate_average_printer_supply_consumption')
    def test_update_printer_supply_status_increase(self, mock_calculate, mock_create_change, mock_update_qty):
        mock_supply = MagicMock()
        mock_printer = MagicMock()
        mock_printer_supply_status = MagicMock()
        mock_printer_supply_status.remaining_supply_percentage = 50
        mock_printer_supply_status.supply = mock_supply
        mock_printer_supply_status.printer = mock_printer
        mock_printer_supply_status.consumption = 100

        new_remaining_supply_percentage = 75
        mock_calculate.return_value = 150

        update_printer_supply_status(mock_printer_supply_status, new_remaining_supply_percentage)

        mock_update_qty.assert_called_once_with(mock_supply)
        mock_create_change.assert_called_once_with(mock_printer, mock_supply)

        self.assertEqual(mock_printer_supply_status.consumption, 150)
        self.assertEqual(mock_printer_supply_status.remaining_supply_percentage, 75)

        mock_printer_supply_status.save.assert_called_once()

    @patch('automation.data_extractor.update_qty_supply')
    @patch('automation.data_extractor.create_change_supply')
    @patch('automation.data_extractor.calculate_average_printer_supply_consumption')
    def test_update_printer_supply_status_decrease(self, mock_calculate, mock_create_change, mock_update_qty):
        mock_supply = MagicMock()
        mock_printer = MagicMock()
        mock_printer_supply_status = MagicMock()
        mock_printer_supply_status.remaining_supply_percentage = 75
        mock_printer_supply_status.supply = mock_supply
        mock_printer_supply_status.printer = mock_printer
        mock_printer_supply_status.consumption = 100

        new_remaining_supply_percentage = 50

        update_printer_supply_status(mock_printer_supply_status, new_remaining_supply_percentage)

        mock_update_qty.assert_not_called()
        mock_create_change.assert_not_called()

        self.assertEqual(mock_printer_supply_status.consumption, 100)
        self.assertEqual(mock_printer_supply_status.remaining_supply_percentage, 50)

        mock_printer_supply_status.save.assert_called_once()

    @patch('automation.data_extractor.update_qty_supply')
    @patch('automation.data_extractor.create_change_supply')
    @patch('automation.data_extractor.calculate_average_printer_supply_consumption')
    def test_update_printer_supply_status_no_change(self, mock_calculate, mock_create_change, mock_update_qty):
        mock_supply = MagicMock()
        mock_printer = MagicMock()
        mock_printer_supply_status = MagicMock()
        mock_printer_supply_status.remaining_supply_percentage = 75
        mock_printer_supply_status.supply = mock_supply
        mock_printer_supply_status.printer = mock_printer
        mock_printer_supply_status.consumption = 100

        new_remaining_supply_percentage = 75

        update_printer_supply_status(mock_printer_supply_status, new_remaining_supply_percentage)

        mock_update_qty.assert_not_called()
        mock_create_change.assert_not_called()

        self.assertEqual(mock_printer_supply_status.consumption, 100)
        self.assertEqual(mock_printer_supply_status.remaining_supply_percentage, 75)

        mock_printer_supply_status.save.assert_called_once()


class UpdateQtySupplyTest(TestCase):
    @patch('monitoring.models.SupplyDetails.objects.get')
    def test_update_qty_supply_success(self, mock_get):
        mock_supply = MagicMock()
        mock_supply_details = MagicMock()
        mock_supply_details.qty = 5

        mock_get.return_value = mock_supply_details

        update_qty_supply(mock_supply)

        self.assertEqual(mock_supply_details.qty, 4)

        mock_supply_details.save.assert_called_once()

    @patch('monitoring.models.SupplyDetails.objects.get')
    def test_update_qty_supply_not_found(self, mock_get):
        mock_get.side_effect = models.SupplyDetails.DoesNotExist

        with self.assertRaises(models.SupplyDetails.DoesNotExist):
            update_qty_supply("non_existent_supply")


class CreateChangeSupplyTest(TestCase):
    def setUp(self):
        self.supply_item = models.SupplyItem.objects.create(
            name='Black Cart test',
            type='cartridge',
            color='black',
            price=1500.00
        )
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='HP')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )

    @patch('monitoring.models.ChangeSupply.save')
    def test_create_change_supply(self, mock_save):
        create_change_supply(self.printer, self.supply_item)

        new_change_supply = models.ChangeSupply(printer=self.printer, supply=self.supply_item)
        new_change_supply.save.assert_called_once()

        self.assertEqual(new_change_supply.printer, self.printer)
        self.assertEqual(new_change_supply.supply, self.supply_item)


class CalculateAveragePrinterSupplyConsumptionTest(TestCase):
    def setUp(self):
        self.supply_item = models.SupplyItem.objects.create(
            name='Black Cart test',
            type='cartridge',
            color='black',
            price=1500.00
        )
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='HP')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )
        self.printer_supply = models.PrinterSupplyStatus.objects.create(
            printer=self.printer,
            supply=self.supply_item,
            remaining_supply_percentage=100,
            consumption=6000
        )
        models.ChangeSupply.objects.create(
            printer=self.printer,
            supply=self.supply_item,
            time_change=f'2025-01-11'
        )
        models.ChangeSupply.objects.create(
            printer=self.printer,
            supply=self.supply_item,
            time_change=f'2025-01-12'
        )
        models.ForecastStat.objects.create(
            printer=self.printer,
            copies_printing=4000,
            time_collect='2025-01-10'
        )
        models.ForecastStat.objects.create(
            printer=self.printer,
            copies_printing=9000,
            time_collect='2025-01-11'
        )

    def test_calculate_average_consumption(self):
        result = calculate_average_printer_supply_consumption(self.printer_supply.printer, self.supply_item, self.printer_supply.consumption)

        expected_consumption = (6000 + (9000 - 4000)) // 2
        self.assertEqual(result, expected_consumption)

    @patch('monitoring.models.ChangeSupply.objects.filter')
    @patch('monitoring.models.ForecastStat.objects.filter')
    def test_calculate_average_consumption_not_enough_data(self, mock_forecast_filter, mock_change_filter):
        mock_printer = MagicMock()
        mock_supply = MagicMock()
        average_consumption = 100

        mock_change_filter.return_value.order_by.return_value[:2] = [MagicMock()]

        result = calculate_average_printer_supply_consumption(mock_printer, mock_supply, average_consumption)

        self.assertIsNone(result)


class SavePrinterStatsToDatabaseTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='Pantum')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )

    def test_save_printer_stats_with_existing_records(self):
        models.Statistics.objects.create(printer=self.printer, page=100, print=50, copies=30, scan=20)
        models.MonthlyStat.objects.create(printer=self.printer, page=1000, print=500, copies=300, scan=200)

        save_printer_stats_to_database(self.printer, page_value=150, print_value=70, copies_value=50, scan_value=30)

        new_stat = models.Statistics.objects.filter(printer=self.printer).last()
        self.assertIsNotNone(new_stat)
        self.assertEqual(new_stat.page, 150)
        self.assertEqual(new_stat.print, 70)
        self.assertEqual(new_stat.copies, 50)
        self.assertEqual(new_stat.scan, 30)

        forecast_stat = models.ForecastStat.objects.filter(printer=self.printer).last()
        self.assertIsNotNone(forecast_stat)
        self.assertEqual(forecast_stat.copies_printing, 120)

        daily_stat = models.DailyStat.objects.filter(printer=self.printer).last()
        self.assertIsNotNone(daily_stat)
        self.assertEqual(daily_stat.page, 50)
        self.assertEqual(daily_stat.print, 20)
        self.assertEqual(daily_stat.copies, 20)
        self.assertEqual(daily_stat.scan, 10)

        monthly_stat = models.MonthlyStat.objects.filter(printer=self.printer).last()
        self.assertIsNotNone(monthly_stat)
        self.assertEqual(monthly_stat.page, 1050)
        self.assertEqual(monthly_stat.print, 520)
        self.assertEqual(monthly_stat.copies, 320)
        self.assertEqual(monthly_stat.scan, 210)

    def test_save_printer_stats_without_existing_records(self):
        save_printer_stats_to_database(self.printer, page_value=150, print_value=70, copies_value=40, scan_value=30)

        new_stat = models.Statistics.objects.filter(printer=self.printer).last()
        self.assertIsNotNone(new_stat)
        self.assertEqual(new_stat.page, 150)
        self.assertEqual(new_stat.print, 70)
        self.assertEqual(new_stat.copies, 40)
        self.assertEqual(new_stat.scan, 30)

        forecast_stat = models.ForecastStat.objects.filter(printer=self.printer).last()
        self.assertIsNotNone(forecast_stat)
        self.assertEqual(forecast_stat.copies_printing, 110)  # copies_value + print_value

        daily_stat = models.DailyStat.objects.filter(printer=self.printer).last()
        self.assertIsNotNone(daily_stat)
        self.assertEqual(daily_stat.page, 0)
        self.assertEqual(daily_stat.print, 0)
        self.assertEqual(daily_stat.copies, 0)
        self.assertEqual(daily_stat.scan, 0)

        monthly_stat = models.MonthlyStat.objects.filter(printer=self.printer).last()
        self.assertIsNotNone(monthly_stat)
        self.assertEqual(monthly_stat.page, 0)
        self.assertEqual(monthly_stat.print, 0)
        self.assertEqual(monthly_stat.copies, 0)
        self.assertEqual(monthly_stat.copies, 0)
        self.assertEqual(monthly_stat.scan, 0)


class AddPrinterParsingSnmpTests(TestCase):
    @patch('automation.data_extractor.ping')
    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_str')
    def test_add_printer_parsing_snmp_success(self, mock_fetch_snmp_data_to_str, mock_engine, mock_ping):
        mock_ping.return_value = True
        mock_ip_printer = MagicMock()
        mock_engine.return_value.__enter__.return_value.Manager.return_value = mock_ip_printer

        mock_ip_printer.get.return_value = "'HP LaserJet 400 M401dn'"
        mock_fetch_snmp_data_to_str.side_effect = ['LaserJet 400 M401dn', 'SN123456']

        result = add_printer_parsing_snmp('192.168.1.100')

        self.assertEqual(result, ['Hewlett-Packard', 'LaserJet 400 M401dn', 'SN123456'])

    @patch('automation.data_extractor.ping')
    def test_add_printer_parsing_snmp_ping_failure(self, mock_ping):
        mock_ping.return_value = False

        result = add_printer_parsing_snmp('192.168.1.100')

        self.assertEqual(result, ['Printer', 'Model', 'Serial_Number'])

    @patch('automation.data_extractor.ping')
    @patch('automation.data_extractor.Engine')
    def test_add_printer_parsing_snmp_exception(self, mock_engine, mock_ping):
        mock_ping.return_value = True
        mock_engine.side_effect = Exception("SNMP error")

        result = add_printer_parsing_snmp('192.168.1.100')

        self.assertEqual(result, ['Printer', 'Model', 'Serial_Number'])


class AddMissingStatisticsToDbTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='Pantum')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )

    @patch('automation.data_extractor.save_printer_stats_to_database')
    def test_add_missing_statistics_when_no_statistics_today(self, mock_save_stats):
        yesterday = timezone.now().date() - timedelta(days=1)
        models.Statistics.objects.create(printer=self.printer, page=100, print=50, copies=30, scan=20, time_collect=yesterday)

        add_missing_statistics_to_db(self.printer)

        mock_save_stats.assert_called_once_with(self.printer, 100, 50, 30, 20)

    @patch('automation.data_extractor.save_printer_stats_to_database')
    def test_does_not_add_statistics_when_statistics_exist_today(self, mock_save_stats):
        models.Statistics.objects.create(printer=self.printer, page=100, print=50, copies=30, scan=20)

        add_missing_statistics_to_db(self.printer)

        mock_save_stats.assert_not_called()

    @patch('automation.data_extractor.save_printer_stats_to_database')
    def test_does_not_add_statistics_when_no_yesterday_statistics(self, mock_save_stats):
        add_missing_statistics_to_db(self.printer)

        mock_save_stats.assert_not_called()


class DetectDeviceErrorsTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='Pantum')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )

    @patch('automation.data_extractor.Engine')
    def test_detect_device_errors_with_active_printer_and_no_error(self, mock_engine):
        mock_ip_printer = MagicMock()
        mock_engine.return_value.__enter__.return_value.Manager.return_value = mock_ip_printer

        mock_ip_printer.get.side_effect = [
            "'(5)'",
            "'\\x00'"
        ]

        detect_device_errors(self.printer.id)

        error_count = models.PrinterError.objects.filter(printer=self.printer).count()
        self.assertEqual(error_count, 0)

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.logger_main')
    def test_detect_device_errors_with_inactive_printer(self, mock_logger, mock_engine):
        self.printer.is_active = False
        self.printer.save()

        detect_device_errors(self.printer.id)
        mock_logger.error.assert_not_called()

    @patch('automation.data_extractor.Engine')
    def test_detect_device_errors_with_exception(self, mock_engine):
        mock_engine.side_effect = Exception("SNMP error")
        detect_device_errors(self.printer.id)


class CheckingActivityTests(TestCase):
    @patch('automation.data_extractor.ping')
    def test_checking_activity_active(self, mock_ping):
        mock_ping.return_value = True
        ip_address = '192.168.1.1'

        result = checking_activity(ip_address)
        self.assertTrue(result)

    @patch('automation.data_extractor.ping')
    def test_checking_activity_inactive(self, mock_ping):
        mock_ping.return_value = False
        ip_address = '192.168.1.1'

        result = checking_activity(ip_address)
        self.assertFalse(result)


class FetchSNMPDataToStr(TestCase):
    def test_return_valid_value(self):
        mock_ip_printer = MagicMock()
        mock_ip_printer.get.return_value = "1.2.3.4.5.6.7.8.9: OctetString(b'TestStr')"

        result = fetch_snmp_data_to_str(mock_ip_printer, 'kyocera', 'stamp')
        self.assertEqual(result, 'TestStr')

    def test_return_invalid_value(self):
        mock_ip_printer = MagicMock()
        mock_ip_printer.get.return_value = "1.2.3.4.5.6.7.8.9: OctetStringbTestStr"

        result = fetch_snmp_data_to_str(mock_ip_printer, 'kyocera', 'stamp')
        self.assertEqual(result, 'Empty')


class FetchSNMPDataToInt(TestCase):
    def test_return_valid_value(self):
        mock_ip_printer = MagicMock()
        mock_ip_printer.get.return_value = "1.2.3.4.5.6.7.8.9: OctetString(123)"

        result = fetch_snmp_data_to_int(mock_ip_printer, 'kyocera', 'stamp')
        self.assertEqual(result, 123)

    def test_return_invalid_value(self):
        mock_ip_printer = MagicMock()
        mock_ip_printer.get.return_value = "1.2.3.4.5.6.7.8.9: OctetString(b'TestStr')"

        result = fetch_snmp_data_to_int(mock_ip_printer, 'kyocera', 'stamp')
        self.assertIsNone(result)


class ParsingSnmpDecoratorTest(TestCase):
    def setUp(self):
        self.printer = MagicMock()
        self.printer.is_active = True

    @patch('monitoring.models.Statistics.objects.filter')
    @patch('automation.data_extractor.save_printer_stats_to_database')
    def test_parsing_snmp_with_no_statistics(self, mock_save_stats, mock_filter):
        mock_filter.return_value.exists.return_value = False

        @parsing_snmp
        def mock_func(printer, *args, **kwargs):
            return 100, 200, 300, 400

        result = mock_func(self.printer)

        mock_save_stats.assert_called_once_with(
            printer=self.printer,
            page_value=100,
            print_value=200,
            copies_value=300,
            scan_value=400
        )

        self.assertEqual(result, (100, 200, 300, 400))

    @patch('monitoring.models.Statistics.objects.filter')
    @patch('automation.data_extractor.save_printer_stats_to_database')
    def test_parsing_snmp_with_existing_statistics(self, mock_save_stats, mock_filter):
        mock_filter.return_value.exists.return_value = True

        @parsing_snmp
        def mock_func(printer, *args, **kwargs):
            return 100, 200, 300, 400

        result = mock_func(self.printer)

        mock_save_stats.assert_not_called()

        self.assertEqual(result, (100, 200, 300, 400))

    @patch('monitoring.models.Statistics.objects.filter')
    @patch('automation.data_extractor.save_printer_stats_to_database')
    def test_parsing_snmp_with_inactive_printer(self, mock_save_stats, mock_filter):
        self.printer.is_active = False

        @parsing_snmp
        def mock_func(printer, *args, **kwargs):
            return 100, 200, 300, 400

        result = mock_func(self.printer)

        mock_save_stats.assert_not_called()

        self.assertEqual(result, (100, 200, 300, 400))


class ParsingSnmpKatushaTest(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='Katusha')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_success(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_fetch_snmp_data.return_value = 100
        result = parsing_snmp_katusha(self.printer)
        self.assertEqual(result, (400, 100, 100, 200))

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_exception(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_engine.return_value = Exception("SNMP engine error")

        with self.assertRaises(Exception):
            parsing_snmp_katusha(self.printer)

        mock_logger.error.assert_called_once()


class ParsingSnmpAvisionTest(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='Avision')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_success(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_fetch_snmp_data.return_value = 100
        result = parsing_snmp_avision(self.printer)
        self.assertEqual(result, (500, 100, 200, 200))

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_exception(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_engine.return_value = Exception("SNMP engine error")

        with self.assertRaises(Exception):
            parsing_snmp_avision(self.printer)

        mock_logger.error.assert_called_once()


class ParsingSnmpHPTest(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='Hewlett-Packard')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )

        self.ip_address_color = models.IPAddress.objects.create(address='192.168.1.125', subnet=self.subnet)
        self.model_color = models.PrinterModel.objects.create(stamp=self.stamp, name='M283fdn')
        self.printer_color = models.Printer.objects.create(
            ip_address=self.ip_address_color,
            model=self.model_color,
            serial_number='SN123456',
        )

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_success(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_fetch_snmp_data.return_value = 100
        result = parsing_snmp_hp(self.printer)
        self.assertEqual(result, (100, 100, 0, 0))

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_color_success(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_fetch_snmp_data.return_value = 100
        result = parsing_snmp_hp(self.printer_color)
        self.assertEqual(result, (300, 100, 0, 200))

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_exception(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_engine.return_value = Exception("SNMP engine error")

        with self.assertRaises(Exception):
            parsing_snmp_hp(self.printer)

        mock_logger.error.assert_called_once()


class ParsingSnmpKyoceraTest(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='Kyocera')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_success(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_fetch_snmp_data.return_value = 100
        result = parsing_snmp_kyosera(self.printer)
        self.assertEqual(result, (300, 100, 100, 100))

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_exception(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_engine.return_value = Exception("SNMP engine error")

        with self.assertRaises(Exception):
            parsing_snmp_kyosera(self.printer)

        mock_logger.error.assert_called_once()


class ParsingSnmpSindohTest(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='Sindoh')
        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='LaserJet')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer = models.Printer.objects.create(
            ip_address=self.ip_address,
            model=self.model,
            serial_number='SN123456',
        )

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_success(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_fetch_snmp_data.return_value = 100
        result = parsing_snmp_sindoh(self.printer)
        self.assertEqual(result, (100, 100, 0, 0))

    @patch('automation.data_extractor.Engine')
    @patch('automation.data_extractor.fetch_snmp_data_to_int')
    @patch('automation.data_extractor.logger_main')
    def test_parsing_snmp_exception(self, mock_logger, mock_fetch_snmp_data, mock_engine):
        mock_engine.return_value = Exception("SNMP engine error")

        with self.assertRaises(Exception):
            parsing_snmp_sindoh(self.printer)

        mock_logger.error.assert_called_once()
