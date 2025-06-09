from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.sessions.models import Session
from monitoring.tasks import (delete_expired_sessions, scan_subnets_regular, checking_activity_regular,
                              update_printer_resource_regular, parsing_katushas_page_counts,
                              parsing_avisions_page_counts, parsing_hps_page_counts, parsing_kyoseras_page_counts,
                              parsing_pantums_page_counts, parsing_sindohs_page_counts, async_detect_device_errors,
                              detect_device_errors_regular, async_update_printer_resource)
from unittest.mock import patch
from monitoring import models
from django.db.models.signals import post_save
from monitoring.signals import printer_created


class DeleteExpiredSessionsTests(TestCase):
    def test_delete_expired_sessions(self):
        expired_session = Session.objects.create(
            session_key=12345,
            expire_date=timezone.now() - timezone.timedelta(days=1)
        )
        valid_session = Session.objects.create(
            session_key=54321,
            expire_date=timezone.now() + timezone.timedelta(days=1)
        )

        actual_sessions_count = Session.objects.count()
        self.assertEqual(actual_sessions_count, 2)

        session_keys = [int(session.session_key) for session in Session.objects.all()]
        self.assertIn(valid_session.session_key, session_keys)
        self.assertIn(expired_session.session_key, session_keys)

        delete_expired_sessions()

        actual_sessions_count_after_task = Session.objects.count()
        self.assertEqual(actual_sessions_count_after_task, 1)

        session_keys = [int(session.session_key) for session in Session.objects.all()]
        self.assertIn(valid_session.session_key, session_keys)
        self.assertNotIn(expired_session.session_key, session_keys)


class ScanSubnetsRegularTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)

    @patch('monitoring.tasks.scan_subnet')
    @patch('monitoring.tasks.add_printer_parsing_snmp')
    @patch('monitoring.tasks.custom_logger')
    def test_scan_subnets_regular_adds_new_ip_and_printer(self, mock_logger, mock_add_printer, mock_scan_subnet):
        mock_scan_subnet.return_value = ['192.168.1.10']
        mock_add_printer.return_value = ['Hewlett-Packard', 'LaserJet', 'SN123456']
        scan_subnets_regular()

        mock_scan_subnet.return_value = ['192.168.1.11']
        mock_add_printer.return_value = ['Hewlett-Packard', 'LaserJet', 'SN654321']
        scan_subnets_regular()

        ip1 = models.IPAddress.objects.get(address='192.168.1.10')
        ip2 = models.IPAddress.objects.get(address='192.168.1.11')

        self.assertEqual(ip1.subnet, self.subnet)
        self.assertEqual(ip2.subnet, self.subnet)

        printer1 = models.Printer.objects.get(ip_address=ip1)
        printer2 = models.Printer.objects.get(ip_address=ip2)
        self.assertEqual(str(printer1.model), 'Hewlett-Packard LaserJet')
        self.assertEqual(printer1.serial_number, 'SN123456')

        mock_logger.info.assert_any_call("IP address 192.168.1.10 has been added successfully")
        mock_logger.info.assert_any_call("IP address 192.168.1.11 has been added successfully")
        mock_logger.info.assert_any_call(f"Printer {printer1} has been added successfully")
        mock_logger.info.assert_any_call(f"Printer {printer2} has been added successfully")

    @patch('monitoring.tasks.scan_subnet')
    @patch('monitoring.tasks.add_printer_parsing_snmp')
    def test_scan_subnets_regular_does_not_add_existing_ip(self, mock_add_printer, mock_scan_subnet):
        existing_ip = models.IPAddress.objects.create(address='192.168.1.10', subnet=self.subnet)

        mock_scan_subnet.return_value = ['192.168.1.10']
        mock_add_printer.return_value = ['Hewlett-Packard', 'LaserJet', 'SN123456']

        scan_subnets_regular()

        self.assertEqual(models.IPAddress.objects.count(), 1)


class CheckingActivityRegularTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address_active = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.ip_address_inactive = models.IPAddress.objects.create(address='192.168.1.111', subnet=self.subnet)
        self.stamp = models.PrinterStamp.objects.create(name='Test Stamp')
        self.model_active = models.PrinterModel.objects.create(stamp=self.stamp, name='Active Printer')
        self.model_inactive = models.PrinterModel.objects.create(stamp=self.stamp, name='Inactive Printer')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer_active = models.Printer.objects.create(model=self.model_active,
                                                            ip_address=self.ip_address_active,
                                                            is_active=True)
        self.printer_inactive = models.Printer.objects.create(model=self.model_inactive,
                                                              ip_address=self.ip_address_inactive,
                                                              is_active=False)

    @patch('monitoring.tasks.checking_activity')
    @patch('monitoring.tasks.custom_logger')
    def test_checking_activity_regular_updates_active_printer(self, mock_logger, mock_checking_activity):
        mock_checking_activity.return_value = False

        checking_activity_regular()

        self.printer_active.refresh_from_db()
        self.assertFalse(self.printer_active.is_active)

        mock_logger.info.assert_called_once_with(f"Printer {self.printer_active} activity has been changed to False")

    @patch('monitoring.tasks.checking_activity')
    @patch('monitoring.tasks.custom_logger')
    def test_checking_activity_regular_updates_inactive_printer(self, mock_logger, mock_checking_activity):
        mock_checking_activity.return_value = True

        checking_activity_regular()

        self.printer_inactive.refresh_from_db()
        self.assertTrue(self.printer_inactive.is_active)

        mock_logger.info.assert_called_once_with(f"Printer {self.printer_inactive} activity has been changed to True")

    @patch('monitoring.tasks.checking_activity')
    def test_checking_activity_regular_no_change_in_activity(self, mock_checking_activity):
        mock_checking_activity.return_value = True

        checking_activity_regular()

        self.printer_active.refresh_from_db()
        self.assertTrue(self.printer_active.is_active)


class UpdatePrinterResourceRegularTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        self.ip_address1 = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.ip_address2 = models.IPAddress.objects.create(address='192.168.1.111', subnet=self.subnet)
        self.stamp1 = models.PrinterStamp.objects.create(name='Test Stamp 1')
        self.stamp2 = models.PrinterStamp.objects.create(name='Test Stamp 2')
        self.model1 = models.PrinterModel.objects.create(stamp=self.stamp1, name='Printer 1')
        self.model2 = models.PrinterModel.objects.create(stamp=self.stamp2, name='Printer 2')
        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer1 = models.Printer.objects.create(model=self.model1, ip_address=self.ip_address1)
        self.printer2 = models.Printer.objects.create(model=self.model2, ip_address=self.ip_address2)

    @patch('monitoring.tasks.update_printer_resource')
    def test_async_detect_device_errors(self, mock_update):
        printer_id = 1
        async_update_printer_resource(printer_id)
        mock_update.assert_called_once_with(printer_id)

    @patch('monitoring.tasks.async_update_printer_resource')
    def test_update_printer_resource_regular_calls_async_update(self, mock_async_update):
        update_printer_resource_regular()

        mock_async_update.delay.assert_any_call(self.printer1.id)
        mock_async_update.delay.assert_any_call(self.printer2.id)

        self.assertEqual(mock_async_update.delay.call_count, 2)


class ParsingKatushasPageCountsTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)

        self.ip_address_active = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.ip_address_inactive = models.IPAddress.objects.create(address='192.168.1.111', subnet=self.subnet)
        self.ip_address_other = models.IPAddress.objects.create(address='192.168.1.100', subnet=self.subnet)

        self.stamp = models.PrinterStamp.objects.create(name='Katusha')
        self.stamp_other = models.PrinterStamp.objects.create(name='Other')

        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='Model')
        self.model_other = models.PrinterModel.objects.create(stamp=self.stamp_other, name='Other')

        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer_active = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_active,
                                                            is_active=True)
        self.printer_inactive = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_inactive,
                                                              is_active=False)
        self.other_printer = models.Printer.objects.create(model=self.model_other, ip_address=self.ip_address_other,
                                                           is_active=True)

    @patch('monitoring.tasks.parsing_snmp_katusha')
    def test_parsing_katushas_page_counts_calls_parsing_snmp_katusha(self, mock_parsing_snmp_katusha):
        parsing_katushas_page_counts()

        mock_parsing_snmp_katusha.assert_called_once_with(self.printer_active)

        self.assertEqual(mock_parsing_snmp_katusha.call_count, 1)


class ParsingAvisionsPageCountsTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)

        self.ip_address_active = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.ip_address_inactive = models.IPAddress.objects.create(address='192.168.1.111', subnet=self.subnet)
        self.ip_address_other = models.IPAddress.objects.create(address='192.168.1.100', subnet=self.subnet)

        self.stamp = models.PrinterStamp.objects.create(name='Avision')
        self.stamp_other = models.PrinterStamp.objects.create(name='Other')

        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='Model')
        self.model_other = models.PrinterModel.objects.create(stamp=self.stamp_other, name='Other')

        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer_active = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_active,
                                                            is_active=True)
        self.printer_inactive = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_inactive,
                                                              is_active=False)
        self.other_printer = models.Printer.objects.create(model=self.model_other, ip_address=self.ip_address_other,
                                                           is_active=True)

    @patch('monitoring.tasks.parsing_snmp_avision')
    def test_parsing_avisions_page_counts_calls_parsing_snmp_katusha(self, mock_parsing_snmp_avision):
        parsing_avisions_page_counts()

        mock_parsing_snmp_avision.assert_called_once_with(self.printer_active)

        self.assertEqual(mock_parsing_snmp_avision.call_count, 1)


class ParsingHpsPageCountsTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)

        self.ip_address_active = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.ip_address_inactive = models.IPAddress.objects.create(address='192.168.1.111', subnet=self.subnet)
        self.ip_address_other = models.IPAddress.objects.create(address='192.168.1.100', subnet=self.subnet)

        self.stamp = models.PrinterStamp.objects.create(name='Hewlett-Packard')
        self.stamp_other = models.PrinterStamp.objects.create(name='Other')

        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='Model')
        self.model_other = models.PrinterModel.objects.create(stamp=self.stamp_other, name='Other')

        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer_active = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_active,
                                                            is_active=True)
        self.printer_inactive = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_inactive,
                                                              is_active=False)
        self.other_printer = models.Printer.objects.create(model=self.model_other, ip_address=self.ip_address_other,
                                                           is_active=True)

    @patch('monitoring.tasks.parsing_snmp_hp')
    def test_parsing_hps_page_counts_calls_parsing_snmp_katusha(self, mock_parsing_snmp_hp):
        parsing_hps_page_counts()

        mock_parsing_snmp_hp.assert_called_once_with(self.printer_active)

        self.assertEqual(mock_parsing_snmp_hp.call_count, 1)


class ParsingKyoserasPageCountsTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)

        self.ip_address_active = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.ip_address_inactive = models.IPAddress.objects.create(address='192.168.1.111', subnet=self.subnet)
        self.ip_address_other = models.IPAddress.objects.create(address='192.168.1.100', subnet=self.subnet)

        self.stamp = models.PrinterStamp.objects.create(name='KYOCERA')
        self.stamp_other = models.PrinterStamp.objects.create(name='Other')

        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='Model')
        self.model_other = models.PrinterModel.objects.create(stamp=self.stamp_other, name='Other')

        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer_active = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_active,
                                                            is_active=True)
        self.printer_inactive = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_inactive,
                                                              is_active=False)
        self.other_printer = models.Printer.objects.create(model=self.model_other, ip_address=self.ip_address_other,
                                                           is_active=True)

    @patch('monitoring.tasks.parsing_snmp_kyosera')
    def test_parsing_hps_page_counts_calls_parsing_snmp_katusha(self, mock_parsing_snmp_kyosera):
        parsing_kyoseras_page_counts()

        mock_parsing_snmp_kyosera.assert_called_once_with(self.printer_active)

        self.assertEqual(mock_parsing_snmp_kyosera.call_count, 1)


class ParsingPantumsPageCountsTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)

        self.ip_address_active = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.ip_address_inactive = models.IPAddress.objects.create(address='192.168.1.111', subnet=self.subnet)
        self.ip_address_other = models.IPAddress.objects.create(address='192.168.1.100', subnet=self.subnet)

        self.stamp = models.PrinterStamp.objects.create(name='Pantum')
        self.stamp_other = models.PrinterStamp.objects.create(name='Other')

        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='Model')
        self.model_other = models.PrinterModel.objects.create(stamp=self.stamp_other, name='Other')

        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer_active = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_active,
                                                            is_active=True)
        self.printer_inactive = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_inactive,
                                                              is_active=False)
        self.other_printer = models.Printer.objects.create(model=self.model_other, ip_address=self.ip_address_other,
                                                           is_active=True)

    @patch('monitoring.tasks.parsing_pantum')
    def test_parsing_hps_page_counts_calls_parsing_snmp_katusha(self, mock_parsing_pantum):
        parsing_pantums_page_counts()

        mock_parsing_pantum.assert_called_once_with(self.printer_active)

        self.assertEqual(mock_parsing_pantum.call_count, 1)


class ParsingSindohsPageCountsTests(TestCase):
    def setUp(self):
        self.subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)

        self.ip_address_active = models.IPAddress.objects.create(address='192.168.1.123', subnet=self.subnet)
        self.ip_address_inactive = models.IPAddress.objects.create(address='192.168.1.111', subnet=self.subnet)
        self.ip_address_other = models.IPAddress.objects.create(address='192.168.1.100', subnet=self.subnet)

        self.stamp = models.PrinterStamp.objects.create(name='SINDOH')
        self.stamp_other = models.PrinterStamp.objects.create(name='Other')

        self.model = models.PrinterModel.objects.create(stamp=self.stamp, name='Model')
        self.model_other = models.PrinterModel.objects.create(stamp=self.stamp_other, name='Other')

        post_save.disconnect(printer_created, sender=models.Printer)
        self.printer_active = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_active,
                                                            is_active=True)
        self.printer_inactive = models.Printer.objects.create(model=self.model, ip_address=self.ip_address_inactive,
                                                              is_active=False)
        self.other_printer = models.Printer.objects.create(model=self.model_other, ip_address=self.ip_address_other,
                                                           is_active=True)

    @patch('monitoring.tasks.parsing_snmp_sindoh')
    def test_parsing_hps_page_counts_calls_parsing_snmp_katusha(self, mock_parsing_snmp_sindoh):
        parsing_sindohs_page_counts()

        mock_parsing_snmp_sindoh.assert_called_once_with(self.printer_active)

        self.assertEqual(mock_parsing_snmp_sindoh.call_count, 1)


class DeviceErrorTasksTest(TestCase):
    @patch('monitoring.tasks.detect_device_errors')
    def test_async_detect_device_errors(self, mock_detect):
        printer_id = 1
        async_detect_device_errors(printer_id)
        mock_detect.assert_called_once_with(printer_id)

    @patch('monitoring.tasks.async_detect_device_errors.delay')
    def test_detect_device_errors_regular(self, mock_delay):
        subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=subnet)
        post_save.disconnect(printer_created, sender=models.Printer)
        stamp = models.PrinterStamp.objects.create(name='Test Stamp 1')
        model = models.PrinterModel.objects.create(stamp=stamp, name='Printer 1')
        models.Printer.objects.create(model=model, ip_address=ip_address)
        detect_device_errors_regular()
        self.assertTrue(mock_delay.called)