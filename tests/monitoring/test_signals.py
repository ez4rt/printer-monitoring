from django.contrib.auth import get_user_model
from django.test import TestCase
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in
from unittest.mock import patch
from monitoring import models
from monitoring.signals import printer_created
from django.db.models.signals import post_save

User = get_user_model()


class UserLoginTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='password')

    def test_logout_previous_user(self):
        self.client.login(username='user1', password='password')
        session_key = self.client.session.session_key

        self.client.logout()

        self.client.login(username='user1', password='password')

        self.assertFalse(Session.objects.filter(session_key=session_key).exists())


class PrinterNotificationTest(TestCase):
    @patch('monitoring.signals.send_msg')
    def test_notify_low_cart(self, mock_send_msg):
        subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=subnet)
        post_save.disconnect(printer_created, sender=models.Printer)
        cabinet = models.Cabinet.objects.create(number='Office 201')
        department = models.Department.objects.create(name='IT')
        location = models.Location.objects.create(department=department, cabinet=cabinet)
        stamp = models.PrinterStamp.objects.create(name='HP')
        model = models.PrinterModel.objects.create(stamp=stamp, name='LaserJet')
        inventory_number = models.InventoryNumber.objects.create(number='in-00-01')
        post_save.disconnect(printer_created, sender=models.Printer)
        printer = models.Printer.objects.create(
            ip_address=ip_address,
            model=model,
            serial_number='SN123456',
            inventory_number=inventory_number,
            location=location,
            date_of_commission=timezone.now(),
            is_active=True,
            is_archived=False,
        )
        supply_item = models.SupplyItem.objects.create(
            name='Black Cart test',
            type='cartridge',
            color='black',
            price=1500.00
        )
        printer_supply = models.PrinterSupplyStatus.objects.create(
            printer=printer,
            supply=supply_item,
            remaining_supply_percentage=0,
            consumption=6000
        )

        mock_send_msg.assert_called_once()


class PrinterErrorNotificationTest(TestCase):
    @patch('monitoring.signals.send_msg')
    def test_notify_error(self, mock_send_msg):
        subnet = models.Subnet.objects.create(name='Test Subnet', address='192.168.1.0', mask=24)
        ip_address = models.IPAddress.objects.create(address='192.168.1.123', subnet=subnet)
        post_save.disconnect(printer_created, sender=models.Printer)
        cabinet = models.Cabinet.objects.create(number='Office 201')
        department = models.Department.objects.create(name='IT')
        location = models.Location.objects.create(department=department, cabinet=cabinet)
        stamp = models.PrinterStamp.objects.create(name='HP')
        model = models.PrinterModel.objects.create(stamp=stamp, name='LaserJet')
        inventory_number = models.InventoryNumber.objects.create(number='in-00-01')
        post_save.disconnect(printer_created, sender=models.Printer)
        printer = models.Printer.objects.create(
            ip_address=ip_address,
            model=model,
            serial_number='SN123456',
            inventory_number=inventory_number,
            location=location,
            date_of_commission=timezone.now(),
            is_active=True,
            is_archived=False,
        )
        printer_error = models.PrinterError.objects.create(
            printer=printer,
            event_date=timezone.now(),
            description="Ошибка печати"
        )

        mock_send_msg.assert_called_once()