from django.contrib.admin.sites import site
from django.test import TestCase
from unittest.mock import patch, MagicMock
from monitoring import models
from monitoring.admin import SubnetAdmin, check_or_add_printer, check_printer, IPAddressAdmin, PrinterAdmin
from django.core.exceptions import ObjectDoesNotExist


class SubnetAdminTest(TestCase):
    def setUp(self):
        self.admin = SubnetAdmin(models.Subnet, site)

    @patch('monitoring.admin.scan_subnet')
    @patch('monitoring.models.IPAddress.objects.get_or_create')
    @patch('monitoring.admin.add_printer')
    def test_save_model_with_scan_subnet(self, mock_add_printer, mock_get_or_create, mock_scan_subnet):
        mock_ip_addresses = ['192.168.1.1', '192.168.1.2']
        mock_scan_subnet.return_value = mock_ip_addresses

        subnet = models.Subnet(name='Test Subnet', address='192.168.1.0', mask=24)
        form = MagicMock()
        form.cleaned_data = {
            'scan_subnet': True,
            'address': '192.168.1.0',
            'mask': 24,
        }

        mock_get_or_create.side_effect = lambda address, defaults: (MagicMock(address=address), True)

        self.admin.save_model(None, subnet, form, change=False)

        mock_scan_subnet.assert_called_once_with('192.168.1.0/24')

        for ip in mock_ip_addresses:
            mock_get_or_create.assert_any_call(
                address=ip,
                defaults={'address': ip, 'subnet': subnet}
            )

        self.assertEqual(mock_add_printer.call_count, len(mock_ip_addresses))

    @patch('monitoring.admin.scan_subnet')
    @patch('monitoring.models.IPAddress.objects.get_or_create')
    @patch('monitoring.admin.add_printer')
    def test_save_model_without_scan_subnet(self, mock_add_printer, mock_get_or_create, mock_scan_subnet):
        subnet = models.Subnet(name='Test Subnet', address='192.168.1.0', mask=24)
        form = MagicMock()
        form.cleaned_data = {
            'scan_subnet': False,
            'address': '192.168.1.0',
            'mask': 24,
        }

        self.admin.save_model(None, subnet, form, change=False)

        mock_scan_subnet.assert_not_called()
        mock_get_or_create.assert_not_called()
        mock_add_printer.assert_not_called()


class PrinterTestCase(TestCase):
    @patch('monitoring.models.Printer.objects.get')
    def test_check_printer_exists(self, mock_get):
        mock_printer = MagicMock()
        mock_printer.serial_number = 'SN123456'
        mock_printer.ip_address = None
        mock_printer.is_archived = True
        mock_printer.is_active = False
        mock_get.return_value = mock_printer

        printer_info = ['Brand', 'Model', 'SN123456']
        obj = MagicMock()

        check_printer(printer_info, obj)

        self.assertEqual(mock_printer.ip_address, obj)
        self.assertFalse(mock_printer.is_archived)
        self.assertTrue(mock_printer.is_active)
        mock_printer.save.assert_called_once()

    @patch('monitoring.models.Printer.objects.get')
    def test_check_printer_does_not_exist(self, mock_get):
        mock_get.side_effect = ObjectDoesNotExist

        printer_info = ['Brand', 'Model', 'SN123456']
        obj = MagicMock()

        with patch('monitoring.admin.create_printer') as mock_create_printer:
            check_or_add_printer(printer_info, obj)

            mock_create_printer.assert_called_once_with(printer_info, obj)


class IPAddressAdminTest(TestCase):
    def setUp(self):
        self.admin = IPAddressAdmin(models.IPAddress, site)

    @patch('monitoring.admin.add_printer_parsing_snmp')
    @patch('monitoring.admin.check_or_add_printer')
    def test_save_model_with_add_printer(self, mock_check_or_add_printer, mock_add_printer_parsing_snmp):
        mock_subnet = models.Subnet.objects.create(name='test subnet', address='192.168.1.0', mask=24)

        mock_ip_address = models.IPAddress(address='192.168.1.1', subnet=mock_subnet)
        form = MagicMock()
        form.cleaned_data = {
            'add_printer': True,
        }

        mock_printer_info = ['Brand', 'Model', 'SN123456']
        mock_add_printer_parsing_snmp.return_value = mock_printer_info

        self.admin.save_model(None, mock_ip_address, form, change=False)

        mock_add_printer_parsing_snmp.assert_called_once_with('192.168.1.1')

        mock_check_or_add_printer.assert_called_once_with(mock_printer_info, mock_ip_address)

    @patch('monitoring.admin.add_printer_parsing_snmp')
    @patch('monitoring.admin.check_or_add_printer')
    def test_save_model_without_add_printer(self, mock_check_or_add_printer, mock_add_printer_parsing_snmp):
        mock_subnet = models.Subnet.objects.create(name='test subnet', address='192.168.1.0', mask=24)

        mock_ip_address = models.IPAddress(address='192.168.1.1', subnet=mock_subnet)
        form = MagicMock()
        form.cleaned_data = {
            'add_printer': False,
        }

        self.admin.save_model(None, mock_ip_address, form, change=False)

        mock_add_printer_parsing_snmp.assert_not_called()
        mock_check_or_add_printer.assert_not_called()

